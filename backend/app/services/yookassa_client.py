from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

YOOKASSA_API = "https://api.yookassa.ru/v3"


def _auth_header() -> str:
    sid = (settings.yookassa_shop_id or "").strip()
    key = (settings.yookassa_secret_key or "").strip()
    raw = f"{sid}:{key}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


async def create_payment(
    *,
    amount_value: str,
    currency: str = "RUB",
    description: str,
    return_url: str,
    metadata: dict[str, str],
) -> dict[str, Any]:
    """Создать платёж с redirect confirmation. amount_value — строка вида «499.00»."""
    if not settings.yookassa_configured:
        raise RuntimeError("yookassa not configured")
    payload: dict[str, Any] = {
        "amount": {"value": amount_value, "currency": currency},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description[:210],
        "metadata": {k: str(v)[:500] for k, v in metadata.items()},
    }
    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Idempotence-Key": str(uuid.uuid4()),
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{YOOKASSA_API}/payments", headers=headers, json=payload)
    if r.status_code >= 400:
        log.warning("yookassa create payment failed: %s %s", r.status_code, (r.text or "")[:800])
        raise RuntimeError(f"YooKassa HTTP {r.status_code}")
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("YooKassa: invalid response")
    return data


def parse_notification_body(body: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None
