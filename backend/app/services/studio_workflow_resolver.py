"""Разбор графа workflow → план генерации (фаза 0)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class WorkflowResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowGenerationPlan:
    model_id: int
    description: str
    reference_ref_id: str
    output_aspect: str
    studio_wave_profile: str
    wan_edit_tier: str
    exif_camera: str
    realism_enabled: bool


HANDLE = {
    "prompt_out": "prompt-out",
    "reference_out": "reference-out",
    "model_out": "model-out",
    "realism_out": "realism-out",
    "gen_prompt_in": "prompt-in",
    "gen_reference_in": "reference-in",
    "gen_model_in": "model-in",
    "gen_realism_in": "realism-in",
}


def _node_map(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for n in nodes:
        nid = str(n.get("id") or "").strip()
        if nid:
            out[nid] = n
    return out


def _source_for_target(
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    for edge in edges:
        if str(edge.get("target") or "") != target_id:
            continue
        th = edge.get("targetHandle")
        if th is not None and str(th) != target_handle:
            continue
        src_id = str(edge.get("source") or "").strip()
        if src_id and src_id in node_map:
            return node_map[src_id]
    return None


def resolve_workflow_generation_plan(
    *,
    target_node_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> WorkflowGenerationPlan:
    node_map = _node_map(nodes)
    target_id = (target_node_id or "").strip()
    target = node_map.get(target_id)
    if not target:
        raise WorkflowResolutionError("Целевая нода не найдена в графе")
    if str(target.get("type") or "") != "imageGeneration":
        raise WorkflowResolutionError("Execute поддерживает только ноду «Генерация»")

    gen_data = target.get("data") if isinstance(target.get("data"), dict) else {}

    model_node = _source_for_target(
        target_id, HANDLE["gen_model_in"], edges, node_map
    )
    if not model_node or str(model_node.get("type") or "") != "model":
        raise WorkflowResolutionError("Подключите ноду «Модель» к входу model")
    model_data = model_node.get("data") if isinstance(model_node.get("data"), dict) else {}
    raw_mid = model_data.get("modelId")
    try:
        model_id = int(raw_mid)
    except (TypeError, ValueError):
        raise WorkflowResolutionError("Выберите модель в ноде «Модель»") from None
    if model_id <= 0:
        raise WorkflowResolutionError("Выберите модель в ноде «Модель»")

    ref_node = _source_for_target(
        target_id, HANDLE["gen_reference_in"], edges, node_map
    )
    if not ref_node or str(ref_node.get("type") or "") != "reference":
        raise WorkflowResolutionError("Подключите ноду «Референс» к входу reference")
    ref_data = ref_node.get("data") if isinstance(ref_node.get("data"), dict) else {}
    ref_id = str(ref_data.get("refId") or "").strip()
    if not ref_id:
        raise WorkflowResolutionError("Загрузите изображение в ноду «Референс»")

    prompt_node = _source_for_target(
        target_id, HANDLE["gen_prompt_in"], edges, node_map
    )
    description = ""
    if prompt_node and str(prompt_node.get("type") or "") == "prompt":
        pdata = prompt_node.get("data") if isinstance(prompt_node.get("data"), dict) else {}
        description = str(pdata.get("prompt") or "").strip()

    realism_enabled = True
    realism_node = _source_for_target(
        target_id, HANDLE["gen_realism_in"], edges, node_map
    )
    if realism_node and str(realism_node.get("type") or "") == "realism":
        rdata = realism_node.get("data") if isinstance(realism_node.get("data"), dict) else {}
        if rdata.get("enabled") is False:
            realism_enabled = False

    output_aspect = str(gen_data.get("outputAspect") or "3:4").strip() or "3:4"
    wave_profile = str(gen_data.get("waveProfile") or "nsfw").strip().lower()
    if wave_profile not in ("regular", "nsfw"):
        wave_profile = "nsfw"
    wan_tier = str(gen_data.get("wanEditTier") or "standard").strip().lower()
    if wan_tier not in ("standard", "mini"):
        wan_tier = "standard"
    exif_camera = str(gen_data.get("exifCamera") or "main").strip() or "main"

    if wave_profile == "regular" and wan_tier != "standard":
        wan_tier = "standard"

    return WorkflowGenerationPlan(
        model_id=model_id,
        description=description,
        reference_ref_id=ref_id,
        output_aspect=output_aspect,
        studio_wave_profile=wave_profile,
        wan_edit_tier=wan_tier,
        exif_camera=exif_camera,
        realism_enabled=realism_enabled,
    )
