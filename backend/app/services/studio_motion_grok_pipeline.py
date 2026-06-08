"""
Grok для motion: сборка кадра (grok_compose) и timeline по реф-видео.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from app.config import settings
from app.services.studio_grok_motion import (
    grok_motion_studio_credentials,
    grok_two_step_motion_prompt_for_studio,
)
from app.services.studio_grok_scene_compose import grok_compose_studio_scene
from app.services.studio_model_images import (
    model_images_for_wavespeed_profile,
    select_grok_compose_wavespeed_identity_images,
    select_model_scene_wavespeed_identity_images,
    sort_model_images_for_studio,
)
from app.services.studio_motion_video import extract_first_frame_jpeg
from app.services.studio_openai import (
    StudioOpenAiCredentials,
    assemble_wavespeed_image_edit_prompt,
    describe_motion_video_first_frame_scene_openai,
    describe_reference_image_openai,
)

if TYPE_CHECKING:
    from app.db.models import UserStudioModel

log = logging.getLogger(__name__)


async def grok_compose_motion_first_frame(
    *,
    pose_reference_bytes: bytes,
    pose_reference_mime: str | None,
    sm: UserStudioModel,
    wave_profile: str,
    user_notes: str,
    lock_hairstyle: bool,
    credentials: StudioOpenAiCredentials | None = None,
) -> tuple[str, str | None, str | None]:
    """
    Grok scene compose для первого кадра.
    Returns (wavespeed_scene_prompt, reference_scene_lock, negative_prompt).
    """
    creds = credentials or grok_motion_studio_credentials()
    imgs = sort_model_images_for_studio(list(sm.images))
    composed = await grok_compose_studio_scene(
        user_ref_bytes=pose_reference_bytes,
        user_ref_mime=pose_reference_mime,
        model_images=imgs,
        model_profile_text=(sm.profile_text or "").strip() or None,
        wave_profile=wave_profile,
        user_notes=user_notes,
        lock_hairstyle=lock_hairstyle,
        credentials=creds,
        standalone_scene_prompt=True,
    )
    return (
        composed.wavespeed_scene_prompt,
        composed.reference_scene_lock or None,
        composed.negative_prompt or None,
    )


def motion_grok_wavespeed_image_urls(
    *,
    pub: str,
    owner_id: int,
    pose_bytes: bytes,
    pose_mime: str,
    sm: UserStudioModel,
    wave_profile: str,
    reference_scene_nude: bool,
    save_pose_reference_bytes,
    create_pose_reference_access_token,
    create_model_image_access_token,
) -> list[str]:
    """Реф позы + face модели для WaveSpeed (режим grok_compose)."""
    from urllib.parse import quote

    imgs_model = sort_model_images_for_studio(list(sm.images))
    imgs_for_ws = model_images_for_wavespeed_profile(imgs_model, wave_profile)
    image_urls: list[str] = []
    fid_pose = save_pose_reference_bytes(
        owner_id=owner_id,
        raw=pose_bytes,
        content_type=pose_mime if pose_mime.startswith("image/") else "image/jpeg",
    )
    ptok = create_pose_reference_access_token(user_id=owner_id, file_id=fid_pose)
    image_urls.append(f"{pub}/api/studio/public-pose-reference?t={quote(ptok, safe='')}")
    for im in select_grok_compose_wavespeed_identity_images(
        imgs_for_ws,
        pose_reference_nude=reference_scene_nude,
    ):
        tok = create_model_image_access_token(user_id=owner_id, image_id=im.id)
        image_urls.append(f"{pub}/api/studio/public-model-image?t={quote(tok, safe='')}")
    return image_urls


def assemble_motion_grok_wavespeed_prompt(
    *,
    refined: str,
    model_profile_text: str | None,
    reference_scene: str | None,
    extra_negative: str | None,
    lock_hairstyle: bool,
    wave_profile: str,
    user_pose_first: bool,
    user_pose_last: bool,
    studio_mode: str = "model_scene",
) -> str:
    return assemble_wavespeed_image_edit_prompt(
        refined,
        studio_mode=studio_mode,
        user_pose_in_api=user_pose_first,
        user_pose_is_last=user_pose_last,
        lock_model_hairstyle=lock_hairstyle,
        prompt_brief_mode="grok_composed",
        model_profile_text=model_profile_text,
        wave_profile=wave_profile,
        reference_scene_description=reference_scene,
        extra_negative=extra_negative,
    )


async def motion_grok_timeline_from_video_path(
    *,
    video_path: Path,
    model_profile_text: str,
    first_frame_jpeg: bytes,
    first_frame_media: str,
    credentials: StudioOpenAiCredentials | None = None,
) -> str:
    creds = credentials or grok_motion_studio_credentials()
    if settings.studio_grok_motion_timeline_enabled:
        return await grok_two_step_motion_prompt_for_studio(
            video_path=video_path,
            model_profile_text=model_profile_text,
            first_frame_jpeg=first_frame_jpeg,
            first_frame_media=first_frame_media,
            credentials=creds,
        )
    from app.services.studio_motion_video import extract_video_sample_frames_jpeg
    from app.services.studio_openai import describe_motion_video_frames_openai

    frames = await anyio.to_thread.run_sync(
        lambda: extract_video_sample_frames_jpeg(video_path, max_frames=4)
    )
    return await describe_motion_video_frames_openai(
        frames_jpeg=frames,
        credentials=credentials,
    )


async def describe_motion_still_for_ui(
    *,
    image_bytes: bytes,
    image_media_type: str | None,
    lock_hairstyle: bool,
    credentials: StudioOpenAiCredentials,
) -> str:
    try:
        return await describe_motion_video_first_frame_scene_openai(
            image_bytes=image_bytes,
            image_media_type=image_media_type,
            credentials=credentials,
        )
    except RuntimeError:
        return await describe_reference_image_openai(
            image_bytes=image_bytes,
            image_media_type=image_media_type,
            hairstyle_from_pose_reference=not lock_hairstyle,
            credentials=credentials,
        )


async def extract_video_first_frame_or_raise(video_path: Path) -> tuple[bytes, str]:
    try:
        raw = await anyio.to_thread.run_sync(
            lambda: extract_first_frame_jpeg(video_path)
        )
    except Exception as e:
        log.warning("motion ffmpeg first frame: %s", e)
        raise RuntimeError(
            "Не удалось прочитать видео. Нужен MP4/WebM/MOV и ffmpeg на сервере."
        ) from e
    if len(raw) < 64:
        raise RuntimeError("Не удалось извлечь кадр из видео.")
    return raw, "image/jpeg"
