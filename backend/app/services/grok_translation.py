"""Перевод сообщений диалогов через xAI Grok (отдельная текстовая модель)."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Final, Literal

from app.config import BACKEND_DIR, settings
from app.services.studio_openai import StudioOpenAiCredentials, chat_completion_openai_compatible_text

log = logging.getLogger(__name__)

TranslationDirection = Literal["fan_to_operator", "operator_to_fan"]

_LANG_NAMES: Final[dict[str, str]] = {
    "ru": "Russian",
    "en": "English",
    "es": "Spanish",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "uk": "Ukrainian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "tr": "Turkish",
    "sv": "Swedish",
    "cs": "Czech",
    "da": "Danish",
    "fi": "Finnish",
    "el": "Greek",
    "hu": "Hungarian",
    "id": "Indonesian",
    "bg": "Bulgarian",
    "ro": "Romanian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "ar": "Arabic",
    "he": "Hebrew",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnamese",
}

_OUTPUT_PREFIX_RE = re.compile(
    r"^(?:translation|перевод|translated text|result)\s*:\s*",
    re.IGNORECASE,
)


def grok_translation_configured() -> bool:
    if not settings.grok_translation_enabled:
        return False
    key = (settings.grok_api_key or "").strip() or (settings.openai_api_key or "").strip()
    return bool(key)


def grok_translation_credentials() -> StudioOpenAiCredentials:
    key = (settings.grok_api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError("Grok translation: GROK_API_KEY not configured")
    base = (settings.grok_base_url or "https://api.x.ai/v1").strip().rstrip("/")
    return StudioOpenAiCredentials(api_key=key, base_url=base)


def _prompt_file_candidates(configured_rel: str, default_filename: str) -> list[Path]:
    rel = (configured_rel or "").strip()
    name = default_filename
    if rel:
        name = (BACKEND_DIR / rel).resolve().name
    ordered = [
        (BACKEND_DIR / rel).resolve() if rel else None,
        (BACKEND_DIR / "data" / "prompts" / name).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / name).resolve(),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for item in ordered:
        if item is None or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def load_grok_translation_system_prompt() -> str:
    configured = (settings.grok_translation_system_path or "").strip()
    for path in _prompt_file_candidates(configured, "grok_chat_translation_system.txt"):
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
    inline = (settings.grok_translation_system_inline or "").strip()
    if inline:
        return inline
    raise RuntimeError(
        "Grok translation system prompt missing: add grok_chat_translation_system.txt "
        "or GROK_TRANSLATION_SYSTEM_INLINE"
    )


def lang_display_name(code: str) -> str:
    norm = (code or "").strip().lower().split("-")[0]
    if not norm or norm == "unknown":
        return "unknown"
    return _LANG_NAMES.get(norm, norm.upper())


def _normalize_lang_code(code: str | None) -> str:
    norm = (code or "").strip().lower().split("-")[0]
    return norm or "unknown"


def build_translation_user_message(
    *,
    text: str,
    direction: TranslationDirection,
    source_lang: str | None,
    target_lang: str,
) -> str:
    src = _normalize_lang_code(source_lang)
    tgt = _normalize_lang_code(target_lang)
    body = (text or "").strip()
    if not body:
        raise ValueError("empty text")
    return (
        f"Direction: {direction}\n"
        f"Source language: {src} ({lang_display_name(src)})\n"
        f"Target language: {tgt} ({lang_display_name(tgt)})\n\n"
        f"Message:\n{body}"
    )


def sanitize_translation_output(raw: str, *, original: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise RuntimeError("Grok translation returned empty text")

    if text.startswith("```") and text.endswith("```"):
        text = text.strip("`").strip()
        if "\n" in text:
            text = text.split("\n", 1)[1].strip()

    text = _OUTPUT_PREFIX_RE.sub("", text).strip()

    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'", "«", "»"}:
        text = text[1:-1].strip()

    if not text:
        raise RuntimeError("Grok translation empty after sanitize")

    orig_len = max(1, len((original or "").strip()))
    if len(text) > orig_len * 4 + 80:
        log.warning(
            "grok translation much longer than source (%s vs %s chars)",
            len(text),
            orig_len,
        )

    return text


async def grok_translate(
    text: str,
    *,
    direction: TranslationDirection,
    source_lang: str | None,
    target_lang: str,
) -> str:
    body = (text or "").strip()
    if not body:
        return body

    tgt = _normalize_lang_code(target_lang)
    src = _normalize_lang_code(source_lang)
    if tgt != "unknown" and src != "unknown" and src == tgt:
        return body

    system = load_grok_translation_system_prompt()
    user = build_translation_user_message(
        text=body,
        direction=direction,
        source_lang=source_lang,
        target_lang=target_lang,
    )
    model = (settings.grok_translation_model or "grok-4.1-fast").strip()
    max_tokens = min(
        int(settings.grok_translation_max_tokens),
        max(128, len(body) * 3 + 64),
    )

    raw = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        temperature=float(settings.grok_translation_temperature),
        credentials=grok_translation_credentials(),
        timeout_seconds=float(settings.grok_translation_timeout_seconds),
    )
    return sanitize_translation_output(raw, original=body)


async def grok_translate_to_russian(text: str, source_lang: str | None) -> str:
    return await grok_translate(
        text,
        direction="fan_to_operator",
        source_lang=source_lang,
        target_lang="ru",
    )


async def grok_translate_from_russian(text: str, target_lang: str) -> str:
    return await grok_translate(
        text,
        direction="operator_to_fan",
        source_lang="ru",
        target_lang=target_lang,
    )
