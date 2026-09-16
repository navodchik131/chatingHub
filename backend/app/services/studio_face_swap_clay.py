"""Face swap: pass 1 clay prep + pass 2 clay→model (Grok заполняет плейсхолдеры)."""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, settings
from app.services.studio_openai import (
    StudioOpenAiCredentials,
    _strip_code_fences,
    chat_completion_openai_compatible_text,
)

log = logging.getLogger(__name__)

_PREP_SFW = "face_swap_clay_prep_sfw.txt"
_PREP_NSFW = "face_swap_clay_prep_nsfw.txt"
_FINAL_MASTER = "face_swap_clay_to_model_master.txt"
_SYSTEM_PREP = "face_swap_clay_grok_prep_system.txt"
_SYSTEM_FINAL = "face_swap_clay_grok_final_system.txt"


def _prompt_candidates(filename: str) -> list[Path]:
    return [
        (BACKEND_DIR / "data" / "prompts" / filename).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / filename).resolve(),
    ]


def _read_prompt_file(filename: str) -> str:
    for path in _prompt_candidates(filename):
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
    tried = ", ".join(str(p) for p in _prompt_candidates(filename))
    raise RuntimeError(f"Clay face swap prompt missing (tried: {tried})")


def load_clay_prep_template(*, wave_profile: str) -> str:
    wp = (wave_profile or "nsfw").strip().lower()
    return _read_prompt_file(_PREP_SFW if wp == "regular" else _PREP_NSFW)


def load_clay_to_model_master_template() -> str:
    return _read_prompt_file(_FINAL_MASTER)


def face_swap_clay_pipeline_enabled() -> bool:
    """Clay prep + Grok final; выключено если classic single-pass включён."""
    from app.services.studio_face_swap_seedream_v5 import face_swap_classic_enabled

    if face_swap_classic_enabled(""):
        return False
    from app.services.studio_anchor_pipeline import face_swap_mannequin_prep_enabled

    return face_swap_mannequin_prep_enabled()


def _read_model_image_file(im: Any) -> tuple[bytes, str]:
    path = (BACKEND_DIR / im.relative_path).resolve()
    if not path.is_file():
        raise RuntimeError(f"Файл снимка модели не найден: {im.relative_path}")
    raw = path.read_bytes()
    if not raw:
        raise RuntimeError(f"Пустой файл снимка модели id={getattr(im, 'id', '?')}")
    ext = path.suffix.lower()
    mime = "image/jpeg"
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    elif ext == ".gif":
        mime = "image/gif"
    return raw, mime


def _image_part(raw: bytes, mime: str) -> dict[str, Any]:
    m = (mime or "image/jpeg").split(";")[0].strip()
    if m not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        m = "image/jpeg"
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{m};base64,{b64}"},
    }


def _grok_vision_model() -> str:
    from app.services.studio_grok_motion import _grok_fps_stills_model
    from app.services.studio_grok_scene_compose import grok_scene_compose_configured

    if grok_scene_compose_configured():
        return (settings.grok_scene_compose_model or "").strip() or _grok_fps_stills_model()
    return (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model


def _warn_unfilled(prompt: str, names: str) -> str:
    if re.search(r"\[(EXPRESSION|BODY|FACE|HAIR)\]", prompt or "", re.I):
        log.warning("clay face swap: unresolved placeholders (%s)", names)
    return (prompt or "").strip()


async def compose_clay_prep_prompt(
    *,
    credentials: StudioOpenAiCredentials | Any,
    wave_profile: str,
    model_profile_text: str | None,
    scene_description: str,
    scene_bytes: bytes,
    scene_mime: str,
    body_image: Any | None = None,
) -> str:
    """Pass 1: реф → глина; NSFW — Image2=тело модели для [BODY]."""
    template = load_clay_prep_template(wave_profile=wave_profile)
    system = _read_prompt_file(_SYSTEM_PREP)
    wp = (wave_profile or "nsfw").strip().lower()
    nsfw = wp != "regular"

    profile = (model_profile_text or "").strip() or "(no profile — derive BODY from body photo only)"
    scene_txt = (scene_description or "").strip()

    user_text = f"PREP TEMPLATE:\n{template}\n\nMODEL PROFILE:\n{profile}\n\n"
    if scene_txt:
        user_text += f"SCENE ANALYSIS:\n{scene_txt}\n\n"
    if nsfw:
        user_text += "Attached: (1) REFERENCE SCENE, (2) MODEL BODY for [BODY].\n"
    else:
        user_text += "Attached: (1) REFERENCE SCENE only.\n"
    user_text += "Output the completed prep prompt only."

    content: list[Any] = [{"type": "text", "text": user_text}]
    content.append(_image_part(scene_bytes, scene_mime or "image/jpeg"))
    if nsfw and body_image is not None:
        body_raw, body_mime = _read_model_image_file(body_image)
        content.append(_image_part(body_raw, body_mime))

    raw = await chat_completion_openai_compatible_text(
        model=_grok_vision_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        max_tokens=8192,
        temperature=0.25,
        credentials=credentials,
        timeout_seconds=float(settings.grok_scene_compose_timeout_seconds or 120.0),
    )
    return _warn_unfilled(_strip_code_fences(raw or "").strip(), "prep")


async def compose_clay_to_model_prompt(
    *,
    credentials: StudioOpenAiCredentials | Any,
    model_profile_text: str | None,
    scene_description: str,
    clay_bytes: bytes,
    clay_mime: str,
    face_image: Any,
    body_image: Any,
    user_notes: str = "",
) -> str:
    """Pass 2: глина + лицо + тело → финальный edit prompt."""
    from app.services.studio_anchor_pipeline import SCENE_OVERLAY_EXCLUSION_BLOCK

    template = load_clay_to_model_master_template()
    system = _read_prompt_file(_SYSTEM_FINAL)

    profile = (model_profile_text or "").strip() or "(no profile — derive from model photos)"
    scene_txt = (scene_description or "").strip()
    notes = (user_notes or "").strip()

    user_text = f"FINAL TEMPLATE:\n{template}\n\nMODEL PROFILE:\n{profile}\n\n"
    if scene_txt:
        user_text += f"SCENE ANALYSIS (expression hints from original reference):\n{scene_txt}\n\n"
    if notes:
        user_text += f"USER NOTES (do not override Image 1 pose):\n{notes}\n\n"
    user_text += (
        "Attached in order: (1) CLAY after pass 1, (2) MODEL FACE, (3) MODEL BODY.\n"
        "Output the completed prompt only."
    )

    face_raw, face_mime = _read_model_image_file(face_image)
    body_raw, body_mime = _read_model_image_file(body_image)

    content: list[Any] = [{"type": "text", "text": user_text}]
    content.append(_image_part(clay_bytes, clay_mime or "image/jpeg"))
    content.append(_image_part(face_raw, face_mime))
    content.append(_image_part(body_raw, body_mime))

    raw = await chat_completion_openai_compatible_text(
        model=_grok_vision_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        max_tokens=8192,
        temperature=0.25,
        credentials=credentials,
        timeout_seconds=float(settings.grok_scene_compose_timeout_seconds or 120.0),
    )
    out = _warn_unfilled(_strip_code_fences(raw or "").strip(), "final")
    upper = out.upper()
    if "OVERLAYS_AND_TEXT" not in upper and "OVERLAYS AND TEXT" not in upper:
        out = f"{out}\n\n{SCENE_OVERLAY_EXCLUSION_BLOCK}"
    return out
