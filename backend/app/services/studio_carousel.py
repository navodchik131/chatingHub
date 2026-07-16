from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

from app.config import BACKEND_DIR, settings
from app.services.studio_grok_motion import grok_motion_studio_credentials
from app.services.studio_openai import (
    StudioOpenAiCredentials,
    _strip_code_fences,
    chat_completion_openai_compatible_text,
)

log = logging.getLogger(__name__)


def _read_text(rel: str) -> str:
    p = (BACKEND_DIR / rel).resolve()
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return ""


def _grok_carousel_prompt_candidates() -> list[Path]:
    rel = (getattr(settings, "grok_carousel_compose_system_path", None) or "").strip()
    name = "grok_carousel_compose_system.txt"
    if rel:
        name = (BACKEND_DIR / rel).name
    ordered = [
        (BACKEND_DIR / rel).resolve() if rel else None,
        (BACKEND_DIR / "data" / "prompts" / name).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / name).resolve(),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for item in ordered:
        if item is None or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def load_grok_carousel_compose_system() -> str:
    inline = (getattr(settings, "grok_carousel_compose_system_inline", None) or "").strip()
    if inline:
        return inline
    for path in _grok_carousel_prompt_candidates():
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t:
                return t
    raise RuntimeError(
        "Промпт Grok carousel пуст: добавьте grok_carousel_compose_system.txt "
        "или GROK_CAROUSEL_COMPOSE_SYSTEM_INLINE"
    )


def parse_carousel_grok_prompts(raw: str, *, count: int) -> list[str]:
    """Parse Grok JSON or «Prompt 1: …» blocks into exactly `count` strings."""
    text = _strip_code_fences(raw or "").strip()
    if not text:
        raise RuntimeError("Grok carousel: пустой ответ")

    if text.startswith("{"):
        try:
            data = json.loads(text)
            prompts = data.get("prompts")
            if isinstance(prompts, list):
                out = [str(p).strip() for p in prompts if str(p).strip()]
                if len(out) >= count:
                    return out[:count]
        except json.JSONDecodeError:
            pass

    found: list[tuple[int, str]] = []
    pattern = re.compile(
        r"(?im)^\s*Prompt\s+(\d+)\s*[:\.]?\s*(.+?)(?=^\s*Prompt\s+\d+\s*[:\.]|\Z)",
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        body = m.group(2).strip()
        if body:
            found.append((int(m.group(1)), body))
    if found:
        found.sort(key=lambda x: x[0])
        out = [p for _, p in found]
        if len(out) >= count:
            return out[:count]

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    numbered = []
    for ln in lines:
        m = re.match(r"^\d+[\).\]]\s*(.+)", ln)
        if m:
            numbered.append(m.group(1).strip())
    if len(numbered) >= count:
        return numbered[:count]

    raise RuntimeError(
        f"Grok carousel: не удалось разобрать {count} промптов из ответа "
        f"(получено {len(found) or len(numbered) or 0})"
    )


def load_carousel_lock_text() -> str:
    t = _read_text("data/prompts/image_studio_carousel_lock.txt")
    if t:
        return t
    return (
        "[CAROUSEL_SCENE_LOCK] Keep same person, outfit, and room as the master image; "
        "only change camera and pose as instructed in SHOT_VARIATION."
    )


def load_carousel_variation_blocks() -> list[str]:
    raw = _read_text("data/prompts/image_studio_carousel_variations.txt")
    if not raw:
        return [
            "Camera: three-quarter from left; body turned away; gaze off-frame left; neutral expression. Same room.",
            "Camera: full body straight-on; subject looks down at phone, candid soft smile. Same environment.",
            "Camera: low angle; mid-laugh, head tilted, eyes not locked on lens. Same outfit and room.",
            "Camera: near profile from right; gaze forward in profile; thoughtful mood. Same background.",
            "Camera: back three-quarter from behind-left; glance over shoulder toward camera; body facing away.",
            "Camera: right three-quarter medium; hand on hip; gaze past camera to the right.",
            "Camera: wider left environmental; leaning casual; looking toward off-camera light.",
            "Camera: close crop from below; subtle smirk; gaze up past lens; asymmetric framing.",
        ]
    parts = [b.strip() for b in raw.split("\n---\n") if b.strip()]
    return parts if parts else [
        "Camera: eye level, medium shot; small pose adjustment only; lock outfit and room."
    ]


def build_carousel_wave_prompt(*, master_refined_json: str, shot_index: int) -> str:
    lock = load_carousel_lock_text()
    blocks = load_carousel_variation_blocks()
    v = blocks[shot_index % len(blocks)]
    base = (master_refined_json or "").strip()
    return (
        f"{lock}\n\nBASE_SCENE_JSON (source of truth for styling — do not delete identity or wardrobe cues):\n"
        f"{base}\n\n[SHOT_VARIATION — this frame only]\n{v}"
    )


def build_carousel_grok_wave_prompt(*, master_scene_context: str, shot_variation: str) -> str:
    lock = load_carousel_lock_text()
    base = (master_scene_context or "").strip() or "(master image is source of truth for identity, outfit, room)"
    variation = (shot_variation or "").strip()
    return (
        f"{lock}\n\nBASE_SCENE (from master frame):\n{base}\n\n"
        f"[SHOT_VARIATION — this frame only]\n{variation}"
    )


def static_carousel_variations(count: int) -> list[str]:
    blocks = load_carousel_variation_blocks()
    return [blocks[i % len(blocks)] for i in range(count)]


async def grok_compose_carousel_prompts(
    *,
    master_image_bytes: bytes,
    master_image_mime: str | None,
    user_direction: str,
    count: int,
    master_scene_text: str | None = None,
    credentials: StudioOpenAiCredentials | None = None,
) -> list[str]:
    """Grok vision → N img2img shot variations for carousel."""
    creds = credentials or grok_motion_studio_credentials()
    system = load_grok_carousel_compose_system()
    n = max(2, min(8, int(count)))
    direction = (user_direction or "").strip() or (
        "Vary camera side (left/right/profile/back three-quarter), distance, and height across frames. "
        "Mix gaze: off-camera, down at hands, profile, over-shoulder — avoid every frame staring into the lens. "
        "Vary expressions (neutral, smile, candid laugh, thoughtful). Same outfit and room."
    )
    scene = (master_scene_text or "").strip()

    ref_mime = (master_image_mime or "image/jpeg").split(";")[0].strip()
    if ref_mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        ref_mime = "image/jpeg"
    ref_b64 = base64.standard_b64encode(master_image_bytes).decode("ascii")

    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"FRAME_COUNT: {n}\n\n"
                f"USER_DIRECTION:\n{direction}\n\n"
                f"MASTER_SCENE_TEXT:\n{scene or '(none — infer from MASTER_IMAGE)'}\n\n"
                "Attached: MASTER_IMAGE"
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:{ref_mime};base64,{ref_b64}"},
        },
    ]

    model = (settings.grok_scene_compose_model or "").strip() or None
    raw_out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system + "\n\nFollow the output format exactly. No markdown fences.",
            },
            {"role": "user", "content": user_parts},
        ],
        max_tokens=int(settings.grok_scene_compose_max_tokens),
        temperature=float(settings.grok_scene_compose_temperature),
        timeout_seconds=float(settings.grok_scene_compose_timeout_seconds),
    )
    return parse_carousel_grok_prompts(raw_out, count=n)
