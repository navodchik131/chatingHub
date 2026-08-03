"""Character appearance profile v1: generation_packs + visibility-aware identity for studio."""

from __future__ import annotations

import json
import re
from typing import Any

from app.services.studio_prompt_bundle import (
    STUDIO_BODY_PROPORTIONS_MAX,
    STUDIO_IDENTITY_LINE_MAX,
    _compact_body_proportions_clause,
    _parse_model_profile_root,
    _profile_identity_fields,
    _truncate_profile_clause,
)

# Lazy import type only
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.studio_reference_analysis import IdentityVisibility

V1_SCHEMA_NAME = "female_character_appearance"
_HIDDEN_MARKERS = ("undefined", "permanently_hidden", "not visible", "скрыт")
_PLACEHOLDER_RE = re.compile(r"<FILL[^>]*>|FILL_OR_LEAVE_FOR_AUTO_DERIVE", re.I)


def _is_unfilled_placeholder(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return True
    if _PLACEHOLDER_RE.search(s):
        parts = [p.strip() for p in re.split(r"[;,|]+", s) if p.strip()]
        if not parts:
            return True
        return all(_PLACEHOLDER_RE.search(p) for p in parts)
    return False


def is_v1_template_dict(data: dict[str, Any]) -> bool:
    meta = data.get("_meta")
    if isinstance(meta, dict) and meta.get("schema_name") == V1_SCHEMA_NAME:
        return True
    return False


def is_v1_character_profile(data: dict[str, Any]) -> bool:
    if is_v1_template_dict(data):
        return True
    return "consistency" in data and (
        "identity" in data or "head_and_face" in data or "generation_packs" in data
    )


def finalize_v1_profile_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Attach derived generation_packs after vision fill or manual edit."""
    out = dict(doc)
    out["generation_packs"] = build_generation_packs(out)
    return out


def parse_profile_document(model_profile_text: str | None) -> dict[str, Any] | None:
    raw = (model_profile_text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if is_v1_character_profile(data):
        return data
    root = _parse_model_profile_root(raw)
    return root if isinstance(root, dict) else None


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_as_text(x) for x in value]
        return ", ".join(p for p in parts if p)
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            if str(k).startswith("_"):
                continue
            t = _as_text(v)
            if t and not _is_hidden_value(t):
                parts.append(f"{k}: {t}")
        return "; ".join(parts)
    return ""


def _usable_pack_text(value: Any) -> str:
    t = _as_text(value)
    if not t or _is_unfilled_placeholder(t):
        return ""
    return t


def _is_hidden_value(text: str) -> bool:
    s = (text or "").strip().lower()
    if not s:
        return True
    if s == "undefined":
        return True
    return any(m in s for m in _HIDDEN_MARKERS)


def _first_non_hidden(*values: Any) -> str:
    for v in values:
        t = _as_text(v)
        if t and not _is_hidden_value(t) and not _is_unfilled_placeholder(t):
            return t
    return ""


def _join_non_empty(parts: list[str], sep: str = "; ") -> str:
    return sep.join(p.strip() for p in parts if p and p.strip())


def _build_figure_lock_v1(doc: dict[str, Any]) -> str:
    packs = doc.get("generation_packs")
    if isinstance(packs, dict):
        existing = _usable_pack_text(packs.get("figure_lock"))
        if existing:
            return existing

    body = doc.get("body")
    if not isinstance(body, dict):
        return ""

    bits: list[str] = []
    height = body.get("height_cm")
    if height:
        bits.append(f"{height} cm")
    build = _as_text(body.get("build"))
    if build:
        bits.append(build)
    sil = _as_text(body.get("silhouette_type"))
    if sil:
        bits.append(sil)

    meas = body.get("measurements_cm")
    if isinstance(meas, dict):
        waist = meas.get("waist")
        hips = meas.get("hips")
        bust = meas.get("bust")
        if waist and hips:
            bits.append(f"waist {waist} hips {hips}")
        elif bust and waist:
            bits.append(f"bust {bust} waist {waist}")

    props = body.get("anatomical_proportions")
    if isinstance(props, dict):
        note = _as_text(props.get("overall_proportion_notes"))
        if note:
            bits.append(note[:220])

    ident = doc.get("identity")
    if isinstance(ident, dict):
        one = _as_text(ident.get("one_line_descriptor"))
        if one and len(bits) < 2:
            bits.append(one)

    return _join_non_empty(bits[:5], ", ")


def _build_face_lock_v1(doc: dict[str, Any]) -> str:
    packs = doc.get("generation_packs")
    if isinstance(packs, dict):
        existing = _usable_pack_text(packs.get("face_lock"))
        if existing:
            return existing

    bits: list[str] = []
    ident = doc.get("identity")
    if isinstance(ident, dict):
        imp = _as_text(ident.get("overall_impression"))
        if imp:
            bits.append(imp[:180])

    skin = doc.get("skin")
    if isinstance(skin, dict):
        tone = _first_non_hidden(skin.get("tone"), skin.get("undertone"))
        if tone:
            bits.append(f"{tone} skin")

    head = doc.get("head_and_face")
    if isinstance(head, dict):
        eyes = head.get("eyes")
        if isinstance(eyes, dict):
            eye_bits = [
                _first_non_hidden(eyes.get("iris_color")),
                _first_non_hidden(eyes.get("shape")),
                _first_non_hidden(eyes.get("gaze_character")),
            ]
            eye_line = _join_non_empty(eye_bits, ", ")
            if eye_line:
                bits.append(f"eyes: {eye_line}")
        brows = head.get("eyebrows")
        if isinstance(brows, dict):
            brow = _first_non_hidden(brows.get("color"), brows.get("shape"))
            if brow:
                bits.append(f"brows: {brow}")

    return _join_non_empty(bits[:4], "; ")


def _build_hair_lock_v1(doc: dict[str, Any]) -> str:
    packs = doc.get("generation_packs")
    if isinstance(packs, dict):
        existing = _usable_pack_text(packs.get("hair_lock"))
        if existing:
            return existing

    hair = doc.get("hair")
    if not isinstance(hair, dict):
        return ""
    bits = [
        _first_non_hidden(hair.get("color"), hair.get("color_details")),
        _first_non_hidden(hair.get("length"), hair.get("length_cm")),
        _first_non_hidden(hair.get("default_style"), hair.get("texture")),
    ]
    return _join_non_empty(bits, ", ")


def _build_accessory_lock_v1(doc: dict[str, Any]) -> str:
    packs = doc.get("generation_packs")
    if isinstance(packs, dict):
        existing = _usable_pack_text(packs.get("accessory_lock"))
        if existing:
            return existing

    acc = doc.get("accessories")
    if not isinstance(acc, dict) or not acc.get("has_accessories"):
        return ""
    items = acc.get("items")
    if not isinstance(items, list):
        return ""
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not (item.get("mandatory") or item.get("always_worn")):
            continue
        name = _as_text(item.get("name") or item.get("type"))
        notes = _as_text(item.get("notes"))
        shape = _as_text(item.get("shape_details"))
        core = _join_non_empty([name, shape[:160], notes[:120]], " — ")
        if core:
            lines.append(core)
    return _join_non_empty(lines, " | ")


def _build_short_summary_v1(doc: dict[str, Any], packs: dict[str, Any]) -> str:
    existing = _usable_pack_text(packs.get("short_prompt_summary"))
    if existing:
        return existing
    consistency = doc.get("consistency")
    if isinstance(consistency, dict):
        s = _usable_pack_text(consistency.get("short_prompt_summary"))
        if s:
            return s
    bits = [
        _as_text(doc.get("identity", {}).get("one_line_descriptor"))
        if isinstance(doc.get("identity"), dict)
        else "",
        packs.get("accessory_lock") or "",
        packs.get("figure_lock") or "",
        packs.get("face_lock") or "",
        packs.get("hair_lock") or "",
    ]
    return _join_non_empty([str(b) for b in bits if b], ". ")


def _build_negative_lock_v1(doc: dict[str, Any]) -> list[str]:
    packs = doc.get("generation_packs")
    if isinstance(packs, dict):
        raw = packs.get("negative_lock")
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
    out: list[str] = []
    consistency = doc.get("consistency")
    if isinstance(consistency, dict):
        for key in ("negative_traits", "must_never_change"):
            raw = consistency.get(key)
            if isinstance(raw, list):
                out.extend(str(x).strip() for x in raw if str(x).strip())
    seen: set[str] = set()
    deduped: list[str] = []
    for item in out:
        low = item.lower()
        if low not in seen:
            seen.add(low)
            deduped.append(item)
    return deduped


def build_generation_packs(doc: dict[str, Any]) -> dict[str, Any]:
    """Derive or return generation_packs for v1 or legacy profile dict."""
    if is_v1_character_profile(doc):
        existing = doc.get("generation_packs")
        packs: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
        derived = {
            "figure_lock": _build_figure_lock_v1(doc),
            "face_lock": _build_face_lock_v1(doc),
            "hair_lock": _build_hair_lock_v1(doc),
            "accessory_lock": _build_accessory_lock_v1(doc),
            "negative_lock": _build_negative_lock_v1(doc),
        }
        for key, value in derived.items():
            if key == "negative_lock":
                if not packs.get(key):
                    packs[key] = value
                continue
            if _usable_pack_text(packs.get(key)):
                continue
            if value:
                packs[key] = value
            else:
                packs.pop(key, None)
        packs["short_prompt_summary"] = _build_short_summary_v1(doc, packs)
        return packs

    # Legacy model_profile
    fields = _profile_identity_fields(doc)
    figure = _compact_body_proportions_clause(
        fields.get("body_proportions") or "",
        max_len=STUDIO_BODY_PROPORTIONS_MAX,
    )
    face = fields.get("face") or ""
    hair = fields.get("hair") or ""
    subj = fields.get("subject") or ""
    keywords = _as_text(doc.get("identity_lock_keywords"))
    negative: list[str] = []
    raw_avoid = doc.get("always_avoid")
    if isinstance(raw_avoid, list):
        negative = [str(x).strip() for x in raw_avoid if str(x).strip()]
    summary_parts = [keywords, subj, figure, face, hair]
    return {
        "short_prompt_summary": _join_non_empty(summary_parts, "; ")[:STUDIO_IDENTITY_LINE_MAX],
        "figure_lock": figure,
        "face_lock": face,
        "hair_lock": hair,
        "accessory_lock": "",
        "negative_lock": negative,
    }


def profile_negative_traits(model_profile_text: str | None) -> str:
    doc = parse_profile_document(model_profile_text)
    if not doc:
        return ""
    packs = build_generation_packs(doc)
    neg = packs.get("negative_lock")
    if isinstance(neg, list) and neg:
        return ", ".join(neg[:24])
    return ""


def filter_v1_profile_for_visibility(
    doc: dict[str, Any],
    visibility: IdentityVisibility,
) -> dict[str, Any]:
    """Return a copy of v1 profile with out-of-frame identity sections removed."""
    import copy

    out = copy.deepcopy(doc)
    face_scope = visibility.include_face
    hair_scope = visibility.include_hair
    body_scope = visibility.include_body_proportions
    head_scope = face_scope or visibility.head_in_reference

    if visibility.headless_crop:
        for key in (
            "head_and_face",
            "hair",
            "accessories",
            "grooming",
        ):
            out.pop(key, None)
        ident = out.get("identity")
        if isinstance(ident, dict):
            ident.pop("overall_impression", None)
            ident.pop("one_line_descriptor", None)

    if not face_scope:
        out.pop("head_and_face", None)
        if not hair_scope:
            out.pop("grooming", None)
        # Mandatory accessories describe face gear — omit unless front face is visible.
        if not face_scope:
            out.pop("accessories", None)

    if not hair_scope:
        out.pop("hair", None)

    if not body_scope:
        out.pop("body", None)
        out.pop("neck_and_shoulders", None)

    packs = out.get("generation_packs")
    if isinstance(packs, dict):
        if not face_scope:
            packs.pop("face_lock", None)
            packs.pop("accessory_lock", None)
        if not hair_scope:
            packs.pop("hair_lock", None)
        if not body_scope:
            packs.pop("figure_lock", None)
        if visibility.headless_crop:
            packs["short_prompt_summary"] = _compact_body_proportions_clause(
                _as_text(packs.get("figure_lock")),
                max_len=STUDIO_IDENTITY_LINE_MAX,
            )

    consistency = out.get("consistency")
    if isinstance(consistency, dict):
        if not face_scope:
            consistency.pop("mandatory_in_every_shot", None)
            anchors = consistency.get("identity_anchors")
            if isinstance(anchors, list):
                consistency["identity_anchors"] = [
                    a
                    for a in anchors
                    if not re.search(r"respirator|mask|eyes|brow|face", str(a), re.I)
                ]

    if not head_scope and not body_scope:
        return {"_meta": out.get("_meta"), "generation_packs": out.get("generation_packs") or {}}

    return out


def filter_model_profile_json_for_visibility(
    model_profile_text: str | None,
    visibility: IdentityVisibility,
) -> str | None:
    if not (model_profile_text or "").strip():
        return model_profile_text
    try:
        data = json.loads(model_profile_text)
    except json.JSONDecodeError:
        return model_profile_text
    if not isinstance(data, dict):
        return model_profile_text

    if is_v1_character_profile(data):
        filtered = filter_v1_profile_for_visibility(data, visibility)
        return json.dumps(filtered, ensure_ascii=False)

    def scrub(obj: dict[str, Any]) -> None:
        if not visibility.include_face:
            obj.pop("face_features", None)
            obj.pop("face", None)
            for key in ("eyes", "nose", "lips"):
                if isinstance(obj.get(key), dict):
                    obj.pop(key, None)
        if not visibility.include_hair:
            obj.pop("hair", None)
        if not visibility.include_expression:
            obj.pop("expression", None)
        if not visibility.include_body_proportions:
            obj.pop("body", None)
            obj.pop("body_type", None)
            obj.pop("body_proportions", None)

    if "model_profile" in data and isinstance(data["model_profile"], dict):
        scrub(data["model_profile"])
    else:
        scrub(data)

    return json.dumps(data, ensure_ascii=False)


def build_identity_line_from_profile(
    model_profile_text: str | None,
    visibility: IdentityVisibility | None,
) -> str:
    """
    Visibility-aware identity line for WaveSpeed (≤ STUDIO_IDENTITY_LINE_MAX).
    Uses generation_packs when present; falls back to legacy field extraction.
    """
    from app.services.studio_reference_analysis import prompt_regions_to_mention

    doc = parse_profile_document(model_profile_text)
    if not doc:
        if visibility is None:
            return (
                "Model body proportions from BODY_REFERENCE and MODEL_PROFILE — "
                "not the pose-reference sitter silhouette."
            )
        mention = prompt_regions_to_mention(visibility)
        return (
            f"Model body on visible regions only ({'; '.join(mention)}). "
            "Do not copy donor silhouette from pose reference."
        )

    packs = build_generation_packs(doc)
    vis = visibility
    bits: list[str] = []

    if vis is None or vis.include_body_proportions:
        figure = _usable_pack_text(packs.get("figure_lock"))
        if figure:
            body = _compact_body_proportions_clause(figure, max_len=STUDIO_BODY_PROPORTIONS_MAX)
            if body:
                bits.append(f"Build: {body}")

    if vis is None or vis.include_face:
        accessory = _usable_pack_text(packs.get("accessory_lock"))
        if accessory:
            bits.append(accessory)
        face = _usable_pack_text(packs.get("face_lock"))
        if face:
            bits.append(face)

    if vis is None or vis.include_hair:
        hair = _usable_pack_text(packs.get("hair_lock"))
        if hair:
            subj_blob = " ".join(bits).lower()
            if hair.lower() not in subj_blob:
                bits.append(hair)

    if not bits:
        summary = _usable_pack_text(packs.get("short_prompt_summary"))
        if summary:
            bits.append(summary[:STUDIO_IDENTITY_LINE_MAX])

    if vis is not None and vis.visible_regions:
        region_hint = ", ".join(sorted(vis.visible_regions))
        joined = _truncate_profile_clause("; ".join(bits), STUDIO_IDENTITY_LINE_MAX - 40)
        if joined:
            return f"Visible regions [{region_hint}]: {joined}. Same person on all visible skin."

    if bits:
        joined = _truncate_profile_clause(
            f"{'; '.join(bits)}. Same person on all visible skin.",
            STUDIO_IDENTITY_LINE_MAX,
        )
        return joined

    summary = _usable_pack_text(packs.get("short_prompt_summary"))
    if summary:
        return _truncate_profile_clause(summary, STUDIO_IDENTITY_LINE_MAX)

    return (
        "Model body proportions from BODY_REFERENCE and MODEL_PROFILE — "
        "not the pose-reference sitter silhouette."
    )


def build_figure_anchor_from_profile(
    model_profile_text: str | None,
    visibility: IdentityVisibility | None = None,
) -> str:
    """Grok FIGURE_LOCK / WaveSpeed anchor — same visibility rules as identity line."""
    return build_identity_line_from_profile(model_profile_text, visibility).strip()
