from __future__ import annotations

import asyncio
import logging
import re
from typing import Final

import httpx
from langdetect import LangDetectException, detect

from app.config import settings
from app.services.grok_translation import (
    grok_translate_from_russian,
    grok_translate_to_russian,
    grok_translation_configured,
)

log = logging.getLogger(__name__)

# Только эмодзи / символы (без букв и цифр) — не гоняем через переводчик
_EMOJI_ONLY_RE = re.compile(
    r"^[\s"
    r"\U0001F300-\U0001FAFF"
    r"\U00002600-\U000027BF"
    r"\U0001F1E0-\U0001F1FF"
    r"\U000024C2-\U0001F251"
    r"\u200d\ufe0f"
    r"\uFE0F"
    r"]+$",
    flags=re.UNICODE,
)

_MEDIA_ONLY_PLACEHOLDERS: Final[frozenset[str]] = frozenset(
    {
        "🎭",
        "[исчезающее медиа недоступно через API]",
    }
)

# DeepL целевые коды (основные)
_DEEPL_TARGETS: Final[dict[str, str]] = {
    "en": "EN",
    "ru": "RU",
    "de": "DE",
    "fr": "FR",
    "es": "ES",
    "it": "IT",
    "pt": "PT",
    "pl": "PL",
    "uk": "UK",
    "ja": "JA",
    "zh": "ZH",
    "ko": "KO",
    "nl": "NL",
    "sv": "SV",
    "cs": "CS",
    "da": "DA",
    "fi": "FI",
    "el": "EL",
    "hu": "HU",
    "id": "ID",
    "tr": "TR",
    "bg": "BG",
    "ro": "RO",
    "sk": "SK",
    "sl": "SL",
}


def detect_lang(text: str) -> str:
    if not text.strip():
        return "en"
    try:
        return detect(text)
    except LangDetectException:
        return "en"


def should_translate_message_text(text: str | None) -> bool:
    """Пропускаем стикеры, чистые эмодзи, URL медиа и прочий не-текст."""
    t = (text or "").strip()
    if not t:
        return False
    if t in _MEDIA_ONLY_PLACEHOLDERS:
        return False
    if t.startswith("http://") or t.startswith("https://"):
        return False
    if _EMOJI_ONLY_RE.fullmatch(t):
        return False
    # Хотя бы одна буква или цифра — считаем переводимым текстом
    if re.search(r"[\w]", t, flags=re.UNICODE):
        return True
    return False


def _deepl_base() -> str:
    return (
        "https://api-free.deepl.com/v2"
        if settings.deepl_use_free
        else "https://api.deepl.com/v2"
    )


async def _deepl_translate(text: str, target_lang: str, source_lang: str | None) -> str:
    key = settings.deepl_api_key
    if not key:
        raise RuntimeError("no deepl key")
    target = _DEEPL_TARGETS.get(target_lang.lower(), target_lang.upper()[:2])
    if len(target) == 2:
        target = target.upper()
    params: dict[str, str] = {
        "auth_key": key,
        "text": text,
        "target_lang": target,
    }
    if source_lang:
        src = _DEEPL_TARGETS.get(source_lang.lower(), source_lang.upper()[:2])
        if len(src) == 2:
            src = src.upper()
        params["source_lang"] = src
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{_deepl_base()}/translate", data=params)
        r.raise_for_status()
        data = r.json()
    return str(data["translations"][0]["text"])


async def _libre_translate(text: str, target: str, source: str | None) -> str:
    url = (settings.libretranslate_url or "https://libretranslate.com").rstrip("/")
    body: dict = {"q": text, "target": target, "format": "text"}
    if source:
        body["source"] = source
    else:
        body["source"] = "auto"
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(f"{url}/translate", json=body)
        r.raise_for_status()
        data = r.json()
    return str(data["translatedText"])


async def _google_translate(text: str, target: str, source: str | None) -> str:
    """Запасной канал через Google (библиотека deep-translator, без своего API-ключа)."""
    from deep_translator import GoogleTranslator

    src = (source or "auto").lower()
    if src == "unknown":
        src = "auto"
    # langdetect и user_lang — обычно двухбуквенные коды (en, de, ru)
    tgt = target.lower().strip()
    if len(tgt) > 2:
        tgt = tgt[:2]

    def _run() -> str:
        return GoogleTranslator(source=src, target=tgt).translate(text)

    return await asyncio.to_thread(_run)


async def _legacy_translate_to_russian(text: str, src: str) -> str:
    """DeepL → LibreTranslate → Google (когда Grok выключен)."""
    try:
        if settings.deepl_api_key:
            return await _deepl_translate(text, "ru", None)
    except Exception as e:
        log.warning("deepl to ru failed: %s", e)
    try:
        return await _libre_translate(text, "ru", src if src != "unknown" else None)
    except Exception as e:
        log.warning("libre to ru failed: %s", e)
    try:
        return await _google_translate(text, "ru", src if src != "unknown" else None)
    except Exception as e:
        log.warning("google fallback to ru failed: %s", e)
    return f"[перевод недоступен] {text}"


async def _legacy_translate_from_russian(text: str, target_lang: str) -> str:
    try:
        if settings.deepl_api_key:
            return await _deepl_translate(text, target_lang, "ru")
    except Exception as e:
        log.warning("deepl from ru failed: %s", e)
    try:
        return await _libre_translate(text, target_lang, "ru")
    except Exception as e:
        log.warning("libre from ru failed: %s", e)
    try:
        return await _google_translate(text, target_lang, "ru")
    except Exception as e:
        log.warning("google fallback from ru failed: %s", e)
    return text


async def _deepl_fallback_to_russian(text: str) -> str | None:
    if not settings.deepl_api_key:
        return None
    try:
        return await _deepl_translate(text, "ru", None)
    except Exception as e:
        log.warning("deepl grok-fallback to ru failed: %s", e)
        return None


async def _deepl_fallback_from_russian(text: str, target_lang: str) -> str | None:
    if not settings.deepl_api_key:
        return None
    try:
        return await _deepl_translate(text, target_lang, "ru")
    except Exception as e:
        log.warning("deepl grok-fallback from ru failed: %s", e)
        return None


async def translate_to_russian(text: str) -> tuple[str, str]:
    """Перевод входящего текста на русский. Возвращает (перевод, исходный_код_языка)."""
    src = detect_lang(text) if (text or "").strip() else "unknown"
    if not should_translate_message_text(text):
        return "", src
    if src.startswith("ru"):
        return text, src
    if grok_translation_configured():
        try:
            out = await grok_translate_to_russian(text, src)
            return out, src
        except Exception as e:
            log.warning("grok to ru failed: %s", e)
            deepl_out = await _deepl_fallback_to_russian(text)
            if deepl_out:
                return deepl_out, src
            return f"[перевод недоступен] {text}", src
    return await _legacy_translate_to_russian(text, src), src


async def translate_from_russian(text: str, target_lang: str) -> str:
    """Ответ на русском → язык пользователя."""
    if not should_translate_message_text(text):
        return (text or "").strip()
    if target_lang.startswith("ru"):
        return text
    if grok_translation_configured():
        try:
            return await grok_translate_from_russian(text, target_lang)
        except Exception as e:
            log.warning("grok from ru failed: %s", e)
            deepl_out = await _deepl_fallback_from_russian(text, target_lang)
            if deepl_out:
                return deepl_out
            return text
    return await _legacy_translate_from_russian(text, target_lang)
