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


def test_resolve_cookies_path_relative(tmp_path, monkeypatch):
    from app.services.ig_bot import download as ig_download

    cookies = tmp_path / "ig-bot" / "cookies.txt"
    cookies.parent.mkdir(parents=True)
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")

    monkeypatch.setattr(ig_download, "APP_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services.ig_bot.download.settings.ig_bot_cookies_path",
        "ig-bot/cookies.txt",
    )

    resolved = ig_download.resolve_cookies_path()
    assert resolved is not None
    assert resolved.is_file()


def test_resolve_cookies_path_missing(tmp_path, monkeypatch):
    from app.services.ig_bot import download as ig_download

    monkeypatch.setattr(ig_download, "APP_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services.ig_bot.download.settings.ig_bot_cookies_path",
        "ig-bot/cookies.txt",
    )

    assert ig_download.resolve_cookies_path() is None


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


def test_ig_bot_reply_menu_buttons():
    from app.connectors.telegram.ig_bot.keyboards import MENU_BUTTONS, reply_menu_kb

    kb = reply_menu_kb()
    labels = {btn.text for row in kb.keyboard for btn in row}
    assert MENU_BUTTONS.issubset(labels)
    assert kb.input_field_placeholder


def test_record_successful_download_increments():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from app.services.ig_bot.limits import _utc_today, record_successful_download

    user = SimpleNamespace(
        id=42,
        telegram_id=1,
        daily_process_day=None,
        daily_process_count=0,
        total_process_count=0,
    )
    session = AsyncMock()

    async def _scalar(stmt):
        return user

    session.scalar = AsyncMock(side_effect=_scalar)
    session.add = MagicMock()
    session.flush = AsyncMock()
    used = asyncio.run(record_successful_download(session, user_id=42))
    assert used == 1
    assert user.daily_process_day == _utc_today()
    assert user.daily_process_count == 1
    assert user.total_process_count == 1
