from __future__ import annotations

import logging
import secrets

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import FanvueConnection, TelegramConnection, User, WavespeedConnection
from app.db.session import get_session
from app.schemas import (
    FanvueIntegrationIn,
    IntegrationStatusOut,
    TelegramIntegrationIn,
    WavespeedIntegrationIn,
)
from app.services.crypto_secret import encrypt_secret
from app.services.workspace import PERM_INTEGRATIONS, assert_permission, workspace_owner_id

log = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _telegram_webhook_registered(tg: TelegramConnection | None) -> bool:
    """Webhook у Telegram есть только если при сохранении вызывали setWebhook (HTTPS)."""
    return bool(tg and tg.is_active and tg.webhook_registered)


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
    base = settings.public_app_url.rstrip("/")
    https = base.lower().startswith("https://")
    reg = _telegram_webhook_registered(tg)
    hint: str | None = None
    if tg and tg.is_active and not reg:
        if not https:
            hint = (
                "Telegram принимает webhook только по HTTPS. На http://localhost "
                "входящие не придут — используйте ngrok/Cloudflare Tunnel, выставьте "
                "PUBLIC_APP_URL=https://… и снова нажмите «Сохранить Telegram». "
                "Ответы из интерфейса с сохранённым токеном работают. "
                "Либо локально: BOT_TOKEN + LEGACY_USER_ID в .env для polling."
            )
        else:
            hint = (
                "Токен сохранён, но webhook у Telegram не подтверждён — сохраните "
                "интеграцию снова после проверки PUBLIC_APP_URL."
            )
    return IntegrationStatusOut(
        telegram_configured=bool(tg and tg.is_active),
        telegram_bot_username=tg.bot_username if tg else None,
        fanvue_configured=bool(fv),
        fanvue_creator_uuid=fv.creator_uuid if fv else None,
        fanvue_webhook_url=(
            f"{base}/api/webhooks/fanvue/{fv.webhook_secret}" if fv else None
        ),
        telegram_webhook_url=(
            f"{base}/api/webhooks/telegram/{tg.webhook_secret}" if tg else None
        ),
        telegram_webhook_registered=reg,
        integration_hint=hint,
        wavespeed_configured=bool(ws and (ws.api_key_encrypted or "").strip()),
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


@router.put("/fanvue", response_model=IntegrationStatusOut)
async def put_fanvue(
    body: FanvueIntegrationIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> IntegrationStatusOut:
    assert_permission(user, PERM_INTEGRATIONS)
    oid = workspace_owner_id(user)
    try:
        enc_tok = encrypt_secret(body.access_token.strip())
        enc_sign = encrypt_secret(body.webhook_signing_secret.strip())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    webhook_secret = secrets.token_hex(16)
    row = await session.scalar(
        select(FanvueConnection).where(FanvueConnection.user_id == oid)
    )
    if row:
        row.creator_uuid = body.creator_uuid.strip()
        row.access_token_encrypted = enc_tok
        row.webhook_signing_secret_encrypted = enc_sign
        row.webhook_secret = webhook_secret
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

    row = await session.scalar(
        select(WavespeedConnection).where(WavespeedConnection.user_id == oid)
    )
    if row:
        row.api_key_encrypted = enc
    else:
        session.add(WavespeedConnection(user_id=oid, api_key_encrypted=enc))
    await session.commit()
    return await _integration_status(session, user)
