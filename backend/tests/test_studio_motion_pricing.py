import math
from unittest.mock import patch

from app.config import settings
from app.services.studio_motion_pricing import (
    motion_video_credit_cost,
    motion_video_duration_seconds,
    motion_video_usd_per_sec,
    motion_video_usd_total,
)


def _patch_motion_pricing_defaults():
    return patch.multiple(
        settings,
        studio_motion_usd_per_sec_with_ref=0.13,
        studio_motion_usd_per_sec_no_ref=0.24,
        studio_motion_mini_usd_per_sec_with_ref=0.0975,
        studio_motion_mini_usd_per_sec_no_ref=0.15,
        studio_motion_seedance_25_usd_per_sec_with_ref=0.22,
        studio_motion_seedance_25_usd_per_sec_no_ref=0.36,
        studio_motion_rub_per_usd=80.0,
        studio_motion_rub_per_credit=3.6,
    )


def test_duration_clamp_api_minimum_four_seconds() -> None:
    assert motion_video_duration_seconds(1) == 4
    assert motion_video_duration_seconds(3) == 4
    assert motion_video_duration_seconds(4) == 4
    assert motion_video_duration_seconds(99) == 15


def test_usd_total_with_ref_bills_ref_plus_output() -> None:
    with _patch_motion_pricing_defaults():
        # 720p standard + ref: 5s ref + 5s output × $0.13 = $1.30
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


def test_resolution_scales_usd_per_sec() -> None:
    with _patch_motion_pricing_defaults():
        assert motion_video_usd_per_sec(
            variant="standard",
            resolution="480p",
            has_motion_reference_video=False,
        ) == 0.12
        assert motion_video_usd_per_sec(
            variant="standard",
            resolution="1080p",
            has_motion_reference_video=False,
        ) == 0.6


def test_five_seconds_standard_motion_control_credits() -> None:
    with _patch_motion_pricing_defaults():
        # ref≈output: 10 × 0.13 = 1.30 USD → 29 cr
        assert motion_video_credit_cost(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
            reference_video_duration=5,
        ) == 29
        # без ref: 5 × 0.24 = 1.20 USD → 27 cr
        assert motion_video_credit_cost(
            5,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=False,
        ) == 27


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
        # 10 × 0.22 = 2.20 USD → 49 cr
        assert v25 == 49


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


def test_matches_settings_formula_without_ref() -> None:
    for dur in (4, 10, 15):
        usd = settings.studio_motion_usd_per_sec_no_ref * dur
        expected = max(
            1,
            math.ceil(
                usd * settings.studio_motion_rub_per_usd / settings.studio_motion_rub_per_credit
            ),
        )
        assert (
            motion_video_credit_cost(
                dur,
                variant="standard",
                resolution="720p",
                has_motion_reference_video=False,
            )
            == expected
        )


def test_grok_imagine_i2v_credit_cost():
    from app.services.studio_motion_pricing import grok_imagine_i2v_credit_cost

    # 6s @ 720p: 0.14*6 + 0.01 = 0.85 USD
    expected = max(
        1,
        math.ceil(
            0.85 * settings.studio_motion_rub_per_usd / settings.studio_motion_rub_per_credit
        ),
    )
    assert grok_imagine_i2v_credit_cost(6, resolution="720p") == expected
    assert grok_imagine_i2v_credit_cost(1, resolution="480p") >= 1
