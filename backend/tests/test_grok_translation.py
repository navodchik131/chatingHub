"""Grok-перевод сообщений диалогов."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.config import BACKEND_DIR, settings
from app.services.grok_translation import (
    build_translation_user_message,
    grok_translation_configured,
    lang_display_name,
    load_grok_translation_system_prompt,
    sanitize_translation_output,
)
from app.services.translation import should_translate_message_text


def test_grok_translation_system_prompt_loads() -> None:
    bundled = (BACKEND_DIR / "_bundled_prompts" / "grok_chat_translation_system.txt").resolve()
    assert bundled.is_file()
    text = load_grok_translation_system_prompt()
    assert "fan_to_operator" in text
    assert "operator_to_fan" in text


def test_lang_display_name() -> None:
    assert lang_display_name("en") == "English"
    assert lang_display_name("de") == "German"
    assert lang_display_name("xx") == "XX"


def test_build_translation_user_message_outbound() -> None:
    msg = build_translation_user_message(
        text="Привет, как дела?",
        direction="operator_to_fan",
        source_lang="ru",
        target_lang="en",
    )
    assert "Direction: operator_to_fan" in msg
    assert "Target language: en (English)" in msg
    assert "Привет, как дела?" in msg


def test_sanitize_translation_output_strips_quotes_and_prefix() -> None:
    assert (
        sanitize_translation_output('Translation: "Hey babe 😘"', original="Привет")
        == "Hey babe 😘"
    )


def test_grok_translation_configured_requires_flag_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "grok_translation_enabled", False)
    monkeypatch.setattr(settings, "grok_api_key", "xai-test")
    assert grok_translation_configured() is False

    monkeypatch.setattr(settings, "grok_translation_enabled", True)
    monkeypatch.setattr(settings, "grok_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert grok_translation_configured() is False

    monkeypatch.setattr(settings, "grok_api_key", "xai-test")
    assert grok_translation_configured() is True


def test_translate_to_russian_uses_grok_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import translation as tr

    monkeypatch.setattr(settings, "grok_translation_enabled", True)
    monkeypatch.setattr(settings, "grok_api_key", "xai-test")
    monkeypatch.setattr(tr, "detect_lang", lambda _t: "en")

    async def _run() -> tuple[str, str]:
        with patch(
            "app.services.translation.grok_translate_to_russian",
            new=AsyncMock(return_value="Привет красавчик"),
        ) as mock_grok:
            out, src = await tr.translate_to_russian("Hey handsome")
        mock_grok.assert_awaited_once()
        return out, src

    out, src = asyncio.run(_run())
    assert out == "Привет красавчик"
    assert src == "en"


def test_should_translate_message_text_skips_media_and_emoji() -> None:
    assert should_translate_message_text("") is False
    assert should_translate_message_text("😘🔥") is False
    assert should_translate_message_text("🎭") is False
    assert should_translate_message_text("https://cdn.example/video.mp4") is False
    assert should_translate_message_text("Hey babe 😘") is True
    assert should_translate_message_text("Привет") is True


def test_translate_to_russian_skips_emoji_only() -> None:
    from app.services import translation as tr

    async def _run() -> tuple[str, str]:
        with patch(
            "app.services.translation.grok_translate_to_russian",
            new=AsyncMock(),
        ) as mock_grok:
            out, src = await tr.translate_to_russian("😘")
        mock_grok.assert_not_called()
        return out, src

    out, src = asyncio.run(_run())
    assert out == ""
    assert src == "en"


def test_translate_from_russian_falls_back_to_deepl_when_grok_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import translation as tr

    monkeypatch.setattr(settings, "grok_translation_enabled", True)
    monkeypatch.setattr(settings, "grok_api_key", "xai-test")
    monkeypatch.setattr(settings, "deepl_api_key", "deepl-test")

    async def _run() -> str:
        with patch(
            "app.services.translation.grok_translate_from_russian",
            new=AsyncMock(side_effect=RuntimeError("api down")),
        ):
            with patch(
                "app.services.translation._deepl_fallback_from_russian",
                new=AsyncMock(return_value="Hey babe"),
            ) as mock_deepl:
                with patch(
                    "app.services.translation._libre_translate",
                    new=AsyncMock(),
                ) as mock_libre:
                    out = await tr.translate_from_russian("Привет", "en")
            mock_deepl.assert_awaited_once()
            mock_libre.assert_not_called()
            return out

    assert asyncio.run(_run()) == "Hey babe"
