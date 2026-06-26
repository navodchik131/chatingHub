"""Извлечение still-референсов одежды и окружения из motion-видео для BoardStory."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudioGeneration, User
from app.services.studio_aspect import normalize_aspect_key
from app.services.studio_generation_status import StudioGenerationStatus
from app.services.studio_generation_storage import (
    generation_has_archive_file,
    studio_finish_image_generation,
)
from app.services.studio_motion_video import extract_video_sample_frames_jpeg
from app.services.studio_model_bootstrap import wavespeed_image_url_for_bootstrap
from app.services.wavespeed_client import gpt_image_2_edit_image_url

log = logging.getLogger(__name__)

_ENVIRONMENT_PROMPT = (
    "Using the reference frame, recreate the EXACT same room and environment from the IDENTICAL "
    "camera angle, viewpoint, perspective, focal length, framing, and crop as the reference — "
    "as if the camera was never moved. Preserve the same soft lighting direction, color temperature, "
    "ambient glow, plush textures, furniture layout, and depth of field. "
    "Remove the person completely — empty scene plate with NO human, NO body parts. "
    "Photorealistic interior plate only. No text, no watermark."
)

_CLOTHING_PROMPT = (
    "From the reference photo, isolate ONLY the visible outfit (top and pants) — same colors, "
    "fabric, cut, glitter, and garment details. "
    "Present as a clean e-commerce flat lay on a plain neutral background "
    "(solid white, light gray, or soft beige — no room, no furniture, no props). "
    "Optional: faceless ghost mannequin on the same neutral backdrop. "
    "NO face, NO hands, NO body, NO identity, NO interior, NO shadows from a room."
)


async def _frame_public_url(
    *,
    api_key: str,
    owner_id: int,
    pub: str,
    frame_bytes: bytes,
    label: str,
) -> str:
    return await wavespeed_image_url_for_bootstrap(
        api_key=api_key,
        owner_id=owner_id,
        pub=pub,
        raw=frame_bytes,
        content_type="image/jpeg",
        label=label,
    )


async def _generate_boardstory_still(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int,
    output_aspect: str,
    prompt: str,
    frame_url: str,
    ws_key: str,
    job_id: int,
    label: str,
) -> tuple[int, str]:
    from app.api.studio_routes import _public_app_base, _studio_archive_image_url

    aspect_key = normalize_aspect_key(output_aspect)
    gen_row = StudioGeneration(
        user_id=owner_id,
        studio_model_id=studio_model_id,
        output_aspect=aspect_key,
        content_type="image/png",
        status=StudioGenerationStatus.PROCESSING,
        relative_path="",
        studio_job_id=job_id,
        prompt_excerpt=prompt[:500],
    )
    session.add(gen_row)
    await session.flush()

    ws_res = await gpt_image_2_edit_image_url(
        api_key=ws_key,
        image_urls=[frame_url],
        prompt=prompt,
        aspect_ratio=aspect_key,
        resolution="1k",
        quality="medium",
        output_format="png",
    )
    _, preview_url = await studio_finish_image_generation(
        session,
        gen_row=gen_row,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        output_aspect=aspect_key,
        refined_prompt=prompt,
        source_url=ws_res.url,
        wavespeed_task_id=ws_res.task_id,
    )
    arch_base = _public_app_base(None)
    out_url = preview_url
    if gen_row.status == StudioGenerationStatus.READY and generation_has_archive_file(gen_row):
        out_url = _studio_archive_image_url(owner_id, gen_row.id, arch_base)
    log.info("boardstory extract %s ok gen=%s", label, gen_row.id)
    return gen_row.id, out_url or preview_url or ""


async def extract_boardstory_refs_from_video(
    session: AsyncSession,
    *,
    owner_id: int,
    actor: User,
    studio_model_id: int,
    video_path: Path,
    output_aspect: str,
    ws_key: str,
    pub: str,
    job_id: int,
    generate_clothing: bool,
    generate_environment: bool,
) -> dict[str, int | str | None]:
    """Генерирует still-рефы одежды/окружения из кадра motion-видео."""
    result: dict[str, int | str | None] = {
        "clothing_generation_id": None,
        "environment_generation_id": None,
        "clothing_image_url": None,
        "environment_image_url": None,
    }
    if not generate_clothing and not generate_environment:
        return result

    frames = extract_video_sample_frames_jpeg(video_path, max_frames=3)
    if not frames:
        raise RuntimeError("Не удалось извлечь кадры из motion-видео.")
    frame = frames[min(1, len(frames) - 1)]

    frame_url = await _frame_public_url(
        api_key=ws_key,
        owner_id=owner_id,
        pub=pub,
        frame_bytes=frame,
        label="boardstory_frame",
    )

    if generate_environment:
        gid, url = await _generate_boardstory_still(
            session,
            owner_id=owner_id,
            studio_model_id=studio_model_id,
            output_aspect=output_aspect,
            prompt=_ENVIRONMENT_PROMPT,
            frame_url=frame_url,
            ws_key=ws_key,
            job_id=job_id,
            label="environment",
        )
        result["environment_generation_id"] = gid
        result["environment_image_url"] = url

    if generate_clothing:
        gid, url = await _generate_boardstory_still(
            session,
            owner_id=owner_id,
            studio_model_id=studio_model_id,
            output_aspect=output_aspect,
            prompt=_CLOTHING_PROMPT,
            frame_url=frame_url,
            ws_key=ws_key,
            job_id=job_id,
            label="clothing",
        )
        result["clothing_generation_id"] = gid
        result["clothing_image_url"] = url

    return result
