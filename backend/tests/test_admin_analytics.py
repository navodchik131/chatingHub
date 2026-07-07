"""Агрегаты админ-панели: вспомогательные функции."""

from __future__ import annotations

from app.services.admin_analytics import _pct
from app.services.admin_segments import SEGMENT_TITLES, VALID_ADMIN_SEGMENTS


def test_pct_rounds() -> None:
    assert _pct(3, 10) == 30.0
    assert _pct(1, 3) == 33.3


def test_pct_zero_total() -> None:
    assert _pct(5, 0) == 0.0


def test_valid_segments_match_titles() -> None:
    assert VALID_ADMIN_SEGMENTS == frozenset(SEGMENT_TITLES.keys())
    assert "yookassa_payments" in VALID_ADMIN_SEGMENTS
    assert "zombie" in VALID_ADMIN_SEGMENTS


def test_segment_titles_non_empty() -> None:
    from app.services.admin_segments import SEGMENT_TITLES

    for key, title in SEGMENT_TITLES.items():
        assert key
        assert title.strip()
