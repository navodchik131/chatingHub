"""OpenAI-compatible embeddings для style RAG."""

from __future__ import annotations

import json
import logging
import math

import httpx

from app.config import settings
from app.services.studio_openai import StudioOpenAiCredentials

log = logging.getLogger(__name__)


def _resolve_credentials(
    credentials: StudioOpenAiCredentials | None,
) -> tuple[str, str, str]:
    if credentials is not None:
        key = credentials.api_key.strip()
        base = (credentials.base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
        org = (credentials.organization or "").strip()
    else:
        key = (settings.openai_api_key or "").strip()
        base = (settings.openai_base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
        org = (settings.openai_organization or "").strip()
    if not key:
        raise RuntimeError("openai not configured for embeddings")
    return key, base, org


async def embed_texts(
    texts: list[str],
    *,
    credentials: StudioOpenAiCredentials | None = None,
    model: str | None = None,
) -> list[list[float]]:
    cleaned = [(t or "").strip() for t in texts]
    if not cleaned:
        return []
    key, base, org = _resolve_credentials(credentials)
    embed_model = (model or settings.companion_style_embed_model or "").strip()
    if not embed_model:
        embed_model = "text-embedding-3-small"

    url = f"{base}/embeddings"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if org:
        headers["OpenAI-Organization"] = org

    payload = {"model": embed_model, "input": cleaned}
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        raise RuntimeError(f"embeddings failed: {r.status_code} {(r.text or '')[:500]}")

    data = r.json()
    rows = data.get("data") or []
    rows.sort(key=lambda x: int(x.get("index", 0)))
    return [list(row.get("embedding") or []) for row in rows]


def parse_embedding_json(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        vec = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(vec, list) or not vec:
        return None
    try:
        return [float(x) for x in vec]
    except (TypeError, ValueError):
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)
