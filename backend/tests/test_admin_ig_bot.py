"""Тесты админ-аналитики IG-бота."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.admin_ig_bot import _display_name, _row_from_user


def test_display_name_prefers_first_name():
    u = SimpleNamespace(
        first_name="Anna",
        last_name="K",
        username="annak",
        telegram_id=123,
    )
    assert _display_name(u) == "Anna K"


def test_row_from_user_daily_count_only_for_today():
    from app.services.ig_bot.limits import _utc_today

    u = SimpleNamespace(
        id=1,
        telegram_id=555,
        username="x",
        first_name="X",
        last_name=None,
        language_code="ru",
        daily_process_count=3,
        daily_process_day=_utc_today(),
        total_process_count=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    row = _row_from_user(u)
    assert row.daily_process_count == 3
    assert row.total_process_count == 3

    u.daily_process_day = "2020-01-01"
    row_old = _row_from_user(u)
    assert row_old.daily_process_count == 0
    assert row_old.total_process_count == 1
