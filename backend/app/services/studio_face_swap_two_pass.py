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
    h.update(f"dress_pose_v2|{wp}|b{body_image_id or 0}|f{face_image_id or 0}".encode())
    h.update(hashlib.sha256(scene_bytes).digest())
    return h.hexdigest()


def extract_scene_section_block(scene_text: str, section: str) -> str:
    """Текст секции POSE / CAMERA из Grok SCENE_ANALYSIS."""
    from app.services.studio_anchor_pipeline import extract_scene_section_from_scene_text

    return extract_scene_section_from_scene_text(scene_text, section)


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
    return out.strip()


def build_dress_pose_pass2_prompt(
    *,
    filtered_anchor: str,
    model_profile_text: str | None,
    visibility_block: str = "",
    vis: Any | None = None,
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
    out = f"{out}\n\n{two_pass_pass2_identity_marks_block(v)}\n\n{SCENE_OVERLAY_EXCLUSION_BLOCK}"
    vis_txt = (visibility_block or "").strip()
    if vis_txt:
        out = f"{out}\n\n{vis_txt}"
    return out.strip()
