"""Разбор графа workflow → план генерации."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

WORKFLOW_WAVE_MODELS = frozenset(
    {"nano-banana-2", "nano-banana-pro", "wan-2.7", "gpt-image-2"}
)


class WorkflowResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowGenerationPlan:
    model_id: int | None
    description: str
    reference_ref_id: str
    reference_role: str
    reference_description: str
    reference_file_name: str
    output_aspect: str
    studio_wave_profile: str
    workflow_wave_model: str
    wan_edit_tier: str
    exif_camera: str
    realism_enabled: bool


HANDLE = {
    "prompt_out": "prompt-out",
    "reference_out": "reference-out",
    "description_out": "description-out",
    "model_out": "model-out",
    "realism_out": "realism-out",
    "ref_description_in": "description-in",
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


def assemble_workflow_grok_notes(
    *,
    prompt_text: str,
    reference_role: str = "",
    reference_description: str = "",
    reference_file_name: str = "",
) -> str:
    """Сборка USER_NOTES для Grok из подключённых нод workflow."""
    sections: list[str] = []
    scene = (prompt_text or "").strip()
    if scene:
        sections.append(f"SCENE_DIRECTION:\n{scene}")

    ref_lines: list[str] = []
    role = (reference_role or "").strip()
    desc = (reference_description or "").strip()
    fname = (reference_file_name or "").strip()
    if role:
        ref_lines.append(f"Reference role: {role}")
    if desc:
        ref_lines.append(desc)
    if fname:
        ref_lines.append(f"Attached reference file: {fname}")
    if ref_lines:
        sections.append("REFERENCE_CONTEXT:\n" + "\n".join(ref_lines))

    return "\n\n".join(sections).strip()


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
    model_id: int | None = None
    if model_node is not None:
        if str(model_node.get("type") or "") != "model":
            raise WorkflowResolutionError("К входу model можно подключить только ноду «Модель»")
        model_data = model_node.get("data") if isinstance(model_node.get("data"), dict) else {}
        raw_mid = model_data.get("modelId")
        if raw_mid is None or str(raw_mid).strip() == "":
            raise WorkflowResolutionError("Выберите модель в ноде «Модель» или отключите её")
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
    ref_file_name = str(ref_data.get("fileName") or "").strip()

    ref_role = ""
    ref_description = ""
    desc_node = _source_for_target(
        str(ref_node.get("id") or ""),
        HANDLE["ref_description_in"],
        edges,
        node_map,
    )
    if desc_node and str(desc_node.get("type") or "") == "refDescription":
        ddata = desc_node.get("data") if isinstance(desc_node.get("data"), dict) else {}
        ref_role = str(ddata.get("role") or "").strip()
        ref_description = str(ddata.get("description") or "").strip()

    prompt_node = _source_for_target(
        target_id, HANDLE["gen_prompt_in"], edges, node_map
    )
    prompt_text = ""
    if prompt_node and str(prompt_node.get("type") or "") == "prompt":
        pdata = prompt_node.get("data") if isinstance(prompt_node.get("data"), dict) else {}
        prompt_text = str(pdata.get("prompt") or "").strip()

    if model_id is None and not (
        prompt_text.strip() or ref_role.strip() or ref_description.strip()
    ):
        raise WorkflowResolutionError(
            "Без модели из кабинета добавьте промпт или описание референса"
        )

    description = assemble_workflow_grok_notes(
        prompt_text=prompt_text,
        reference_role=ref_role,
        reference_description=ref_description,
        reference_file_name=ref_file_name,
    )

    realism_enabled = True
    realism_node = _source_for_target(
        target_id, HANDLE["gen_realism_in"], edges, node_map
    )
    if realism_node and str(realism_node.get("type") or "") == "realism":
        rdata = realism_node.get("data") if isinstance(realism_node.get("data"), dict) else {}
        if rdata.get("enabled") is False:
            realism_enabled = False

    output_aspect = str(gen_data.get("outputAspect") or "3:4").strip() or "3:4"

    wave_model = str(gen_data.get("waveModelId") or "wan-2.7").strip().lower()
    if wave_model not in WORKFLOW_WAVE_MODELS:
        wave_model = "wan-2.7"

    nsfw_enabled = gen_data.get("nsfwEnabled")
    if nsfw_enabled is False:
        wave_profile = "regular"
    else:
        wave_profile = "nsfw"

    if wave_profile == "nsfw" and wave_model != "wan-2.7":
        raise WorkflowResolutionError(
            "В режиме NSFW доступна только модель Wan 2.7"
        )
    if wave_profile == "regular" and wave_model == "wan-2.7":
        raise WorkflowResolutionError(
            "Wan 2.7 доступна только в режиме NSFW — отключите Regular или выберите другую модель"
        )

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
        reference_role=ref_role,
        reference_description=ref_description,
        reference_file_name=ref_file_name,
        output_aspect=output_aspect,
        studio_wave_profile=wave_profile,
        workflow_wave_model=wave_model,
        wan_edit_tier=wan_tier,
        exif_camera=exif_camera,
        realism_enabled=realism_enabled,
    )
