"""Сборка промпта для WaveSpeed: разделение identity/scene, neg отдельно, без дублей с суффиксами."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.studio_openai import (
    _strip_code_fences,
    load_canonical_realism_engine,
)

log = logging.getLogger(__name__)

# Анатомия/артефакты — без существительных сцены (bed, blanket и т.д.)
_CANONICAL_STUDIO_NEGATIVE = (
    "deformed hands, extra fingers, fused fingers, missing fingers, bad anatomy, "
    "duplicate limbs, extra arms, malformed joints, watermark, text, logo, "
    "uncanny symmetry, Facetune, beauty-filter face, influencer glamour, plastic skin, "
    "airbrushed, CGI, 3d render, heavy fake bokeh, stock photo, catalog lighting, "
    "TikTok reshaped eyes or jaw, composite collage, face pasted on wrong body, "
    "mismatched skin tone face vs body"
)

_SCENE_FROM_REF_LITERAL = "from_pose_reference_input_image_only"


def _merge_negative_parts(*parts: str | None) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for block in parts:
        if not block or not str(block).strip():
            continue
        for piece in re.split(r"[,;\n]+", str(block)):
            t = piece.strip().lower()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(piece.strip())
    return ", ".join(out)


def _always_avoid_from_profile(model_profile_text: str | None) -> str:
    if not model_profile_text or not model_profile_text.strip():
        return ""
    try:
        data = json.loads(model_profile_text.strip())
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    prof = data.get("model_profile")
    if not isinstance(prof, dict):
        prof = data
    raw = prof.get("always_avoid")
    if isinstance(raw, list):
        return ", ".join(str(x).strip() for x in raw if str(x).strip())
    if isinstance(raw, str):
        return raw.strip()
    return ""


def _avoid_list_from_constraints(data: dict[str, Any]) -> list[str]:
    cons = data.get("constraints")
    if not isinstance(cons, dict):
        return []
    raw = cons.get("avoid")
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def extract_studio_negative_prompt(
    refined_data: dict[str, Any],
    *,
    model_profile_text: str | None,
) -> str:
    neg = refined_data.pop("negative_prompt", None)
    neg_s = neg.strip() if isinstance(neg, str) else ""
    avoid_parts = _avoid_list_from_constraints(refined_data)
    cons = refined_data.get("constraints")
    if isinstance(cons, dict) and "avoid" in cons:
        cons = dict(cons)
        cons.pop("avoid", None)
        if cons:
            refined_data["constraints"] = cons
        elif "constraints" in refined_data and not cons:
            refined_data.pop("constraints", None)
    avoid_merged = ", ".join(avoid_parts)
    profile_avoid = _always_avoid_from_profile(model_profile_text)
    return _merge_negative_parts(_CANONICAL_STUDIO_NEGATIVE, neg_s, avoid_merged, profile_avoid)


def _enforce_compact_scene_literals(data: dict[str, Any]) -> None:
    scene = data.get("scene_from_reference_image")
    if not isinstance(scene, dict):
        return
    for key in ("pose_and_composition", "wardrobe_and_environment", "lighting_and_camera"):
        if key in scene:
            scene[key] = _SCENE_FROM_REF_LITERAL


def prepare_positive_prompt_json(
    refined_text: str,
    *,
    brief_mode: str,
    model_profile_text: str | None,
) -> tuple[str, str]:
    """
    Возвращает (positive_json_str, negative_prompt_line).
    brief_mode: full | compact_pose_image | text_scene
    """
    raw = _strip_code_fences(refined_text)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        log.warning("studio prompt bundle: refined output not JSON, pass-through")
        return refined_text.strip(), _CANONICAL_STUDIO_NEGATIVE

    if not isinstance(data, dict):
        return refined_text.strip(), _CANONICAL_STUDIO_NEGATIVE

    re_obj = load_canonical_realism_engine()
    if re_obj is not None:
        data["realism_engine"] = re_obj

    negative = extract_studio_negative_prompt(data, model_profile_text=model_profile_text)

    mode = (brief_mode or "full").strip().lower()
    if mode == "compact_pose_image":
        _enforce_compact_scene_literals(data)

    positive = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return positive, negative


def append_negative_to_wavespeed_prompt(prompt: str, negative: str) -> str:
    neg = (negative or "").strip()
    if not neg:
        return prompt
    base = (prompt or "").rstrip()
    return f"{base}\n\n[NEGATIVE_PROMPT] {neg}"
