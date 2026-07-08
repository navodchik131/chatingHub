"""Сценарные ноды workflow: optional layer между примитивами и генерацией."""

from __future__ import annotations

from typing import Any

SCENARIO_NODE_TYPES = frozenset(
    {
        "scenarioOutfitChange",
        "scenarioLocationChange",
        "scenarioMotionVideo",
        "scenarioFirstFrame",
    }
)

SCENARIO_IMAGE_TYPES = frozenset(
    {"scenarioOutfitChange", "scenarioLocationChange", "scenarioFirstFrame"}
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
        "SCENARIO — location change: keep subject identity, face, body, wardrobe, pose, "
        "camera angle, framing, and crop EXACTLY from MODEL_PROFILE and/or photo-base reference. "
        "Replace ONLY background, environment, surroundings, and scene lighting with location "
        "reference(s). Do NOT alter the person's appearance, proportions, or camera geometry."
    )
    if not base:
        return hint
    return f"{base}\n\n{hint}"


def location_change_role_hints() -> dict[str, str]:
    return {
        "photo base": "subject identity, pose, camera, and framing anchor",
        "photo_base": "subject identity, pose, camera, and framing anchor",
        "model": "subject identity from studio profile",
        "location": "target environment / background to apply",
        "environment": "target environment / background to apply",
        "scene": "target environment / background to apply",
    }
