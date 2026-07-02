"""Проверка подписи webhook Tribute (заголовок trbt-signature, HMAC-SHA256)."""

from __future__ import annotations

import hashlib
import hmac


def verify_tribute_webhook_signature(
    raw: bytes, signature: str | None, api_key: str
) -> bool:
    if not signature or not (api_key or "").strip():
        return False
    sig = signature.strip()
    if sig.lower().startswith("sha256="):
        sig = sig.split("=", 1)[1]
    expected = hmac.new(api_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), sig.lower())
