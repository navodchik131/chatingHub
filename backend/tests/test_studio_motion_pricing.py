import math
from contextlib import ExitStack
from unittest.mock import patch

from app.config import settings
from app.services.studio_motion_pricing import (
    motion_video_credit_cost,
    motion_video_duration_seconds,
    motion_video_usd_per_sec,
    motion_video_usd_total,
)


def _patch_motion_pricing_defaults():
    stack = ExitStack()
    stack.enter_context(
        patch.multiple(
            settings,
            studio_motion_usd_per_sec_with_ref=0.13,
            studio_motion_usd_per_sec_no_ref=0.24,
            studio_motion_mini_usd_per_sec_with_ref=0.0975,
            studio_motion_mini_usd_per_sec_no_ref=0.15,
            studio_motion_seedance_25_usd_per_sec_with_ref=0.22,
            studio_motion_seedance_25_usd_per_sec_no_ref=0.36,
        )
    )
    stack.enter_context(
        patch(
            "app.services.studio_provider_pricing.refresh_provider_pricing",
            side_effect=lambda force=False: None,
        )
    )
    stack.enter_context(
        patch(
            "app.services.studio_motion_pricing.video_wavespeed_usd_per_sec_720p",
            side_effect=lambda variant="standard", has_ref=False: {
                ("standard", True): 0.13,
                ("standard", False): 0.24,
                ("mini", True): 0.0975,
                ("mini", False): 0.15,
                ("seedance_25", True): 0.22,
                ("seedance_25", False): 0.36,
            }[(variant if variant in ("mini", "seedance_25") else "standard", has_ref)],
        )
    )
    return stack


def test_duration_clamp_api_minimum_four_seconds() -> None:
    assert motion_video_duration_seconds(1) == 4
    assert motion_video_duration_seconds(3) == 4
    assert motion_video_duration_seconds(4) == 4
    assert motion_video_duration_seconds(99) == 15


def test_usd_total_with_ref_bills_ref_plus_output() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_usd_total(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
            reference_video_duration=5,
        ) == 1.3
        assert motion_video_usd_total(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=False,
        ) == 1.2


def test_five_seconds_standard_motion_control_credits() -> None:
    with _patch_motion_pricing_defaults():
        # 10 × 0.13 = 1.30 USD → 130 cent-credits
        assert motion_video_credit_cost(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
            reference_video_duration=5,
        ) == 130
        assert motion_video_credit_cost(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=False,
        ) == 120


def test_seedance_25_more_expensive_than_20_with_ref() -> None:
    with _patch_motion_pricing_defaults():
        v20 = motion_video_credit_cost(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
            reference_video_duration=5,
        )
        v25 = motion_video_credit_cost(
            5,
            variant="seedance_25",
            resolution="720p",
            has_motion_reference_video=True,
            reference_video_duration=5,
        )
        assert v25 > v20
        assert v25 == 221


def test_motion_ref_unknown_duration_bills_output_only() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_usd_total(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
            reference_video_duration=None,
        ) == 0.65


def test_motion_ref_shorter_than_output_uses_actual_ref() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_usd_total(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
            reference_video_duration=3,
        ) == 1.04


def test_matches_usd_cent_formula_without_ref() -> None:
    with _patch_motion_pricing_defaults():
        for dur in (4, 10, 15):
            usd = 0.24 * dur
            expected = max(1, int(math.ceil(usd * 100)))
            assert (
                motion_video_credit_cost(
                    dur,
                    variant="standard",
                    resolution="720p",
                    has_motion_reference_video=False,
                )
                == expected
            )
