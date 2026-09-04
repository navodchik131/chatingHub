"""Тесты Grok shot-analyst для Motion Control."""

from app.services.motion_control_grok import (
    apply_motion_control_shot_analyst_instruction,
    motion_control_grok_audio_policy,
    parse_motion_control_user_brief,
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


def test_parse_user_brief_plain_text_goes_to_what_happens():
    fields = parse_motion_control_user_brief("Она плюёт на разъём")
    assert fields["what_happens"] == "Она плюёт на разъём"
    assert fields["must_transfer"] == ""


def test_parse_user_brief_structured_sections():
    raw = """WHAT HAPPENS:
Девушка проверяет кабель

MUST TRANSFER:
- плевок на контакты

CALL IT WHAT IT IS:
- spit"""
    fields = parse_motion_control_user_brief(raw)
    assert "проверяет кабель" in fields["what_happens"]
    assert "плевок" in fields["must_transfer"]
    assert "spit" in fields["call_it"]


def test_apply_instruction_injects_user_brief_placeholders():
    tpl = """WHAT HAPPENS:
<<<BRIEF_WHAT_HAPPENS>>>

MUST TRANSFER:
<<<BRIEF_MUST_TRANSFER>>>"""
    out = apply_motion_control_shot_analyst_instruction(
        tpl,
        audio_policy="GENERATE",
        user_brief="WHAT HAPPENS:\nТест\n\nMUST TRANSFER:\n- бит",
    )
    assert "Тест" in out
    assert "бит" in out
    assert "<<<BRIEF_" not in out
    assert "## PER-PROJECT NOTES" not in out
