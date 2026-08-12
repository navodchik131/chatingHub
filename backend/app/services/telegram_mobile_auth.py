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
from app.db.models import User
from app.services.telegram_identity import (
    create_owner_from_telegram,
    find_owner_by_telegram_id,
    link_telegram_to_owner,
)

SESSION_TTL_SECONDS = 300
START_PREFIX = "mm_"
LINK_START_PREFIX = "mml_"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mobile_auth_start_param(session_id: str) -> str:
    return f"{START_PREFIX}{session_id}"


def parse_mobile_auth_start_param(raw: str | None) -> str | None:
    arg = (raw or "").strip()
    if arg.startswith(LINK_START_PREFIX):
        return None
    if not arg.startswith(START_PREFIX):
        return None
    session_id = arg[len(START_PREFIX) :].strip()
    return session_id or None


def parse_mobile_link_start_param(raw: str | None) -> str | None:
    arg = (raw or "").strip()
    if not arg.startswith(LINK_START_PREFIX):
        return None
    session_id = arg[len(LINK_START_PREFIX) :].strip()
    return session_id or None


def mobile_link_start_param(session_id: str) -> str:
    return f"{LINK_START_PREFIX}{session_id}"


async def create_mobile_link_session(
    session: AsyncSession,
    *,
    owner_user_id: int,
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
        link_owner_user_id=int(owner_user_id),
        expires_at=_now() + timedelta(seconds=SESSION_TTL_SECONDS),
    )
    session.add(row)
    await session.flush()
    return row


def telegram_link_deep_link_for_session(session_id: str) -> str:
    bot_username = (settings.telegram_login_bot_username or "").strip().lstrip("@")
    return f"https://t.me/{bot_username}?start={mobile_link_start_param(session_id)}"


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
    if row.status == "done":
        if row.link_owner_user_id:
            owner = await session.get(User, row.link_owner_user_id)
            return {
                "status": "done",
                "telegram_linked": True,
                "telegram_username": owner.telegram_username if owner else None,
            }
        if row.access_token:
            return {"status": "done", "access_token": row.access_token}
    if row.expires_at < _now():
        if row.status != "done":
            row.status = "expired"
            await session.flush()
        return {"status": "expired"}
    return {"status": row.status}


async def poll_mobile_link_session(
    session: AsyncSession,
    session_id: str,
    *,
    owner_user_id: int,
) -> dict:
    row = await get_mobile_auth_session(session, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Сессия привязки не найдена")
    if row.link_owner_user_id != int(owner_user_id):
        raise HTTPException(status_code=403, detail="Сессия привязки принадлежит другому пользователю")
    return await poll_mobile_auth_session(session, session_id)


async def complete_mobile_link_session(
    session: AsyncSession,
    *,
    session_id: str,
    telegram_id: int,
    telegram_username: str | None,
) -> TelegramMobileAuthSession:
    row = await get_mobile_auth_session(session, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Сессия привязки не найдена или устарела")
    if not row.link_owner_user_id:
        raise HTTPException(status_code=400, detail="Некорректная сессия привязки")
    if row.expires_at < _now():
        row.status = "expired"
        await session.flush()
        raise HTTPException(status_code=410, detail="Сессия привязки истекла — начните снова")
    if row.status == "done":
        return row

    owner = await session.get(User, row.link_owner_user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Владелец аккаунта не найден")
    await link_telegram_to_owner(
        session,
        owner,
        telegram_id=telegram_id,
        telegram_username=telegram_username,
    )
    row.status = "done"
    row.telegram_id = int(telegram_id)
    row.completed_at = _now()
    await session.flush()
    return row


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
    if row.link_owner_user_id:
        return await complete_mobile_link_session(
            session,
            session_id=session_id,
            telegram_id=telegram_id,
            telegram_username=telegram_username,
        )
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
