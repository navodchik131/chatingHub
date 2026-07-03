"""Индексация style RAG из реальных диалогов в БД."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    BotResponseEvent,
    CompanionStyleExample,
    Conversation,
    Message,
    MessageDirection,
)
from app.db.session import SessionLocal
from app.services.companion_bot.style_embeddings import embed_texts
from app.services.companion_bot.style_extract import StylePairCandidate, extract_pairs_from_messages
from app.services.studio_openai import StudioOpenAiCredentials

log = logging.getLogger(__name__)


async def _load_bot_ratings(
    session: AsyncSession, outbound_ids: list[int]
) -> dict[int, int | None]:
    if not outbound_ids:
        return {}
    rows = await session.execute(
        select(BotResponseEvent.outbound_message_id, BotResponseEvent.operator_rating).where(
            BotResponseEvent.outbound_message_id.in_(outbound_ids)
        )
    )
    return {int(mid): rating for mid, rating in rows.all() if mid is not None}


async def _upsert_pair(
    session: AsyncSession,
    *,
    owner_id: int,
    pair: StylePairCandidate,
    embedding: list[float] | None,
) -> bool:
    existing = await session.scalar(
        select(CompanionStyleExample.id).where(
            CompanionStyleExample.source_outbound_message_id == pair.source_outbound_message_id
        )
    )
    if existing:
        return False

    row = CompanionStyleExample(
        user_id=owner_id,
        studio_model_id=pair.studio_model_id,
        fan_message=pair.fan_message,
        model_reply=pair.model_reply,
        lang=pair.lang,
        tags_json=json.dumps(list(pair.tags), ensure_ascii=False) if pair.tags else None,
        source_conversation_id=pair.source_conversation_id,
        source_inbound_message_id=pair.source_inbound_message_id,
        source_outbound_message_id=pair.source_outbound_message_id,
        quality_score=pair.quality_score,
        is_human=pair.is_human,
        embedding_json=json.dumps(embedding) if embedding else None,
    )
    session.add(row)
    return True


async def _trim_owner_index(session: AsyncSession, owner_id: int) -> int:
    cap = int(settings.companion_style_index_max_pairs_per_owner)
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(CompanionStyleExample)
            .where(CompanionStyleExample.user_id == owner_id)
        )
        or 0
    )
    if total <= cap:
        return 0

    overflow = total - cap
    stale_ids = list(
        (
            await session.scalars(
                select(CompanionStyleExample.id)
                .where(CompanionStyleExample.user_id == owner_id)
                .order_by(CompanionStyleExample.quality_score.asc(), CompanionStyleExample.id.asc())
                .limit(overflow)
            )
        ).all()
    )
    if not stale_ids:
        return 0
    for sid in stale_ids:
        row = await session.get(CompanionStyleExample, sid)
        if row:
            await session.delete(row)
    return len(stale_ids)


async def rebuild_style_index_for_owner(
    session: AsyncSession,
    *,
    owner_id: int,
    credentials: StudioOpenAiCredentials | None = None,
) -> dict[str, int]:
    lookback_days = int(settings.companion_style_index_lookback_days)
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    max_convs = int(settings.companion_style_index_max_conversations_per_run)

    conv_ids = list(
        (
            await session.scalars(
                select(Conversation.id)
                .where(
                    Conversation.user_id == owner_id,
                    Conversation.updated_at >= since,
                )
                .order_by(Conversation.updated_at.desc())
                .limit(max_convs)
            )
        ).all()
    )

    added = 0
    scanned = 0
    pairs_found = 0
    pending_pairs: list[StylePairCandidate] = []

    async def _flush_embeddings() -> None:
        nonlocal added
        if not pending_pairs:
            return
        texts = [p.fan_message for p in pending_pairs]
        vectors: list[list[float]] = []
        try:
            vectors = await embed_texts(texts, credentials=credentials)
        except Exception as e:
            log.warning("style index embed batch failed owner=%s: %s", owner_id, e)
            vectors = [[] for _ in pending_pairs]

        for pair, vec in zip(pending_pairs, vectors):
            emb = vec if vec else None
            if await _upsert_pair(session, owner_id=owner_id, pair=pair, embedding=emb):
                added += 1
        pending_pairs.clear()

    for conv_id in conv_ids:
        conv = await session.get(Conversation, conv_id)
        if not conv:
            continue
        scanned += 1
        messages = list(
            (
                await session.scalars(
                    select(Message)
                    .where(Message.conversation_id == conv_id)
                    .order_by(Message.id.asc())
                    .limit(400)
                )
            ).all()
        )
        if len(messages) < 2:
            continue

        outbound_ids = [m.id for m in messages if m.direction == MessageDirection.outbound]
        bot_ratings = await _load_bot_ratings(session, outbound_ids)
        pairs = extract_pairs_from_messages(messages, conv=conv, bot_ratings=bot_ratings)
        pairs_found += len(pairs)
        for pair in pairs:
            pending_pairs.append(pair)
            if len(pending_pairs) >= 32:
                await _flush_embeddings()

    await _flush_embeddings()
    trimmed = await _trim_owner_index(session, owner_id)
    await session.commit()

    return {
        "conversations_scanned": scanned,
        "pairs_found": pairs_found,
        "pairs_added": added,
        "pairs_trimmed": trimmed,
    }


async def _owner_ids_to_index(session: AsyncSession) -> list[int]:
    lookback_days = int(settings.companion_style_index_lookback_days)
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    rows = await session.scalars(
        select(Conversation.user_id)
        .where(Conversation.updated_at >= since)
        .distinct()
    )
    return [int(x) for x in rows.all()]


async def rebuild_style_index(*, owner_id: int | None = None) -> dict[str, int]:
    totals = {
        "owners": 0,
        "conversations_scanned": 0,
        "pairs_found": 0,
        "pairs_added": 0,
        "pairs_trimmed": 0,
    }
    async with SessionLocal() as session:
        owner_ids = [owner_id] if owner_id is not None else await _owner_ids_to_index(session)

    for oid in owner_ids:
        async with SessionLocal() as session:
            try:
                stats = await rebuild_style_index_for_owner(session, owner_id=oid)
            except Exception:
                log.exception("style index rebuild failed owner=%s", oid)
                continue
        totals["owners"] += 1
        for k in ("conversations_scanned", "pairs_found", "pairs_added", "pairs_trimmed"):
            totals[k] += int(stats.get(k, 0))
        log.info("companion style index owner=%s stats=%s", oid, stats)

    log.info("companion style index done totals=%s", totals)
    return totals


async def style_index_is_empty() -> bool:
    async with SessionLocal() as session:
        n = int(
            await session.scalar(select(func.count()).select_from(CompanionStyleExample)) or 0
        )
        return n == 0


async def companion_style_index_loop() -> None:
    interval_h = max(1.0, float(settings.companion_style_index_interval_hours or 6))
    first = True
    while True:
        try:
            if first and settings.companion_style_index_on_startup:
                if await style_index_is_empty():
                    log.info("companion style index empty — running initial rebuild")
                    await rebuild_style_index()
                else:
                    log.info("companion style index already populated — skip startup rebuild")
            elif not first:
                await rebuild_style_index()
        except Exception:
            log.exception("companion style index loop failed")
        first = False
        await asyncio.sleep(interval_h * 3600.0)
