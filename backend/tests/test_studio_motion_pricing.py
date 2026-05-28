import math
from unittest.mock import patch

from app.config import settings
from app.services.studio_motion_pricing import motion_video_credit_cost


def _patch_motion_pricing_defaults():
    return patch.multiple(
        settings,
        studio_motion_usd_per_sec_with_ref=0.5,
        studio_motion_usd_per_sec_no_ref=0.25,
        studio_motion_rub_per_usd=80.0,
        studio_motion_rub_per_credit=3.6,
    )


def test_one_second_rate_defaults() -> None:
    from app.services.studio_motion_pricing import _motion_video_credit_cost_raw

    with _patch_motion_pricing_defaults():
        # $0.50 × 80 / 3.6 ≈ 11.11 → 12 (тариф за 1 с; ролик мин. 4 с → 48 кр.)
        assert _motion_video_credit_cost_raw(1, has_motion_reference_video=True) == 12
        assert _motion_video_credit_cost_raw(1, has_motion_reference_video=False) == 6


def test_billing_uses_api_duration_minimum() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_credit_cost(1, has_motion_reference_video=True) == 45


def test_five_seconds_scales_with_duration() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_credit_cost(5, has_motion_reference_video=True) == 56
        assert motion_video_credit_cost(5, has_motion_reference_video=False) == 28


def test_matches_settings_formula() -> None:
    for dur in (4, 10, 15):
        for ref in (True, False):
            usd = (
                settings.studio_motion_usd_per_sec_with_ref
                if ref
                else settings.studio_motion_usd_per_sec_no_ref
            )
            expected = max(
                1,
                math.ceil(
                    usd * dur * settings.studio_motion_rub_per_usd / settings.studio_motion_rub_per_credit
                ),
            )
            assert motion_video_credit_cost(dur, has_motion_reference_video=ref) == expected
