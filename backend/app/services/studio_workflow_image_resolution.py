"""Разрешение (1k/2k/4k) для workflow-генерации картинок по модели WaveSpeed."""

from __future__ import annotations

from app.services.studio_aspect import ASPECT_PRESETS, normalize_aspect_key

WORKFLOW_MODEL_RESOLUTION_OPTIONS: dict[str, tuple[str, ...]] = {
    "nano-banana-2": ("1k", "2k", "4k"),
    "nano-banana-pro": ("1k", "2k", "4k"),
    "gpt-image-2": ("1k", "2k", "4k"),
    "seedream-v5.0-pro": ("1k", "2k"),
    "wan-2.7": ("1k", "2k", "4k"),
}

WORKFLOW_MODEL_RESOLUTION_DEFAULT: dict[str, str] = {
    "nano-banana-2": "1k",
    "nano-banana-pro": "2k",
    "gpt-image-2": "1k",
    "seedream-v5.0-pro": "1k",
    "wan-2.7": "2k",
}

_RESOLUTION_SCALE: dict[str, float] = {
    "1k": 0.75,
    "2k": 1.0,
    "4k": 1.5,
}


def workflow_api_model_id(ui_or_api_model_id: str) -> str:
    mid = (ui_or_api_model_id or "wan-2.7").strip().lower()
    if mid == "wan-2.7-pro":
        return "wan-2.7"
    return mid


def workflow_resolution_options(model_id: str) -> tuple[str, ...]:
    mid = workflow_api_model_id(model_id)
    return WORKFLOW_MODEL_RESOLUTION_OPTIONS.get(mid, ("2k",))


def default_workflow_image_resolution(model_id: str) -> str:
    mid = workflow_api_model_id(model_id)
    return WORKFLOW_MODEL_RESOLUTION_DEFAULT.get(mid, workflow_resolution_options(mid)[0])


def normalize_workflow_image_resolution(model_id: str, raw: str | None) -> str:
    options = workflow_resolution_options(model_id)
    default = default_workflow_image_resolution(model_id)
    res = (raw or default).strip().lower()
    if res not in options:
        return default
    return res


def workflow_wavespeed_size_for_resolution(aspect_key: str, resolution: str) -> str:
    """Пиксельный size для WAN / Seedream edit (масштаб относительно пресета формата)."""
    k = normalize_aspect_key(aspect_key)
    w, h = ASPECT_PRESETS[k]
    scale = _RESOLUTION_SCALE.get((resolution or "2k").strip().lower(), 1.0)
    nw = max(512, min(8192, int(round(w * scale))))
    nh = max(512, min(8192, int(round(h * scale))))
    return f"{nw}x{nh}"


def workflow_resolution_options_public(model_id: str) -> list[dict[str, str]]:
    labels = {"1k": "1K", "2k": "2K", "4k": "4K"}
    return [
        {"id": rid, "label": labels.get(rid, rid.upper())}
        for rid in workflow_resolution_options(model_id)
    ]
