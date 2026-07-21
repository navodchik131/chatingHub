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
    hint = (
        "SCENARIO — location change (strict in-place background swap):\n"
        "PRIORITY 1 — photo-base reference defines EVERYTHING about the subject: face, skin, "
        "hair style and color, body, wardrobe, props, pose, limb angles, gaze, camera geometry, "
        "selfie arm / crop, subject scale in frame. Do NOT change any of these.\n"
        "PRIORITY 2 — location / environment reference(s) donate ONLY background pixels: "
        "architecture, ground, sky, distant objects, ambient light and weather behind the subject.\n"
        "FORBIDDEN: copying people from location refs; new hairstyle or outfit; re-pose or reframe; "
        "inventing a different place; face-swap; studio MODEL photos overriding photo-base identity.\n"
        "If text conflicts, photo-base wins for subject geometry; location refs win only for background."
    )
    if not base:
        return hint
    return f"{base}\n\n{hint}"


def location_change_role_hints() -> dict[str, str]:
    return {
        "photo base": "full source photo — identity, pose, camera, crop, wardrobe, hair (DO NOT copy background)",
        "photo_base": "full source photo — identity, pose, camera, crop, wardrobe, hair (DO NOT copy background)",
        "model": "same as photo base when no studio model node — full subject anchor",
        "location": "background / environment donor ONLY — no people",
        "environment": "background / environment donor ONLY — no people",
        "scene": "background / environment donor ONLY — no people",
    }


def is_location_change_scenario(scenario_type: str | None) -> bool:
    return (scenario_type or "").strip() == "scenarioLocationChange"


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
        "small object, minor retouch).\n"
        "If a detail / element reference is attached, use it ONLY as the look of that element — "
        "do NOT replace the whole scene with it.\n"
        "FORBIDDEN: new location, reframe, re-pose, new identity, face-swap, inventing a different shot."
    )
    if not base:
        return hint
    return f"{base}\n\n{hint}"
