"""Дневные лимиты EXIF-бота и проверка подписки на канал."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ExifBotUser

log = logging.getLogger(__name__)

_CHANNEL_SUBSCRIBED_STATUSES = frozenset({"creator", "administrator", "member"})


class ExifBotDailyLimitExceeded(Exception):
    def __init__(self, *, used: int, limit: int, subscribed: bool) -> None:
        self.used = used
        self.limit = limit
        self.subscribed = subscribed
        super().__init__(f"daily limit exceeded: {used}/{limit}")


@dataclass(frozen=True)
class ExifBotUsageStatus:
    used: int
    limit: int
    remaining: int
    subscribed: bool
    channel_url: str
    channel_label: str


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def channel_public_url() -> str:
    raw = (settings.exif_bot_subscribe_channel or "").strip()
    if raw.startswith("@"):
        return f"https://t.me/{raw.lstrip('@')}"
    if raw.startswith("-100"):
        return settings.exif_bot_subscribe_channel_url.strip() or "https://t.me/ModelMate_app"
    if raw.startswith("http"):
        return raw
    return "https://t.me/ModelMate_app"


def channel_display_label() -> str:
    raw = (settings.exif_bot_subscribe_channel or "").strip()
    if raw.startswith("@"):
        return raw
    return settings.exif_bot_subscribe_channel_label.strip() or "@ModelMate_app"


def _daily_limit_for_subscriber(subscribed: bool) -> int:
    if subscribed:
        return int(settings.exif_bot_daily_limit_subscribed)
    return int(settings.exif_bot_daily_limit_default)


def _normalize_used(user: ExifBotUser) -> int:
    today = _utc_today()
    if (user.daily_process_day or "") != today:
        return 0
    return max(0, int(user.daily_process_count or 0))


def effective_total_process_count(user: ExifBotUser) -> int:
    """Lifetime counter; не меньше сегодняшнего (на случай рассинхрона до backfill)."""
    total = max(0, int(user.total_process_count or 0))
    return max(total, _normalize_used(user))


async def is_channel_subscriber(bot: Bot, telegram_user_id: int) -> bool:
    """Проверка подписки через getChatMember (бот должен быть админом канала)."""
    channel = (settings.exif_bot_subscribe_channel or "").strip()
    if not channel:
        return False
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=telegram_user_id)
    except TelegramBadRequest as e:
        log.warning(
            "exif bot channel check failed user=%s channel=%s: %s",
            telegram_user_id,
            channel,
            e,
        )
        return False
    except Exception:
        log.warning("exif bot channel check error user=%s", telegram_user_id, exc_info=True)
        return False

    status = str(getattr(member, "status", "") or "")
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return status in _CHANNEL_SUBSCRIBED_STATUSES


async def get_usage_status(
    session: AsyncSession,
    user: ExifBotUser,
    bot: Bot,
) -> ExifBotUsageStatus:
    subscribed = await is_channel_subscriber(bot, user.telegram_id)
    limit = _daily_limit_for_subscriber(subscribed)
    used = _normalize_used(user)
    remaining = max(0, limit - used)
    return ExifBotUsageStatus(
        used=used,
        limit=limit,
        remaining=remaining,
        subscribed=subscribed,
        channel_url=channel_public_url(),
        channel_label=channel_display_label(),
    )


def _html_channel_link(label: str, url: str) -> str:
    safe_label = html.escape(label, quote=False)
    safe_url = html.escape(url, quote=True)
    return f'<a href="{safe_url}">{safe_label}</a>'


def format_usage_message(status: ExifBotUsageStatus) -> str:
    """HTML для parse_mode=HTML (@ModelMate_app ломает legacy Markdown из‑за _)."""
    sub_line = (
        f"✅ Подписка на {html.escape(status.channel_label, quote=False)} — "
        f"лимит <b>{status.limit}</b> фото/сутки."
        if status.subscribed
        else (
            f"Подпишитесь на {_html_channel_link(status.channel_label, status.channel_url)} — "
            f"<b>{settings.exif_bot_daily_limit_subscribed}</b> фото/сутки "
            f"(сейчас <b>{settings.exif_bot_daily_limit_default}</b>)."
        )
    )
    return (
        "<b>Лимит обработок (UTC, сброс в полночь)</b>\n\n"
        f"Сегодня: <b>{status.used}</b> / <b>{status.limit}</b> "
        f"(осталось <b>{status.remaining}</b>)\n\n"
        f"{sub_line}\n\n"
        "Считается каждая успешная обработка фото."
    )


def format_limit_exceeded_message(status: ExifBotUsageStatus) -> str:
    if status.subscribed:
        return (
            f"Дневной лимит исчерпан: <b>{status.used}</b> / <b>{status.limit}</b>.\n\n"
            "Новые обработки — завтра (UTC)."
        )
    return (
        f"Дневной лимит исчерпан: <b>{status.used}</b> / <b>{status.limit}</b>.\n\n"
        f"Подпишитесь на {_html_channel_link(status.channel_label, status.channel_url)} — "
        f"получите <b>{settings.exif_bot_daily_limit_subscribed}</b> фото в сутки.\n\n"
        "После подписки нажмите «Проверить подписку»."
    )


async def ensure_can_process(
    session: AsyncSession,
    user: ExifBotUser,
    bot: Bot,
) -> ExifBotUsageStatus:
    status = await get_usage_status(session, user, bot)
    if status.remaining <= 0:
        log.info(
            "exif bot daily limit blocked user=%s used=%s limit=%s subscribed=%s",
            user.telegram_id,
            status.used,
            status.limit,
            status.subscribed,
        )
        raise ExifBotDailyLimitExceeded(
            used=status.used,
            limit=status.limit,
            subscribed=status.subscribed,
        )
    return status


async def record_successful_process(session: AsyncSession, *, user_id: int) -> int:
    """Увеличивает счётчик после успешной обработки. Возвращает новое значение used."""
    from sqlalchemy import select

    user = await session.scalar(
        select(ExifBotUser).where(ExifBotUser.id == user_id).with_for_update()
    )
    if user is None:
        raise ValueError("Пользователь EXIF-бота не найден.")
    today = _utc_today()
    if (user.daily_process_day or "") != today:
        user.daily_process_day = today
        user.daily_process_count = 0
    user.daily_process_count = int(user.daily_process_count or 0) + 1
    user.total_process_count = int(user.total_process_count or 0) + 1
    if user.total_process_count < user.daily_process_count:
        user.total_process_count = user.daily_process_count
    session.add(user)
    await session.flush()
    log.info(
        "exif bot daily use user=%s daily=%s total=%s day=%s",
        user.telegram_id,
        user.daily_process_count,
        user.total_process_count,
        user.daily_process_day,
    )
    return int(user.daily_process_count)
