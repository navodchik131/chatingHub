from app.services.evolink_client import (
    format_evolink_video_edit_prompt,
    normalize_evolink_aspect_ratio,
    normalize_evolink_duration,
    resolve_evolink_model,
    wavespeed_tags_to_evolink,
    _normalize_evolink_quality,
)
from app.services.studio_evolink_motion_pricing import (
    apply_seedance_sale_credit_cost,
    evolink_video_credit_cost,
    evolink_video_duration_seconds,
    normalize_evolink_resolution,
)


def test_wavespeed_tags_to_evolink():
    assert wavespeed_tags_to_evolink("Identity @Image1, motion @Video1") == (
        "Identity @image1, motion @video1"
    )
    assert wavespeed_tags_to_evolink("@Image2 @Video3") == "@image2 @video3"


def test_resolve_evolink_model_variants():
    assert resolve_evolink_model(
        variant="standard",
        has_reference_video=False,
        has_reference_images=False,
        image_to_video=False,
    ) == "seedance-2.0-text-to-video"
    assert resolve_evolink_model(
        variant="mini",
        has_reference_video=True,
        has_reference_images=False,
        image_to_video=False,
    ) == "seedance-2.0-mini-reference-to-video"
    assert resolve_evolink_model(
        variant="seedance_25",
        has_reference_video=True,
        has_reference_images=True,
        image_to_video=False,
    ) == "seedance-2.5-video-edit"
    assert resolve_evolink_model(
        variant="seedance_25",
        has_reference_video=False,
        has_reference_images=True,
        image_to_video=True,
    ) == "seedance-2.5-image-to-video"


def test_evolink_aspect_and_duration_normalization():
    assert normalize_evolink_aspect_ratio("seedance-2.5-image-to-video", "9:16") == "adaptive"
    assert normalize_evolink_aspect_ratio("seedance-2.5-text-to-video", "9:16") == "9:16"
    assert normalize_evolink_duration("seedance-2.5-video-edit", 8) == -1
    assert normalize_evolink_duration("seedance-2.5-text-to-video", 8) == 8


def test_format_evolink_video_edit_prompt():
    assert format_evolink_video_edit_prompt("Replace @Video1 with @Image1").startswith(
        "Edit the video:"
    )
    assert " @video1" in format_evolink_video_edit_prompt("Replace @Video1").lower()
    assert format_evolink_video_edit_prompt("Edit the video: keep motion").startswith(
        "Edit the video:"
    )


def test_normalize_evolink_quality_seedance_25():
    assert _normalize_evolink_quality("1080p", variant="seedance_25") == "720p"
    assert _normalize_evolink_quality("480p", variant="seedance_25") == "480p"
    assert normalize_evolink_resolution("4k", variant="seedance_25") == "720p"
    assert normalize_evolink_resolution("1080p", variant="standard") == "720p"


def test_normalize_evolink_seedance_variant():
    from app.services.studio_evolink_motion_pricing import normalize_evolink_seedance_variant

    assert normalize_evolink_seedance_variant("mini") == "standard"
    assert normalize_evolink_seedance_variant("seedance_25") == "seedance_25"


def test_evolink_duration_limits():
    assert evolink_video_duration_seconds("20", variant="standard") == 15
    assert evolink_video_duration_seconds("25", variant="seedance_25") == 25


def test_apply_seedance_sale_credit_cost_always_charges():
    assert apply_seedance_sale_credit_cost("pro", 12) == 12
    assert apply_seedance_sale_credit_cost("standard", 12) == 12
    assert evolink_video_credit_cost(5, has_motion_reference_video=False, variant="standard") >= 1
