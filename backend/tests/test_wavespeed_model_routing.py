"""Маршрутизация WaveSpeed image-edit: UI-модель vs .env default."""

from app.services.wavespeed_client import (
    SEEDREAM_V50_PRO_EDIT_PATH,
    WAN_27_IMAGE_EDIT_PRO_PATH,
    WAN_27_IMAGE_EDIT_STANDARD_PATH,
    resolve_studio_image_edit_post_path,
)


def test_wan_pro_ui_uses_wan_endpoint_not_env_seedream() -> None:
    # Даже если WAVESPEED_SEEDREAM_EDIT_PATH = Seedream (default в config)
    path = resolve_studio_image_edit_post_path(
        wave_model_id="wan-2.7",
        wan_edit_tier="pro",
    )
    assert path == WAN_27_IMAGE_EDIT_PRO_PATH
    assert path != SEEDREAM_V50_PRO_EDIT_PATH


def test_wan_standard_ui() -> None:
    path = resolve_studio_image_edit_post_path(
        wave_model_id="wan-2.7",
        wan_edit_tier="standard",
    )
    assert path == WAN_27_IMAGE_EDIT_STANDARD_PATH


def test_seedream_ui_explicit() -> None:
    path = resolve_studio_image_edit_post_path(wave_model_id="seedream-v5.0-pro")
    assert path == SEEDREAM_V50_PRO_EDIT_PATH


def test_wan_27_pro_id_implies_pro_tier() -> None:
    path = resolve_studio_image_edit_post_path(wave_model_id="wan-2.7-pro")
    assert path == WAN_27_IMAGE_EDIT_PRO_PATH
