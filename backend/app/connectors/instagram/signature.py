"""Meta webhook signature verification (X-Hub-Signature-256)."""

from __future__ import annotations

import hashlib
import hmac


def verify_meta_webhook_signature(
    payload: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    secret = (app_secret or "").strip()
    if not secret or not signature_header:
        return False
    header = signature_header.strip()
    if not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)
