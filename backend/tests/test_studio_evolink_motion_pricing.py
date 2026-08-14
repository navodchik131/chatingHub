from app.services.studio_evolink_motion_pricing import (
    evolink_quote_reference_image_count,
    evolink_video_credit_cost,
    evolink_video_usd_total,
)


class _Img:
    def __init__(self, kind: str):
        self.image_kind = kind


def test_evolink_prompt_only_quotes_one_image():
    imgs = [_Img("face"), _Img("turnaround")]
    n = evolink_quote_reference_image_count(
        prompt_only_mode=True,
        has_first_frame=True,
        has_motion_video=False,
        model_images=imgs,
    )
    assert n == 1


def test_evolink_prompt_only_4s_720p_output_pricing():
    usd = evolink_video_usd_total(
        4,
        variant="standard",
        resolution="720p",
        has_motion_reference_video=False,
    )
    assert abs(usd - 0.796) < 0.001
    assert evolink_video_credit_cost(
        4,
        variant="standard",
        resolution="720p",
        has_motion_reference_video=False,
    ) == 80


def test_evolink_motion_video_ref_bills_input_plus_output():
    usd = evolink_video_usd_total(
        4,
        variant="standard",
        resolution="720p",
        has_motion_reference_video=True,
        reference_video_duration=4,
    )
    assert abs(usd - 0.968) < 0.001


def test_evolink_short_ref_video_14s_output_matches_evolink_ui():
    """Instagram ref ~3s + 14s output @ $0.121/s ≈ $2.07 on EvoLink."""
    usd = evolink_video_usd_total(
        14,
        variant="standard",
        resolution="720p",
        has_motion_reference_video=True,
        reference_video_duration=3,
    )
    assert abs(usd - 2.057) < 0.01
    assert evolink_video_credit_cost(
        14,
        variant="standard",
        resolution="720p",
        has_motion_reference_video=True,
        reference_video_duration=3,
    ) == 206
