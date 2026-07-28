"""Контакты login-бота и backfill из users / auth-сессий."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram.types import User as TgUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TelegramLoginBotContact, TelegramMobileAuthSession, User


async def upsert_login_bot_contact(
    session: AsyncSession,
    tg_user: TgUser,
) -> None:
    now = datetime.now(timezone.utc)
    telegram_id = int(tg_user.id)
    username = (tg_user.username or "").strip() or None
    first_name = (tg_user.first_name or "").strip() or None
    last_name = (tg_user.last_name or "").strip() or None
    language_code = (tg_user.language_code or "").strip() or None

    existing = (
        await session.execute(
            select(TelegramLoginBotContact).where(
                TelegramLoginBotContact.telegram_id == telegram_id
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        session.add(
            TelegramLoginBotContact(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                blocked=False,
                start_count=1,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        return

    existing.username = username
    existing.first_name = first_name
    existing.last_name = last_name
    existing.language_code = language_code
    existing.last_seen_at = now
    existing.start_count = (existing.start_count or 0) + 1
    if existing.blocked:
        existing.blocked = False


async def backfill_login_bot_contacts(session: AsyncSession) -> int:
    """Добавить telegram_id из users и завершённых auth-сессий (идемпотентно)."""
    now = datetime.now(timezone.utc)
    added = 0

    user_rows = (
        await session.execute(
            select(User.telegram_id, User.telegram_username).where(User.telegram_id.is_not(None))
        )
    ).all()
    session_rows = (
        await session.execute(
            select(TelegramMobileAuthSession.telegram_id).where(
                TelegramMobileAuthSession.telegram_id.is_not(None)
            )
        )
    ).all()

    seen: set[int] = set()
    candidates: list[tuple[int, str | None]] = []
    for tg_id, tg_username in user_rows:
        if tg_id is None:
            continue
        tid = int(tg_id)
        if tid in seen:
            continue
        seen.add(tid)
        candidates.append((tid, (tg_username or "").strip() or None))

    for (tg_id,) in session_rows:
        if tg_id is None:
            continue
        tid = int(tg_id)
        if tid in seen:
            continue
        seen.add(tid)
        candidates.append((tid, None))

    if not candidates:
        return 0

    existing_ids = set(
        (
            await session.execute(select(TelegramLoginBotContact.telegram_id))
        )
        .scalars()
        .all()
    )

    for telegram_id, username in candidates:
        if telegram_id in existing_ids:
            continue
        session.add(
            TelegramLoginBotContact(
                telegram_id=telegram_id,
                username=username,
                blocked=False,
                start_count=0,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        added += 1

    if added:
        await session.flush()
    return added


async def build_login_bot_admin_stats(session: AsyncSession) -> dict:
    await backfill_login_bot_contacts(session)

    now = datetime.now(timezone.utc)
    day7 = now - timedelta(days=7)
    day30 = now - timedelta(days=30)

    total = int(
        await session.scalar(select(func.count()).select_from(TelegramLoginBotContact)) or 0
    )
    blocked = int(
        await session.scalar(
            select(func.count())
            .select_from(TelegramLoginBotContact)
            .where(TelegramLoginBotContact.blocked.is_(True))
        )
        or 0
    )
    active_7d = int(
        await session.scalar(
            select(func.count())
            .select_from(TelegramLoginBotContact)
            .where(
                TelegramLoginBotContact.blocked.is_(False),
                TelegramLoginBotContact.last_seen_at >= day7,
            )
        )
        or 0
    )
    active_30d = int(
        await session.scalar(
            select(func.count())
            .select_from(TelegramLoginBotContact)
            .where(
                TelegramLoginBotContact.blocked.is_(False),
                TelegramLoginBotContact.last_seen_at >= day30,
            )
        )
        or 0
    )

    return {
        "total_contacts": total,
        "reachable_contacts": max(total - blocked, 0),
        "blocked_contacts": blocked,
        "active_contacts_7d": active_7d,
        "active_contacts_30d": active_30d,
    }


async def list_reachable_login_bot_contact_ids(session: AsyncSession) -> list[int]:
    rows = (
        await session.execute(
            select(TelegramLoginBotContact.telegram_id).where(
                TelegramLoginBotContact.blocked.is_(False)
            )
        )
    ).scalars().all()
    return [int(r) for r in rows]
