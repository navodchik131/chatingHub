"""Язык исходящих сообщений оператора: EN по умолчанию, «auto» — явный режим детекции."""

from __future__ import annotations

from app.db.models import Conversation
from app.services.translation import detect_lang

DEFAULT_OUTBOUND_LANG = "en"
AUTO_OUTBOUND_LANG = "auto"


def resolve_outbound_lang(conv: Conversation, *, last_fan_text: str | None = None) -> str:
    """
    Целевой язык перевода исходящих (оператор пишет по-русски → клиенту).
    NULL / пусто → English; «auto» → детекция с последних входящих.
    """
    forced = (conv.outbound_lang or "").strip().lower()
    if forced == AUTO_OUTBOUND_LANG:
        if last_fan_text and last_fan_text.strip():
            detected = detect_lang(last_fan_text).lower().strip()
            if detected and detected != "unknown":
                return detected[:2] if len(detected) > 2 else detected
        hint = (conv.user_lang or "").strip().lower()
        return hint or DEFAULT_OUTBOUND_LANG
    if forced:
        return forced[:16]
    return DEFAULT_OUTBOUND_LANG


def maybe_update_detected_user_lang(conv: Conversation, src_lang: str | None) -> None:
    """Обновляем user_lang только для подсказки «Авто», без скачков языка в режиме EN по умолчанию."""
    if not src_lang or src_lang == "unknown":
        return
    if (conv.outbound_lang or "").strip().lower() == AUTO_OUTBOUND_LANG:
        conv.user_lang = src_lang
    elif not conv.user_lang:
        conv.user_lang = src_lang
