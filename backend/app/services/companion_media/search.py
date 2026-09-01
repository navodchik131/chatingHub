"""Семантический поиск медиа для companion bot с дедупом и раскрытием паков."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CompanionMediaAsset, CompanionMediaPack
from app.services.companion_bot.style_embeddings import (
    cosine_similarity,
    embed_texts,
    parse_embedding_json,
)
from app.services.companion_media.library import asset_to_dict, get_sent_asset_ids
from app.services.studio_keys import load_owner_studio_billing, studio_llm_credentials

log = logging.getLogger(__name__)

_CANDIDATE_LIMIT = 200


def expand_pack_assets(
    *,
    pack_assets: list[CompanionMediaAsset],
    matched_asset_id: int | None,
    sent_asset_ids: set[int],
    max_send_count: int,
) -> list[CompanionMediaAsset]:
    """Из серии берём до max_send_count кадров, начиная с совпавшего; уже отправленные пропускаем."""
    available = [
        a
        for a in sorted(pack_assets, key=lambda x: (x.sort_order, x.id))
        if a.status == "active" and a.id not in sent_asset_ids
    ]
    if not available:
        return []

    if matched_asset_id is not None:
        idx = next((i for i, a in enumerate(available) if a.id == matched_asset_id), None)
        if idx is not None:
            ordered = available[idx:] + available[:idx]
        else:
            ordered = available
    else:
        ordered = available

    return ordered[: max(1, min(max_send_count, len(ordered)))]


def rank_assets_by_embedding(
    *,
    query_vec: list[float],
    candidates: list[CompanionMediaAsset],
    limit: int = 5,
) -> list[tuple[CompanionMediaAsset, float]]:
    scored: list[tuple[CompanionMediaAsset, float]] = []
    for asset in candidates:
        vec = parse_embedding_json(asset.embedding_json)
        if not vec:
            continue
        scored.append((asset, cosine_similarity(query_vec, vec)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


async def pick_companion_media(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int,
    query: str,
    conversation_id: int | None = None,
    expand_pack: bool = True,
    tier: str | None = None,
) -> dict[str, Any]:
    """
    Подбор медиа по семантическому запросу.
    Если лучший кандидат в паке — возвращаем серию (до max_send_count).
    Уже отправленные этому conversation_id исключаются.
    """
    q = (query or "").strip()
    if not q:
        return {"assets": [], "matched_asset_id": None, "pack_id": None, "reason": "empty_query"}

    sent_ids: set[int] = set()
    if conversation_id is not None:
        sent_ids = await get_sent_asset_ids(session, conversation_id=conversation_id)

    asset_q = select(CompanionMediaAsset).where(
        CompanionMediaAsset.user_id == owner_id,
        CompanionMediaAsset.studio_model_id == studio_model_id,
        CompanionMediaAsset.status == "active",
    )
    if tier:
        asset_q = asset_q.where(CompanionMediaAsset.tier == tier)
    if sent_ids:
        asset_q = asset_q.where(CompanionMediaAsset.id.not_in(sent_ids))

    candidates = list((await session.scalars(asset_q.limit(_CANDIDATE_LIMIT))).all())
    if not candidates:
        return {
            "assets": [],
            "matched_asset_id": None,
            "pack_id": None,
            "reason": "no_available_assets",
        }

    with_emb = [a for a in candidates if parse_embedding_json(a.embedding_json)]
    matched: CompanionMediaAsset | None = None
    score = 0.0

    if with_emb:
        billing = await load_owner_studio_billing(session, owner_id)
        credentials = studio_llm_credentials(billing)
        try:
            q_vecs = await embed_texts([q], credentials=credentials)
            q_vec = q_vecs[0] if q_vecs else []
        except Exception as e:
            log.warning("companion media search embed query failed: %s", e)
            q_vec = []

        if q_vec:
            ranked = rank_assets_by_embedding(query_vec=q_vec, candidates=with_emb, limit=1)
            if ranked:
                matched, score = ranked[0]

    # Fallback без embedding: простой match по title/description/tags
    if matched is None:
        low = q.lower()
        for asset in candidates:
            blob = " ".join(
                filter(
                    None,
                    [
                        asset.title or "",
                        asset.description or "",
                        asset.tags_json or "",
                    ],
                )
            ).lower()
            if low in blob or any(tok in blob for tok in low.split() if len(tok) > 2):
                matched = asset
                score = 0.1
                break
        if matched is None:
            matched = candidates[0]
            score = 0.0

    pack_names: dict[int, str] = {}
    result_assets: list[CompanionMediaAsset] = [matched]

    if expand_pack and matched.pack_id:
        pack = await session.get(CompanionMediaPack, matched.pack_id)
        if pack and pack.status == "active":
            pack_assets = list(
                (
                    await session.scalars(
                        select(CompanionMediaAsset).where(
                            CompanionMediaAsset.pack_id == pack.id,
                            CompanionMediaAsset.status == "active",
                        )
                    )
                ).all()
            )
            result_assets = expand_pack_assets(
                pack_assets=pack_assets,
                matched_asset_id=matched.id,
                sent_asset_ids=sent_ids,
                max_send_count=pack.max_send_count,
            )
            pack_names[pack.id] = pack.name

    out = []
    for a in result_assets:
        pack_name = pack_names.get(a.pack_id) if a.pack_id else None
        row = asset_to_dict(a, pack_name=pack_name, owner_id=owner_id)
        row["match_score"] = round(score, 4) if a.id == matched.id else None
        out.append(row)

    return {
        "assets": out,
        "matched_asset_id": matched.id,
        "pack_id": matched.pack_id,
        "reason": "ok",
    }
