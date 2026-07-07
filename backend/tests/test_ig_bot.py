"""Тесты Instagram download-бота."""

from __future__ import annotations

import pytest

from app.services.ig_bot.urls import (
    extract_instagram_url,
    is_single_media_url,
    validate_instagram_media_url,
)


def test_extract_instagram_reel_url():
    url = extract_instagram_url("смотри https://www.instagram.com/reel/ABC123_xyz/")
    assert url == "https://www.instagram.com/reel/ABC123_xyz/"


def test_extract_instagram_post_url():
    url = extract_instagram_url("https://instagram.com/p/XYZ789/")
    assert url == "https://instagram.com/p/XYZ789/"


def test_extract_rejects_profile():
    assert extract_instagram_url("https://www.instagram.com/someuser/") is None


def test_validate_single_media():
    validate_instagram_media_url("https://www.instagram.com/reel/AbC/")
    assert is_single_media_url("https://www.instagram.com/reels/xY_z/")
    with pytest.raises(ValueError, match="Поддерживаются"):
        validate_instagram_media_url("https://www.instagram.com/user/")


def test_ig_bot_daily_limit():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from app.config import settings
    from app.db.models import IgBotUser
    from app.services.ig_bot.limits import (
        IgBotDailyLimitExceeded,
        _utc_today,
        ensure_can_download,
    )

    class FakeBot:
        pass

    user = IgBotUser(
        id=1,
        telegram_id=999,
        daily_process_count=settings.ig_bot_daily_limit_default,
        daily_process_day=_utc_today(),
    )

    async def _run():
        with patch(
            "app.services.ig_bot.limits.is_channel_subscriber",
            new=AsyncMock(return_value=False),
        ):
            with pytest.raises(IgBotDailyLimitExceeded):
                await ensure_can_download(None, user, FakeBot())  # type: ignore[arg-type]

    asyncio.run(_run())
