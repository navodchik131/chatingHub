import math
from unittest.mock import patch

from app.config import settings
from app.services.studio_motion_pricing import (
    motion_video_credit_cost,
    motion_video_duration_seconds,
    motion_video_usd_per_sec,
)


def _patch_motion_pricing_defaults():
    return patch.multiple(
        settings,
        studio_motion_usd_per_sec_with_ref=0.5,
        studio_motion_usd_per_sec_no_ref=0.25,
        studio_motion_mini_usd_per_sec_with_ref=0.0975,
        studio_motion_mini_usd_per_sec_no_ref=0.15,
        studio_motion_rub_per_usd=80.0,
        studio_motion_rub_per_credit=3.6,
    )


def test_duration_clamp_api_minimum_four_seconds() -> None:
    assert motion_video_duration_seconds(1) == 4
    assert motion_video_duration_seconds(3) == 4
    assert motion_video_duration_seconds(4) == 4
    assert motion_video_duration_seconds(99) == 15


def test_one_second_rate_defaults() -> None:
    from app.services.studio_motion_pricing import _motion_video_credit_cost_raw

    with _patch_motion_pricing_defaults():
        # standard 720p: $0.50 × 80 / 3.6 ≈ 11.11 → 12 кр. за 1 с
        assert _motion_video_credit_cost_raw(
            1,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
        ) == 12
        assert _motion_video_credit_cost_raw(
            1,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=False,
        ) == 6
        # mini 720p: $0.15 × 80 / 3.6 ≈ 3.33 → 4 кр.
        assert _motion_video_credit_cost_raw(
            1,
            variant="mini",
            resolution="720p",
            has_motion_reference_video=False,
        ) == 4


def test_resolution_scales_usd_per_sec() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_usd_per_sec(
            variant="standard",
            resolution="480p",
            has_motion_reference_video=False,
        ) == 0.125
        assert motion_video_usd_per_sec(
            variant="standard",
            resolution="1080p",
            has_motion_reference_video=False,
        ) == 0.625


def test_billing_uses_api_duration_minimum() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_credit_cost(1, has_motion_reference_video=True) == 45


def test_five_seconds_scales_with_duration() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_credit_cost(5, has_motion_reference_video=True) == 56
        assert motion_video_credit_cost(5, has_motion_reference_video=False) == 28


def test_mini_cheaper_than_standard_at_same_resolution() -> None:
    with _patch_motion_pricing_defaults():
        std = motion_video_credit_cost(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=False,
        )
        mini = motion_video_credit_cost(
            5,
            variant="mini",
            resolution="720p",
            has_motion_reference_video=False,
        )
        assert mini < std


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
            assert (
                motion_video_credit_cost(
                    dur,
                    variant="standard",
                    resolution="720p",
                    has_motion_reference_video=ref,
                )
                == expected
            )
