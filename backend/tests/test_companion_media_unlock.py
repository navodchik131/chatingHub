"""Тесты автоunlock paid-медиа после доната."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.companion_bot.media_planner import MediaPlan
from app.services.companion_bot.media_unlock import (
    build_unlock_thank_you_text,
    donation_amount_usd_cents,
)


def test_donation_amount_usd_cents() -> None:
    ev = SimpleNamespace(currency="USD", amount_minor=450)
    assert donation_amount_usd_cents(ev) == 450

    ev_eur = SimpleNamespace(currency="EUR", amount_minor=450)
    assert donation_amount_usd_cents(ev_eur) == 0


def test_build_unlock_thank_you_text_ru_en() -> None:
    assert build_unlock_thank_you_text(lang="ru")
    assert build_unlock_thank_you_text(lang="en")


def test_media_plan_from_pending_offer_shape() -> None:
    plan = MediaPlan(
        action="send_paid_unlocked",
        asset_ids=[10, 11],
        price_usd_cents=450,
        reason="donation_unlock_pending_offer",
    )
    d = plan.to_dict()
    assert d["action"] == "send_paid_unlocked"
    assert d["asset_ids"] == [10, 11]
