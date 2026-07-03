"""Персистентная очередь companion bot (PostgreSQL/SQLite)."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CompanionJob, CompanionJobKind, CompanionJobStatus
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

_POLL_SEC = 2.0
_MAX_ATTEMPTS = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def enqueue_companion_reply(
    session: AsyncSession,
    *,
    owner_user_id: int,
    conv_id: int,
    trigger_message_id: int,
) -> CompanionJob:
    job = CompanionJob(
        owner_user_id=owner_user_id,
        conversation_id=conv_id,
        kind=CompanionJobKind.reply,
        trigger_message_id=trigger_message_id,
        run_after=_utcnow(),
        status=CompanionJobStatus.pending,
    )
    session.add(job)
    await session.flush()
    log.info(
        "companion job enqueued kind=reply conv=%s trigger=%s job=%s",
        conv_id,
        trigger_message_id,
        job.id,
    )
    return job


async def enqueue_companion_followup(
    session: AsyncSession,
    *,
    owner_user_id: int,
    conv_id: int,
    after_outbound_message_id: int,
) -> CompanionJob:
    delay = random.uniform(
        settings.companion_followup_delay_min_sec,
        settings.companion_followup_delay_max_sec,
    )
    job = CompanionJob(
        owner_user_id=owner_user_id,
        conversation_id=conv_id,
        kind=CompanionJobKind.followup,
        trigger_message_id=after_outbound_message_id,
        run_after=_utcnow() + timedelta(seconds=delay),
        status=CompanionJobStatus.pending,
    )
    session.add(job)
    await session.flush()
    log.info(
        "companion job enqueued kind=followup conv=%s outbound=%s job=%s run_after=%ss",
        conv_id,
        after_outbound_message_id,
        job.id,
        int(delay),
    )
    return job


async def enqueue_companion_send(
    session: AsyncSession,
    *,
    owner_user_id: int,
    conv_id: int,
    trigger_message_id: int,
    event_id: int,
    delay_sec: float,
    followup: bool = False,
) -> CompanionJob:
    payload = json.dumps({"event_id": event_id, "followup": followup}, ensure_ascii=False)
    job = CompanionJob(
        owner_user_id=owner_user_id,
        conversation_id=conv_id,
        kind=CompanionJobKind.send,
        trigger_message_id=trigger_message_id,
        payload_json=payload,
        run_after=_utcnow() + timedelta(seconds=max(0.0, delay_sec)),
        status=CompanionJobStatus.pending,
    )
    session.add(job)
    await session.flush()
    log.info(
        "companion job enqueued kind=send conv=%s event=%s job=%s delay=%ss",
        conv_id,
        event_id,
        job.id,
        int(delay_sec),
    )
    return job


async def _claim_due_jobs(session: AsyncSession, *, limit: int = 8) -> list[CompanionJob]:
    now = _utcnow()
    ids = list(
        (
            await session.scalars(
                select(CompanionJob.id)
                .where(
                    CompanionJob.status == CompanionJobStatus.pending,
                    CompanionJob.run_after <= now,
                )
                .order_by(CompanionJob.run_after.asc(), CompanionJob.id.asc())
                .limit(limit)
            )
        ).all()
    )
    if not ids:
        return []

    await session.execute(
        update(CompanionJob)
        .where(
            CompanionJob.id.in_(ids),
            CompanionJob.status == CompanionJobStatus.pending,
        )
        .values(
            status=CompanionJobStatus.running,
            started_at=now,
            attempts=CompanionJob.attempts + 1,
        )
    )
    await session.commit()
    return list(
        (
            await session.scalars(select(CompanionJob).where(CompanionJob.id.in_(ids)))
        ).all()
    )


async def _finish_job(
    session: AsyncSession,
    job: CompanionJob,
    *,
    ok: bool,
    error: str | None = None,
) -> None:
    row = await session.get(CompanionJob, job.id)
    if not row:
        return
    if ok:
        row.status = CompanionJobStatus.done
        row.completed_at = _utcnow()
        row.last_error = None
    elif row.attempts >= _MAX_ATTEMPTS:
        row.status = CompanionJobStatus.failed
        row.completed_at = _utcnow()
        row.last_error = (error or "")[:2000] or None
    else:
        row.status = CompanionJobStatus.pending
        row.run_after = _utcnow() + timedelta(seconds=15 * row.attempts)
        row.last_error = (error or "")[:2000] or None
    await session.commit()


async def _execute_job(job: CompanionJob) -> None:
    from app.services.companion_bot.orchestrator import (
        run_companion_followup_job,
        run_companion_reply_job,
        run_companion_send_job,
    )

    if job.kind == CompanionJobKind.reply:
        await run_companion_reply_job(
            owner_user_id=job.owner_user_id,
            conv_id=job.conversation_id,
            trigger_message_id=job.trigger_message_id,
        )
    elif job.kind == CompanionJobKind.followup:
        await run_companion_followup_job(
            owner_user_id=job.owner_user_id,
            conv_id=job.conversation_id,
            after_outbound_message_id=job.trigger_message_id,
        )
    elif job.kind == CompanionJobKind.send:
        payload: dict = {}
        if job.payload_json:
            try:
                parsed = json.loads(job.payload_json)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                pass
        event_id = int(payload.get("event_id") or 0)
        followup = bool(payload.get("followup"))
        if event_id <= 0:
            raise ValueError("send job missing event_id")
        await run_companion_send_job(
            owner_user_id=job.owner_user_id,
            conv_id=job.conversation_id,
            trigger_message_id=job.trigger_message_id,
            event_id=event_id,
            followup=followup,
        )
    else:
        raise ValueError(f"unknown job kind {job.kind}")


async def process_due_companion_jobs() -> int:
    async with SessionLocal() as session:
        jobs = await _claim_due_jobs(session)
    if not jobs:
        return 0

    for job in jobs:
        try:
            await _execute_job(job)
            async with SessionLocal() as session:
                await _finish_job(session, job, ok=True)
        except Exception as e:
            log.exception("companion job failed id=%s kind=%s", job.id, job.kind.value)
            async with SessionLocal() as session:
                await _finish_job(session, job, ok=False, error=str(e))
    return len(jobs)


async def companion_job_worker_loop() -> None:
    log.info("Companion job worker started (poll=%ss)", _POLL_SEC)
    while True:
        try:
            n = await process_due_companion_jobs()
            if n:
                log.debug("companion jobs processed=%s", n)
        except Exception:
            log.exception("companion job worker tick failed")
        await asyncio.sleep(_POLL_SEC)
