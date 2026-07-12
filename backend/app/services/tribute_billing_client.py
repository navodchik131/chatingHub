"""HTTP-клиент Tribute API (платформа ModelMate)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

TRIBUTE_API = "https://tribute.tg/api/v1"


async def fetch_tribute_product(
    product_id: int,
    *,
    api_key: str,
) -> dict[str, Any]:
    key = (api_key or "").strip()
    if not key:
        raise RuntimeError("tribute billing api key not configured")
    headers = {"Api-Key": key}
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.get(f"{TRIBUTE_API}/products/{int(product_id)}", headers=headers)
    if r.status_code >= 400:
        log.warning("tribute product fetch failed id=%s status=%s", product_id, r.status_code)
        raise RuntimeError(f"Tribute HTTP {r.status_code}")
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("Tribute: invalid product response")
    return data
