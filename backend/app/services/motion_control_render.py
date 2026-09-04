"""Сборка Motion Control render: depth map + Grok prompt + ref URLs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import StudioGeneration
from app.services.motion_control_grok import grok_motion_control_shot_prompt
from app.services.motion_depth_map import ensure_motion_depth_map_video
from app.services.studio_grok_motion import grok_motion_api_configured, grok_motion_studio_credentials
from app.services.studio_image_token import create_generation_image_access_token, create_motion_video_access_token
from app.services.studio_seedance_t2v import generation_still_public_url

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MotionControlT2VPackage:
    seed_prompt: str
    ref_images: list[str]
    ref_videos: list[str]
    prompt_source: str = "motion_control_grok_depth"
    depth_file_id: str = ""


async def _load_turnaround_bytes(session: AsyncSession, *, owner_id: int, generation_id: int) -> tuple[bytes, str]:
    from app.api.studio_routes import _load_owned_generation_still_for_motion

    row, data, mime = await _load_owned_generation_still_for_motion(
        session,
        owner_id=owner_id,
        generation_id=generation_id,
        actor=None,
    )
    if row is None or len(data) < 64:
        raise RuntimeError("Не удалось загрузить развёртку для Grok.")
    return data, mime or "image/jpeg"


async def prepare_motion_control_depth_t2v(
    *,
    session: AsyncSession,
    owner_id: int,
    pub: str,
    vpath: Path,
    mv_id: str,
    turnaround_gid: int,
    per_project_notes: str = "",
    wants_reference_audio: bool = True,
    has_ref_audio: bool | None = None,
) -> MotionControlT2VPackage:
    """
    Motion Control wizard v2:
    1) depth-map video из реф-клипа
    2) Grok: video + turnaround → T2V prompt
    3) refs: @Video1=depth, @Image1=turnaround
    """
    if not grok_motion_api_configured():
        raise RuntimeError(
            "Для Motion Control нужен GROK_API_KEY — Grok анализирует референс-видео и пишет промпт."
        )

    timeout = max(60.0, float(settings.motion_outline_render_timeout_sec))
    depth_path = await anyio.to_thread.run_sync(
        lambda: ensure_motion_depth_map_video(owner_id, mv_id, vpath, timeout=timeout)
    )

    turnaround_url = generation_still_public_url(
        owner_id=owner_id,
        generation_id=turnaround_gid,
        public_app_base=pub,
        token_factory=create_generation_image_access_token,
    )
    if not turnaround_url:
        raise RuntimeError("Не удалось подготовить URL развёртки")

    ta_bytes, ta_mime = await _load_turnaround_bytes(session, owner_id=owner_id, generation_id=turnaround_gid)

    seed_prompt = await grok_motion_control_shot_prompt(
        video_path=vpath,
        character_image_bytes=ta_bytes,
        character_image_mime=ta_mime,
        credentials=grok_motion_studio_credentials(),
        per_project_notes=per_project_notes,
        wants_reference_audio=wants_reference_audio,
        has_ref_audio=has_ref_audio,
    )

    depth_tok = create_motion_video_access_token(user_id=owner_id, file_id=mv_id)
    depth_url = f"{pub}/api/studio/public-motion-depth-video?t={quote(depth_tok, safe='')}"

    return MotionControlT2VPackage(
        seed_prompt=seed_prompt,
        ref_images=[turnaround_url],
        ref_videos=[depth_url],
        depth_file_id=mv_id,
    )
