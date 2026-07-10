"""Telegram-идентичность владельца workspace и вспомогательные проверки."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.db.models import User
from app.services.auth_provision import provision_workspace_owner

_TELEGRAM_EMAIL_RE = re.compile(r"^tg(\d+)@telegram\.local$")


def synthetic_telegram_email(telegram_id: int) -> str:
    return f"tg{int(telegram_id)}@telegram.local"


def parse_synthetic_telegram_id(email: str) -> int | None:
    m = _TELEGRAM_EMAIL_RE.match((email or "").strip().lower())
    if not m:
        return None
    return int(m.group(1))


def is_real_owner_email(email: str) -> bool:
    return parse_synthetic_telegram_id(email) is None and not (email or "").endswith(
        "@workspace.local"
    )


def owner_email_setup_required(user: User) -> bool:
    if user.parent_user_id is not None:
        return False
    if not user.auth_email_verified:
        return True
    return not is_real_owner_email(user.email)


def owner_telegram_linked(user: User) -> bool:
    return user.parent_user_id is None and user.telegram_id is not None


async def find_owner_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(
        select(User).where(
            User.telegram_id == int(telegram_id),
            User.parent_user_id.is_(None),
        )
    )


async def assert_telegram_id_available(
    session: AsyncSession,
    telegram_id: int,
    *,
    except_user_id: int | None = None,
) -> None:
    existing = await find_owner_by_telegram_id(session, telegram_id)
    if existing and existing.id != except_user_id:
        raise HTTPException(
            status_code=409,
            detail="Этот Telegram уже привязан к другому аккаунту ModelMate",
        )


async def link_telegram_to_owner(
    session: AsyncSession,
    owner: User,
    *,
    telegram_id: int,
    telegram_username: str | None,
) -> None:
    if owner.parent_user_id is not None:
        raise HTTPException(status_code=403, detail="Привязка Telegram только для владельца")
    await assert_telegram_id_available(session, telegram_id, except_user_id=owner.id)
    owner.telegram_id = int(telegram_id)
    owner.telegram_username = (telegram_username or "").strip().lstrip("@")[:64] or None
    owner.telegram_linked_at = datetime.now(timezone.utc)


async def create_owner_from_telegram(
    session: AsyncSession,
    *,
    telegram_id: int,
    telegram_username: str | None,
    referral_code: str | None = None,
) -> User:
    await assert_telegram_id_available(session, telegram_id)
    email = synthetic_telegram_email(telegram_id)
    random_password = secrets.token_urlsafe(32)
    user = await provision_workspace_owner(
        session,
        email=email,
        hashed_password=hash_password(random_password),
        auth_email_verified=False,
        referral_code=referral_code,
    )
    await link_telegram_to_owner(
        session,
        user,
        telegram_id=telegram_id,
        telegram_username=telegram_username,
    )
    return user


async def complete_owner_email(
    session: AsyncSession,
    owner: User,
    *,
    email: str,
    password: str,
) -> User:
    if owner.parent_user_id is not None:
        raise HTTPException(status_code=403, detail="Только владелец может задать email")
    normalized = email.lower().strip()
    if not is_real_owner_email(normalized):
        raise HTTPException(status_code=400, detail="Укажите рабочий email")
    dup = await session.scalar(
        select(User.id).where(User.email == normalized, User.id != owner.id)
    )
    if dup:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    owner.email = normalized
    owner.hashed_password = hash_password(password)
    owner.auth_email_verified = True
    return owner
