"""Workflow: полный промпт для видео из motion-референса + still-референсов."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.services.studio_grok_motion import (
    grok_compose_workflow_video_prompt,
    grok_motion_api_configured,
    grok_motion_studio_credentials,
)
from app.services.studio_motion_grok_pipeline import (
    describe_motion_still_for_ui,
    extract_video_first_frame_or_raise,
    motion_grok_timeline_from_video_path,
)
from app.services.studio_motion_video import resolve_motion_video_file
from app.services.studio_openai import describe_reference_image_openai
from app.services.studio_workflow_refs import load_workflow_reference
from app.services.studio_workflow_resolver import WorkflowReferenceItem

log = logging.getLogger(__name__)


async def _load_generation_still_bytes(
    session: AsyncSession,
    *,
    owner_id: int,
    generation_id: int,
    actor: User,
) -> tuple[bytes, str]:
    from app.api.studio_routes import _load_owned_generation_still_for_motion

    _row, raw, mime = await _load_owned_generation_still_for_motion(
        session,
        owner_id=owner_id,
        generation_id=generation_id,
        actor=actor,
    )
    return raw, mime


async def _describe_reference_block(
    *,
    label: str,
    image_bytes: bytes,
    image_media: str,
    role: str,
    notes: str,
    credentials,
) -> str:
    role_s = (role or "").strip()
    notes_s = (notes or "").strip()
    try:
        body = await describe_reference_image_openai(
            image_bytes=image_bytes,
            image_media_type=image_media,
            hairstyle_from_pose_reference=True,
            credentials=credentials,
        )
    except RuntimeError as e:
        log.warning("workflow video prompt: describe %s failed: %s", label, e)
        body = notes_s or role_s or f"{label} image attached"
    parts = [f"{label}:"]
    if role_s:
        parts.append(f"  Role: {role_s}")
    if notes_s:
        parts.append(f"  Notes: {notes_s}")
    parts.append(f"  Visual: {body.strip()}")
    return "\n".join(parts)


async def compose_workflow_video_generation_prompt(
    session: AsyncSession,
    *,
    owner_id: int,
    actor: User,
    model_id: int,
    motion_video_file_id: str,
    first_frame_generation_id: int | None,
    sheet_generation_id: int | None,
    references: list[WorkflowReferenceItem],
    user_notes: str,
    llm_credentials,
) -> dict[str, Any]:
    """
    Анализ motion-видео + still-контекста → полный промпт для video generation.
    Возвращает dict для job result (refined_prompt, motion_timeline, …).
    """
    if not grok_motion_api_configured():
        raise RuntimeError(
            "Grok не настроен: задайте GROK_API_KEY для генерации промпта по видео."
        )

    mv_id = (motion_video_file_id or "").strip()
    vpath = resolve_motion_video_file(owner_id, mv_id)
    if vpath is None:
        raise RuntimeError("Motion-видео не найдено. Загрузите снова.")

    from app.services.workspace_model_access import require_studio_model_access

    sm = await require_studio_model_access(session, actor, model_id, load_images=True)
    profile = (sm.profile_text or "").strip() or ""

    first_frame: bytes
    first_frame_media = "image/jpeg"
    if first_frame_generation_id is not None:
        first_frame, first_frame_media = await _load_generation_still_bytes(
            session,
            owner_id=owner_id,
            generation_id=first_frame_generation_id,
            actor=actor,
        )
    else:
        first_frame, first_frame_media = await extract_video_first_frame_or_raise(vpath)

    grok_creds = grok_motion_studio_credentials()
    timeline = await motion_grok_timeline_from_video_path(
        video_path=vpath,
        model_profile_text=profile,
        first_frame_jpeg=first_frame,
        first_frame_media=first_frame_media,
        credentials=grok_creds,
    )

    first_frame_scene: str | None = None
    try:
        first_frame_scene = (
            await describe_motion_still_for_ui(
                image_bytes=first_frame,
                image_media_type=first_frame_media,
                lock_hairstyle=True,
                credentials=llm_credentials,
            )
        ).strip() or None
    except RuntimeError as e:
        log.warning("workflow video prompt: first frame scene skipped: %s", e)

    reference_blocks: list[str] = []
    if first_frame_scene:
        reference_blocks.append(f"OPENING_FRAME_SCENE:\n{first_frame_scene}")

    if sheet_generation_id is not None:
        sheet_bytes, sheet_mime = await _load_generation_still_bytes(
            session,
            owner_id=owner_id,
            generation_id=sheet_generation_id,
            actor=actor,
        )
        sheet_block = await _describe_reference_block(
            label="CHARACTER_TURNAROUND_SHEET",
            image_bytes=sheet_bytes,
            image_media=sheet_mime,
            role="character turnaround / identity reference",
            notes="Multi-view character sheet for consistent face, body, hair, wardrobe.",
            credentials=llm_credentials,
        )
        reference_blocks.append(sheet_block)

    for i, ref in enumerate(references, 1):
        if not (ref.ref_id or "").strip():
            continue
        try:
            ref_bytes, ref_mime = load_workflow_reference(owner_id, ref.ref_id)
        except (FileNotFoundError, ValueError) as e:
            raise RuntimeError(
                f"Референс «{ref.file_name or ref.ref_id}» не найден"
            ) from e
        ref_block = await _describe_reference_block(
            label=f"WORKFLOW_REFERENCE_{i}",
            image_bytes=ref_bytes,
            image_media=ref_mime,
            role=ref.role,
            notes=ref.description,
            credentials=llm_credentials,
        )
        reference_blocks.append(ref_block)

    composed = await grok_compose_workflow_video_prompt(
        motion_timeline=timeline.strip(),
        model_profile_text=profile,
        first_frame_jpeg=first_frame,
        first_frame_media=first_frame_media,
        first_frame_scene=first_frame_scene,
        reference_blocks=reference_blocks,
        user_notes=(user_notes or "").strip(),
        credentials=grok_creds,
        max_chars=int(settings.studio_seedance_t2v_prompt_max_chars or 6000),
    )

    return {
        "refined_prompt": composed.strip(),
        "motion_timeline": timeline.strip(),
        "reference_scene_description": first_frame_scene,
        "motion_video_file_id": mv_id,
        "studio_model_id": model_id,
    }
