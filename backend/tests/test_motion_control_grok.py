"""Тесты Grok shot-analyst для Motion Control."""

from app.services.motion_control_grok import (
    apply_motion_control_shot_analyst_instruction,
    motion_control_grok_audio_policy,
)


def test_audio_policy_plate_when_ref_audio_present():
    assert motion_control_grok_audio_policy(wants_reference_audio=False, has_ref_audio=True) == "PLATE"
    assert motion_control_grok_audio_policy(wants_reference_audio=True, has_ref_audio=True) == "PLATE"


def test_audio_policy_generate_without_ref_audio_but_wants_sound():
    assert motion_control_grok_audio_policy(wants_reference_audio=True, has_ref_audio=False) == "GENERATE"


def test_audio_policy_plate_silent_clip():
    assert motion_control_grok_audio_policy(wants_reference_audio=False, has_ref_audio=False) == "PLATE"


def test_apply_instruction_injects_audio_policy():
    tpl = "AUDIO POLICY = <<<AUDIO_POLICY>>>"
    out = apply_motion_control_shot_analyst_instruction(tpl, audio_policy="PLATE")
    assert "AUDIO POLICY = PLATE" in out
    assert "<<<AUDIO_POLICY>>>" not in out
