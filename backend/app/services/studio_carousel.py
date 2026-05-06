from __future__ import annotations

import logging
from pathlib import Path

from app.config import BACKEND_DIR

log = logging.getLogger(__name__)


def _read_text(rel: str) -> str:
    p = (BACKEND_DIR / rel).resolve()
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return ""


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
            "Camera: eye level, three-quarter left, medium shot; subtle pose change; same outfit and room.",
            "Camera: slightly low angle, full body; shift weight; same environment.",
            "Camera: closer portrait framing; soft gaze; same styling and background.",
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
