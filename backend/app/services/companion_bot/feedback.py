"""Nightly-агрегация оценок ответов AI-компаньона."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    BotResponseEvent,
    BotResponseEventStatus,
    CompanionFeedbackReport,
    Conversation,
    User,
)
from app.db.session import SessionLocal
from app.services.studio_openai import _chat_completion_text

log = logging.getLogger(__name__)


def _day_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


async def _owner_ids_with_events(
    session: AsyncSession, *, since: datetime, until: datetime
) -> list[int]:
    stmt = (
        select(Conversation.user_id)
        .join(BotResponseEvent, BotResponseEvent.conversation_id == Conversation.id)
        .where(
            BotResponseEvent.created_at >= since,
            BotResponseEvent.created_at < until,
        )
        .distinct()
    )
    return [int(x) for x in (await session.scalars(stmt)).all()]


async def _build_report_for_owner(
    session: AsyncSession,
    *,
    owner_id: int,
    since: datetime,
    until: datetime,
    report_day: date,
) -> CompanionFeedbackReport | None:
    stmt = (
        select(BotResponseEvent)
        .join(Conversation, BotResponseEvent.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == owner_id,
            BotResponseEvent.created_at >= since,
            BotResponseEvent.created_at < until,
        )
        .order_by(BotResponseEvent.id.asc())
    )
    events = list((await session.scalars(stmt)).all())
    if not events:
        return None

    sent = [e for e in events if e.status == BotResponseEventStatus.sent]
    pos = [e for e in sent if e.operator_rating == 1]
    neg = [e for e in sent if e.operator_rating == -1]
    unrated = [e for e in sent if e.operator_rating in (None, 0)]

    stats = {
        "total_events": len(events),
        "sent": len(sent),
        "draft": sum(1 for e in events if e.status == BotResponseEventStatus.draft),
        "failed": sum(1 for e in events if e.status == BotResponseEventStatus.failed),
        "rejected": sum(1 for e in events if e.status == BotResponseEventStatus.rejected),
        "rating_positive": len(pos),
        "rating_negative": len(neg),
        "rating_unrated": len(unrated),
        "edited_before_send": sum(1 for e in sent if e.was_edited),
    }

    lines = [
        f"## AI-компаньон · {report_day.isoformat()}",
        "",
        f"- Отправлено: **{stats['sent']}** · 👍 {stats['rating_positive']} · 👎 {stats['rating_negative']} · без оценки {stats['rating_unrated']}",
        f"- Черновики: {stats['draft']} · ошибки: {stats['failed']} · отклонено: {stats['rejected']}",
        f"- Отредактировано оператором перед отправкой: {stats['edited_before_send']}",
        "",
    ]

    if pos:
        lines.append("### Что зашло (👍)")
        for e in pos[:5]:
            snippet = (e.sent_text or e.draft_text or "").strip().replace("\n", " ")[:180]
            lines.append(f"- {snippet}")
        lines.append("")

    if neg:
        lines.append("### Что не зашло (👎)")
        for e in neg[:5]:
            snippet = (e.sent_text or e.draft_text or "").strip().replace("\n", " ")[:180]
            lines.append(f"- {snippet}")
        lines.append("")

    ai_block = ""
    if (settings.openai_api_key or "").strip() and (pos or neg):
        sample = "\n".join(
            [
                *(f"GOOD: {(e.sent_text or e.draft_text or '')[:200]}" for e in pos[:3]),
                *(f"BAD: {(e.sent_text or e.draft_text or '')[:200]}" for e in neg[:3]),
            ]
        )
        try:
            ai_block = await _chat_completion_text(
                model=(settings.openai_studio_model or "").strip() or "gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты аналитик чат-бота companion. По примерам GOOD/BAD дай 3–5 "
                            "коротких правил стиля на русском (markdown bullets). "
                            "Только наблюдения из примеров, без выдумок."
                        ),
                    },
                    {"role": "user", "content": sample[:6000]},
                ],
                max_tokens=600,
                temperature=0.25,
                timeout_seconds=60.0,
            )
        except Exception as e:
            log.warning("companion feedback AI summary failed owner=%s: %s", owner_id, e)

    if ai_block.strip():
        lines.append("### Рекомендации для промпта")
        lines.append(ai_block.strip())
        lines.append("")

    content = "\n".join(lines).strip()
    report_dt = _day_start_utc(report_day)
    existing = await session.scalar(
        select(CompanionFeedbackReport).where(
            CompanionFeedbackReport.user_id == owner_id,
            CompanionFeedbackReport.report_date == report_dt,
        )
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.content = content
        existing.stats_json = json.dumps(stats, ensure_ascii=False)
        existing.updated_at = now
        return existing

    row = CompanionFeedbackReport(
        user_id=owner_id,
        report_date=report_dt,
        content=content,
        stats_json=json.dumps(stats, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    return row


async def run_companion_feedback_reports(*, for_day: date | None = None) -> int:
    """Сгенерировать отчёты за календарный день UTC. Возвращает число отчётов."""
    day = for_day or (datetime.now(timezone.utc).date() - timedelta(days=1))
    since = _day_start_utc(day)
    until = since + timedelta(days=1)
    n = 0
    async with SessionLocal() as session:
        owner_ids = await _owner_ids_with_events(session, since=since, until=until)
        for oid in owner_ids:
            user = await session.get(User, oid)
            if not user or not user.is_active:
                continue
            row = await _build_report_for_owner(
                session,
                owner_id=oid,
                since=since,
                until=until,
                report_day=day,
            )
            if row:
                n += 1
        await session.commit()
    log.info("companion feedback reports: day=%s count=%s", day.isoformat(), n)
    return n


async def companion_feedback_loop() -> None:
    await asyncio.sleep(300)
    interval_h = max(1.0, float(settings.companion_feedback_interval_hours or 24))
    while True:
        try:
            await run_companion_feedback_reports()
        except Exception:
            log.exception("companion feedback loop failed")
        await asyncio.sleep(interval_h * 3600)


async def list_feedback_reports(
    session: AsyncSession, *, owner_id: int, limit: int = 14
) -> list[CompanionFeedbackReport]:
    lim = max(1, min(limit, 60))
    return list(
        (
            await session.scalars(
                select(CompanionFeedbackReport)
                .where(CompanionFeedbackReport.user_id == owner_id)
                .order_by(CompanionFeedbackReport.report_date.desc())
                .limit(lim)
            )
        ).all()
    )
