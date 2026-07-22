"""Анализ референса и сборка промпта только по видимым частям тела."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.config import BACKEND_DIR, settings
from app.db.models import UserStudioModelImage
from app.services.studio_grok_motion import _grok_fps_stills_model, grok_motion_studio_credentials
from app.services.studio_grok_scene_compose import grok_scene_compose_configured
from app.services.studio_openai import (
    StudioOpenAiCredentials,
    _strip_code_fences,
    chat_completion_openai_compatible_text,
)

log = logging.getLogger(__name__)

_REGION_ALIASES = {
    "FACE": "FACE",
    "HAIR": "HAIR",
    "NECK": "NECK",
    "CHEST": "CHEST",
    "TORSO": "TORSO",
    "HANDS": "HANDS",
    "HAND": "HANDS",
    "ARMS": "ARMS",
    "ARM": "ARMS",
    "LEGS": "LEGS",
    "LEG": "LEGS",
    "FEET": "FEET",
    "FOOT": "FEET",
    "BUTT": "BUTT",
    "GLUTES": "BUTT",
    "FULL_BODY": "FULL_BODY",
    "FULLBODY": "FULL_BODY",
}


class ReferenceAnalysis(BaseModel):
    face_in_frame: bool = False
    hair_in_frame: bool = False
    head_partial: bool = False
    visible_regions: list[str] = Field(default_factory=list)
    framing_crop: str = ""
    pose_summary: str = ""
    clothing_summary: str = ""
    background_summary: str = ""
    lighting_summary: str = ""
    camera_summary: str = ""
    capture_type: str = ""
    wardrobe_coverage: str = ""
    scene_notes: str = ""

    def normalized_regions(self) -> set[str]:
        out: set[str] = set()
        for raw in self.visible_regions:
            key = _REGION_ALIASES.get(str(raw or "").strip().upper())
            if key:
                out.add(key)
        if self.face_in_frame:
            out.add("FACE")
        if self.hair_in_frame:
            out.add("HAIR")
        return out


@dataclass(frozen=True)
class IdentityVisibility:
    include_face: bool
    include_hair: bool
    include_expression: bool
    include_body_proportions: bool
    include_hands_detail: bool
    """True when reference shows back/side of head or hair without visible face."""
    head_in_reference: bool
    """True when reference has no face AND no partial head — legs-only crop, etc."""
    headless_crop: bool
    allowed_image_kinds: frozenset[str]
    visible_regions: frozenset[str] = frozenset()

    @property
    def crop_locked_no_face(self) -> bool:
        """API alias — same as headless_crop."""
        return self.headless_crop


@dataclass(frozen=True)
class StudioPromptPlan:
    analysis: ReferenceAnalysis
    visibility: IdentityVisibility
    reference_scene_description: str
    pruned_skeleton: str
    filtered_model_profile_text: str | None
    effective_studio_mode: str
    skip_no_face_suffix: bool


def load_reference_analyze_prompt() -> str:
    path = (BACKEND_DIR / "data/prompts/image_studio_reference_analyze.txt").resolve()
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    bundled = (BACKEND_DIR / "_bundled_prompts/image_studio_reference_analyze.txt").resolve()
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8").strip()
    return ""


def build_identity_visibility(
    analysis: ReferenceAnalysis,
    *,
    wave_profile: str = "nsfw",
) -> IdentityVisibility:
    regions = analysis.normalized_regions()
    face = bool(analysis.face_in_frame)
    hair = bool(analysis.hair_in_frame) or "HAIR" in regions
    body_visible = bool(
        regions
        & {"TORSO", "CHEST", "NECK", "LEGS", "FEET", "BUTT", "FULL_BODY", "ARMS", "HANDS"}
    )
    hands = bool(regions & {"HANDS", "ARMS"})
    head_partial = bool(analysis.head_partial)
    headless_crop = not face and not head_partial
    head_in_reference = face or head_partial or hair

    allowed: set[str] = {"body", "other", "turnaround"}
    if face:
        allowed.add("face")
    if body_visible and (wave_profile or "").strip().lower() == "nsfw":
        if regions & {"LEGS", "FEET", "BUTT", "TORSO", "CHEST", "FULL_BODY"}:
            allowed.add("genitals")
    if not face:
        allowed.discard("face")

    return IdentityVisibility(
        include_face=face,
        include_hair=hair,
        include_expression=face,
        include_body_proportions=body_visible,
        include_hands_detail=hands,
        head_in_reference=head_in_reference,
        headless_crop=headless_crop,
        allowed_image_kinds=frozenset(allowed),
        visible_regions=frozenset(regions),
    )


def format_reference_scene_from_analysis(analysis: ReferenceAnalysis) -> str:
    lines = [
        f"FRAMING: {analysis.framing_crop or '(unspecified)'}",
        f"POSE: {analysis.pose_summary or '(unspecified)'}",
        f"CLOTHING: {analysis.clothing_summary or analysis.wardrobe_coverage or '(unspecified)'}",
        f"BACKGROUND: {analysis.background_summary or '(unspecified)'}",
        f"LIGHT: {analysis.lighting_summary or '(unspecified)'}",
        f"CAMERA_DISTANCE: {analysis.camera_summary or '(unspecified)'}",
        f"CAPTURE_TYPE: {analysis.capture_type or '(unspecified)'}",
        f"WARDROBE_COVERAGE: {analysis.wardrobe_coverage or '(unspecified)'}",
        f"VISIBLE_REGIONS: {', '.join(sorted(analysis.normalized_regions())) or 'none listed'}",
    ]
    if not analysis.face_in_frame:
        if analysis.head_partial:
            lines.append(
                "FACE_IN_FRAME: false — back/side of head or hair may be visible; "
                "preserve that mass exactly; do NOT synthesize eyes/nose/mouth from model photos."
            )
        else:
            lines.append(
                "FACE_IN_FRAME: false — no head in crop; do not widen framing or add a head."
            )
    if analysis.hair_in_frame:
        lines.append("HAIR_IN_FRAME: true — hair extent in crop only; color/style from MODEL_PROFILE.")
    elif not analysis.face_in_frame:
        lines.append("HAIR_IN_FRAME: false — omit hair identity fields unless hair appears in crop.")
    notes = (analysis.scene_notes or "").strip()
    if notes:
        lines.append("")
        lines.append(notes)
    return "\n".join(lines)


def build_visibility_plan_block(visibility: IdentityVisibility) -> str:
    include: list[str] = []
    exclude: list[str] = []
    if visibility.include_face:
        include.append("face_features / face likeness from MODEL_PROFILE")
    else:
        exclude.append("face_features, expression, eyes, mouth, gaze — face NOT in reference crop")
    if visibility.include_hair:
        include.append("hair color/style from MODEL_PROFILE in hair_in_scene")
    else:
        exclude.append("hair_in_scene and profile hair — no hair visible in crop")
    if visibility.include_body_proportions:
        include.append("body_type / skin tone on visible anatomy from MODEL_PROFILE")
    if visibility.include_hands_detail:
        include.append("hands detail in pose.hands")
    if visibility.headless_crop:
        exclude.append("widening shot, adding headroom, inventing head/face from identity photos")
    elif not visibility.include_face and visibility.head_in_reference:
        exclude.append(
            "facial features from model photos — preserve visible head/back/hair from pose reference only"
        )
    lines = ["## VISIBILITY_PLAN (server — obey strictly)"]
    if include:
        lines.append("INCLUDE in JSON: " + "; ".join(include))
    if exclude:
        lines.append("OMIT or leave minimal: " + "; ".join(exclude))
    lines.append(
        f"Allowed model reference photo kinds for this crop: {', '.join(sorted(visibility.allowed_image_kinds))}"
    )
    return "\n".join(lines)


_REGION_PROMPT_LABELS: dict[str, str] = {
    "FACE": "face / expression / gaze",
    "HAIR": "hair (color/style from MODEL for visible hair mass only)",
    "NECK": "neck",
    "CHEST": "chest / bust",
    "TORSO": "torso / waist / midsection",
    "HANDS": "hands / fingers",
    "ARMS": "arms",
    "LEGS": "legs / thighs / knees",
    "FEET": "feet / ankles",
    "BUTT": "hips / buttocks",
    "FULL_BODY": "full-body proportions",
}

_ALL_REGION_KEYS = frozenset(_REGION_PROMPT_LABELS)


def prompt_regions_to_mention(visibility: IdentityVisibility) -> list[str]:
    """Human labels for anatomy the final prompt MAY describe."""
    regions = visibility.visible_regions
    if not regions:
        if visibility.include_body_proportions:
            return ["visible body anatomy in crop"]
        return ["scene and pose only"]
    out: list[str] = []
    for key in sorted(regions):
        label = _REGION_PROMPT_LABELS.get(key)
        if label:
            out.append(label)
    if not visibility.include_face and "face / expression / gaze" in out:
        out.remove("face / expression / gaze")
    if not visibility.include_hair and any("hair" in x for x in out):
        out = [x for x in out if "hair" not in x]
    return out or ["scene and pose only"]


def prompt_regions_to_omit(visibility: IdentityVisibility) -> list[str]:
    """Human labels for anatomy that must NOT appear in the final prompt."""
    present = visibility.visible_regions
    omit_keys = _ALL_REGION_KEYS - present
    out: list[str] = []
    for key in sorted(omit_keys):
        label = _REGION_PROMPT_LABELS.get(key)
        if label:
            out.append(label)
    if not visibility.include_face:
        out.append("face, eyes, expression, gaze, smile, lips")
    if not visibility.include_hair and not visibility.head_in_reference:
        out.append("hair color/style from MODEL")
    out.append(
        "meta instructions about reference photos (match face from, body reference, character sheet, image 1)"
    )
    # dedupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for item in out:
        low = item.lower()
        if low in seen:
            continue
        seen.add(low)
        deduped.append(item)
    return deduped


def build_prompt_region_policy_block(visibility: IdentityVisibility) -> str:
    mention = prompt_regions_to_mention(visibility)
    omit = prompt_regions_to_omit(visibility)
    lines = [
        "## PROMPT_REGION_POLICY (server — mandatory for ---PROMPT--- / wavespeed_scene_prompt)",
        "PROMPT_MENTION (describe ONLY these — scene + MODEL identity on visible parts): "
        + "; ".join(mention),
        "PROMPT_OMIT (must NOT appear anywhere in output prose): " + "; ".join(omit),
    ]
    if visibility.headless_crop:
        lines.append(
            "CROP_LOCK: no head/face in output — do not widen framing or invent a face from model photos."
        )
    elif not visibility.include_face and visibility.head_in_reference:
        lines.append(
            "HEAD_LOCK: back/side of head or hair mass from reference only — "
            "no eyes, nose, mouth, or front face from model photos."
        )
    return "\n".join(lines)


_META_PROSE_RE = re.compile(
    r"\b("
    r"match\s+(face|hair|body|likeness)|"
    r"(face|body|character)\s+reference\s+photo|"
    r"attached\s+model\s+reference|"
    r"use\s+(the\s+)?(face|body)\s+reference|"
    r"from\s+the\s+(face|body)\s+reference|"
    r"character\s+sheet"
    r")\b",
    re.IGNORECASE,
)

_FORBIDDEN_TERM_GROUPS: dict[str, tuple[str, ...]] = {
    "face": (
        "face",
        "facial",
        "eyes",
        "eye contact",
        "gaze",
        "expression",
        "smile",
        "lips",
        "nose",
        "mouth",
        "jawline",
        "cheek",
        "forehead",
        "chin",
        "looking at",
        "portrait likeness",
    ),
    "hair_model": ("hairstyle", "hair color", "hair texture", "blonde hair", "brunette hair"),
    "legs": (" legs", " leg ", "thigh", "thighs", "calf", "calves", "knee", "knees"),
    "feet": (" feet", " foot ", "ankle", "ankles", "toes"),
    "hands": (" hands", " hand ", "fingers", "fingernails", " palms"),
    "arms": (" arms", " arm ", "forearm", "forearms", "elbow", "elbows"),
    "chest": (" bust", " chest", " breasts", " nipple", " nipples", " décolleté", " decollete"),
    "butt": (" buttocks", " butt ", " glute", " glutes", " hip width"),
    "torso": (" waist", " midsection", " abs", " torso", " stomach", " belly"),
}


def sanitize_wavespeed_prose_for_visibility(
    prose: str,
    visibility: IdentityVisibility | None,
) -> str:
    """Post-filter: drop sentences that mention anatomy absent from the reference crop."""
    text = (prose or "").strip()
    if not text or visibility is None:
        return text

    regions = visibility.visible_regions
    forbidden: list[str] = []
    if not visibility.include_face:
        forbidden.extend(_FORBIDDEN_TERM_GROUPS["face"])
    if not visibility.include_hair and "HAIR" not in regions:
        forbidden.extend(_FORBIDDEN_TERM_GROUPS["hair_model"])
    for group, keys in (
        ("legs", {"LEGS", "FULL_BODY"}),
        ("feet", {"FEET", "FULL_BODY"}),
        ("hands", {"HANDS", "FULL_BODY"}),
        ("arms", {"ARMS", "FULL_BODY"}),
        ("chest", {"CHEST", "FULL_BODY"}),
        ("butt", {"BUTT", "FULL_BODY"}),
        ("torso", {"TORSO", "FULL_BODY"}),
    ):
        if not (regions & keys):
            forbidden.extend(_FORBIDDEN_TERM_GROUPS[group])

    parts = re.split(r"(?<=[.!?])\s+", text)
    kept: list[str] = []
    for sentence in parts:
        s = sentence.strip()
        if not s:
            continue
        low = s.lower()
        if _META_PROSE_RE.search(s):
            continue
        if any(term in low for term in forbidden):
            continue
        kept.append(s)
    out = " ".join(kept).strip()
    return out or text


def _parse_analysis_json(raw: str) -> ReferenceAnalysis:
    text = _strip_code_fences(raw).strip()
    if not text:
        raise RuntimeError("empty reference analysis")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"reference analysis JSON invalid: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError("reference analysis must be a JSON object")
    return ReferenceAnalysis.model_validate(data)


async def analyze_reference_image(
    *,
    image_bytes: bytes,
    image_media_type: str | None,
    credentials: StudioOpenAiCredentials | None = None,
) -> ReferenceAnalysis:
    import base64

    instruction = load_reference_analyze_prompt()
    if not instruction:
        raise RuntimeError(
            "Промпт анализа референса пуст: image_studio_reference_analyze.txt"
        )

    creds = credentials
    if creds is None:
        creds = grok_motion_studio_credentials() if grok_scene_compose_configured() else None

    if grok_scene_compose_configured():
        model = (settings.grok_scene_compose_model or "").strip() or _grok_fps_stills_model()
    else:
        model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    mime = (image_media_type or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"

    raw = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Return only valid JSON matching the requested schema.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            },
        ],
        max_tokens=2048,
        temperature=0.25,
        credentials=creds,
        timeout_seconds=120.0,
    )
    return _parse_analysis_json(raw)


def parse_reference_analysis_json(raw: str | None) -> ReferenceAnalysis | None:
    if not (raw or "").strip():
        return None
    try:
        return ReferenceAnalysis.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return None


def filter_model_profile_for_visibility(
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

    def scrub(obj: dict[str, Any]) -> None:
        if not visibility.include_face:
            obj.pop("face_features", None)
            obj.pop("face", None)
        if not visibility.include_hair:
            obj.pop("hair", None)
        if not visibility.include_expression:
            obj.pop("expression", None)

    if "model_profile" in data and isinstance(data["model_profile"], dict):
        scrub(data["model_profile"])
    else:
        scrub(data)

    return json.dumps(data, ensure_ascii=False)


def prune_skeleton_for_visibility(
    skeleton: str,
    visibility: IdentityVisibility,
) -> str:
    try:
        data = json.loads(skeleton)
    except json.JSONDecodeError:
        return skeleton
    if not isinstance(data, dict):
        return skeleton

    if "identity_reference" in data:
        id_ref = data.get("identity_reference")
        if isinstance(id_ref, dict):
            data["identity_reference"] = _filter_compact_identity(id_ref, visibility)
        return json.dumps(data, ensure_ascii=False, indent=2)

    subj = data.get("subject")
    if isinstance(subj, dict):
        ident = subj.get("identity")
        if isinstance(ident, dict):
            if not visibility.include_face:
                ident.pop("face_features", None)
            if not visibility.include_hair:
                ident.pop("hair", None)
            if not visibility.include_body_proportions:
                ident.pop("body_type", None)
        if not visibility.include_expression:
            subj.pop("expression", None)
        if not visibility.include_hair:
            subj.pop("hair_in_scene", None)
        if not visibility.include_hands_detail:
            pose = subj.get("pose")
            if isinstance(pose, dict):
                pose["hands"] = "<FILL only if hands visible in reference crop; else omit or 'not visible'>"

    return json.dumps(data, ensure_ascii=False, indent=2)


def _filter_compact_identity(
    identity: dict[str, Any],
    visibility: IdentityVisibility,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if identity.get("subject"):
        out["subject"] = identity["subject"]
    if visibility.include_face and identity.get("face"):
        out["face"] = identity["face"]
    if visibility.include_hair and identity.get("hair"):
        out["hair"] = identity["hair"]
    if visibility.include_body_proportions and identity.get("body_proportions"):
        out["body_proportions"] = identity["body_proportions"]
    elif identity.get("body_proportions"):
        out["body_proportions"] = identity["body_proportions"]
    if not out.get("subject") and identity.get("subject"):
        out["subject"] = identity["subject"]
    return out


def filter_identity_reference_dict(
    identity: dict[str, str],
    visibility: IdentityVisibility,
) -> dict[str, str]:
    return {
        k: v
        for k, v in identity.items()
        if v
        and (
            (k == "face" and visibility.include_face)
            or (k == "hair" and visibility.include_hair)
            or (k == "body_proportions" and visibility.include_body_proportions)
            or k == "subject"
        )
    }


def filter_model_images_for_visibility(
    imgs: list[UserStudioModelImage],
    visibility: IdentityVisibility,
) -> list[UserStudioModelImage]:
    allowed = visibility.allowed_image_kinds
    return [
        im
        for im in imgs
        if (im.image_kind or "other").strip().lower() in allowed
    ]


def visibility_pose_prefix_kind(visibility: IdentityVisibility | None) -> str:
    """WAN pose-ref prefix: face_visible | face_hidden | headless."""
    if visibility is None:
        return "face_visible"
    if visibility.include_face:
        return "face_visible"
    if visibility.headless_crop:
        return "headless"
    return "face_hidden"


def build_grok_identity_instruction(visibility: IdentityVisibility) -> str:
    if visibility.include_face:
        return (
            "IDENTITY_RULE: face, hair, and body traits from MODEL apply only where PROMPT_MENTION allows. "
            "Do not mention anatomy listed under PROMPT_OMIT."
        )
    if visibility.head_in_reference:
        return (
            "IDENTITY_RULE: face is NOT visible — preserve back/side of head or hair mass from the reference crop. "
            "Apply MODEL hair color only to visible hair; apply MODEL body proportions only to PROMPT_MENTION regions. "
            "Never describe eyes, nose, mouth, smile, or front-facing face."
        )
    return (
        "IDENTITY_RULE: headless crop — describe ONLY PROMPT_MENTION body parts plus scene/pose/light. "
        "Do not invent or paste a face. Never mention face, hair from MODEL, or off-crop anatomy."
    )


def build_grok_visibility_context(
    *,
    visibility: IdentityVisibility | None,
    reference_scene_description: str | None = None,
) -> str:
    blocks: list[str] = []
    if reference_scene_description and reference_scene_description.strip():
        blocks.append(
            "REFERENCE_ANALYSIS (authoritative geometry/framing — not donor identity):\n"
            + reference_scene_description.strip()
        )
    if visibility is not None:
        blocks.append(build_prompt_region_policy_block(visibility))
        blocks.append(build_grok_identity_instruction(visibility))
        blocks.append(build_visibility_plan_block(visibility))
    return "\n\n".join(blocks)


def resolve_effective_studio_mode(
    requested_mode: str,
    visibility: IdentityVisibility,
) -> str:
    """Visibility drives prompts/images; only correct manual no_face when face is visible."""
    mode = (requested_mode or "model").strip().lower()
    if mode == "no_face" and visibility.include_face:
        return "model"
    return mode


def build_studio_prompt_plan(
    *,
    analysis: ReferenceAnalysis,
    skeleton: str,
    model_profile_text: str | None,
    requested_studio_mode: str,
    wave_profile: str = "nsfw",
) -> StudioPromptPlan:
    visibility = build_identity_visibility(analysis, wave_profile=wave_profile)
    effective_mode = resolve_effective_studio_mode(requested_studio_mode, visibility)
    return StudioPromptPlan(
        analysis=analysis,
        visibility=visibility,
        reference_scene_description=format_reference_scene_from_analysis(analysis),
        pruned_skeleton=prune_skeleton_for_visibility(skeleton, visibility),
        filtered_model_profile_text=filter_model_profile_for_visibility(
            model_profile_text, visibility
        ),
        effective_studio_mode=effective_mode,
        skip_no_face_suffix=visibility.headless_crop,
    )


def analysis_summary_ru(analysis: ReferenceAnalysis) -> str:
    regions = ", ".join(sorted(analysis.normalized_regions())) or "не указано"
    parts = [f"В кадре: {regions}"]
    if analysis.face_in_frame:
        parts.append("лицо видно")
    else:
        parts.append("лица нет")
    if analysis.hair_in_frame:
        parts.append("волосы в кадре")
    fc = (analysis.framing_crop or "").strip()
    if fc:
        parts.append(fc[:120])
    return " · ".join(parts)
