from app.services.studio_workflow_image_resolution import (
    default_workflow_image_resolution,
    normalize_workflow_image_resolution,
    workflow_wavespeed_size_for_resolution,
)


def test_normalize_workflow_image_resolution_per_model():
    assert normalize_workflow_image_resolution("gpt-image-2", "4k") == "4k"
    assert normalize_workflow_image_resolution("gpt-image-2", "8k") == "1k"
    assert normalize_workflow_image_resolution("seedream-v5.0-pro", "4k") == "1k"
    assert normalize_workflow_image_resolution("wan-2.7-pro", "2k") == "2k"


def test_default_workflow_image_resolution():
    assert default_workflow_image_resolution("nano-banana-pro") == "2k"
    assert default_workflow_image_resolution("wan-2.7") == "2k"


def test_workflow_wavespeed_size_for_resolution_scales():
    base = workflow_wavespeed_size_for_resolution("9:16", "2k")
    low = workflow_wavespeed_size_for_resolution("9:16", "1k")
    high = workflow_wavespeed_size_for_resolution("9:16", "4k")
    assert base == "1080x1920"
    assert low == "810x1440"
    assert high == "1620x2880"
