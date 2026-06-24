"""Разбор графа workflow → план генерации."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

WORKFLOW_WAVE_MODELS = frozenset(
    {"nano-banana-2", "nano-banana-pro", "wan-2.7", "gpt-image-2"}
)

_PRIMARY_REF_ROLE_HINTS = (
    "photo base",
    "photo_base",
    "base",
    "model",
    "subject",
    "pose",
    "scene",
    "photo edit",
    "photo_edit",
)


class WorkflowResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowReferenceItem:
    ref_id: str
    role: str
    description: str
    file_name: str
    node_id: str = ""


@dataclass(frozen=True)
class WorkflowGenerationPlan:
    model_id: int | None
    description: str
    references: tuple[WorkflowReferenceItem, ...]
    output_aspect: str
    studio_wave_profile: str
    workflow_wave_model: str
    wan_edit_tier: str
    exif_camera: str
    realism_enabled: bool

    @property
    def reference_ref_id(self) -> str:
        return self.references[0].ref_id if self.references else ""

    @property
    def reference_role(self) -> str:
        return self.references[0].role if self.references else ""

    @property
    def reference_description(self) -> str:
        return self.references[0].description if self.references else ""

    @property
    def reference_file_name(self) -> str:
        return self.references[0].file_name if self.references else ""


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


def _sources_for_target(
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Все ноды-источники для одного входа (несколько референсов на reference-in)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for edge in edges:
        if str(edge.get("target") or "") != target_id:
            continue
        th = edge.get("targetHandle")
        if th is not None and str(th) != target_handle:
            continue
        src_id = str(edge.get("source") or "").strip()
        if not src_id or src_id in seen:
            continue
        node = node_map.get(src_id)
        if node is not None:
            seen.add(src_id)
            out.append(node)
    return out


def _reference_description_for_node(
    ref_node: dict[str, Any],
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    ref_id = str(ref_node.get("id") or "").strip()
    desc_node = None
    for edge in edges:
        if str(edge.get("target") or "") != ref_id:
            continue
        if edge.get("targetHandle") is not None and str(edge.get("targetHandle")) != HANDLE[
            "ref_description_in"
        ]:
            continue
        src_id = str(edge.get("source") or "").strip()
        if src_id in node_map:
            desc_node = node_map[src_id]
            break
    if desc_node and str(desc_node.get("type") or "") == "refDescription":
        ddata = desc_node.get("data") if isinstance(desc_node.get("data"), dict) else {}
        role = str(ddata.get("role") or "").strip()
        description = str(ddata.get("description") or "").strip()
        return role, description
    return "", ""


def _role_sort_key(role: str) -> tuple[int, str]:
    r = (role or "").strip().lower()
    for i, hint in enumerate(_PRIMARY_REF_ROLE_HINTS):
        if hint in r:
            return (0, r)
    return (1, r)


def sort_workflow_references(
    references: tuple[WorkflowReferenceItem, ...] | list[WorkflowReferenceItem],
) -> tuple[WorkflowReferenceItem, ...]:
    """Primary ref (photo base / pose / model) first — остальные по роли."""
    if not references:
        return ()
    return tuple(sorted(references, key=lambda ref: _role_sort_key(ref.role)))


def assemble_workflow_grok_notes(
    *,
    prompt_text: str,
    references: list[WorkflowReferenceItem] | None = None,
    reference_role: str = "",
    reference_description: str = "",
    reference_file_name: str = "",
) -> str:
    """Сборка USER_NOTES для Grok из подключённых нод workflow."""
    sections: list[str] = []
    scene = (prompt_text or "").strip()
    if scene:
        sections.append(f"SCENE_DIRECTION:\n{scene}")

    ref_items: list[WorkflowReferenceItem] = list(references or [])
    if not ref_items and (
        (reference_role or "").strip()
        or (reference_description or "").strip()
        or (reference_file_name or "").strip()
    ):
        ref_items = [
            WorkflowReferenceItem(
                ref_id="",
                role=(reference_role or "").strip(),
                description=(reference_description or "").strip(),
                file_name=(reference_file_name or "").strip(),
            )
        ]

    if ref_items:
        blocks: list[str] = []
        for i, ref in enumerate(sort_workflow_references(ref_items), 1):
            lines: list[str] = [f"Reference {i}:"]
            role = (ref.role or "").strip()
            desc = (ref.description or "").strip()
            fname = (ref.file_name or "").strip()
            if role:
                lines.append(f"  Role: {role}")
            if desc:
                lines.append(f"  Notes: {desc}")
            if fname:
                lines.append(f"  File: {fname}")
            blocks.append("\n".join(lines))
        sections.append(
            "REFERENCE_CONTEXT (each attached workflow image is labeled to match its Role):\n"
            + "\n\n".join(blocks)
        )

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

    model_node = _sources_for_target(target_id, HANDLE["gen_model_in"], edges, node_map)
    model_node = model_node[0] if model_node else None
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

    ref_nodes = _sources_for_target(target_id, HANDLE["gen_reference_in"], edges, node_map)
    if not ref_nodes:
        raise WorkflowResolutionError("Подключите хотя бы одну ноду «Референс» к входу reference")

    references: list[WorkflowReferenceItem] = []
    for ref_node in ref_nodes:
        if str(ref_node.get("type") or "") != "reference":
            raise WorkflowResolutionError("К входу reference можно подключить только ноды «Референс»")
        ref_data = ref_node.get("data") if isinstance(ref_node.get("data"), dict) else {}
        ref_id = str(ref_data.get("refId") or "").strip()
        if not ref_id:
            raise WorkflowResolutionError("Загрузите изображение во все подключённые ноды «Референс»")
        ref_role, ref_description = _reference_description_for_node(ref_node, edges, node_map)
        references.append(
            WorkflowReferenceItem(
                ref_id=ref_id,
                role=ref_role,
                description=ref_description,
                file_name=str(ref_data.get("fileName") or "").strip(),
                node_id=str(ref_node.get("id") or "").strip(),
            )
        )

    sorted_refs = sort_workflow_references(references)

    prompt_node = _sources_for_target(target_id, HANDLE["gen_prompt_in"], edges, node_map)
    prompt_node = prompt_node[0] if prompt_node else None
    prompt_text = ""
    if prompt_node and str(prompt_node.get("type") or "") == "prompt":
        pdata = prompt_node.get("data") if isinstance(prompt_node.get("data"), dict) else {}
        prompt_text = str(pdata.get("prompt") or "").strip()

    has_ref_context = any(
        (r.role or "").strip() or (r.description or "").strip() for r in sorted_refs
    )
    if model_id is None and not (prompt_text.strip() or has_ref_context):
        raise WorkflowResolutionError(
            "Без модели из кабинета добавьте промпт или описание референса"
        )

    description = assemble_workflow_grok_notes(
        prompt_text=prompt_text,
        references=list(sorted_refs),
    )

    realism_enabled = True
    realism_nodes = _sources_for_target(target_id, HANDLE["gen_realism_in"], edges, node_map)
    realism_node = realism_nodes[0] if realism_nodes else None
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
        references=sorted_refs,
        output_aspect=output_aspect,
        studio_wave_profile=wave_profile,
        workflow_wave_model=wave_model,
        wan_edit_tier=wan_tier,
        exif_camera=exif_camera,
        realism_enabled=realism_enabled,
    )
