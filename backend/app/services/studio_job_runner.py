"""Диспетчер фоновых задач студии (lazy import handlers из studio_routes)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudioJob, User


async def _execute_motion_control_dress(session: AsyncSession, job: StudioJob, user: User) -> dict:
    from app.api.studio_motion_control_routes import execute_motion_control_dress

    return await execute_motion_control_dress(session, job, user)


async def _execute_motion_control_turnaround(session: AsyncSession, job: StudioJob, user: User) -> dict:
    from app.api.studio_motion_control_routes import execute_motion_control_turnaround

    return await execute_motion_control_turnaround(session, job, user)


async def execute_studio_job(session: AsyncSession, job: StudioJob, user: User) -> dict[str, Any]:
    from app.api import studio_routes as sr

    handlers: dict[str, Any] = {
        "refine_prompt": sr._studio_job_execute_refine_prompt,
        "motion_first_frame": sr._studio_job_execute_motion_first_frame,
        "motion_video_outline": sr._studio_job_execute_motion_video_outline,
        "motion_compose_video_prompt": sr._studio_job_execute_motion_compose_video_prompt,
        "workflow_compose_video_prompt": sr._studio_job_execute_workflow_compose_video_prompt,
        "motion_render_video": sr._studio_job_execute_motion_render_video,
        "shot_batch_render": sr._studio_job_execute_shot_batch_render,
        "video_upscale": sr._studio_job_execute_video_upscale,
        "upscale": sr._studio_job_execute_upscale,
        "carousel": sr._studio_job_execute_carousel,
        "model_bootstrap_face_merge": sr._studio_job_execute_model_bootstrap_face_merge,
        "model_bootstrap_body_compose": sr._studio_job_execute_model_bootstrap_body_compose,
        "model_bootstrap_sheet": sr._studio_job_execute_model_bootstrap_sheet,
        "seedance_director_generate": sr._studio_job_execute_seedance_director_generate,
        "motion_control_dress": _execute_motion_control_dress,
        "motion_control_turnaround": _execute_motion_control_turnaround,
    }
    fn = handlers.get(job.job_type)
    if fn is None:
        raise RuntimeError(f"Неизвестный тип задачи: {job.job_type}")
    return await fn(session, job, user)
