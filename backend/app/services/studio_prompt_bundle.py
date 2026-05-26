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

_CANONICAL_STUDIO_NEGATIVE = (
    "deformed hands, extra fingers, fused fingers, missing fingers, bad anatomy, "
    "duplicate limbs, extra arms, malformed joints, watermark, text, logo, "
    "uncanny symmetry, Facetune, beauty-filter face, influencer glamour, plastic skin, "
    "airbrushed, CGI, 3d render, heavy fake bokeh, stock photo, catalog lighting, "
    "TikTok reshaped eyes or jaw, composite collage, face pasted on wrong body, "
    "mismatched skin tone face vs body"
)

_SCENE_FROM_REF_LITERAL = "from_pose_reference_input_image_only"

_COMPACT_MUST_KEEP = [
    "One real person; face, skin, hair, and body proportions from identity_reference and model reference photos (images 2+) on all visible skin",
    "Pose, outfit, framing, background, and scene lighting from pose reference (image 1) and pose_reference_notes — never copy pose or backdrop from identity photos",
    "Unified skin grain face-to-body; scene light direction on MODEL skin, not donor complexion",
]

_COMPACT_IDENTITY_FIELD_MAX = 420
_COMPACT_SCENE_NOTES_MAX = 720

_SCENE_NOTE_KEYS = (
    "POSE:",
    "FRAMING:",
    "HEAD_GEOMETRY",
    "CAMERA_",
    "CLOTHING",
    "BACKGROUND",
    "LIGHT_ON",
    "CAPTURE_TYPE",
    "VIEW_DIRECTION",
    "SHOT_TYPE",
    "BODY_ORIENTATION",
)

# Слова сцены в always_avoid профиля — не тащим в negative (конфликт с балконом, закатом и т.д.)
_SCENE_AVOID_RE = re.compile(
    r"\b("
    r"selfie|bedroom|blanket|morning\s+light|boudoir|kitchen|bathroom|"
    r"gym\s+mirror|hotel\s+room|living\s+room|indoor\s+studio|outdoor\s+villa|"
    r"balcony|rice\s+field|swimming\s+pool|sunset\s+sky|glass\s+railing|"
    r"halter|skirt|crochet|professional\s+studio|catalog\s+lighting"
    r")\b",
    re.I,
)

_QUALITY_AVOID_HINTS = (
    "plastic",
    "anatomy",
    "deform",
    "finger",
    "airbrush",
    "cgi",
    "render",
    "watermark",
    "logo",
    "blur",
    "bokeh",
    "symmetry",
    "facetune",
    "beauty",
    "glamour",
    "stock",
    "makeup",
    "quality",
    "composite",
    "pasted",
    "mismatched",
    "generic",
    "reshaped",
    "jaw",
    "eyes",
    "nudity",
    "over-smil",
)

_IDENTITY_AVOID_HINTS = (
    "flat chest",
    "flat butt",
    "small breast",
    "narrow hip",
    "ghost skin",
    "pale white",
    "very dark skin",
    "wrong hair",
    "black hair",
    "blonde",
    "red hair",
    "ginger",
    "braid",
    "short hair",
    "straight hair",
    "exposed breast",
    "front-facing camera",
)

_DESC_SCENE_SPLIT_RE = re.compile(
    r"\s*,\s*(?=standing|seated|sitting|laying|lying|leaning|posing|on\s+an?\s+|"
    r"with\s+her\s+|with\s+his\s+|body\s+angled|back\s+facing|facing\s+the\s+camera)",
    re.I,
)


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


def _is_scene_specific_avoid_term(term: str) -> bool:
    t = term.strip().lower()
    if not t:
        return True
    if _SCENE_AVOID_RE.search(t):
        return True
    if any(
        w in t
        for w in (
            "setting",
            "backdrop",
            "outfit",
            "dress",
            "wardrobe",
            "location",
            "room",
            "beach",
            "street",
            "cafe",
        )
    ):
        return True
    return False


def _keep_avoid_term(term: str) -> bool:
    t = term.strip().lower()
    if not t or _is_scene_specific_avoid_term(term):
        return False
    if any(h in t for h in _QUALITY_AVOID_HINTS):
        return True
    if any(h in t for h in _IDENTITY_AVOID_HINTS):
        return True
    return False


def _filter_avoid_csv(raw: str) -> str:
    kept = [a for a in re.split(r"[,;\n]+", raw) if _keep_avoid_term(a)]
    return ", ".join(kept)


def _parse_model_profile_root(model_profile_text: str | None) -> dict[str, Any] | None:
    if not model_profile_text or not model_profile_text.strip():
        return None
    try:
        data = json.loads(model_profile_text.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    prof = data.get("model_profile")
    return prof if isinstance(prof, dict) else data


def _as_text(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, dict):
        parts = [_as_text(v) for v in val.values() if _as_text(v)]
        return "; ".join(parts)
    if isinstance(val, list):
        return "; ".join(_as_text(v) for v in val if _as_text(v))
    return ""


def _truncate_identity_field(text: str, *, max_len: int = _COMPACT_IDENTITY_FIELD_MAX) -> str:
    s = (text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def compact_scene_notes_from_reference(description: str | None) -> str:
    """Короткая выжимка REFERENCE_IMAGE для compact JSON (поза в тексте + image 1)."""
    raw = (description or "").strip()
    if not raw:
        return ""
    lines: list[str] = []
    for line in raw.splitlines():
        t = line.strip()
        if not t:
            continue
        upper = t.upper()
        if any(k in upper for k in _SCENE_NOTE_KEYS):
            lines.append(t)
    text = " ".join(lines) if lines else raw
    return _truncate_identity_field(text, max_len=_COMPACT_SCENE_NOTES_MAX)


def _compact_profile_identity_fields(prof: dict[str, Any] | None) -> dict[str, str]:
    """Сжатый identity для WAN compact — не весь вложенный профиль в одну строку."""
    if not prof:
        return {}
    keywords = _as_text(prof.get("identity_lock_keywords"))
    full = _profile_identity_fields(prof)
    if keywords:
        full["subject"] = _truncate_identity_field(keywords, max_len=300)
    for key in ("face", "hair", "body_proportions"):
        if full.get(key):
            full[key] = _truncate_identity_field(full[key])
    return full


def _profile_identity_fields(prof: dict[str, Any] | None) -> dict[str, str]:
    if not prof:
        return {}
    age = _as_text(prof.get("age"))
    eth = _as_text(prof.get("ethnicity"))
    face = _as_text(prof.get("face_features") or prof.get("face"))
    body = _as_text(
        prof.get("body_type")
        or prof.get("body_proportions")
        or prof.get("body")
    )
    hair_raw = prof.get("hair")
    hair = _as_text(hair_raw)
    if isinstance(hair_raw, dict):
        hair = _as_text(
            {
                "color": hair_raw.get("color"),
                "length": hair_raw.get("length"),
                "style": hair_raw.get("style_default") or hair_raw.get("style"),
            }
        )
    subj_bits = [b for b in (age, eth) if b]
    subject = ""
    if subj_bits:
        subject = f"{', '.join(subj_bits)}"
        if hair:
            subject += f", {hair.split(';')[0].strip()}"
    return {
        "subject": subject,
        "face": face,
        "hair": hair,
        "body_proportions": body,
    }


def _llm_identity_fields(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    id_ref = data.get("identity_reference")
    if isinstance(id_ref, dict):
        for k in ("subject", "face", "hair", "body_proportions"):
            v = _as_text(id_ref.get(k))
            if v:
                out[k] = v
        if out:
            return out

    subj = data.get("subject")
    if not isinstance(subj, dict):
        return out

    desc = _as_text(subj.get("description"))
    if desc:
        parts = _DESC_SCENE_SPLIT_RE.split(desc, maxsplit=1)
        out["subject"] = parts[0].strip()
        if len(parts) > 1 and "hourglass" in desc.lower():
            m = re.search(
                r"(curvy|hourglass|athletic|full\s+round\s+bust|pronounced\s+round\s+glutes)[^.]*",
                desc,
                re.I,
            )
            if m and "body_proportions" not in out:
                out["body_proportions"] = m.group(0).strip()

    ident = subj.get("identity")
    if isinstance(ident, dict):
        if not out.get("face"):
            out["face"] = _as_text(ident.get("face_features"))
        if not out.get("body_proportions"):
            out["body_proportions"] = _as_text(ident.get("body_type"))
        hair_i = ident.get("hair")
        if not out.get("hair") and isinstance(hair_i, dict):
            out["hair"] = _as_text(
                {
                    "color": hair_i.get("color"),
                    "length": hair_i.get("length"),
                    "style": hair_i.get("style_default"),
                }
            )

    body = subj.get("body")
    if isinstance(body, dict):
        frame = _as_text(body.get("frame"))
        chest = _as_text(body.get("chest"))
        legs = _as_text(body.get("legs"))
        skin = body.get("skin")
        skin_t = _as_text(skin.get("tone")) if isinstance(skin, dict) else ""
        parts = [p for p in (frame, chest, legs) if p]
        if parts:
            body_line = "; ".join(parts)
            if skin_t:
                body_line += f"; skin tone {skin_t}"
            if not out.get("body_proportions"):
                out["body_proportions"] = body_line
            elif chest or frame:
                out["body_proportions"] = body_line

    hair_block = subj.get("hair")
    if not out.get("hair") and isinstance(hair_block, dict):
        out["hair"] = _as_text(
            {
                "color": hair_block.get("color"),
                "style": hair_block.get("style"),
                "effect": hair_block.get("effect"),
            }
        )

    return out


def _pick_identity_field(
    key: str,
    *,
    profile: dict[str, str],
    llm: dict[str, str],
) -> str:
    p = profile.get(key, "").strip()
    l = llm.get(key, "").strip()
    if key == "body_proportions":
        return p or l
    if key == "subject":
        if p:
            return p
        return l
    return p or l


def coerce_compact_pose_positive(
    data: dict[str, Any],
    *,
    model_profile_text: str | None,
    reference_scene_description: str | None = None,
) -> dict[str, Any]:
    """
    Жёстко собирает compact JSON: сцена — image 1 + краткие pose_reference_notes;
    identity (включая фигуру) — сжато из профиля/LLM.
    """
    prof_root = _parse_model_profile_root(model_profile_text)
    prof_id = _compact_profile_identity_fields(prof_root)
    llm_id = _llm_identity_fields(data)

    identity = {
        k: _pick_identity_field(k, profile=prof_id, llm=llm_id)
        for k in ("subject", "face", "hair", "body_proportions")
    }
    if not any(identity.values()):
        log.warning("compact pose coerce: empty identity_reference, keeping minimal placeholder")
        identity["subject"] = identity["subject"] or "studio model identity from reference photos"

    user_overrides = _as_text(data.get("user_overrides"))

    snapshot = "casual realistic smartphone snapshot, natural phone grain"
    aspect = "3:4"
    ps = data.get("photography_style")
    if isinstance(ps, dict):
        snapshot = _as_text(ps.get("snapshot_authenticity")) or snapshot
        aspect = _as_text(ps.get("aspect_ratio")) or aspect
    else:
        photo = data.get("photography")
        if isinstance(photo, dict):
            aspect = _as_text(photo.get("aspect_ratio")) or aspect
            snap = _as_text(photo.get("camera_style")) or _as_text(photo.get("texture"))
            if snap:
                snapshot = snap

    mood = ""
    life = ""
    tv = data.get("the_vibe")
    if isinstance(tv, dict):
        mood = _as_text(tv.get("mood"))
        life = _as_text(tv.get("life_in_frame") or tv.get("intimacy_level") or tv.get("intimacy"))

    scene_notes = compact_scene_notes_from_reference(reference_scene_description)
    scene_pose = scene_notes or _SCENE_FROM_REF_LITERAL
    return {
        "identity_reference": identity,
        "scene_from_reference_image": {
            "pose_and_composition": scene_pose,
            "wardrobe_and_environment": scene_pose,
            "lighting_and_camera": scene_pose,
            "pose_reference_notes": scene_notes,
        },
        "user_overrides": user_overrides,
        "photography_style": {
            "snapshot_authenticity": snapshot,
            "aspect_ratio": aspect,
        },
        "the_vibe": {
            "mood": mood or "natural",
            "life_in_frame": life or "everyday candid moment",
        },
        "constraints": {"must_keep": list(_COMPACT_MUST_KEEP)},
    }


def _always_avoid_from_profile(model_profile_text: str | None) -> str:
    prof = _parse_model_profile_root(model_profile_text)
    if not prof:
        return ""
    raw = prof.get("always_avoid")
    if isinstance(raw, list):
        merged = ", ".join(str(x).strip() for x in raw if str(x).strip())
    elif isinstance(raw, str):
        merged = raw.strip()
    else:
        return ""
    return _filter_avoid_csv(merged)


def _avoid_list_from_constraints(data: dict[str, Any]) -> list[str]:
    cons = data.get("constraints")
    if not isinstance(cons, dict):
        return []
    raw = cons.get("avoid")
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip() and _keep_avoid_term(str(x))]
    if isinstance(raw, str) and raw.strip():
        return [a for a in re.split(r"[,;\n]+", raw) if _keep_avoid_term(a)]
    return []


def extract_studio_negative_prompt(
    refined_data: dict[str, Any],
    *,
    model_profile_text: str | None,
) -> str:
    neg = refined_data.pop("negative_prompt", None)
    neg_s = neg.strip() if isinstance(neg, str) else ""
    if neg_s:
        neg_s = _filter_avoid_csv(neg_s)
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


def prepare_positive_prompt_json(
    refined_text: str,
    *,
    brief_mode: str,
    model_profile_text: str | None,
    reference_scene_description: str | None = None,
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

    mode = (brief_mode or "full").strip().lower()
    if mode == "compact_pose_image":
        data = coerce_compact_pose_positive(
            data,
            model_profile_text=model_profile_text,
            reference_scene_description=reference_scene_description,
        )

    re_obj = load_canonical_realism_engine()
    if re_obj is not None:
        data["realism_engine"] = re_obj

    negative = extract_studio_negative_prompt(data, model_profile_text=model_profile_text)

    positive = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return positive, negative


def append_negative_to_wavespeed_prompt(prompt: str, negative: str) -> str:
    neg = (negative or "").strip()
    if not neg:
        return prompt
    base = (prompt or "").rstrip()
    return f"{base}\n\n[NEGATIVE_PROMPT] {neg}"
