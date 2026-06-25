from app.services.studio_model_bootstrap import (
    DEFAULT_FACE_MERGE_PROMPT,
    DEFAULT_MODEL_SHEET_PROMPT,
    DEFAULT_WORKFLOW_SHEET_PROMPT,
    humanize_wavespeed_provider_error,
    resolve_face_merge_prompt,
    resolve_model_sheet_prompt,
    resolve_workflow_model_sheet_prompt,
    append_workflow_first_frame_face_grid,
)
from app.services.wavespeed_client import _wavespeed_task_failed_error


def test_resolve_face_merge_prompt_empty_uses_default():
    assert resolve_face_merge_prompt("") == DEFAULT_FACE_MERGE_PROMPT
    assert resolve_face_merge_prompt("   ") == DEFAULT_FACE_MERGE_PROMPT


def test_resolve_face_merge_prompt_custom():
    custom = "My custom merge prompt"
    assert resolve_face_merge_prompt(custom) == custom


def test_resolve_model_sheet_prompt_empty_uses_default():
    assert resolve_model_sheet_prompt("") == DEFAULT_MODEL_SHEET_PROMPT
    assert resolve_model_sheet_prompt("   ") == DEFAULT_MODEL_SHEET_PROMPT


def test_resolve_model_sheet_prompt_custom():
    custom = "Своя раскладка на белом фоне"
    assert resolve_model_sheet_prompt(custom) == custom


def test_append_workflow_first_frame_face_grid():
    out = append_workflow_first_frame_face_grid("Scene with model.")
    assert "white guide grid" in out.lower()
    assert "Scene with model." in out
    again = append_workflow_first_frame_face_grid(out)
    assert again == out


def test_resolve_workflow_model_sheet_prompt_includes_grid():
    out = resolve_workflow_model_sheet_prompt("")
    assert "grid" in out.lower()
    assert "back" in out.lower()
    assert "65" in out or "75" in out
    assert DEFAULT_WORKFLOW_SHEET_PROMPT.split()[0] in out


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


def test_submit_does_not_retry_on_504(monkeypatch):
    """POST при 504 не должен повторяться — иначе две задачи в WaveSpeed."""
    import httpx

    from app.services import wavespeed_client as wc

    calls = {"n": 0}

    class FakeResp:
        status_code = 504
        text = "<html>504 Gateway Time-out</html>"

        def json(self):
            raise ValueError("not json")

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            calls["n"] += 1
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: FakeClient())

    import pytest

    with pytest.raises(RuntimeError, match="504"):
        import asyncio

        asyncio.run(
            wc._wavespeed_submit_image_prediction(
                api_key="k",
                full_post_url="https://api.wavespeed.ai/api/v3/openai/gpt-image-2/edit",
                body={"prompt": "x", "images": []},
            )
        )
    assert calls["n"] == 1


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
