"""Feedback loop для style RAG: понижение quality_score при 👎."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BotResponseEvent, CompanionStyleExample, Message

log = logging.getLogger(__name__)

_DOWNRANK = 0.35
_FLOOR = 0.15


async def downrank_style_example_for_negative_rating(
    session: AsyncSession,
    *,
    event: BotResponseEvent,
) -> bool:
    if not event.outbound_message_id:
        return False
    outbound = await session.get(Message, event.outbound_message_id)
    if not outbound:
        return False

    row = await session.scalar(
        select(CompanionStyleExample).where(
            CompanionStyleExample.source_outbound_message_id == outbound.id
        )
    )
    if not row:
        return False

    prev = float(row.quality_score or 1.0)
    row.quality_score = max(_FLOOR, prev - _DOWNRANK)
    log.info(
        "companion style downrank example=%s outbound=%s score=%.2f->%.2f",
        row.id,
        outbound.id,
        prev,
        row.quality_score,
    )
    return True
