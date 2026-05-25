"""Диспетчер фоновых задач студии (lazy import handlers из studio_routes)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudioJob, User


async def execute_studio_job(session: AsyncSession, job: StudioJob, user: User) -> dict[str, Any]:
    from app.api import studio_routes as sr

    handlers: dict[str, Any] = {
        "refine_prompt": sr._studio_job_execute_refine_prompt,
        "motion_first_frame": sr._studio_job_execute_motion_first_frame,
        "motion_render_video": sr._studio_job_execute_motion_render_video,
        "upscale": sr._studio_job_execute_upscale,
        "carousel": sr._studio_job_execute_carousel,
    }
    fn = handlers.get(job.job_type)
    if fn is None:
        raise RuntimeError(f"Неизвестный тип задачи: {job.job_type}")
    return await fn(session, job, user)
