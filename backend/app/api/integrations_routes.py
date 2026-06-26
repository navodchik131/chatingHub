from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
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
from app.db.models import (
    CreditAccount,
    FanvueConnection,
    FanvueOAuthState,
    LlmConnection,
    Subscription,
    TelegramConnection,
    User,
    WavespeedConnection,
)
from app.db.session import get_session
from app.schemas import (
    FanvueIntegrationIn,
    FanvueOAuthStartOut,
    IntegrationStatusOut,
    LlmIntegrationIn,
    TelegramIntegrationIn,
    WavespeedIntegrationIn,
)
from app.services.billing_plan import is_credits_plan, normalize_billing_plan
from app.services.crypto_secret import encrypt_secret
from app.services.fanvue_connection import (
    fanvue_platform_webhook_signing_secret,
    fanvue_platform_webhook_url,
)
from app.services.studio_keys import wavespeed_cabinet_flags
from app.services.workspace import PERM_INTEGRATIONS, assert_permission, workspace_owner_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _telegram_webhook_registered(tg: TelegramConnection | None) -> bool:
    """Webhook у Telegram есть только если при сохранении вызывали setWebhook (HTTPS)."""
    return bool(tg and tg.is_active and tg.webhook_registered)


def _fanvue_webhook_url(fv: FanvueConnection | None) -> str | None:
    platform = fanvue_platform_webhook_url()
    if platform:
        return platform
    base = settings.public_app_url.rstrip("/")
    if fv:
        return f"{base}/api/webhooks/fanvue/{fv.webhook_secret}"
    return None


def _fanvue_oauth_ready() -> bool:
    return fanvue_oauth_configured() and bool(fanvue_platform_webhook_signing_secret())


async def _integration_status(session: AsyncSession, user: User) -> IntegrationStatusOut:
    oid = workspace_owner_id(user)
    tg = await session.scalar(
        select(TelegramConnection).where(TelegramConnection.user_id == oid)
    )
    fv = await session.scalar(
        select(FanvueConnection).where(FanvueConnection.user_id == oid)
    )
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
    return IntegrationStatusOut(
        telegram_configured=bool(tg and tg.is_active),
        telegram_bot_username=tg.bot_username if tg else None,
        fanvue_configured=bool(fv),
        fanvue_creator_uuid=fv.creator_uuid if fv else None,
        fanvue_webhook_url=_fanvue_webhook_url(fv),
        fanvue_oauth_available=_fanvue_oauth_ready(),
        fanvue_oauth_connected=bool(fv and fv.oauth_connected_at),
        telegram_webhook_url=(
            f"{base}/api/webhooks/telegram/{tg.webhook_secret}" if tg else None
        ),
        telegram_webhook_registered=reg,
        integration_hint=hint,
        wavespeed_configured=wavespeed_configured,
        wavespeed_managed_by_platform=wavespeed_managed_by_platform,
        llm_configured=llm_configured,
    )


@router.get("", response_model=IntegrationStatusOut)
async def integration_status(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    return await _integration_status(session, user)


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
    bot = Bot(token=raw, session=session_aio) if session_aio else Bot(token=raw)
    webhook_registered = False
    try:
        me = await bot.get_me()
        if https:
            await bot.set_webhook(wh_url, drop_pending_updates=True)
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
        await bot.session.close()

    row = await session.scalar(
        select(TelegramConnection).where(TelegramConnection.user_id == oid)
    )
    if row:
        row.bot_token_encrypted = enc
        row.webhook_secret = webhook_secret
        row.bot_username = me.username
        row.is_active = True
        row.webhook_registered = webhook_registered
    else:
        row = TelegramConnection(
            user_id=oid,
            bot_token_encrypted=enc,
            webhook_secret=webhook_secret,
            bot_username=me.username,
            webhook_registered=webhook_registered,
            is_active=True,
        )
        session.add(row)
    await session.commit()

    return await _integration_status(session, user)


async def _save_fanvue_oauth_tokens(
    session: AsyncSession,
    *,
    user_id: int,
    creator_uuid: str,
    token_payload: dict,
) -> None:
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

    row = await session.scalar(
        select(FanvueConnection).where(FanvueConnection.user_id == user_id)
    )
    now = datetime.now(timezone.utc)
    if row:
        row.creator_uuid = creator_uuid
        row.access_token_encrypted = enc_access
        row.refresh_token_encrypted = enc_refresh
        row.token_expires_at = expires_at
        row.oauth_connected_at = now
    else:
        row = FanvueConnection(
            user_id=user_id,
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


@router.post("/fanvue/oauth/start", response_model=FanvueOAuthStartOut)
async def fanvue_oauth_start(
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
    state = generate_oauth_state()
    code_verifier, code_challenge = generate_pkce_pair()
    session.add(
        FanvueOAuthState(
            state=state,
            user_id=oid,
            code_verifier=code_verifier,
        )
    )
    await session.commit()
    return FanvueOAuthStartOut(
        authorize_url=build_fanvue_authorize_url(state=state, code_challenge=code_challenge)
    )


@router.get("/fanvue/oauth/callback")
async def fanvue_oauth_callback(
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

    created = pending.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > timedelta(minutes=15):
        await session.execute(delete(FanvueOAuthState).where(FanvueOAuthState.state == state))
        await session.commit()
        return RedirectResponse(url=fail, status_code=302)

    user_id = pending.user_id
    code_verifier = pending.code_verifier
    await session.execute(delete(FanvueOAuthState).where(FanvueOAuthState.state == state))
    await session.commit()

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
        await _save_fanvue_oauth_tokens(
            session,
            user_id=user_id,
            creator_uuid=creator_uuid,
            token_payload=token_payload,
        )
    except FanvueOAuthError as e:
        log.warning("fanvue oauth callback failed user=%s: %s", user_id, e)
        q = urlencode({"account": "integrations", "fanvue": "error"})
        return RedirectResponse(url=f"{base}/?{q}", status_code=302)
    except Exception:
        log.exception("fanvue oauth callback failed user=%s", user_id)
        q = urlencode({"account": "integrations", "fanvue": "error"})
        return RedirectResponse(url=f"{base}/?{q}", status_code=302)

    return RedirectResponse(url=ok, status_code=302)


@router.delete("/fanvue", response_model=IntegrationStatusOut)
async def delete_fanvue(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    row = await session.scalar(
        select(FanvueConnection).where(FanvueConnection.user_id == oid)
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
