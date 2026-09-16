"""Face swap classic — один Grok master prompt и edit ref→face→body (без mannequin prep)."""

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

_MASTER = "face_swap_seedream_v5_master.txt"
_SYSTEM = "face_swap_seedream_v5_grok_compose_system.txt"


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
    raise RuntimeError(f"Seedream v5 face swap prompt file missing (tried: {tried})")


def load_face_swap_seedream_v5_master_template() -> str:
    return _read_prompt_file(_MASTER)


def load_face_swap_seedream_v5_grok_system() -> str:
    return _read_prompt_file(_SYSTEM)


def face_swap_classic_enabled(wave_model_id: str = "") -> bool:
    """Classic face swap для любой WaveSpeed-модели (Grok + один edit, без mannequin)."""
    _ = wave_model_id
    return bool(getattr(settings, "studio_face_swap_seedream_v5_classic", True))


def face_swap_seedream_v5_classic_enabled(wave_model_id: str) -> bool:
    """Обратная совместимость — то же, что face_swap_classic_enabled."""
    return face_swap_classic_enabled(wave_model_id)


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


def _strip_unfilled_placeholders(prompt: str) -> str:
    """На случай если Grok оставил скобки — логируем, не падаем."""
    if re.search(r"\[(FACE|MARKS|HAIR|BODY|EXPRESSION)\]", prompt or "", re.I):
        log.warning("face swap classic compose: unresolved placeholders in prompt")
    return (prompt or "").strip()


async def compose_classic_face_swap_prompt(
    *,
    credentials: StudioOpenAiCredentials | Any,
    model_profile_text: str | None,
    scene_description: str,
    scene_bytes: bytes,
    scene_mime: str,
    face_image: Any,
    body_image: Any,
    user_notes: str = "",
) -> str:
    """
    Grok заполняет master template: identity из профиля/фото модели, [EXPRESSION] с рефа.
    """
    from app.config import settings as cfg
    from app.services.studio_grok_motion import _grok_fps_stills_model
    from app.services.studio_grok_scene_compose import grok_scene_compose_configured

    if grok_scene_compose_configured():
        model = (cfg.grok_scene_compose_model or "").strip() or _grok_fps_stills_model()
    else:
        model = (cfg.openai_studio_model_vision or "").strip() or cfg.openai_studio_model

    master = load_face_swap_seedream_v5_master_template()
    system = load_face_swap_seedream_v5_grok_system()

    profile = (model_profile_text or "").strip() or "(no profile text — derive only from model photos)"
    scene_txt = (scene_description or "").strip()
    notes = (user_notes or "").strip()

    user_text = (
        "MASTER TEMPLATE (replace all placeholders):\n"
        f"{master}\n\n"
        "MODEL PROFILE:\n"
        f"{profile}\n\n"
    )
    if scene_txt:
        user_text += f"SCENE ANALYSIS (hints for [EXPRESSION] and hair arrangement vs Image 1):\n{scene_txt}\n\n"
    if notes:
        user_text += f"USER NOTES (optional mood, do not override Image 1 pose):\n{notes}\n\n"
    user_text += (
        "Attached images in order: (1) REFERENCE SCENE = future Image 1, "
        "(2) MODEL FACE = future Image 2, (3) MODEL BODY = future Image 3.\n"
        "Output the completed prompt only."
    )

    scene_m = (scene_mime or "image/jpeg").split(";")[0].strip()
    face_raw, face_mime = _read_model_image_file(face_image)
    body_raw, body_mime = _read_model_image_file(body_image)

    content: list[Any] = [{"type": "text", "text": user_text}]
    content.append(_image_part(scene_bytes, scene_m))
    content.append(_image_part(face_raw, face_mime))
    content.append(_image_part(body_raw, body_mime))

    raw = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        max_tokens=8192,
        temperature=0.25,
        credentials=credentials,
        timeout_seconds=float(cfg.grok_scene_compose_timeout_seconds or 120.0),
    )
    out = _strip_code_fences(raw or "").strip()
    return _strip_unfilled_placeholders(out)


async def compose_seedream_v5_face_swap_prompt(**kwargs: Any) -> str:
    """Alias для compose_classic_face_swap_prompt."""
    return await compose_classic_face_swap_prompt(**kwargs)
