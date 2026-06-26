"""Workflow: полный промпт для видео из motion-референса + still-референсов."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.services.studio_grok_motion import (
    grok_compose_boardstory_video_prompt,
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
from app.services.studio_workflow_boardstory import (
    BoardStoryImageSlot,
    boardstory_tag_rules_text,
    compute_boardstory_layout,
)
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


async def _describe_boardstory_slot(
    session: AsyncSession,
    *,
    owner_id: int,
    actor: User,
    slot: BoardStoryImageSlot,
    label: str,
    llm_credentials,
) -> str:
    if slot.generation_id is not None:
        img_bytes, img_mime = await _load_generation_still_bytes(
            session,
            owner_id=owner_id,
            generation_id=slot.generation_id,
            actor=actor,
        )
    elif slot.ref_id:
        img_bytes, img_mime = load_workflow_reference(owner_id, slot.ref_id)
    else:
        return f"{label}: (empty)"
    return await _describe_reference_block(
        label=label,
        image_bytes=img_bytes,
        image_media=img_mime,
        role=slot.role,
        notes=slot.description,
        credentials=llm_credentials,
    )


async def _estimate_boardstory_model_image_count(session: AsyncSession, *, model_id: int, actor: User) -> int:
    from app.services.studio_seedance_t2v import filter_model_images_for_seedance_video
    from app.services.workspace_model_access import require_studio_model_access

    sm = await require_studio_model_access(session, actor, model_id, load_images=True)
    return len(filter_model_images_for_seedance_video(list(sm.images), minimal=False, include_body=False))


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
    boardstory_mode: bool = False,
    clothing_ref: BoardStoryImageSlot | None = None,
    environment_ref: BoardStoryImageSlot | None = None,
) -> dict[str, Any]:
    """
    Анализ motion-видео + still-контекста → полный промпт для video generation.
    BoardStory: без первого кадра, промпт с @ImageN/@VideoN.
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

    grok_creds = grok_motion_studio_credentials()

    if boardstory_mode:
        n_model = await _estimate_boardstory_model_image_count(session, model_id=model_id, actor=actor)
        if n_model <= 0:
            raise RuntimeError(
                "У модели нет фото в кабинете. Добавьте turnaround и/или face."
            )
        layout = compute_boardstory_layout(
            n_model,
            has_clothing=clothing_ref is not None,
            has_environment=environment_ref is not None,
            n_other=len([r for r in references if (r.ref_id or "").strip()]),
        )
        tag_rules = boardstory_tag_rules_text(layout, has_motion=True)

        timeline = await motion_grok_timeline_from_video_path(
            video_path=vpath,
            model_profile_text=profile,
            first_frame_jpeg=None,
            first_frame_media="image/jpeg",
            credentials=grok_creds,
        )

        reference_blocks: list[str] = []
        if clothing_ref is not None:
            reference_blocks.append(
                await _describe_boardstory_slot(
                    session,
                    owner_id=owner_id,
                    actor=actor,
                    slot=clothing_ref,
                    label="CLOTHING_REFERENCE",
                    llm_credentials=llm_credentials,
                )
            )
        if environment_ref is not None:
            reference_blocks.append(
                await _describe_boardstory_slot(
                    session,
                    owner_id=owner_id,
                    actor=actor,
                    slot=environment_ref,
                    label="ENVIRONMENT_REFERENCE",
                    llm_credentials=llm_credentials,
                )
            )
        for i, ref in enumerate(references, 1):
            if not (ref.ref_id or "").strip():
                continue
            ref_bytes, ref_mime = load_workflow_reference(owner_id, ref.ref_id)
            reference_blocks.append(
                await _describe_reference_block(
                    label=f"WORKFLOW_REFERENCE_{i}",
                    image_bytes=ref_bytes,
                    image_media=ref_mime,
                    role=ref.role,
                    notes=ref.description,
                    credentials=llm_credentials,
                )
            )

        composed = await grok_compose_boardstory_video_prompt(
            motion_timeline=timeline.strip(),
            model_profile_text=profile,
            reference_tag_rules=tag_rules,
            reference_blocks=reference_blocks,
            user_notes=(user_notes or "").strip(),
            credentials=grok_creds,
            max_chars=int(settings.studio_seedance_t2v_prompt_max_chars or 6000),
        )

        return {
            "refined_prompt": composed.strip(),
            "motion_timeline": timeline.strip(),
            "reference_scene_description": None,
            "motion_video_file_id": mv_id,
            "studio_model_id": model_id,
            "boardstory_mode": True,
            "boardstory_layout": {
                "n_model_images": layout.n_model_images,
                "n_clothing_images": layout.n_clothing_images,
                "n_environment_images": layout.n_environment_images,
            },
        }

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

    reference_blocks = []
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
        "boardstory_mode": False,
    }
