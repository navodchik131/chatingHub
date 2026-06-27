"""BoardStory: автогенерация opening still (модель в позе из motion-видео) перед Seedance T2V."""

from __future__ import annotations

import logging
from pathlib import Path

import anyio

from app.db.models import UserStudioModel
from app.services.studio_grok_motion import grok_motion_studio_credentials
from app.services.studio_image_token import (
    create_model_image_access_token,
    create_pose_reference_access_token,
)
from app.services.studio_motion_grok_pipeline import (
    assemble_motion_grok_wavespeed_prompt,
    grok_compose_motion_first_frame,
    motion_model_scene_wavespeed_image_urls,
)
from app.services.studio_motion_video import extract_first_frame_jpeg
from app.services.studio_openai import StudioOpenAiCredentials
from app.services.studio_pose_reference import save_pose_reference_bytes
from app.services.wavespeed_client import nano_banana_pro_edit_image_url

log = logging.getLogger(__name__)


def _nano_reorder_pose_last(image_urls: list[str]) -> list[str]:
    """Nano: identity refs first, pose frame from video last."""
    if len(image_urls) >= 2:
        return image_urls[1:] + [image_urls[0]]
    return image_urls


async def generate_boardstory_opening_still_url(
    *,
    video_path: Path,
    sm: UserStudioModel,
    owner_id: int,
    pub: str,
    ws_key: str,
    output_aspect: str = "9:16",
    wave_profile: str = "regular",
    lock_hairstyle: bool = True,
    credentials: StudioOpenAiCredentials | None = None,
) -> str | None:
    """
    Кадр t=0: pose/scene из motion-видео + лицо модели (Nano Banana).
    Возвращает HTTPS URL для @Image1 в Seedance T2V.
    """
    base = (pub or "").strip().rstrip("/")
    if not base.lower().startswith("https://"):
        log.warning("boardstory opening frame: PUBLIC_APP_URL must be HTTPS")
        return None
    if not (ws_key or "").strip():
        return None

    try:
        first_frame = await anyio.to_thread.run_sync(
            lambda vp=video_path: extract_first_frame_jpeg(vp)
        )
    except Exception as e:
        log.warning("boardstory opening frame extract failed: %s", e)
        return None
    if len(first_frame) < 64:
        return None

    creds = credentials or grok_motion_studio_credentials()
    try:
        refined, reference_scene, grok_neg = await grok_compose_motion_first_frame(
            pose_reference_bytes=first_frame,
            pose_reference_mime="image/jpeg",
            sm=sm,
            wave_profile=wave_profile,
            user_notes="BoardStory opening frame: replace the video actor with this model.",
            lock_hairstyle=lock_hairstyle,
            credentials=creds,
        )
    except Exception as e:
        log.warning("boardstory opening frame grok compose failed: %s", e)
        return None

    try:
        image_urls = motion_model_scene_wavespeed_image_urls(
            pub=base,
            owner_id=owner_id,
            pose_bytes=first_frame,
            pose_mime="image/jpeg",
            sm=sm,
            wave_profile=wave_profile,
            save_pose_reference_bytes=save_pose_reference_bytes,
            create_pose_reference_access_token=create_pose_reference_access_token,
            create_model_image_access_token=create_model_image_access_token,
        )
    except Exception as e:
        log.warning("boardstory opening frame ref urls failed: %s", e)
        return None
    if not image_urls:
        return None

    if wave_profile == "regular":
        image_urls = _nano_reorder_pose_last(image_urls)

    wavespeed_prompt = assemble_motion_grok_wavespeed_prompt(
        refined=refined,
        model_profile_text=(sm.profile_text or "").strip() or None,
        reference_scene=reference_scene or None,
        extra_negative=grok_neg,
        lock_hairstyle=lock_hairstyle,
        wave_profile=wave_profile,
        user_pose_first=False,
        user_pose_last=True,
        studio_mode="model_scene",
    )
    from app.services.studio_model_bootstrap import append_workflow_first_frame_face_grid

    wavespeed_prompt = append_workflow_first_frame_face_grid(wavespeed_prompt)

    try:
        ws_res = await nano_banana_pro_edit_image_url(
            api_key=ws_key,
            image_urls=image_urls,
            prompt=wavespeed_prompt,
            aspect_ratio=output_aspect,
            wave_profile=wave_profile,
            reference_scene_description=reference_scene,
        )
        url = (ws_res.url or "").strip()
        return url or None
    except Exception as e:
        log.warning("boardstory opening frame nano failed: %s", e)
        return None
