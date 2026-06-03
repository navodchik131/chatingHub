from app.services.studio_model_bootstrap import (
    DEFAULT_FACE_MERGE_PROMPT,
    humanize_wavespeed_provider_error,
    resolve_face_merge_prompt,
)
from app.services.wavespeed_client import _wavespeed_task_failed_error


def test_resolve_face_merge_prompt_empty_uses_default():
    assert resolve_face_merge_prompt("") == DEFAULT_FACE_MERGE_PROMPT
    assert resolve_face_merge_prompt("   ") == DEFAULT_FACE_MERGE_PROMPT


def test_resolve_face_merge_prompt_custom():
    custom = "My custom merge prompt"
    assert resolve_face_merge_prompt(custom) == custom


def test_task_failed_error_beats_envelope_credits_message():
    resp = {
        "code": 402,
        "message": "Insufficient credits. Please top up",
        "data": {
            "status": "failed",
            "error": "Content flagged as potentially sensitive. Please try different prompts or images.",
        },
    }
    assert "sensitive" in (_wavespeed_task_failed_error(resp) or "").lower()


def test_humanize_sensitive_sheet_error():
    msg = humanize_wavespeed_provider_error(
        "WaveSpeed: Content flagged as potentially sensitive."
    )
    assert "модерац" in msg.lower()
