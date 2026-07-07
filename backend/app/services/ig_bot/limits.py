"""Дневные лимиты IG-бота и проверка подписки на канал."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import IgBotUser

log = logging.getLogger(__name__)

_CHANNEL_SUBSCRIBED_STATUSES = frozenset({"creator", "administrator", "member"})


class IgBotDailyLimitExceeded(Exception):
    def __init__(self, *, used: int, limit: int, subscribed: bool) -> None:
        self.used = used
        self.limit = limit
        self.subscribed = subscribed
        super().__init__(f"daily limit exceeded: {used}/{limit}")


@dataclass(frozen=True)
class IgBotUsageStatus:
    used: int
    limit: int
    remaining: int
    subscribed: bool
    channel_url: str
    channel_label: str


def _utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def channel_public_url() -> str:
    raw = (settings.ig_bot_subscribe_channel or "").strip()
    if raw.startswith("@"):
        return f"https://t.me/{raw.lstrip('@')}"
    if raw.startswith("-100"):
        return settings.ig_bot_subscribe_channel_url.strip() or "https://t.me/ModelMate_app"
    if raw.startswith("http"):
        return raw
    return "https://t.me/ModelMate_app"


def channel_display_label() -> str:
    raw = (settings.ig_bot_subscribe_channel or "").strip()
    if raw.startswith("@"):
        return raw
    return settings.ig_bot_subscribe_channel_label.strip() or "@ModelMate_app"


def _daily_limit_for_subscriber(subscribed: bool) -> int:
    if subscribed:
        return int(settings.ig_bot_daily_limit_subscribed)
    return int(settings.ig_bot_daily_limit_default)


def _normalize_used(user: IgBotUser) -> int:
    today = _utc_today()
    if (user.daily_process_day or "") != today:
        return 0
    return max(0, int(user.daily_process_count or 0))


async def is_channel_subscriber(bot: Bot, telegram_user_id: int) -> bool:
    channel = (settings.ig_bot_subscribe_channel or "").strip()
    if not channel:
        return False
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=telegram_user_id)
    except TelegramBadRequest as e:
        log.warning(
            "ig bot channel check failed user=%s channel=%s: %s",
            telegram_user_id,
            channel,
            e,
        )
        return False
    except Exception:
        log.warning("ig bot channel check error user=%s", telegram_user_id, exc_info=True)
        return False

    status = str(getattr(member, "status", "") or "")
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return status in _CHANNEL_SUBSCRIBED_STATUSES


async def get_usage_status(
    session: AsyncSession,
    user: IgBotUser,
    bot: Bot,
) -> IgBotUsageStatus:
    from sqlalchemy import select

    if session is not None and user.id is not None:
        fresh = await session.scalar(select(IgBotUser).where(IgBotUser.id == user.id))
        if fresh is not None:
            user = fresh
    subscribed = await is_channel_subscriber(bot, user.telegram_id)
    limit = _daily_limit_for_subscriber(subscribed)
    used = _normalize_used(user)
    remaining = max(0, limit - used)
    return IgBotUsageStatus(
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


def format_usage_message(status: IgBotUsageStatus) -> str:
    sub_line = (
        f"✅ Подписка на {html.escape(status.channel_label, quote=False)} — "
        f"лимит <b>{status.limit}</b> видео/сутки."
        if status.subscribed
        else (
            f"Подпишитесь на {_html_channel_link(status.channel_label, status.channel_url)} — "
            f"<b>{settings.ig_bot_daily_limit_subscribed}</b> видео/сутки "
            f"(сейчас <b>{settings.ig_bot_daily_limit_default}</b>)."
        )
    )
    return (
        "<b>Лимит скачиваний (UTC, сброс в полночь)</b>\n\n"
        f"Сегодня: <b>{status.used}</b> / <b>{status.limit}</b> "
        f"(осталось <b>{status.remaining}</b>)\n\n"
        f"{sub_line}\n\n"
        "Считается каждое успешно отправленное видео."
    )


def format_limit_exceeded_message(status: IgBotUsageStatus) -> str:
    if status.subscribed:
        return (
            f"Дневной лимит исчерпан: <b>{status.used}</b> / <b>{status.limit}</b>.\n\n"
            "Новые скачивания — завтра (UTC)."
        )
    return (
        f"Дневной лимит исчерпан: <b>{status.used}</b> / <b>{status.limit}</b>.\n\n"
        f"Подпишитесь на {_html_channel_link(status.channel_label, status.channel_url)} — "
        f"получите <b>{settings.ig_bot_daily_limit_subscribed}</b> видео в сутки.\n\n"
        "После подписки нажмите «Проверить подписку»."
    )


async def ensure_can_download(
    session: AsyncSession,
    user: IgBotUser,
    bot: Bot,
) -> IgBotUsageStatus:
    status = await get_usage_status(session, user, bot)
    if status.remaining <= 0:
        log.info(
            "ig bot daily limit blocked user=%s used=%s limit=%s subscribed=%s",
            user.telegram_id,
            status.used,
            status.limit,
            status.subscribed,
        )
        raise IgBotDailyLimitExceeded(
            used=status.used,
            limit=status.limit,
            subscribed=status.subscribed,
        )
    return status


async def record_successful_download(session: AsyncSession, *, user_id: int) -> int:
    from sqlalchemy import select

    user = await session.scalar(
        select(IgBotUser).where(IgBotUser.id == user_id).with_for_update()
    )
    if user is None:
        raise ValueError("Пользователь IG-бота не найден.")
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
        "ig bot daily use user=%s daily=%s total=%s day=%s",
        user.telegram_id,
        user.daily_process_count,
        user.total_process_count,
        user.daily_process_day,
    )
    return int(user.daily_process_count)
