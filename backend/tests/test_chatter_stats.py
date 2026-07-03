"""Tests for chatter KPI aggregation."""

from __future__ import annotations

from datetime import date

from app.db.models import User
from app.services.chatter_stats import _period_bounds


def test_period_bounds() -> None:
    start, end = _period_bounds(date(2026, 7, 1), date(2026, 7, 2))
    assert start.year == 2026 and start.month == 7 and start.day == 1
    assert end.day == 2


def test_member_login_on_user() -> None:
    actor = User(id=1, parent_user_id=2, member_login="op1")
    assert actor.member_login == "op1"
