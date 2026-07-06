"""Тесты лимитов EXIF-бота."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.exif_bot.limits import (
    ExifBotDailyLimitExceeded,
    _normalize_used,
    _utc_today,
    ensure_can_process,
    format_usage_message,
    is_channel_subscriber,
    record_successful_process,
)


def test_normalize_used_resets_on_new_day():
    user = SimpleNamespace(daily_process_day="2020-01-01", daily_process_count=9)
    assert _normalize_used(user) == 0


def test_normalize_used_same_day():
    user = SimpleNamespace(daily_process_day=_utc_today(), daily_process_count=3)
    assert _normalize_used(user) == 3


def test_is_channel_subscriber_member():
    bot = AsyncMock()
    bot.get_chat_member.return_value = SimpleNamespace(status="member")
    assert asyncio.run(is_channel_subscriber(bot, 123)) is True


def test_is_channel_subscriber_left():
    bot = AsyncMock()
    bot.get_chat_member.return_value = SimpleNamespace(status="left")
    assert asyncio.run(is_channel_subscriber(bot, 123)) is False


def test_ensure_can_process_raises_when_exhausted():
    from app.config import settings

    bot = AsyncMock()
    bot.get_chat_member.return_value = SimpleNamespace(status="left")
    user = SimpleNamespace(
        telegram_id=1,
        daily_process_day=_utc_today(),
        daily_process_count=settings.exif_bot_daily_limit_default,
    )
    session = AsyncMock()
    with pytest.raises(ExifBotDailyLimitExceeded):
        asyncio.run(ensure_can_process(session, user, bot))


def test_record_successful_process_increments():
    user = SimpleNamespace(
        id=42,
        telegram_id=1,
        daily_process_day=None,
        daily_process_count=0,
    )
    session = AsyncMock()

    async def _scalar(stmt):
        return user

    session.scalar = AsyncMock(side_effect=_scalar)
    session.add = MagicMock()
    session.flush = AsyncMock()
    used = asyncio.run(record_successful_process(session, user_id=42))
    assert used == 1
    assert user.daily_process_day == _utc_today()
    assert user.daily_process_count == 1


def test_list_iphone_presets_from_11():
    from app.services.studio_camera_presets import get_camera_preset_by_id, list_camera_presets

    iphones = list_camera_presets(iphone_only=True)
    assert len(iphones) >= 23
    assert get_camera_preset_by_id("iphone_11") is not None
    assert get_camera_preset_by_id("iphone_16_pro_max") is not None
    others = list_camera_presets(iphone_only=False)
    assert all(not p["id"].startswith("iphone_") for p in others)


def test_format_usage_message_contains_limits():
    from app.services.exif_bot.limits import ExifBotUsageStatus

    msg = format_usage_message(
        ExifBotUsageStatus(
            used=2,
            limit=10,
            remaining=8,
            subscribed=False,
            channel_url="https://t.me/ModelMate_app",
            channel_label="@ModelMate_app",
        )
    )
    assert "2" in msg and "10" in msg and "ModelMate" in msg
    assert "<a href=" in msg
    assert "@ModelMate_app" in msg
    assert "**" not in msg


def test_format_usage_message_subscribed_escapes_channel_label():
    from app.services.exif_bot.limits import ExifBotUsageStatus

    msg = format_usage_message(
        ExifBotUsageStatus(
            used=1,
            limit=50,
            remaining=49,
            subscribed=True,
            channel_url="https://t.me/ModelMate_app",
            channel_label="@ModelMate_app",
        )
    )
    assert "@ModelMate_app" in msg
    assert "<b>50</b>" in msg
    assert "**" not in msg
