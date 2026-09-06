"""Motion Control wizard: переключение outline vs depth v2."""

from app.config import settings
from app.services.studio_motion_video import motion_outline_requested


def test_motion_outline_wizard_explicit_flag():
    params = {"motion_control_wizard": "1", "use_motion_outline": "1"}
    assert motion_outline_requested(params) is True


def test_motion_outline_wizard_depth_v2_when_outline_off():
    params = {"motion_control_wizard": "1", "use_motion_outline": "0"}
    assert motion_outline_requested(params) is False


def test_motion_outline_non_wizard_uses_settings():
    params = {"motion_control_wizard": "0"}
    assert motion_outline_requested(params) is bool(settings.motion_outline_enabled)
