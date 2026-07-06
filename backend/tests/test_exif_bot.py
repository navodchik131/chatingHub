"""Тесты EXIF Telegram bot."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.exif_bot.process import profile_is_ready


def test_profile_is_ready_with_preset_only():
    p = SimpleNamespace(
        phone_exif_selfie_json=None,
        phone_exif_main_json=None,
        camera_preset_id="iphone_15_pro",
    )
    assert profile_is_ready(p) is True


def test_profile_is_ready_with_selfie_json():
    p = SimpleNamespace(
        phone_exif_selfie_json='{"make":"Apple"}',
        phone_exif_main_json=None,
        camera_preset_id=None,
    )
    assert profile_is_ready(p) is True


def test_profile_is_ready_empty():
    p = SimpleNamespace(
        phone_exif_selfie_json=None,
        phone_exif_main_json=None,
        camera_preset_id=None,
    )
    assert profile_is_ready(p) is False


def test_parse_geo_logic():
    from app.connectors.telegram.exif_bot.handlers import _parse_geo

    assert _parse_geo("55.7558, 37.6173") == (55.7558, 37.6173)
    assert _parse_geo("bad") is None
