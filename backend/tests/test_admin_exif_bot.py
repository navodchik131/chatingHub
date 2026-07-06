"""Тесты админ-аналитики EXIF-бота."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.admin_exif_bot import _display_name, _row_from_user


def test_display_name_prefers_first_name():
    u = SimpleNamespace(
        first_name="Anna",
        last_name="K",
        username="annak",
        telegram_id=123,
    )
    assert _display_name(u) == "Anna K"


def test_display_name_falls_back_to_username():
    u = SimpleNamespace(
        first_name=None,
        last_name=None,
        username="botuser",
        telegram_id=999,
    )
    assert _display_name(u) == "@botuser"


def test_row_from_user_daily_count_only_for_today():
    from app.services.exif_bot.limits import _utc_today

    u = SimpleNamespace(
        id=1,
        telegram_id=555,
        username="x",
        first_name="X",
        last_name=None,
        language_code="ru",
        daily_process_count=7,
        daily_process_day=_utc_today(),
        total_process_count=42,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    row = _row_from_user(u, profiles_count=2)
    assert row.daily_process_count == 7
    assert row.total_process_count == 42
    assert row.profiles_count == 2

    u.daily_process_day = "2020-01-01"
    row_old = _row_from_user(u, profiles_count=2)
    assert row_old.daily_process_count == 0
