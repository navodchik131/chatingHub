"""Подбор примеров стиля чаттера: БД (реальные чаты) + fallback JSON."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CompanionStyleExample
from app.services.companion_bot.style_embeddings import (
    cosine_similarity,
    embed_texts,
    parse_embedding_json,
)
from app.services.studio_openai import StudioOpenAiCredentials

log = logging.getLogger(__name__)

_EXAMPLES_PATH = Path(__file__).resolve().parents[3] / "data" / "companion_style_examples.json"
_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)
_CANDIDATE_LIMIT = 350


@lru_cache(maxsize=1)
def _load_static_examples() -> tuple[dict, ...]:
    if not _EXAMPLES_PATH.is_file():
        return ()
    try:
        raw = json.loads(_EXAMPLES_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("companion static style examples parse failed: %s", e)
        return ()
    if not isinstance(raw, list):
        return ()
    out: list[dict] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        fan = str(row.get("fan_message") or "").strip()
        reply = str(row.get("model_reply") or "").strip()
        if fan and reply:
            out.append(
                {
                    "fan_message": fan,
                    "model_reply": reply,
                    "tags": list(row.get("tags") or []),
                    "lang": str(row.get("lang") or "").lower()[:2],
                    "quality_score": 0.8,
                }
            )
    return tuple(out)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1}


def _token_score(*, fan_text: str, example: dict, lang: str, followup: bool) -> float:
    score = float(example.get("quality_score") or 1.0)
    ex_lang = example.get("lang") or ""
    if lang and ex_lang:
        score += 2.0 if ex_lang == lang[:2] else -0.5

    fan_tokens = _tokens(fan_text)
    ex_tokens = _tokens(example.get("fan_message") or "")
    if fan_tokens and ex_tokens:
        overlap = len(fan_tokens & ex_tokens) / max(len(fan_tokens | ex_tokens), 1)
        score += overlap * 6.0

    tags = example.get("tags") or []
    low = fan_text.lower()
    if followup and "retention" in tags:
        score += 1.5
    if "?" in fan_text and ("question" in tags or "factual" in tags):
        score += 2.0
    if any(w in low for w in ("скуч", "bored", "miss", "скуча")):
        if "retention" in tags or "warm" in tags or "bored" in tags:
            score += 1.5
    if any(w in low for w in ("привет", "hey", "hi", "hello")):
        if "greeting" in tags:
            score += 1.5
    if any(w in low for w in ("бот", "ghost", "игнор")):
        if "trust" in tags or "repair" in tags:
            score += 2.0
    if len(fan_text) <= 20 and "short" in tags:
        score += 1.0
    return score


def _row_to_dict(row: CompanionStyleExample) -> dict:
    tags: list[str] = []
    if row.tags_json:
        try:
            parsed = json.loads(row.tags_json)
            if isinstance(parsed, list):
                tags = [str(t) for t in parsed]
        except json.JSONDecodeError:
            tags = []
    return {
        "fan_message": row.fan_message,
        "model_reply": row.model_reply,
        "lang": (row.lang or "")[:2],
        "tags": tags,
        "quality_score": float(row.quality_score or 1.0),
        "embedding": parse_embedding_json(row.embedding_json),
        "source": "db",
    }


async def _load_db_candidates(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int | None,
    lang: str,
) -> list[dict]:
    stmt = (
        select(CompanionStyleExample)
        .where(CompanionStyleExample.user_id == owner_id)
        .order_by(CompanionStyleExample.quality_score.desc(), CompanionStyleExample.id.desc())
        .limit(_CANDIDATE_LIMIT)
    )
    if studio_model_id:
        stmt = stmt.where(
            or_(
                CompanionStyleExample.studio_model_id.is_(None),
                CompanionStyleExample.studio_model_id == studio_model_id,
            )
        )

    rows = list((await session.scalars(stmt)).all())
    if not rows:
        return []

    lang2 = (lang or "")[:2].lower()
    preferred = [r for r in rows if (r.lang or "")[:2].lower() == lang2]
    pool = preferred if len(preferred) >= 8 else rows
    return [_row_to_dict(r) for r in pool]


async def _rank_with_embeddings(
    *,
    query: str,
    candidates: list[dict],
    credentials: StudioOpenAiCredentials | None,
) -> list[dict]:
    with_emb = [c for c in candidates if c.get("embedding")]
    if not with_emb:
        return candidates

    try:
        q_vecs = await embed_texts([query], credentials=credentials)
    except Exception as e:
        log.info("companion style rag embed query failed: %s", e)
        return candidates
    if not q_vecs or not q_vecs[0]:
        return candidates

    q = q_vecs[0]
    ranked: list[tuple[float, dict]] = []
    for c in with_emb:
        sim = cosine_similarity(q, c["embedding"])
        ranked.append((sim + float(c.get("quality_score") or 1.0) * 0.05, c))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked]


def _pick_top(
    *,
    fan_text: str,
    lang: str,
    followup: bool,
    candidates: list[dict],
    limit: int,
) -> list[dict]:
    query = fan_text.strip()
    if followup and not query:
        query = "follow up fan silent"

    ranked: list[tuple[float, dict]] = []
    for ex in candidates:
        ranked.append((_token_score(fan_text=query, example=ex, lang=lang, followup=followup), ex))
    ranked.sort(key=lambda x: x[0], reverse=True)

    picked: list[dict] = []
    for score, ex in ranked:
        if score <= 0 and picked:
            break
        if ex in picked:
            continue
        picked.append(ex)
        if len(picked) >= limit:
            break
    return picked


async def retrieve_style_examples(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int | None,
    fan_text: str | None,
    lang: str,
    followup: bool = False,
    limit: int | None = None,
    credentials: StudioOpenAiCredentials | None = None,
) -> list[dict]:
    if not settings.companion_style_rag_enabled:
        return []

    top_k = limit or int(settings.companion_style_rag_top_k)
    query = (fan_text or "").strip()
    if followup and not query:
        query = "follow up fan silent"

    db_candidates = await _load_db_candidates(
        session,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        lang=lang,
    )
    if db_candidates:
        ranked = await _rank_with_embeddings(
            query=query,
            candidates=db_candidates,
            credentials=credentials,
        )
        picked = _pick_top(
            fan_text=query,
            lang=lang,
            followup=followup,
            candidates=ranked,
            limit=top_k,
        )
        if picked:
            return picked

    static = list(_load_static_examples())
    if not static:
        return []
    return _pick_top(
        fan_text=query,
        lang=lang,
        followup=followup,
        candidates=static,
        limit=top_k,
    )


async def format_style_examples_block(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int | None,
    fan_text: str | None,
    lang: str,
    followup: bool = False,
    credentials: StudioOpenAiCredentials | None = None,
) -> str:
    examples = await retrieve_style_examples(
        session,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        fan_text=fan_text,
        lang=lang,
        followup=followup,
        credentials=credentials,
    )
    if not examples:
        return ""

    source = examples[0].get("source", "static")
    header = (
        "STYLE REFERENCE from your team's real chats"
        if source == "db"
        else "STYLE REFERENCE (senior chatter examples"
    )
    lines = [
        f"{header} — match TONE and LENGTH, never copy verbatim):",
    ]
    for i, ex in enumerate(examples, 1):
        lines.append(f"{i}. Fan: {ex['fan_message']}")
        lines.append(f"   Good reply: {ex['model_reply']}")
    lines.append(
        "Use these only as rhythm/vibe guides. Your reply must fit THIS transcript and CANON FACTS."
    )
    return "\n".join(lines) + "\n\n"
