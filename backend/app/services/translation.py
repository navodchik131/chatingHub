from __future__ import annotations

import asyncio
import logging
from typing import Final

import httpx
from langdetect import LangDetectException, detect

from app.config import settings

log = logging.getLogger(__name__)

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


async def translate_to_russian(text: str) -> tuple[str, str]:
    """Перевод входящего текста на русский. Возвращает (перевод, исходный_код_языка)."""
    src = detect_lang(text)
    if src.startswith("ru"):
        return text, src
    try:
        if settings.deepl_api_key:
            out = await _deepl_translate(text, "ru", None)
            return out, src
    except Exception as e:
        log.warning("deepl to ru failed: %s", e)
    try:
        out = await _libre_translate(text, "ru", src if src != "unknown" else None)
        return out, src
    except Exception as e:
        log.warning("libre to ru failed: %s", e)
    try:
        out = await _google_translate(text, "ru", src if src != "unknown" else None)
        return out, src
    except Exception as e:
        log.warning("google fallback to ru failed: %s", e)
    return f"[перевод недоступен] {text}", src


async def translate_from_russian(text: str, target_lang: str) -> str:
    """Ответ на русском → язык пользователя."""
    if target_lang.startswith("ru"):
        return text
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
