"""Проверка заголовка X-Fanvue-Signature (HMAC-SHA256)."""

from __future__ import annotations

import hashlib
import hmac
import time


def verify_fanvue_webhook_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: str,
    *,
    max_age_seconds: int = 300,
) -> bool:
    """
    Формат заголовка: ``t=<unix_ts>,v0=<hex_hmac>``.
    Подпись считается от строки ``{timestamp}.{raw_body_utf8}``.
    """
    if not secret or not signature_header:
        return False
    ts_s: str | None = None
    sig_hex: str | None = None
    for part in signature_header.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "t":
            ts_s = v
        elif k == "v0":
            sig_hex = v
    if not ts_s or not sig_hex:
        return False
    try:
        ts = int(ts_s, 10)
    except ValueError:
        return False
    now = int(time.time())
    if abs(now - ts) > max_age_seconds:
        return False
    try:
        body_text = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        return False
    signed = f"{ts_s}.{body_text}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(sig_hex.encode("ascii"), expected.encode("ascii"))
    except (ValueError, AttributeError):
        return False
