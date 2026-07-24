from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.utils.token import TokenValidationError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.connectors.fanvue.oauth import (
    FanvueOAuthError,
    build_fanvue_authorize_url,
    exchange_fanvue_authorization_code,
    fanvue_oauth_configured,
    fetch_fanvue_current_user,
    generate_oauth_state,
    generate_pkce_pair,
)
from app.connectors.instagram.oauth import (
    InstagramOAuthError,
    build_instagram_authorize_url,
    exchange_instagram_authorization_code,
    fetch_instagram_profile,
    generate_oauth_state as generate_instagram_oauth_state,
    instagram_oauth_configured,
    resolve_instagram_profile_ids,
    subscribe_instagram_webhooks,
)
from app.db.models import (
    CompanionJob,
    CompanionJobStatus,
    CompanionStyleExample,
    Conversation,
    CreditAccount,
    FanvueConnection,
    FanvueOAuthState,
    InstagramConnection,
    InstagramOAuthState,
    LlmConnection,
    Platform,
    Subscription,
    TelegramConnection,
    TributeConnection,
    User,
    WavespeedConnection,
)
from app.db.session import SessionLocal, get_session
from app.schemas import (
    CompanionFeedbackReportOut,
    CompanionStyleIndexStatsOut,
    FanvueIntegrationIn,
    FanvueOAuthStartIn,
    FanvueOAuthStartOut,
    FanvueSyncOut,
    InstagramOAuthStartIn,
    InstagramOAuthStartOut,
    IntegrationHealthOut,
    IntegrationStatusOut,
    LlmIntegrationIn,
    PlatformConnectionOut,
    PlatformConnectionPatchIn,
    TelegramIntegrationIn,
    TributeIntegrationIn,
    WavespeedIntegrationIn,
)
from app.services.billing_plan import is_credits_plan, normalize_billing_plan
from app.services.crypto_secret import encrypt_secret
from app.services.fanvue_connection import (
    fanvue_platform_webhook_signing_secret,
    fanvue_platform_webhook_url,
)
from app.services.instagram_connection import (
    instagram_platform_webhook_url,
    instagram_webhook_configured,
)
from app.services.companion_bot.feedback import list_feedback_reports
from app.services.fanvue_sync import sync_fanvue_chat_history
from app.services.plan_entitlements import plan_limits_for_sub
from app.services.platform_connections import (
    assert_can_add_platform_connection,
    assert_can_add_tribute_connection,
    sync_conversations_model_from_connection,
    validate_connection_studio_model,
)
from app.services.tribute_connection import tribute_webhook_url_for_connection
from app.services.studio_keys import wavespeed_cabinet_flags
from app.services.workspace import PERM_INTEGRATIONS, assert_permission, workspace_owner_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _apply_companion_connection_patch(
    row: TelegramConnection | FanvueConnection,
    body: PlatformConnectionPatchIn,
) -> None:
    if "companion_mode" in body.model_fields_set and body.companion_mode is not None:
        row.companion_mode = body.companion_mode
    if "companion_delay_min_sec" in body.model_fields_set and body.companion_delay_min_sec is not None:
        row.companion_delay_min_sec = int(body.companion_delay_min_sec)
    if "companion_delay_max_sec" in body.model_fields_set and body.companion_delay_max_sec is not None:
        row.companion_delay_max_sec = int(body.companion_delay_max_sec)
    if (
        "companion_max_replies_per_hour" in body.model_fields_set
        and body.companion_max_replies_per_hour is not None
    ):
        row.companion_max_replies_per_hour = int(body.companion_max_replies_per_hour)
    delay_min = int(row.companion_delay_min_sec or 0)
    delay_max = int(row.companion_delay_max_sec or delay_min)
    if delay_max < delay_min:
        row.companion_delay_max_sec = delay_min


def _fanvue_oauth_ready() -> bool:
    return fanvue_oauth_configured() and bool(fanvue_platform_webhook_signing_secret())


def _instagram_oauth_ready() -> bool:
    return instagram_oauth_configured() and instagram_webhook_configured()


async def _background_fanvue_history_sync(user_id: int, connection_id: int | None = None) -> None:
    async with SessionLocal() as session:
        if connection_id is not None:
            row = await session.scalar(
                select(FanvueConnection).where(
                    FanvueConnection.id == connection_id,
                    FanvueConnection.user_id == user_id,
                )
            )
        else:
            row = await session.scalar(
                select(FanvueConnection)
                .where(FanvueConnection.user_id == user_id)
                .order_by(FanvueConnection.id.asc())
                .limit(1)
            )
        if not row:
            return
        try:
            await sync_fanvue_chat_history(session, conn=row)
        except Exception:
            log.exception("background fanvue history sync failed user=%s", user_id)


def _telegram_webhook_registered(tg: TelegramConnection | None) -> bool:
    """Webhook у Telegram есть только если при сохранении вызывали setWebhook (HTTPS)."""
    return bool(tg and tg.is_active and tg.webhook_registered)


def _fanvue_webhook_url_for_conn(fv: FanvueConnection | None) -> str | None:
    platform = fanvue_platform_webhook_url()
    if platform:
        return platform
    base = settings.public_app_url.rstrip("/")
    if fv:
        return f"{base}/api/webhooks/fanvue/{fv.webhook_secret}"
    return None


def _telegram_connection_out(
    tg: TelegramConnection, *, base: str
) -> PlatformConnectionOut:
    return PlatformConnectionOut(
        id=tg.id,
        platform="telegram",
        label=tg.label,
        studio_model_id=tg.studio_model_id,
        bot_username=tg.bot_username,
        webhook_registered=_telegram_webhook_registered(tg),
        webhook_url=f"{base}/api/webhooks/telegram/{tg.webhook_secret}",
        is_active=bool(tg.is_active),
        companion_mode=tg.companion_mode or "off",
        companion_delay_min_sec=int(tg.companion_delay_min_sec or 5),
        companion_delay_max_sec=int(tg.companion_delay_max_sec or 45),
        companion_max_replies_per_hour=int(tg.companion_max_replies_per_hour or 60),
    )


def _fanvue_connection_out(fv: FanvueConnection) -> PlatformConnectionOut:
    return PlatformConnectionOut(
        id=fv.id,
        platform="fanvue",
        label=fv.label,
        studio_model_id=fv.studio_model_id,
        creator_uuid=fv.creator_uuid,
        oauth_connected=bool(fv.oauth_connected_at),
        webhook_url=_fanvue_webhook_url_for_conn(fv),
        is_active=True,
        companion_mode=fv.companion_mode or "off",
        companion_delay_min_sec=int(fv.companion_delay_min_sec or 5),
        companion_delay_max_sec=int(fv.companion_delay_max_sec or 45),
        companion_max_replies_per_hour=int(fv.companion_max_replies_per_hour or 60),
    )


def _instagram_connection_out(ig: InstagramConnection) -> PlatformConnectionOut:
    return PlatformConnectionOut(
        id=ig.id,
        platform="instagram",
        label=ig.label,
        studio_model_id=ig.studio_model_id,
        instagram_user_id=ig.instagram_user_id,
        instagram_username=ig.instagram_username,
        oauth_connected=bool(ig.oauth_connected_at),
        webhook_url=instagram_platform_webhook_url(),
        is_active=True,
    )


def _tribute_connection_out(tr: TributeConnection) -> PlatformConnectionOut:
    return PlatformConnectionOut(
        id=tr.id,
        platform="tribute",
        label=tr.label,
        studio_model_id=tr.studio_model_id,
        webhook_url=tribute_webhook_url_for_connection(tr),
        is_active=bool(tr.is_active),
    )


async def _integration_status(session: AsyncSession, user: User) -> IntegrationStatusOut:
    oid = workspace_owner_id(user)
    tg_rows = list(
        (
            await session.scalars(
                select(TelegramConnection)
                .where(TelegramConnection.user_id == oid)
                .order_by(TelegramConnection.id.asc())
            )
        ).all()
    )
    fv_rows = list(
        (
            await session.scalars(
                select(FanvueConnection)
                .where(FanvueConnection.user_id == oid)
                .order_by(FanvueConnection.id.asc())
            )
        ).all()
    )
    ig_rows = list(
        (
            await session.scalars(
                select(InstagramConnection)
                .where(InstagramConnection.user_id == oid)
                .order_by(InstagramConnection.id.asc())
            )
        ).all()
    )
    tr_rows = list(
        (
            await session.scalars(
                select(TributeConnection)
                .where(TributeConnection.user_id == oid)
                .order_by(TributeConnection.id.asc())
            )
        ).all()
    )
    tg = next((r for r in tg_rows if r.is_active), tg_rows[0] if tg_rows else None)
    fv = fv_rows[0] if fv_rows else None
    ig = ig_rows[0] if ig_rows else None
    tr = next((r for r in tr_rows if r.is_active), tr_rows[0] if tr_rows else None)
    ws = await session.scalar(
        select(WavespeedConnection).where(WavespeedConnection.user_id == oid)
    )
    sub = await session.scalar(
        select(Subscription).where(Subscription.user_id == oid)
    )
    cr = await session.scalar(select(CreditAccount).where(CreditAccount.user_id == oid))
    demo_rem = int(cr.demo_generations_remaining) if cr else 0
    plan = normalize_billing_plan(sub.billing_plan if sub else None)
    wavespeed_configured, wavespeed_managed_by_platform = wavespeed_cabinet_flags(
        plan=plan, ws_row=ws, sub=sub, demo_generations_remaining=demo_rem
    )
    platform_llm_ok = bool((settings.openai_api_key or "").strip())
    llm_configured = platform_llm_ok
    base = settings.public_app_url.rstrip("/")
    https = base.lower().startswith("https://")
    reg = _telegram_webhook_registered(tg)
    hint: str | None = None
    hint_parts: list[str] = []
    if is_credits_plan(plan) and demo_rem > 0 and wavespeed_managed_by_platform:
        hint_parts.append(
            f"Бесплатные генерации: осталось {demo_rem}. Ключ WaveSpeed не нужен — "
            "студия работает на нашей инфраструктуре."
        )
    elif is_credits_plan(plan) and not wavespeed_configured and demo_rem <= 0:
        hint_parts.append(
            "Пополните кредиты в «Тариф и баланс» или оформите Standard / Pro для работы в студии."
        )
    if tg and tg.is_active and not reg:
        if not https:
            hint_parts.append(
                "Входящие из Telegram работают только если сайт доступен по защищённому адресу (HTTPS). "
                "Обратитесь к администратору с правильным публичным адресом приложения и при необходимости "
                "сохраните подключение снова. Отправка сообщений из этого раздела с сохранённым токеном может работать и без входящего канала."
            )
        else:
            hint_parts.append(
                "Токен сохранён, но входящие из Telegram ещё не подтверждены. Сохраните настройки Telegram ещё раз "
                "после проверки адреса сайта у администратора."
            )
    if hint_parts:
        hint = "\n\n".join(hint_parts)
    lim = plan_limits_for_sub(sub)
    return IntegrationStatusOut(
        telegram_configured=bool(tg and tg.is_active),
        telegram_bot_username=tg.bot_username if tg else None,
        fanvue_configured=bool(fv),
        fanvue_creator_uuid=fv.creator_uuid if fv else None,
        fanvue_webhook_url=_fanvue_webhook_url_for_conn(fv),
        fanvue_oauth_available=_fanvue_oauth_ready(),
        fanvue_oauth_connected=bool(fv and fv.oauth_connected_at),
        instagram_configured=bool(ig),
        instagram_oauth_available=_instagram_oauth_ready(),
        instagram_webhook_url=instagram_platform_webhook_url(),
        telegram_webhook_url=(
            f"{base}/api/webhooks/telegram/{tg.webhook_secret}" if tg else None
        ),
        telegram_webhook_registered=reg,
        integration_hint=hint,
        wavespeed_configured=wavespeed_configured,
        wavespeed_managed_by_platform=wavespeed_managed_by_platform,
        llm_configured=llm_configured,
        telegram_connections=[
            _telegram_connection_out(r, base=base) for r in tg_rows if r.is_active
        ],
        fanvue_connections=[_fanvue_connection_out(r) for r in fv_rows],
        instagram_connections=[_instagram_connection_out(r) for r in ig_rows],
        tribute_configured=bool(tr and tr.is_active),
        tribute_connections=[_tribute_connection_out(r) for r in tr_rows if r.is_active],
        max_connections_per_platform=lim.max_models,
    )


@router.get("", response_model=IntegrationStatusOut)
async def integration_status(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    return await _integration_status(session, user)


@router.get("/health", response_model=IntegrationHealthOut)
async def integration_health(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationHealthOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    pending_jobs = int(
        await session.scalar(
            select(func.count())
            .select_from(CompanionJob)
            .join(Conversation, CompanionJob.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == oid,
                CompanionJob.status.in_(
                    [CompanionJobStatus.pending, CompanionJobStatus.running]
                ),
            )
        )
        or 0
    )
    failed_jobs = int(
        await session.scalar(
            select(func.count())
            .select_from(CompanionJob)
            .join(Conversation, CompanionJob.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == oid,
                CompanionJob.status == CompanionJobStatus.failed,
                CompanionJob.updated_at >= since,
            )
        )
        or 0
    )
    style_count = int(
        await session.scalar(
            select(func.count())
            .select_from(CompanionStyleExample)
            .where(CompanionStyleExample.user_id == oid)
        )
        or 0
    )

    status = await _integration_status(session, user)
    issues: list[str] = []
    if pending_jobs > 50:
        issues.append(f"Большая очередь companion: {pending_jobs} задач")
    if failed_jobs > 0:
        issues.append(f"Companion jobs failed за 24ч: {failed_jobs}")
    if style_count < 10:
        issues.append("Мало примеров style RAG — переиндексируйте из чатов")
    if status.telegram_configured and not status.telegram_webhook_registered:
        issues.append("Telegram webhook не зарегистрирован")

    return IntegrationHealthOut(
        companion_pending_jobs=pending_jobs,
        companion_failed_jobs_24h=failed_jobs,
        companion_style_examples=style_count,
        telegram_webhook_ok=bool(
            status.telegram_configured and status.telegram_webhook_registered
        ),
        fanvue_oauth_ok=bool(status.fanvue_oauth_connected),
        issues=issues,
    )


@router.get("/companion-feedback", response_model=list[CompanionFeedbackReportOut])
async def api_companion_feedback_reports(
    limit: int = Query(default=14, ge=1, le=60),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[CompanionFeedbackReportOut]:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    rows = await list_feedback_reports(session, owner_id=oid, limit=limit)
    out: list[CompanionFeedbackReportOut] = []
    for r in rows:
        stats: dict = {}
        if r.stats_json:
            try:
                stats = json.loads(r.stats_json)
            except json.JSONDecodeError:
                stats = {}
        out.append(
            CompanionFeedbackReportOut(
                id=r.id,
                report_date=r.report_date,
                content=r.content,
                stats=stats,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return out


@router.post("/companion/rebuild-style-index", response_model=CompanionStyleIndexStatsOut)
async def api_rebuild_companion_style_index(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> CompanionStyleIndexStatsOut:
    """Переиндексировать style RAG из реальных чатов workspace (ручной запуск)."""
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    from app.services.companion_bot.style_index import rebuild_style_index

    stats = await rebuild_style_index(owner_id=oid)
    return CompanionStyleIndexStatsOut(**stats)


@router.put("/telegram", response_model=IntegrationStatusOut)
async def put_telegram(
    body: TelegramIntegrationIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    raw = body.bot_token.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="empty bot token")
    try:
        enc = encrypt_secret(raw)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    public_base = settings.public_app_url.strip().rstrip("/")
    https = public_base.lower().startswith("https://")

    webhook_secret = secrets.token_hex(16)
    wh_url = f"{public_base}/api/webhooks/telegram/{webhook_secret}"

    proxy = (settings.telegram_proxy or "").strip()
    session_aio = AiohttpSession(proxy=proxy) if proxy else None
    bot: Bot | None = None
    try:
        bot = Bot(token=raw, session=session_aio) if session_aio else Bot(token=raw)
    except TokenValidationError as e:
        raise HTTPException(
            status_code=400,
            detail="Неверный формат токена BotFather. Скопируйте токен целиком (123456789:AAH…).",
        ) from e
    webhook_registered = False
    try:
        me = await bot.get_me()
        if https:
            from app.connectors.telegram.webhook import register_telegram_webhook

            await register_telegram_webhook(bot, wh_url, drop_pending_updates=True)
            webhook_registered = True
        else:
            log.info(
                "Пропуск setWebhook: PUBLIC_APP_URL=%s не HTTPS — токен сохраняем, "
                "входящие по webhook недоступны до HTTPS (туннель/прод).",
                public_base,
            )
    except Exception as e:
        log.exception("telegram setWebhook failed")
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось проверить токен или зарегистрировать webhook: {e}",
        ) from e
    finally:
        if bot is not None:
            await bot.session.close()

    sub = await session.scalar(select(Subscription).where(Subscription.user_id == oid))
    if body.studio_model_id is not None:
        await validate_connection_studio_model(session, oid, body.studio_model_id)

    try:
        row: TelegramConnection | None = None
        if body.connection_id is not None:
            row = await session.scalar(
                select(TelegramConnection).where(
                    TelegramConnection.id == body.connection_id,
                    TelegramConnection.user_id == oid,
                )
            )
            if not row:
                raise HTTPException(status_code=404, detail="Подключение Telegram не найдено")
        else:
            existing = list(
                (
                    await session.scalars(
                        select(TelegramConnection).where(TelegramConnection.user_id == oid)
                    )
                ).all()
            )
            if len(existing) == 1:
                row = existing[0]
            elif len(existing) == 0:
                await assert_can_add_platform_connection(
                    session, oid, sub, platform=Platform.telegram
                )
            else:
                await assert_can_add_platform_connection(
                    session, oid, sub, platform=Platform.telegram
                )

        label = (body.label or "").strip() or None
        if row:
            row.bot_token_encrypted = enc
            row.webhook_secret = webhook_secret
            row.bot_username = me.username
            row.is_active = True
            row.webhook_registered = webhook_registered
            if label is not None:
                row.label = label
            if body.studio_model_id is not None:
                row.studio_model_id = body.studio_model_id
                await sync_conversations_model_from_connection(
                    session,
                    platform=Platform.telegram,
                    connection_id=row.id,
                    studio_model_id=body.studio_model_id,
                )
        else:
            row = TelegramConnection(
                user_id=oid,
                label=label,
                studio_model_id=body.studio_model_id,
                bot_token_encrypted=enc,
                webhook_secret=webhook_secret,
                bot_username=me.username,
                webhook_registered=webhook_registered,
                is_active=True,
            )
            session.add(row)
        await session.commit()
        return await _integration_status(session, user)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        log.exception("put_telegram failed user=%s owner=%s", user.id, oid)
        raise HTTPException(
            status_code=500,
            detail="Не удалось сохранить подключение Telegram. Обновите сервер (миграции БД) или проверьте FERNET_KEY.",
        ) from e


async def _save_fanvue_oauth_tokens(
    session: AsyncSession,
    *,
    user_id: int,
    creator_uuid: str,
    token_payload: dict,
    connection_id: int | None = None,
    label: str | None = None,
    studio_model_id: int | None = None,
) -> FanvueConnection:
    access = str(token_payload.get("access_token") or "").strip()
    if not access:
        raise FanvueOAuthError("Fanvue token response missing access_token")
    refresh = str(token_payload.get("refresh_token") or "").strip() or None
    enc_access = encrypt_secret(access)
    enc_refresh = encrypt_secret(refresh) if refresh else None
    expires_at: datetime | None = None
    expires_in = token_payload.get("expires_in")
    if expires_in is not None:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None

    row: FanvueConnection | None = None
    if connection_id is not None:
        row = await session.scalar(
            select(FanvueConnection).where(
                FanvueConnection.id == connection_id,
                FanvueConnection.user_id == user_id,
            )
        )
    if row is None:
        existing = list(
            (
                await session.scalars(
                    select(FanvueConnection).where(FanvueConnection.user_id == user_id)
                )
            ).all()
        )
        if len(existing) == 1 and connection_id is None:
            row = existing[0]

    now = datetime.now(timezone.utc)
    if row:
        row.creator_uuid = creator_uuid
        row.access_token_encrypted = enc_access
        row.refresh_token_encrypted = enc_refresh
        row.token_expires_at = expires_at
        row.oauth_connected_at = now
        if label is not None:
            row.label = label
        if studio_model_id is not None:
            row.studio_model_id = studio_model_id
            await sync_conversations_model_from_connection(
                session,
                platform=Platform.fanvue,
                connection_id=row.id,
                studio_model_id=studio_model_id,
            )
    else:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        await assert_can_add_platform_connection(
            session, user_id, sub, platform=Platform.fanvue
        )
        if studio_model_id is not None:
            await validate_connection_studio_model(session, user_id, studio_model_id)
        row = FanvueConnection(
            user_id=user_id,
            label=label,
            studio_model_id=studio_model_id,
            creator_uuid=creator_uuid,
            access_token_encrypted=enc_access,
            refresh_token_encrypted=enc_refresh,
            token_expires_at=expires_at,
            webhook_signing_secret_encrypted=None,
            webhook_secret=secrets.token_hex(16),
            oauth_connected_at=now,
        )
        session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.post("/fanvue/oauth/start", response_model=FanvueOAuthStartOut)
async def fanvue_oauth_start(
    body: FanvueOAuthStartIn | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> FanvueOAuthStartOut:
    assert_permission(user, PERM_INTEGRATIONS)
    if not _fanvue_oauth_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "Fanvue OAuth не настроен на сервере. "
                "Нужны FANVUE_CLIENT_ID, FANVUE_CLIENT_SECRET и FANVUE_WEBHOOK_SIGNING_SECRET."
            ),
        )
    oid = workspace_owner_id(user)
    payload = body or FanvueOAuthStartIn()
    if payload.studio_model_id is not None:
        await validate_connection_studio_model(session, oid, payload.studio_model_id)
    if payload.connection_id is not None:
        row = await session.scalar(
            select(FanvueConnection).where(
                FanvueConnection.id == payload.connection_id,
                FanvueConnection.user_id == oid,
            )
        )
        if not row:
            raise HTTPException(status_code=404, detail="Подключение Fanvue не найдено")
    state = generate_oauth_state()
    code_verifier, code_challenge = generate_pkce_pair()
    session.add(
        FanvueOAuthState(
            state=state,
            user_id=oid,
            code_verifier=code_verifier,
            connection_id=payload.connection_id,
            label=(payload.label or "").strip() or None,
            studio_model_id=payload.studio_model_id,
        )
    )
    await session.commit()
    return FanvueOAuthStartOut(
        authorize_url=build_fanvue_authorize_url(state=state, code_challenge=code_challenge)
    )


@router.get("/fanvue/oauth/callback")
async def fanvue_oauth_callback(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    base = settings.public_app_url.rstrip("/")
    fail = f"{base}/?account=integrations&fanvue=error"
    ok = f"{base}/?account=integrations&fanvue=connected"

    if error:
        log.warning("fanvue oauth denied: %s %s", error, error_description or "")
        q = urlencode({"account": "integrations", "fanvue": "error", "reason": error})
        return RedirectResponse(url=f"{base}/?{q}", status_code=302)

    if not code or not state:
        return RedirectResponse(url=fail, status_code=302)

    pending = await session.scalar(
        select(FanvueOAuthState).where(FanvueOAuthState.state == state.strip())
    )
    if not pending:
        return RedirectResponse(url=fail, status_code=302)

    mobile_oauth = (pending.label or "").strip() == "__mobile__"
    if mobile_oauth:
        fail = f"{base}/mobile-oauth-return.html?provider=fanvue&status=error"
        ok = f"{base}/mobile-oauth-return.html?provider=fanvue&status=connected"

    created = pending.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > timedelta(minutes=15):
        await session.execute(delete(FanvueOAuthState).where(FanvueOAuthState.state == state))
        await session.commit()
        return RedirectResponse(url=fail, status_code=302)

    user_id = pending.user_id
    code_verifier = pending.code_verifier
    oauth_connection_id = pending.connection_id
    oauth_label = None if mobile_oauth else pending.label
    oauth_studio_model_id = pending.studio_model_id
    await session.execute(delete(FanvueOAuthState).where(FanvueOAuthState.state == state))
    await session.commit()

    saved_conn_id: int | None = None
    try:
        token_payload = await exchange_fanvue_authorization_code(
            code=code.strip(),
            code_verifier=code_verifier,
        )
        access = str(token_payload.get("access_token") or "").strip()
        me = await fetch_fanvue_current_user(access)
        creator_uuid = str(me.get("uuid") or me.get("id") or "").strip()
        if not creator_uuid:
            raise FanvueOAuthError("Fanvue /users/me missing uuid")
        saved = await _save_fanvue_oauth_tokens(
            session,
            user_id=user_id,
            creator_uuid=creator_uuid,
            token_payload=token_payload,
            connection_id=oauth_connection_id,
            label=oauth_label,
            studio_model_id=oauth_studio_model_id,
        )
        saved_conn_id = saved.id
    except FanvueOAuthError as e:
        log.warning("fanvue oauth callback failed user=%s: %s", user_id, e)
        if mobile_oauth:
            return RedirectResponse(url=fail, status_code=302)
        q = urlencode({"account": "integrations", "fanvue": "error"})
        return RedirectResponse(url=f"{base}/?{q}", status_code=302)
    except Exception:
        log.exception("fanvue oauth callback failed user=%s", user_id)
        if mobile_oauth:
            return RedirectResponse(url=fail, status_code=302)
        q = urlencode({"account": "integrations", "fanvue": "error"})
        return RedirectResponse(url=f"{base}/?{q}", status_code=302)

    background_tasks.add_task(_background_fanvue_history_sync, user_id, saved_conn_id)
    return RedirectResponse(url=ok, status_code=302)


@router.post("/fanvue/sync", response_model=FanvueSyncOut)
async def fanvue_sync_history(
    connection_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> FanvueSyncOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    if connection_id is not None:
        row = await session.scalar(
            select(FanvueConnection).where(
                FanvueConnection.id == connection_id,
                FanvueConnection.user_id == oid,
            )
        )
    else:
        row = await session.scalar(
            select(FanvueConnection)
            .where(FanvueConnection.user_id == oid)
            .order_by(FanvueConnection.id.asc())
            .limit(1)
        )
    if not row:
        raise HTTPException(status_code=404, detail="Fanvue is not connected")
    try:
        stats = await sync_fanvue_chat_history(session, conn=row)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.exception("fanvue sync failed user=%s", oid)
        raise HTTPException(status_code=500, detail="Fanvue sync failed") from e
    return FanvueSyncOut(
        chats_processed=int(stats["chats_processed"]),
        messages_imported=int(stats["messages_imported"]),
        messages_skipped=int(stats["messages_skipped"]),
        messages_empty=int(stats["messages_empty"]),
        errors=list(stats["errors"]) if isinstance(stats["errors"], list) else [],
    )


@router.delete("/fanvue", response_model=IntegrationStatusOut)
async def delete_fanvue(
    connection_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    if connection_id is not None:
        row = await session.scalar(
            select(FanvueConnection).where(
                FanvueConnection.id == connection_id,
                FanvueConnection.user_id == oid,
            )
        )
    else:
        row = await session.scalar(
            select(FanvueConnection)
            .where(FanvueConnection.user_id == oid)
            .order_by(FanvueConnection.id.asc())
            .limit(1)
        )
    if row:
        await session.delete(row)
        await session.commit()
    return await _integration_status(session, user)


@router.put("/fanvue", response_model=IntegrationStatusOut)
async def put_fanvue(
    body: FanvueIntegrationIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    """Legacy: ручной ввод token/uuid/signing secret (если OAuth недоступен)."""
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    try:
        enc_tok = encrypt_secret(body.access_token.strip())
        enc_sign: str | None = None
        sign_raw = (body.webhook_signing_secret or "").strip()
        if sign_raw:
            enc_sign = encrypt_secret(sign_raw)
        elif not fanvue_platform_webhook_signing_secret():
            raise HTTPException(
                status_code=400,
                detail="Webhook signing secret required when platform secret is not configured",
            )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    row = await session.scalar(
        select(FanvueConnection).where(FanvueConnection.user_id == oid)
    )
    webhook_secret = row.webhook_secret if row else secrets.token_hex(16)
    if row:
        row.creator_uuid = body.creator_uuid.strip()
        row.access_token_encrypted = enc_tok
        if enc_sign:
            row.webhook_signing_secret_encrypted = enc_sign
    else:
        row = FanvueConnection(
            user_id=oid,
            creator_uuid=body.creator_uuid.strip(),
            access_token_encrypted=enc_tok,
            webhook_signing_secret_encrypted=enc_sign,
            webhook_secret=webhook_secret,
        )
        session.add(row)
    await session.commit()
    return await _integration_status(session, user)


@router.patch("/telegram/{connection_id}", response_model=IntegrationStatusOut)
async def patch_telegram_connection(
    connection_id: int,
    body: PlatformConnectionPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(TelegramConnection).where(
            TelegramConnection.id == connection_id,
            TelegramConnection.user_id == oid,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Подключение Telegram не найдено")
    if "label" in body.model_fields_set:
        row.label = (body.label or "").strip() or None
    if "studio_model_id" in body.model_fields_set:
        await validate_connection_studio_model(session, oid, body.studio_model_id)
        row.studio_model_id = body.studio_model_id
        await sync_conversations_model_from_connection(
            session,
            platform=Platform.telegram,
            connection_id=row.id,
            studio_model_id=body.studio_model_id,
        )
    _apply_companion_connection_patch(row, body)
    await session.commit()
    return await _integration_status(session, user)


@router.delete("/telegram/{connection_id}", response_model=IntegrationStatusOut)
async def delete_telegram_connection(
    connection_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(TelegramConnection).where(
            TelegramConnection.id == connection_id,
            TelegramConnection.user_id == oid,
        )
    )
    if row:
        row.is_active = False
        row.webhook_registered = False
        await session.commit()
    return await _integration_status(session, user)


@router.patch("/fanvue/{connection_id}", response_model=IntegrationStatusOut)
async def patch_fanvue_connection(
    connection_id: int,
    body: PlatformConnectionPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(FanvueConnection).where(
            FanvueConnection.id == connection_id,
            FanvueConnection.user_id == oid,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Подключение Fanvue не найдено")
    if "label" in body.model_fields_set:
        row.label = (body.label or "").strip() or None
    if "studio_model_id" in body.model_fields_set:
        await validate_connection_studio_model(session, oid, body.studio_model_id)
        row.studio_model_id = body.studio_model_id
        await sync_conversations_model_from_connection(
            session,
            platform=Platform.fanvue,
            connection_id=row.id,
            studio_model_id=body.studio_model_id,
        )
    _apply_companion_connection_patch(row, body)
    await session.commit()
    return await _integration_status(session, user)


async def _save_instagram_oauth_tokens(
    session: AsyncSession,
    *,
    user_id: int,
    instagram_user_id: str,
    instagram_alt_user_id: str | None = None,
    instagram_username: str | None,
    token_payload: dict,
    connection_id: int | None = None,
    label: str | None = None,
    studio_model_id: int | None = None,
) -> InstagramConnection:
    access = str(token_payload.get("access_token") or "").strip()
    if not access:
        raise InstagramOAuthError("Instagram token response missing access_token")
    enc_access = encrypt_secret(access)
    expires_at: datetime | None = None
    expires_in = token_payload.get("expires_in")
    if expires_in is not None:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None

    row: InstagramConnection | None = None
    if connection_id is not None:
        row = await session.scalar(
            select(InstagramConnection).where(
                InstagramConnection.id == connection_id,
                InstagramConnection.user_id == user_id,
            )
        )
    if row is None:
        existing = list(
            (
                await session.scalars(
                    select(InstagramConnection).where(InstagramConnection.user_id == user_id)
                )
            ).all()
        )
        if len(existing) == 1 and connection_id is None:
            row = existing[0]

    now = datetime.now(timezone.utc)
    if row:
        row.instagram_user_id = instagram_user_id
        row.instagram_alt_user_id = instagram_alt_user_id
        row.instagram_username = instagram_username
        row.access_token_encrypted = enc_access
        row.token_expires_at = expires_at
        row.oauth_connected_at = now
        if label is not None:
            row.label = label
        if studio_model_id is not None:
            row.studio_model_id = studio_model_id
            await sync_conversations_model_from_connection(
                session,
                platform=Platform.instagram,
                connection_id=row.id,
                studio_model_id=studio_model_id,
            )
    else:
        sub = await session.scalar(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        await assert_can_add_platform_connection(
            session, user_id, sub, platform=Platform.instagram
        )
        if studio_model_id is not None:
            await validate_connection_studio_model(session, user_id, studio_model_id)
        row = InstagramConnection(
            user_id=user_id,
            label=label,
            studio_model_id=studio_model_id,
            instagram_user_id=instagram_user_id,
            instagram_alt_user_id=instagram_alt_user_id,
            instagram_username=instagram_username,
            access_token_encrypted=enc_access,
            token_expires_at=expires_at,
            oauth_connected_at=now,
        )
        session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.post("/instagram/oauth/start", response_model=InstagramOAuthStartOut)
async def instagram_oauth_start(
    body: InstagramOAuthStartIn | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> InstagramOAuthStartOut:
    assert_permission(user, PERM_INTEGRATIONS)
    if not _instagram_oauth_ready():
        raise HTTPException(
            status_code=503,
            detail=(
                "Instagram OAuth не настроен на сервере. "
                "Нужны INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET и INSTAGRAM_WEBHOOK_VERIFY_TOKEN."
            ),
        )
    oid = workspace_owner_id(user)
    payload = body or InstagramOAuthStartIn()
    if payload.studio_model_id is not None:
        await validate_connection_studio_model(session, oid, payload.studio_model_id)
    if payload.connection_id is not None:
        row = await session.scalar(
            select(InstagramConnection).where(
                InstagramConnection.id == payload.connection_id,
                InstagramConnection.user_id == oid,
            )
        )
        if not row:
            raise HTTPException(status_code=404, detail="Подключение Instagram не найдено")
    state = generate_instagram_oauth_state()
    session.add(
        InstagramOAuthState(
            state=state,
            user_id=oid,
            connection_id=payload.connection_id,
            label=(payload.label or "").strip() or None,
            studio_model_id=payload.studio_model_id,
        )
    )
    await session.commit()
    return InstagramOAuthStartOut(
        authorize_url=build_instagram_authorize_url(state=state)
    )


@router.get("/instagram/oauth/callback")
async def instagram_oauth_callback(
    session: AsyncSession = Depends(get_session),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    base = settings.public_app_url.rstrip("/")
    fail = f"{base}/?account=integrations&instagram=error"
    ok = f"{base}/?account=integrations&instagram=connected"

    if error:
        log.warning("instagram oauth denied: %s %s", error, error_description or "")
        q = urlencode({"account": "integrations", "instagram": "error", "reason": error})
        return RedirectResponse(url=f"{base}/?{q}", status_code=302)

    if not code or not state:
        return RedirectResponse(url=fail, status_code=302)

    pending = await session.scalar(
        select(InstagramOAuthState).where(InstagramOAuthState.state == state.strip())
    )
    if not pending:
        return RedirectResponse(url=fail, status_code=302)

    created = pending.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > timedelta(minutes=15):
        await session.execute(delete(InstagramOAuthState).where(InstagramOAuthState.state == state))
        await session.commit()
        return RedirectResponse(url=fail, status_code=302)

    user_id = pending.user_id
    oauth_connection_id = pending.connection_id
    oauth_label = pending.label
    oauth_studio_model_id = pending.studio_model_id
    await session.execute(delete(InstagramOAuthState).where(InstagramOAuthState.state == state))
    await session.commit()

    try:
        token_payload = await exchange_instagram_authorization_code(code=code.strip())
        access = str(token_payload.get("access_token") or "").strip()
        profile = await fetch_instagram_profile(access)
        ig_user_id, ig_alt_user_id = resolve_instagram_profile_ids(profile, token_payload)
        if not ig_user_id:
            raise InstagramOAuthError("Instagram profile missing id")
        username = str(profile.get("username") or "").strip() or None
        log.info(
            "instagram oauth profile ids primary=%s alt=%s username=%s",
            ig_user_id[:16],
            (ig_alt_user_id or "")[:16] or "—",
            username or "—",
        )
        await subscribe_instagram_webhooks(access, fields="messages")
        await _save_instagram_oauth_tokens(
            session,
            user_id=user_id,
            instagram_user_id=ig_user_id,
            instagram_alt_user_id=ig_alt_user_id,
            instagram_username=username,
            token_payload=token_payload,
            connection_id=oauth_connection_id,
            label=oauth_label,
            studio_model_id=oauth_studio_model_id,
        )
    except InstagramOAuthError as e:
        log.warning("instagram oauth callback failed user=%s: %s", user_id, e)
        return RedirectResponse(url=fail, status_code=302)
    except Exception:
        log.exception("instagram oauth callback failed user=%s", user_id)
        return RedirectResponse(url=fail, status_code=302)

    return RedirectResponse(url=ok, status_code=302)


@router.patch("/instagram/{connection_id}", response_model=IntegrationStatusOut)
async def patch_instagram_connection(
    connection_id: int,
    body: PlatformConnectionPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(InstagramConnection).where(
            InstagramConnection.id == connection_id,
            InstagramConnection.user_id == oid,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Подключение Instagram не найдено")
    if "label" in body.model_fields_set:
        row.label = (body.label or "").strip() or None
    if "studio_model_id" in body.model_fields_set:
        await validate_connection_studio_model(session, oid, body.studio_model_id)
        row.studio_model_id = body.studio_model_id
        await sync_conversations_model_from_connection(
            session,
            platform=Platform.instagram,
            connection_id=row.id,
            studio_model_id=body.studio_model_id,
        )
    await session.commit()
    return await _integration_status(session, user)


@router.delete("/instagram", response_model=IntegrationStatusOut)
async def delete_instagram(
    connection_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    if connection_id is not None:
        row = await session.scalar(
            select(InstagramConnection).where(
                InstagramConnection.id == connection_id,
                InstagramConnection.user_id == oid,
            )
        )
    else:
        row = await session.scalar(
            select(InstagramConnection)
            .where(InstagramConnection.user_id == oid)
            .order_by(InstagramConnection.id.asc())
            .limit(1)
        )
    if row:
        await session.delete(row)
        await session.commit()
    return await _integration_status(session, user)


@router.put("/tribute", response_model=IntegrationStatusOut)
async def put_tribute(
    body: TributeIntegrationIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == oid))
    raw_key = body.api_key.strip()
    if len(raw_key) < 8:
        raise HTTPException(status_code=400, detail="empty api key")
    try:
        enc = encrypt_secret(raw_key)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    if body.studio_model_id is not None:
        await validate_connection_studio_model(session, oid, body.studio_model_id)

    row: TributeConnection | None = None
    if body.connection_id is not None:
        row = await session.scalar(
            select(TributeConnection).where(
                TributeConnection.id == body.connection_id,
                TributeConnection.user_id == oid,
            )
        )
        if not row:
            raise HTTPException(status_code=404, detail="Подключение Tribute не найдено")
    else:
        existing = list(
            (
                await session.scalars(
                    select(TributeConnection).where(TributeConnection.user_id == oid)
                )
            ).all()
        )
        if len(existing) == 1:
            row = existing[0]
        elif len(existing) == 0:
            await assert_can_add_tribute_connection(session, oid, sub)
        else:
            await assert_can_add_tribute_connection(session, oid, sub)

    label = (body.label or "").strip() or None
    if row:
        row.api_key_encrypted = enc
        row.is_active = True
        if label is not None:
            row.label = label
        if body.studio_model_id is not None:
            row.studio_model_id = body.studio_model_id
    else:
        row = TributeConnection(
            user_id=oid,
            label=label,
            studio_model_id=body.studio_model_id,
            api_key_encrypted=enc,
            webhook_secret=secrets.token_urlsafe(32),
            is_active=True,
        )
        session.add(row)
    await session.commit()
    return await _integration_status(session, user)


@router.patch("/tribute/{connection_id}", response_model=IntegrationStatusOut)
async def patch_tribute_connection(
    connection_id: int,
    body: PlatformConnectionPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(TributeConnection).where(
            TributeConnection.id == connection_id,
            TributeConnection.user_id == oid,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Подключение Tribute не найдено")
    if "label" in body.model_fields_set:
        row.label = (body.label or "").strip() or None
    if "studio_model_id" in body.model_fields_set:
        await validate_connection_studio_model(session, oid, body.studio_model_id)
        row.studio_model_id = body.studio_model_id
    await session.commit()
    return await _integration_status(session, user)


@router.delete("/tribute", response_model=IntegrationStatusOut)
async def delete_tribute(
    connection_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    if connection_id is not None:
        row = await session.scalar(
            select(TributeConnection).where(
                TributeConnection.id == connection_id,
                TributeConnection.user_id == oid,
            )
        )
    else:
        row = await session.scalar(
            select(TributeConnection)
            .where(TributeConnection.user_id == oid)
            .order_by(TributeConnection.id.asc())
            .limit(1)
        )
    if row:
        await session.delete(row)
        await session.commit()
    return await _integration_status(session, user)


@router.put("/wavespeed", response_model=IntegrationStatusOut)
async def put_wavespeed(
    body: WavespeedIntegrationIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    raw = body.api_key.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="empty api key")
    try:
        enc = encrypt_secret(raw)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    try:
        row = await session.scalar(
            select(WavespeedConnection).where(WavespeedConnection.user_id == oid)
        )
        if row:
            row.api_key_encrypted = enc
        else:
            session.add(WavespeedConnection(user_id=oid, api_key_encrypted=enc))
        from app.services.funnel_analytics import record_funnel_event_once

        await record_funnel_event_once(session, user=user, event="ws_key_saved")
        await session.commit()
        return await _integration_status(session, user)
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        log.exception("put_wavespeed failed user=%s owner=%s", user.id, oid)
        raise HTTPException(
            status_code=500,
            detail="Не удалось сохранить ключ WaveSpeed. Обновите сервер (миграции БД) или проверьте FERNET_KEY.",
        ) from e


@router.put("/llm", response_model=IntegrationStatusOut)
async def put_llm(
    body: LlmIntegrationIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    raw = body.api_key.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="empty api key")
    try:
        enc = encrypt_secret(raw)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    base_url = body.base_url
    if base_url:
        base_url = base_url.rstrip("/")

    row = await session.scalar(select(LlmConnection).where(LlmConnection.user_id == oid))
    if row:
        row.api_key_encrypted = enc
        row.base_url = base_url
    else:
        session.add(LlmConnection(user_id=oid, api_key_encrypted=enc, base_url=base_url))
    await session.commit()
    return await _integration_status(session, user)
