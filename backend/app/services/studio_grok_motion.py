"""
Двухшаговый Grok (OpenAI-compatible /v1): таймлайн по секундам по кадрам референс-видео,
затем подмена описания людей на профиль сохранённой модели и согласование с первым кадром целевого ролика.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from app.config import settings
from app.services.studio_motion_video import extract_video_timeline_frames_jpeg
from app.services.studio_openai import StudioOpenAiCredentials, chat_completion_openai_compatible_text

log = logging.getLogger(__name__)

_TIMELINE_SYSTEM_EN = (
    "You follow instructions precisely. Reply only in English as requested. "
    "No preamble, no markdown code fences unless the schema explicitly asks for plain section headers "
    "[t s] lines without ``` blocks."
)


def grok_motion_studio_credentials() -> StudioOpenAiCredentials:
    key = (settings.grok_api_key or "").strip() or (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError(
            "Задайте GROK_API_KEY в .env (или временно OPENAI_API_KEY) для Grok motion timeline."
        )
    base = (settings.grok_base_url or "").strip().rstrip("/") or "https://api.x.ai/v1"
    return StudioOpenAiCredentials(api_key=key, base_url=base, organization="")


def _grok_motion_model() -> str:
    return (settings.grok_motion_model or "").strip() or "grok-2-vision-1212"


async def grok_step1_timeline_from_video(
    *,
    video_path: Path,
    credentials: StudioOpenAiCredentials,
) -> str:
    frames, _span = extract_video_timeline_frames_jpeg(
        video_path,
        max_seconds=settings.grok_motion_max_seconds,
        max_width=settings.grok_motion_max_frame_width,
    )
    if not frames:
        raise RuntimeError("Не удалось извлечь кадры для Grok (ffmpeg).")

    model = _grok_motion_model()
    intro = (
        f"You are given {len(frames)} still images in chronological order. "
        "They are 1 Hz samples from the start of a short reference video — image i ≈ second i from t=0.\n"
        "Write ONE continuous English video-generation brief that can drive image-to-video.\n"
        "Structure:\n"
        "- For each second t from 0 through N-1 (N = number of images), output a line starting with "
        "the exact token `[t s]` then a rich description: full-body pose, limb angles, weight shifts, "
        "head angle and gaze, facial expression, hair motion, clothing folds, hands, micro-movements, "
        "camera position/move (pan/tilt/dolly/track), lens feel, background parallax, lighting direction and quality.\n"
        "- Then one paragraph prefixed `[Global motion]` summarizing rhythm, energy, transitions between seconds, "
        "and any repeating beats.\n"
        "Rules: describe only what is visible; do not invent story beats; do not name real celebrities; "
        "write the performer neutrally (body type, wardrobe, markings) knowing identity will be replaced later — "
        "but preserve motion and timing faithfully.\n"
        "Plain text only (no Markdown tables)."
    )

    content: list[dict] = [{"type": "text", "text": intro}]
    for i, raw in enumerate(frames):
        b64 = base64.standard_b64encode(raw).decode("ascii")
        content.append({"type": "text", "text": f"Sample at ~{i} s:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
        )

    out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": _TIMELINE_SYSTEM_EN},
            {"role": "user", "content": content},
        ],
        max_tokens=8192,
        temperature=0.25,
        credentials=credentials,
        timeout_seconds=float(settings.studio_archive_download_timeout_seconds),
    )
    text = (out or "").strip()
    if len(text) < 80:
        raise RuntimeError("Grok вернул слишком короткое описание таймлайна.")
    log.info("grok motion step1 chars=%s frames=%s", len(text), len(frames))
    return text


async def grok_step2_rewrite_for_target_model(
    *,
    timeline_english: str,
    model_profile_text: str,
    first_frame_jpeg: bytes,
    first_frame_media: str,
    credentials: StudioOpenAiCredentials,
) -> str:
    model = _grok_motion_model()
    mime = (first_frame_media or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"
    b64 = base64.standard_b64encode(first_frame_jpeg).decode("ascii")

    profile = (model_profile_text or "").strip()
    profile_block = (
        profile
        if profile
        else "TARGET_MODEL_PROFILE (text): empty — derive target persona only from the attached first-frame image;"
        " assume it is the canonical look for the synthesized video."
    )

    user_instruction = (
        "You merge a motion timeline with a locked target persona for video generation.\n\n"
        f"{profile_block}\n\n"
        "---\n"
        "REFERENCE_MOTION_TIMELINE (English, keep choreography and timing exactly):\n"
        f"{timeline_english.strip()}\n\n"
        "---\n"
        "TASK:\n"
        "1) Read REFERENCE_MOTION_TIMELINE. Preserve every `[t s]` line and `[Global motion]` pacing — "
        "do not shorten the seconds coverage; keep the same chronological structure.\n"
        "2) Wherever the timeline describes the on-screen person's identity or appearance "
        "(face shape, ethnicity guess, hair, makeup, physique, tattoos, scars, approximate age/gender cues, wardrobe brand logos), "
        "replace those phrases so they describe ONLY the TARGET_MODEL_PROFILE (text) "
        "+ what is visibly consistent with the attached first-frame image.\n"
        "3) Do NOT rename or invent new motions, camera beats, backgrounds, props, lighting setup, "
        "or durations — choreography and environment stay from the timeline.\n"
        "4) If the timeline is silent about a detail the profile requires (e.g. hair length), harmonize subtly "
        "without changing the poses.\n"
        "Output: a single plain English brief (same `[t s]` + `[Global motion]` skeleton), ready to paste "
        "into an image-to-video model together with the first-frame image.\n"
    )

    content: list[dict] = [
        {"type": "text", "text": user_instruction},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        },
    ]

    out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": _TIMELINE_SYSTEM_EN},
            {"role": "user", "content": content},
        ],
        max_tokens=10240,
        temperature=0.2,
        credentials=credentials,
        timeout_seconds=min(600.0, float(settings.studio_archive_download_timeout_seconds) + 180.0),
    )
    text = (out or "").strip()
    if len(text) < 80:
        raise RuntimeError("Grok вернул слишком короткий итоговый промпт.")
    log.info("grok motion step2 chars=%s", len(text))
    return text


async def grok_two_step_motion_prompt_for_studio(
    *,
    video_path: Path,
    model_profile_text: str,
    first_frame_jpeg: bytes,
    first_frame_media: str,
    credentials: StudioOpenAiCredentials,
) -> str:
    timeline = await grok_step1_timeline_from_video(
        video_path=video_path,
        credentials=credentials,
    )
    return await grok_step2_rewrite_for_target_model(
        timeline_english=timeline,
        model_profile_text=model_profile_text,
        first_frame_jpeg=first_frame_jpeg,
        first_frame_media=first_frame_media,
        credentials=credentials,
    )


def grok_motion_api_configured() -> bool:
    return bool((settings.grok_api_key or "").strip() or (settings.openai_api_key or "").strip())
