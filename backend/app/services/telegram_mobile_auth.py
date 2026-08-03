"""Mobile Telegram login через /start в login-боте (без web widget)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_utils import create_access_token
from app.config import settings
from app.db.models import TelegramMobileAuthSession
from app.services.device_signal import DeviceSignal
from app.services.funnel_analytics import record_funnel_event_once
from app.services.telegram_identity import create_owner_from_telegram, find_owner_by_telegram_id

SESSION_TTL_SECONDS = 300
START_PREFIX = "mm_"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mobile_auth_start_param(session_id: str) -> str:
    return f"{START_PREFIX}{session_id}"


def parse_mobile_auth_start_param(raw: str | None) -> str | None:
    arg = (raw or "").strip()
    if not arg.startswith(START_PREFIX):
        return None
    session_id = arg[len(START_PREFIX) :].strip()
    return session_id or None


async def create_mobile_auth_session(
    session: AsyncSession,
    *,
    referral_code: str | None = None,
    is_partner: bool = False,
    device_key: str | None = None,
) -> TelegramMobileAuthSession:
    if not settings.telegram_login_configured:
        raise HTTPException(status_code=503, detail="Telegram Login не настроен на сервере")
    bot_username = (settings.telegram_login_bot_username or "").strip().lstrip("@")
    if not bot_username:
        raise HTTPException(status_code=503, detail="Telegram Login не настроен на сервере")

    session_id = secrets.token_urlsafe(24)
    row = TelegramMobileAuthSession(
        id=session_id,
        status="pending",
        referral_code=(referral_code or "").strip().upper()[:16] or None,
        is_partner=bool(is_partner),
        device_key=(device_key or "").strip()[:64] or None,
        expires_at=_now() + timedelta(seconds=SESSION_TTL_SECONDS),
    )
    session.add(row)
    await session.flush()
    return row


def telegram_deep_link_for_session(session_id: str) -> str:
    bot_username = (settings.telegram_login_bot_username or "").strip().lstrip("@")
    return f"https://t.me/{bot_username}?start={mobile_auth_start_param(session_id)}"


async def get_mobile_auth_session(
    session: AsyncSession,
    session_id: str,
) -> TelegramMobileAuthSession | None:
    sid = (session_id or "").strip()
    if not sid:
        return None
    return await session.get(TelegramMobileAuthSession, sid)


async def poll_mobile_auth_session(
    session: AsyncSession,
    session_id: str,
) -> dict:
    row = await get_mobile_auth_session(session, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Сессия входа не найдена")
    if row.status == "done" and row.access_token:
        return {"status": "done", "access_token": row.access_token}
    if row.expires_at < _now():
        if row.status != "done":
            row.status = "expired"
            await session.flush()
        return {"status": "expired"}
    return {"status": row.status}


async def complete_mobile_auth_session(
    session: AsyncSession,
    *,
    session_id: str,
    telegram_id: int,
    telegram_username: str | None,
) -> TelegramMobileAuthSession:
    row = await get_mobile_auth_session(session, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Сессия входа не найдена или устарела")
    if row.expires_at < _now():
        row.status = "expired"
        await session.flush()
        raise HTTPException(status_code=410, detail="Сессия входа истекла — начните снова в приложении")
    if row.status == "done" and row.access_token:
        return row

    existing = await find_owner_by_telegram_id(session, telegram_id)
    if existing:
        if not existing.is_active:
            raise HTTPException(status_code=403, detail="account disabled")
        user = existing
        existing.telegram_username = (telegram_username or "").strip().lstrip("@")[:64] or None
    else:
        device_signal = None
        if row.device_key:
            device_signal = DeviceSignal(
                device_key=row.device_key,
                ip_hash="",
                ua_hash="",
                fp_hash=None,
            )
        user = await create_owner_from_telegram(
            session,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
            referral_code=row.referral_code,
            is_partner=bool(getattr(row, "is_partner", False)),
            device_signal=device_signal,
        )
        await record_funnel_event_once(session, user=user, event="signup_telegram")

    token = create_access_token(str(user.id))
    row.status = "done"
    row.access_token = token
    row.telegram_id = int(telegram_id)
    row.completed_at = _now()
    await session.flush()
    return row
