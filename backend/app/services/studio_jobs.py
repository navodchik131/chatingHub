"""Очередь фоновых задач студии: создание, выполнение, опрос, WebSocket."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BACKEND_DIR
from app.db.models import StudioJob, StudioJobStatus, User
from app.db.session import SessionLocal
from app.services.realtime import hub

log = logging.getLogger(__name__)

STUDIO_JOB_TYPES = frozenset(
    {
        "refine_prompt",
        "motion_first_frame",
        "motion_compose_video_prompt",
        "motion_render_video",
        "upscale",
        "carousel",
    }
)

_JOBS_ROOT = BACKEND_DIR / "data" / "studio_jobs"


def studio_job_dir(job_id: int) -> Path:
    return _JOBS_ROOT / str(job_id)


def save_studio_job_file(job_id: int, name: str, data: bytes) -> str:
    """Сохраняет файл задачи; возвращает относительный путь от BACKEND_DIR."""
    d = studio_job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / name
    path.write_bytes(data)
    return path.relative_to(BACKEND_DIR).as_posix()


def load_studio_job_file(rel_path: str) -> bytes:
    path = (BACKEND_DIR / rel_path).resolve()
    if not str(path).startswith(str(BACKEND_DIR.resolve())):
        raise FileNotFoundError("invalid job file path")
    return path.read_bytes()


async def update_studio_job_params(
    session: AsyncSession,
    job: StudioJob,
    params: dict[str, Any],
) -> None:
    job.params_json = json.dumps(params, ensure_ascii=False)
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    await session.commit()


async def create_studio_job(
    session: AsyncSession,
    *,
    owner_id: int,
    actor_user_id: int,
    job_type: str,
    params: dict[str, Any],
) -> StudioJob:
    if job_type not in STUDIO_JOB_TYPES:
        raise ValueError(f"unknown studio job type: {job_type}")
    job = StudioJob(
        user_id=owner_id,
        actor_user_id=actor_user_id,
        job_type=job_type,
        status=StudioJobStatus.pending.value,
        params_json=json.dumps(params, ensure_ascii=False),
    )
    session.add(job)
    await session.flush()
    await session.commit()
    await session.refresh(job)
    return job


async def get_owned_studio_job(
    session: AsyncSession,
    job_id: int,
    owner_id: int,
) -> StudioJob | None:
    job = await session.get(StudioJob, job_id)
    if not job or job.user_id != owner_id:
        return None
    return job


def job_params(job: StudioJob) -> dict[str, Any]:
    try:
        raw = json.loads(job.params_json or "{}")
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def job_result_dict(job: StudioJob) -> dict[str, Any] | None:
    if not job.result_json:
        return None
    try:
        raw = json.loads(job.result_json)
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) else None


def schedule_studio_job(job_id: int) -> None:
    asyncio.create_task(_run_studio_job(job_id))


async def _run_studio_job(job_id: int) -> None:
    from app.services.studio_job_runner import execute_studio_job

    try:
        async with SessionLocal() as session:
            job = await session.get(StudioJob, job_id)
            if not job or job.status != StudioJobStatus.pending.value:
                return
            job.status = StudioJobStatus.running.value
            job.started_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()

        async with SessionLocal() as session:
            job = await session.get(StudioJob, job_id)
            if not job:
                return
            user = await session.get(User, job.actor_user_id)
            if not user:
                job.status = StudioJobStatus.failed.value
                job.error_message = "Пользователь задачи не найден"
                job.completed_at = datetime.now(timezone.utc)
                await session.commit()
                await _notify_job(job)
                return

            try:
                result = await execute_studio_job(session, job, user)
                job.status = StudioJobStatus.completed.value
                job.result_json = json.dumps(result, ensure_ascii=False)
                job.error_message = None
            except HTTPException as e:
                log.warning("studio job %s (%s) rejected: %s", job_id, job.job_type, e.detail)
                job.status = StudioJobStatus.failed.value
                detail = e.detail
                if isinstance(detail, str):
                    job.error_message = detail[:4000]
                else:
                    job.error_message = str(detail)[:4000]
                job.result_json = None
            except Exception as e:
                log.exception("studio job %s (%s) failed", job_id, job.job_type)
                job.status = StudioJobStatus.failed.value
                job.error_message = (str(e) or type(e).__name__)[:4000]
                job.result_json = None
            job.completed_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await _notify_job(job)
    except Exception:
        log.exception("studio job runner crashed for job_id=%s", job_id)
        try:
            async with SessionLocal() as session:
                job = await session.get(StudioJob, job_id)
                if job and job.status == StudioJobStatus.running.value:
                    job.status = StudioJobStatus.failed.value
                    job.error_message = "Внутренняя ошибка выполнения задачи"
                    job.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                    await _notify_job(job)
        except Exception:
            log.exception("failed to mark studio job %s as failed", job_id)


async def _notify_job(job: StudioJob) -> None:
    generation_id: int | None = None
    result = job_result_dict(job)
    if result:
        raw_gid = result.get("generation_id")
        if isinstance(raw_gid, int):
            generation_id = raw_gid
        elif isinstance(raw_gid, str) and raw_gid.isdigit():
            generation_id = int(raw_gid)
    if generation_id is None:
        ph = job_params(job).get("placeholder_generation_id")
        if isinstance(ph, int):
            generation_id = ph
        elif isinstance(ph, str) and ph.isdigit():
            generation_id = int(ph)

    await hub.broadcast_user(
        job.user_id,
        {
            "type": "studio_job",
            "job_id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "error_message": job.error_message,
            "generation_id": generation_id,
        },
    )
    if generation_id is not None:
        await hub.broadcast_user(
            job.user_id,
            {
                "type": "studio_generation",
                "generation_id": generation_id,
                "status": job.status,
                "job_id": job.id,
            },
        )
