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
    boardstory_clothing_env_swap_mode,
    boardstory_tag_rules_text,
    boardstory_video_only_swap_mode,
    build_boardstory_clothing_env_swap_prompt,
    build_boardstory_video_only_swap_prompt,
    compute_boardstory_layout,
    filter_model_images_for_boardstory,
    finalize_boardstory_t2v_prompt,
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


async def _validate_boardstory_model_refs(session: AsyncSession, *, model_id: int, actor: User) -> None:
    from app.services.workspace_model_access import require_studio_model_access

    sm = await require_studio_model_access(session, actor, model_id, load_images=True)
    if not filter_model_images_for_boardstory(list(sm.images)):
        raise RuntimeError(
            "У модели нет фото для BoardStory (лицо, развёртка или тело). "
            "Добавьте снимки в кабинете модели."
        )


async def _estimate_boardstory_model_image_count(session: AsyncSession, *, model_id: int, actor: User) -> int:
    from app.services.workspace_model_access import require_studio_model_access

    sm = await require_studio_model_access(session, actor, model_id, load_images=True)
    return len(filter_model_images_for_boardstory(list(sm.images)))


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
    generate_clothing_from_video: bool = False,
    generate_environment_from_video: bool = False,
    send_video_reference: bool = True,
    output_aspect: str = "9:16",
    ws_key: str | None = None,
    pub: str | None = None,
    job_id: int | None = None,
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
        await _validate_boardstory_model_refs(session, model_id=model_id, actor=actor)
        n_model = await _estimate_boardstory_model_image_count(session, model_id=model_id, actor=actor)

        extract_result: dict[str, int | str | None] = {
            "clothing_generation_id": None,
            "environment_generation_id": None,
            "clothing_image_url": None,
            "environment_image_url": None,
        }
        if (generate_clothing_from_video or generate_environment_from_video) and ws_key and pub and job_id:
            from app.services.studio_workflow_boardstory_extract import extract_boardstory_refs_from_video

            extract_result = await extract_boardstory_refs_from_video(
                session,
                owner_id=owner_id,
                actor=actor,
                studio_model_id=model_id,
                video_path=vpath,
                output_aspect=output_aspect,
                ws_key=ws_key,
                pub=pub,
                job_id=job_id,
                generate_clothing=generate_clothing_from_video and clothing_ref is None,
                generate_environment=generate_environment_from_video and environment_ref is None,
            )
            if generate_clothing_from_video and extract_result.get("clothing_generation_id"):
                clothing_ref = BoardStoryImageSlot(
                    kind="clothing",
                    generation_id=int(extract_result["clothing_generation_id"]),
                    role="clothing from video",
                )
            if generate_environment_from_video and extract_result.get("environment_generation_id"):
                environment_ref = BoardStoryImageSlot(
                    kind="environment",
                    generation_id=int(extract_result["environment_generation_id"]),
                    role="environment from video",
                )

        layout = compute_boardstory_layout(
            n_model,
            has_clothing=clothing_ref is not None,
            has_environment=environment_ref is not None,
            n_other=len([r for r in references if (r.ref_id or "").strip()]),
        )
        clothing_from_video = clothing_ref is None
        environment_from_video = environment_ref is None
        use_video_only_swap = boardstory_video_only_swap_mode(
            clothing_ref=clothing_ref,
            environment_ref=environment_ref,
            generate_clothing_from_video=generate_clothing_from_video,
            generate_environment_from_video=generate_environment_from_video,
            send_video_reference=send_video_reference,
        )
        use_clothing_env_swap = boardstory_clothing_env_swap_mode(
            clothing_ref=clothing_ref,
            environment_ref=environment_ref,
            send_video_reference=send_video_reference,
        )
        use_fixed_prompt = use_video_only_swap or use_clothing_env_swap

        timeline = ""
        if not use_fixed_prompt:
            timeline = await motion_grok_timeline_from_video_path(
                video_path=vpath,
                model_profile_text=profile,
                first_frame_jpeg=None,
                first_frame_media="image/jpeg",
                credentials=grok_creds,
            )

        reference_blocks: list[str] = []
        tag_rules = ""
        if not use_fixed_prompt:
            tag_rules = boardstory_tag_rules_text(
                layout,
                has_motion=send_video_reference,
                clothing_from_video=clothing_from_video,
                environment_from_video=environment_from_video,
                send_video_reference=send_video_reference,
            )
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

        max_prompt_chars = int(settings.studio_seedance_t2v_prompt_max_chars or 6000)
        if use_video_only_swap:
            composed = build_boardstory_video_only_swap_prompt(
                user_notes=(user_notes or "").strip(),
                n_model_images=layout.n_model_images,
                max_chars=max_prompt_chars,
            )
            prompt_mode = "video_only_swap"
        elif use_clothing_env_swap:
            composed = build_boardstory_clothing_env_swap_prompt(
                user_notes=(user_notes or "").strip(),
                n_model_images=layout.n_model_images,
                clothing_tag=layout.clothing_tag or "@Image2",
                environment_tag=layout.environment_tag or "@Image3",
                max_chars=max_prompt_chars,
            )
            prompt_mode = "clothing_env_swap"
        else:
            composed = await grok_compose_boardstory_video_prompt(
                motion_timeline=timeline.strip(),
                model_profile_text=profile,
                reference_tag_rules=tag_rules,
                reference_blocks=reference_blocks,
                user_notes=(user_notes or "").strip(),
                send_video_reference=send_video_reference,
                credentials=grok_creds,
                max_chars=max_prompt_chars,
            )
            composed = finalize_boardstory_t2v_prompt(
                composed,
                layout=layout,
                n_motion_videos=1 if send_video_reference else 0,
                max_chars=max_prompt_chars,
            )
            prompt_mode = "grok_compose"

        return {
            "refined_prompt": composed.strip(),
            "motion_timeline": timeline.strip(),
            "reference_scene_description": None,
            "motion_video_file_id": mv_id,
            "studio_model_id": model_id,
            "boardstory_mode": True,
            "boardstory_prompt_mode": prompt_mode,
            "send_video_reference": send_video_reference,
            "boardstory_layout": {
                "n_model_images": layout.n_model_images,
                "n_clothing_images": layout.n_clothing_images,
                "n_environment_images": layout.n_environment_images,
            },
            **extract_result,
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
