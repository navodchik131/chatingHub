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


def test_humanize_gateway_timeout_strips_html():
    from app.services.wavespeed_client import format_wavespeed_user_error

    msg = format_wavespeed_user_error(
        "<html><head><title>504 Gateway Time-out</title></head></html>"
    )
    assert "504" in msg
    assert "<html" not in msg.lower()
    assert "архив" in msg.lower()


def test_humanize_credits_no_public_app_url_hint():
    msg = humanize_wavespeed_provider_error(
        "WaveSpeed: Insufficient credits. Please top up your account to continue."
    )
    assert "insufficient credits" in msg.lower() or "пополните баланс" in msg.lower()
    assert "PUBLIC_APP_URL" not in msg
