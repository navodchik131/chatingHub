"""Face swap: pass 1 dress+pose на сером фоне, pass 2 замена персонажа на реф-сцене."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, settings

log = logging.getLogger(__name__)

_PASS1 = "face_swap_dress_pose_pass1.txt"
_PASS2 = "face_swap_dress_pose_pass2.txt"


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
    raise RuntimeError(f"Two-pass face swap prompt missing (tried: {tried})")


def face_swap_two_pass_enabled() -> bool:
    """Dress+pose → swap; выключается classic single-pass."""
    if not getattr(settings, "studio_face_swap_two_pass", True):
        return False
    from app.services.studio_face_swap_seedream_v5 import face_swap_classic_enabled

    if face_swap_classic_enabled(""):
        return False
    from app.services.studio_anchor_pipeline import face_swap_mannequin_prep_enabled

    return face_swap_mannequin_prep_enabled()


def dress_pose_prep_cache_key(
    *,
    scene_bytes: bytes,
    wave_profile: str,
    body_image_id: int | None,
    face_image_id: int | None,
) -> str:
    """Кэш pass 1: тело+лицо+реф → модель в одежде и позе рефа на сером фоне."""
    h = hashlib.sha256()
    wp = (wave_profile or "nsfw").strip().lower()
    h.update(f"dress_pose_v3|{wp}|b{body_image_id or 0}|f{face_image_id or 0}".encode())
    h.update(hashlib.sha256(scene_bytes).digest())
    return h.hexdigest()


def extract_scene_section_block(scene_text: str, section: str) -> str:
    """Текст секции POSE / CAMERA / CROP из Grok SCENE_ANALYSIS."""
    from app.services.studio_anchor_pipeline import extract_scene_section_from_scene_text

    return extract_scene_section_from_scene_text(scene_text, section)


def _visibility_face_line(scene_text: str) -> str:
    """Строка `- Face: …` из VISIBILITY — там же отметка partially visible."""
    m = re.search(r"(?im)^\s*[-*]?\s*face\s*:\s*(.+)$", scene_text or "")
    return m.group(1).strip() if m else ""


def build_crop_lock_block(scene_description: str, *, image_label: str) -> str:
    """Жёсткий лок кадра: не дорисовывать то, что обрезано рамкой рефа."""
    crop = extract_scene_section_block(scene_description, "CROP").strip()
    face_line = _visibility_face_line(scene_description)
    lines = [
        f"CROP LOCK (mandatory — reproduce the framing of {image_label} exactly):",
        f"- Any body part cut off by the frame edge in {image_label} must stay cut off in the output.",
        "- Do not zoom out, do not widen the crop, do not shift the camera to reveal more of the body.",
        "- Do not complete or reconstruct a head, face, limb, or any body part that the frame cuts off.",
        "- If only part of the face is inside the frame (for example only chin, lips and jaw), keep exactly "
        "that part visible and keep the rest outside the frame — never render the whole face.",
        "- Keep the same distance from the camera and the same subject scale within the frame.",
    ]
    if crop:
        lines.append("")
        lines.append(crop)
    if face_line:
        lines.append("")
        lines.append(f"Face in frame: {face_line}")
    return "\n".join(lines)


def reference_aspect_key(scene_bytes: bytes, fallback: str) -> str:
    """Аспект pass 1 = аспект рефа, иначе рамка кадра и кроп не совпадут."""
    from app.services.studio_aspect import ASPECT_PRESETS, normalize_aspect_key

    try:
        fb = normalize_aspect_key(fallback)
    except Exception:
        fb = "9:16"
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(scene_bytes)) as im:
            w, h = im.size
    except Exception:
        return fb
    if not w or not h:
        return fb
    ratio = w / h
    best = min(
        ASPECT_PRESETS.items(),
        key=lambda kv: abs((kv[1][0] / kv[1][1]) - ratio),
    )
    return best[0]


def _model_marks_snippet(filtered_anchor: str, model_profile_text: str | None) -> str:
    """Краткий контекст тату/пирсингов модели для pass 1 (не с рефа)."""
    src = (filtered_anchor or model_profile_text or "").strip()
    if not src:
        return (
            "No tattoos or piercings documented for this model — output must have none; "
            "do not copy any from image 3."
        )
    picked: list[str] = []
    for line in src.splitlines():
        low = line.lower()
        if any(
            k in low
            for k in (
                "tattoo",
                "pierc",
                "freckle",
                "mole",
                "scar",
                "birthmark",
                "distinguishing",
                "jewelry",
                "body mod",
                "no tattoo",
                "no pierc",
            )
        ):
            s = line.strip()
            if s:
                picked.append(s)
    if picked:
        return "MODEL MARKS (keep only these on the model):\n" + "\n".join(picked[:24])
    if re.search(r"(?i)no\s+tattoo|without\s+tattoo|has_tattoos.?false", src):
        return "MODEL MARKS: Profile indicates no tattoos — output none; do not copy from image 3."
    return (
        "MODEL MARKS: Use only freckles, moles, tattoos, and piercings visible on model images 1–2; "
        "never from image 3."
    )


def _body_difference_snippet(filtered_anchor: str, model_profile_text: str | None) -> str:
    """Кратко: фигура модели для pass 2 (не копировать реф-персонажа)."""
    src = (filtered_anchor or model_profile_text or "").strip()
    if not src:
        return (
            "Use the body shape, proportions and skin tone from image 2 only; "
            "do not match the reference person's physique from image 1."
        )
    compact = re.sub(r"\s+", " ", src)
    if len(compact) > 900:
        compact = compact[:897].rstrip() + "…"
    return compact


def build_dress_pose_pass1_prompt(
    *,
    scene_description: str,
    visibility_block: str = "",
    filtered_anchor: str = "",
    model_profile_text: str | None = None,
    vis: Any | None = None,
) -> str:
    """Pass 1: WaveSpeed [body, face, reference]."""
    from app.services.studio_anchor_pipeline import (
        AnchorVisibility,
        two_pass_pass1_identity_marks_block,
    )

    v = vis if isinstance(vis, AnchorVisibility) else AnchorVisibility()
    template = _read_prompt_file(_PASS1)
    pose = extract_scene_section_block(scene_description, "POSE") or (
        "Match the full body pose, limb placement and gaze from image 3 exactly."
    )
    camera = extract_scene_section_block(scene_description, "CAMERA") or (
        "Match the camera angle, height, distance and crop from image 3 exactly."
    )
    out = (
        template.replace("{{POSE_DESCRIPTION}}", pose.strip())
        .replace("{{CAMERA_DESCRIPTION}}", camera.strip())
    )
    marks_ctx = _model_marks_snippet(filtered_anchor, model_profile_text)
    out = f"{out}\n\n{marks_ctx}\n\n{two_pass_pass1_identity_marks_block(v)}"
    vis_txt = (visibility_block or "").strip()
    if vis_txt:
        out = f"{out}\n\n{vis_txt}"
    # CROP LOCK последним: он уточняет частично обрезанное лицо поверх общей видимости.
    out = f"{out}\n\n{build_crop_lock_block(scene_description, image_label='image 3')}"
    return out.strip()


def build_dress_pose_pass2_prompt(
    *,
    filtered_anchor: str,
    model_profile_text: str | None,
    visibility_block: str = "",
    vis: Any | None = None,
    scene_description: str = "",
) -> str:
    """Pass 2: WaveSpeed [reference, pass1 result, face]."""
    from app.services.studio_anchor_pipeline import (
        AnchorVisibility,
        SCENE_OVERLAY_EXCLUSION_BLOCK,
        two_pass_pass2_identity_marks_block,
    )

    v = vis if isinstance(vis, AnchorVisibility) else AnchorVisibility()
    template = _read_prompt_file(_PASS2)
    body_diff = _body_difference_snippet(filtered_anchor, model_profile_text)
    out = template.replace("{{BODY_DIFFERENCE}}", body_diff)
    out = (
        f"{out}\n\n{two_pass_pass2_identity_marks_block(v)}"
        f"\n\n{SCENE_OVERLAY_EXCLUSION_BLOCK}"
    )
    vis_txt = (visibility_block or "").strip()
    if vis_txt:
        out = f"{out}\n\n{vis_txt}"
    out = f"{out}\n\n{build_crop_lock_block(scene_description, image_label='image 1')}"
    return out.strip()
