"""Сценарные ноды workflow: optional layer между примитивами и генерацией."""

from __future__ import annotations

from typing import Any

SCENARIO_NODE_TYPES = frozenset(
    {
        "scenarioOutfitChange",
        "scenarioLocationChange",
        "scenarioFaceSwap",
        "scenarioMotionVideo",
        "scenarioFirstFrame",
    }
)

SCENARIO_IMAGE_TYPES = frozenset(
    {
        "scenarioOutfitChange",
        "scenarioLocationChange",
        "scenarioFaceSwap",
        "scenarioFirstFrame",
    }
)
SCENARIO_VIDEO_TYPES = frozenset({"scenarioMotionVideo"})

HANDLE_PIPELINE_IN = "pipeline-in"
HANDLE_PIPELINE_OUT = "pipeline-out"


def is_scenario_node(node: dict[str, Any] | None) -> bool:
    if node is None:
        return False
    return str(node.get("type") or "") in SCENARIO_NODE_TYPES


def scenario_type_of(node: dict[str, Any] | None) -> str | None:
    if not is_scenario_node(node):
        return None
    return str(node.get("type") or "")


def find_upstream_scenario_for_target(
    target_id: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Scenario на pipeline-in генерации или на любом входе scenario-цепочки."""
    for edge in edges:
        if str(edge.get("target") or "") != target_id:
            continue
        th = edge.get("targetHandle")
        if th is not None and str(th) not in (HANDLE_PIPELINE_IN,):
            continue
        src_id = str(edge.get("source") or "").strip()
        src = node_map.get(src_id)
        if is_scenario_node(src):
            return src
    return None


def resolve_plan_target_id(
    target_id: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    """
    Если к генерации подключён scenario через pipeline-in — резолвим входы с scenario.
    Иначе plain: target_id без scenario.
    """
    scenario = find_upstream_scenario_for_target(target_id, edges, node_map)
    if scenario is None:
        return target_id, None
    return str(scenario.get("id") or "").strip(), scenario


def scenario_data(node: dict[str, Any] | None) -> dict[str, Any]:
    if node is None:
        return {}
    data = node.get("data")
    return data if isinstance(data, dict) else {}


def enrich_description_for_outfit_change(description: str) -> str:
    base = (description or "").strip()
    hint = (
        "SCENARIO — outfit change: keep the subject identity from MODEL_PROFILE / photo base; "
        "replace only clothing with the outfit reference (garments, colors, layers from clothes ref). "
        "Same pose and scene unless USER notes say otherwise."
    )
    if not base:
        return hint
    return f"{base}\n\n{hint}"


def enrich_description_for_first_frame(description: str) -> str:
    base = (description or "").strip()
    hint = (
        "SCENARIO — first frame: single still at motion t=0; identity from MODEL_PROFILE; "
        "pose, wardrobe, lighting and environment from motion reference and USER notes."
    )
    if not base:
        return hint
    return f"{base}\n\n{hint}"


def outfit_change_role_hints() -> dict[str, str]:
    return {
        "photo base": "subject identity and pose anchor",
        "photo_base": "subject identity and pose anchor",
        "clothes": "target outfit to apply",
        "clothing": "target outfit to apply",
        "outfit": "target outfit to apply",
    }


def enrich_description_for_location_change(description: str) -> str:
    base = (description or "").strip()
    hint = LOCATION_CHANGE_SCENARIO_HINT
    if not base:
        return hint
    return f"{base}\n\n{hint}"


LOCATION_CHANGE_DEFAULT_PROMPT = (
    "Place the model from Image 1 in the same pose and camera angle in the new location from Image 2 — "
    "do not carry over lighting or shadows from Image 1. Adapt the location to the model. "
    "Make the whole scene look organic and natural. Keep object proportions realistic. "
    "Adapt the overall location lighting to cast realistic shadows on the model; "
    "the location alone is the source of truth for all light and illumination. "
    "Unified grain and color grading across the entire frame."
)

LOCATION_CHANGE_SCENARIO_HINT = (
    "SCENARIO — location change (reconstruct environment, not paste background):\n"
    "PRIORITY 1 — photo-base reference (Image 1) defines EVERYTHING about the subject AND frame geometry: "
    "face, skin, hair, body, wardrobe, props, pose, limb angles, gaze, camera height/angle/distance, "
    "crop edges, horizon, floor plane, subject scale, depth of field.\n"
    "PRIORITY 2 — location reference(s) (Image 2+) supply place identity ONLY: architecture, materials, "
    "palette, time of day, weather mood, ambient light character — re-project these elements behind "
    "the subject to match Image 1 perspective; never copy location-ref camera or people.\n"
    "WaveSpeed receives Image 1 = photo-base edit canvas, Image 2+ = location material references.\n"
    "FORBIDDEN: cutout composite, pasted background, wrong perspective, mismatched horizon, floating "
    "subject, copying people from location refs, re-pose, reframe, new hairstyle/outfit, face-swap.\n"
    "If text conflicts, photo-base wins for subject and camera geometry; location refs win only for "
    "place materials and atmosphere."
)


def is_location_donor_ref_role(role: str | None) -> bool:
    r = (role or "").strip().lower()
    if not r:
        return False
    return any(h in r for h in ("location", "environment", "background"))


def location_change_role_hints() -> dict[str, str]:
    return {
        "photo base": (
            "geometry lock — identity, pose, camera, crop, scale, floor contact, light on subject "
            "(DO NOT copy this background)"
        ),
        "photo_base": (
            "geometry lock — identity, pose, camera, crop, scale, floor contact, light on subject "
            "(DO NOT copy this background)"
        ),
        "model": "same as photo base — full subject + frame geometry anchor",
        "location": "place materials / mood donor — re-project to Image 1 geometry; no people; no camera copy",
        "environment": "place materials / mood donor — re-project to Image 1 geometry; no people; no camera copy",
        "scene": "place materials / mood donor — re-project to Image 1 geometry; no people; no camera copy",
    }


def is_location_change_scenario(scenario_type: str | None) -> bool:
    return (scenario_type or "").strip() == "scenarioLocationChange"


LOCATION_CHANGE_WAVESPEED_PREFIX = (
    "[LOCATION CHANGE — reconstruct environment; NOT flat background paste]\n"
    "Image 1 = photo-base EDIT CANVAS: keep this exact person (face, skin, hair, body, clothes, props), "
    "pose, gaze, camera height/angle/distance, crop, horizon, floor plane, subject scale, and key light on skin.\n"
    "Image 2+ = location MATERIAL/MOOD references ONLY — place type, materials, palette, atmosphere. "
    "Never copy people, camera angle, framing, or perspective from Image 2+.\n\n"
    "MANDATORY: Rebuild the whole environment around the locked subject as one real photograph:\n"
    "• Re-project walls, floor, ceiling, sky, and props to Image 1 vanishing lines and horizon.\n"
    "• Reshape location elements from Image 2+ to match Image 1 camera angle — do NOT paste Image 2 flat behind the subject.\n"
    "• Align floor plane and ground contact; add believable contact shadows under feet/hands.\n"
    "• Keep key light direction on the subject from Image 1; shift ambient color/warmth toward Image 2 mood only.\n"
    "• Match background depth-of-field / blur to Image 1.\n\n"
)

LOCATION_CHANGE_WAVESPEED_SUFFIX = (
    "\n\n[LOCATION CHANGE ENFORCEMENT] One coherent photograph — no cutout composite, no sticker subject, "
    "no flat pasted backdrop, no location-ref camera copied, no floating feet, no mismatched horizon or lighting direction."
)

LOCATION_CHANGE_DEFAULT_NEGATIVE = (
    "cutout composite, pasted background, flat backdrop, wrong perspective, mismatched horizon, "
    "floating subject, sticker person, location reference camera copied, people from location reference, "
    "face swap, reframe, re-pose, inconsistent shadows, wrong floor angle"
)


def build_location_change_wavespeed_geometry_block(
    reference_scene_description: str | None,
    location_donor_description: str | None,
) -> str:
    parts: list[str] = []
    ref = (reference_scene_description or "").strip()
    if ref:
        parts.append(
            "LOCKED FRAME GEOMETRY (Image 1 analysis — rewrite environment to match this):\n" + ref
        )
    loc = (location_donor_description or "").strip()
    if loc:
        parts.append(loc)
    if not parts:
        return ""
    parts.append(
        "Rebuild background perspective, floor angle, ambient fill, and environmental light to fit the locked "
        "frame geometry while using the location materials above — not a flat swap."
    )
    return "\n\n".join(parts) + "\n\n"


def enrich_description_for_face_swap(description: str) -> str:
    base = (description or "").strip()
    hint = (
        "SCENARIO — face / model swap (strict scene lock):\n"
        "PRIORITY 1 — scene reference defines pose, limb angles, head yaw/gaze, camera height/angle/distance, "
        "crop edges, background, props, environmental light, and wardrobe coverage zones. Do NOT change these.\n"
        "PRIORITY 2 — replace ONLY the person in the scene with identity from MODEL_PROFILE "
        "(studio model photos) OR from the identity workflow reference (model / subject / photo base): "
        "face, skin, hair, body proportions.\n"
        "FORBIDDEN: copying the original person's face from the scene ref; re-pose or reframe; new background; "
        "face-swap paste look — rebuild one coherent individual from MODEL_PROFILE in the locked scene geometry."
    )
    if not base:
        return hint
    return f"{base}\n\n{hint}"


def face_swap_role_hints() -> dict[str, str]:
    return {
        "scene": "pose + camera + crop + background donor — NOT identity",
        "pose": "pose + camera + crop + background donor — NOT identity",
        "camera": "pose + camera + crop + background donor — NOT identity",
        "photo base": "full scene donor — geometry only, NOT the person's identity",
        "photo_base": "full scene donor — geometry only, NOT the person's identity",
    }


def is_face_swap_scenario(scenario_type: str | None) -> bool:
    return (scenario_type or "").strip() == "scenarioFaceSwap"


def is_detail_edit_scenario(scenario_type: str | None) -> bool:
    return (scenario_type or "").strip() == "scenarioDetailEdit"


def is_detail_edit_ref_role(role: str | None) -> bool:
    """Кадр, который точечно редактируем (не смена сцены / не face swap)."""
    return "frame to edit" in (role or "").lower()


def is_detail_donor_ref_role(role: str | None) -> bool:
    low = (role or "").lower()
    return "detail" in low or "element reference" in low


def workflow_refs_indicate_detail_edit(
    references: list[Any] | tuple[Any, ...] | None,
    *,
    scenario_type: str | None = None,
) -> bool:
    """Detail-edit: явный scenarioDetailEdit или роль «frame to edit» на референсе."""
    if is_detail_edit_scenario(scenario_type):
        return True
    for ref in references or ():
        role = getattr(ref, "role", None)
        if role is None and isinstance(ref, dict):
            role = ref.get("role")
        if is_detail_edit_ref_role(str(role or "")):
            return True
    return False


def enrich_description_for_detail_edit(description: str) -> str:
    base = (description or "").strip()
    hint = (
        "SCENARIO — detail edit (in-place retouch of one frame):\n"
        "PRIORITY 1 — photo-base / frame-to-edit reference is the FULL edit canvas: keep the same person, "
        "pose, camera, crop, lighting, background and overall composition unless USER_NOTES explicitly change them.\n"
        "PRIORITY 2 — apply ONLY the local change described in USER_NOTES (color, prop, garment detail, "
        "small object, subtle retouch).\n"
        "If a detail / element reference is attached, use it ONLY as the look of that element — "
        "do NOT replace the whole scene with it. WaveSpeed receives Image 1 = edit canvas, Image 2 = detail ref "
        "when present — the composed prompt MUST explicitly cite Image 2 / detail reference for that element.\n"
        "FORBIDDEN: new location, reframe, re-pose, new identity, face-swap, inventing a different shot."
    )
    if not base:
        return hint
    return f"{base}\n\n{hint}"


def order_detail_edit_refs_for_wavespeed(
    refs: list[tuple[Any, Any, Any]] | tuple[Any, Any, Any],
) -> list[tuple[Any, Any, Any]]:
    """WaveSpeed: сначала кадр для правки, затем опциональный detail-ref."""
    items = list(refs)
    if not items:
        return []

    def _role(meta: Any) -> str:
        if isinstance(meta, dict):
            return str(meta.get("role") or "")
        return str(getattr(meta, "role", "") or "")

    base = [r for r in items if is_detail_edit_ref_role(_role(r[2]))]
    detail = [r for r in items if is_detail_donor_ref_role(_role(r[2]))]
    seen = {id(r) for r in base + detail}
    other = [r for r in items if id(r) not in seen]
    ordered = (base or [items[0]]) + detail + other
    return ordered


def workflow_detail_ref_attached(
    refs: list[tuple[Any, Any, Any]] | tuple[Any, Any, Any] | None,
) -> bool:
    for _b, _m, meta in refs or ():
        role = meta.get("role") if isinstance(meta, dict) else getattr(meta, "role", "")
        if is_detail_donor_ref_role(str(role or "")):
            return True
    return False
