"""Разбор графа workflow → план генерации."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.studio_workflow_boardstory import (
    BoardStoryImageSlot,
    classify_boardstory_ref_role,
)

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


def _is_node_enabled(node: dict[str, Any] | None) -> bool:
    if node is None:
        return False
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    return data.get("disabled") is not True


def _require_enabled_target(target: dict[str, Any] | None, *, label: str = "Нода") -> None:
    if target is not None and not _is_node_enabled(target):
        raise WorkflowResolutionError(f"{label} отключена — включите её для запуска")


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
    motion_video_file_id: str = ""

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


@dataclass(frozen=True)
class WorkflowTurnaroundPlan:
    source_generation_id: int
    model_id: int | None
    prompt_extra: str


@dataclass(frozen=True)
class WorkflowVideoPlan:
    model_id: int | None
    first_frame_generation_id: int | None
    sheet_generation_id: int | None
    motion_video_file_id: str
    prompt: str
    output_aspect: str
    duration_seconds: int
    seedance_variant: str
    video_resolution: str
    generate_audio: bool
    auto_motion_prompt: bool
    negative_prompt: str
    video_provider: str = "seedance_t2v"
    prompt_from_compose: bool = False
    boardstory_mode: bool = False
    clothing_ref: BoardStoryImageSlot | None = None
    environment_ref: BoardStoryImageSlot | None = None
    extra_refs: tuple[WorkflowReferenceItem, ...] = ()


@dataclass(frozen=True)
class WorkflowVideoPromptComposePlan:
    model_id: int
    motion_video_file_id: str
    first_frame_generation_id: int | None
    sheet_generation_id: int | None
    references: tuple[WorkflowReferenceItem, ...]
    user_notes: str
    boardstory_mode: bool = True
    clothing_ref: BoardStoryImageSlot | None = None
    environment_ref: BoardStoryImageSlot | None = None


_PROMPT_SOURCE_NODE_TYPES = frozenset({"prompt", "videoPromptCompose"})


def resolve_upstream_prompt_text(
    *,
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> tuple[str, str | None]:
    """Текст промпта с upstream-ноды (prompt или videoPromptCompose)."""
    sources = _sources_for_target(target_id, target_handle, edges, node_map)
    for src in sources:
        ntype = str(src.get("type") or "")
        if ntype not in _PROMPT_SOURCE_NODE_TYPES:
            raise WorkflowResolutionError(
                "К входу prompt можно подключить ноду «Промпт» или «Промпт по видео»"
            )
        pdata = src.get("data") if isinstance(src.get("data"), dict) else {}
        text = str(pdata.get("prompt") or "").strip()
        if text:
            return text, ntype
    return "", None


def _resolve_workflow_references_for_target(
    *,
    target_id: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> tuple[WorkflowReferenceItem, ...]:
    ref_nodes = _sources_for_target(target_id, HANDLE["gen_reference_in"], edges, node_map)
    references: list[WorkflowReferenceItem] = []
    for ref_node in ref_nodes:
        if str(ref_node.get("type") or "") != "reference":
            raise WorkflowResolutionError(
                "К входу reference можно подключить только ноды «Референс»"
            )
        if not _is_node_enabled(ref_node):
            continue
        ref_data = ref_node.get("data") if isinstance(ref_node.get("data"), dict) else {}
        ref_id = str(ref_data.get("refId") or "").strip()
        if not ref_id:
            raise WorkflowResolutionError(
                "Загрузите изображение во все подключённые ноды «Референс»"
            )
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
    return sort_workflow_references(references)


def resolve_workflow_video_prompt_compose_plan(
    *,
    target_node_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> WorkflowVideoPromptComposePlan:
    node_map = _node_map(nodes)
    target_id = (target_node_id or "").strip()
    target = node_map.get(target_id)
    if not target:
        raise WorkflowResolutionError("Целевая нода не найдена в графе")
    _require_enabled_target(target)
    if str(target.get("type") or "") != "videoPromptCompose":
        raise WorkflowResolutionError("Неверный тип ноды для промпта по видео")

    model_nodes = _sources_for_target(target_id, HANDLE["gen_model_in"], edges, node_map)
    model_id = _parse_model_id_from_node(model_nodes[0] if model_nodes else None)
    if model_id is None:
        raise WorkflowResolutionError("Подключите ноду «Модель» и выберите модель")

    motion_nodes = _sources_for_target(target_id, HANDLE["motion_video_in"], edges, node_map)
    motion_video_file_id = ""
    if motion_nodes:
        mnode = motion_nodes[0]
        if str(mnode.get("type") or "") != "motionVideo":
            raise WorkflowResolutionError(
                "К входу motion video можно подключить только ноду «Motion-видео»"
            )
        mdata = mnode.get("data") if isinstance(mnode.get("data"), dict) else {}
        motion_video_file_id = str(mdata.get("motionVideoFileId") or "").strip()
    if not motion_video_file_id:
        raise WorkflowResolutionError("Подключите motion-видео с загруженным файлом")

    ff_gid = resolve_upstream_generation_id_optional(
        target_id=target_id,
        target_handle=HANDLE["first_frame_in"],
        edges=edges,
        node_map=node_map,
        label="первый кадр",
    )
    sheet_gid = resolve_upstream_generation_id_optional(
        target_id=target_id,
        target_handle=HANDLE["sheet_in"],
        edges=edges,
        node_map=node_map,
        label="развёртка",
    )

    user_notes = ""
    note_nodes = _sources_for_target(target_id, HANDLE["gen_prompt_in"], edges, node_map)
    if note_nodes:
        nnode = note_nodes[0]
        if str(nnode.get("type") or "") != "prompt":
            raise WorkflowResolutionError(
                "К входу prompt (доп. указания) можно подключить только ноду «Промпт»"
            )
        ndata = nnode.get("data") if isinstance(nnode.get("data"), dict) else {}
        user_notes = str(ndata.get("prompt") or "").strip()

    references = _resolve_workflow_references_for_target(
        target_id=target_id,
        edges=edges,
        node_map=node_map,
    )

    clothing_ref = _resolve_boardstory_slot_for_handle(
        target_id=target_id,
        target_handle=HANDLE["clothing_in"],
        default_kind="clothing",
        edges=edges,
        node_map=node_map,
    )
    environment_ref = _resolve_boardstory_slot_for_handle(
        target_id=target_id,
        target_handle=HANDLE["environment_in"],
        default_kind="environment",
        edges=edges,
        node_map=node_map,
    )
    boardstory_mode = ff_gid is None and sheet_gid is None

    return WorkflowVideoPromptComposePlan(
        model_id=model_id,
        motion_video_file_id=motion_video_file_id,
        first_frame_generation_id=ff_gid,
        sheet_generation_id=sheet_gid,
        references=references,
        user_notes=user_notes,
        boardstory_mode=boardstory_mode,
        clothing_ref=clothing_ref,
        environment_ref=environment_ref,
    )


def _parse_model_id_from_node(model_node: dict[str, Any] | None) -> int | None:
    if model_node is None:
        return None
    if str(model_node.get("type") or "") != "model":
        raise WorkflowResolutionError("К входу model можно подключить только ноду «Модель»")
    model_data = model_node.get("data") if isinstance(model_node.get("data"), dict) else {}
    raw_mid = model_data.get("modelId")
    if raw_mid is None or str(raw_mid).strip() == "":
        return None
    try:
        mid = int(raw_mid)
    except (TypeError, ValueError):
        raise WorkflowResolutionError("Выберите модель в ноде «Модель»") from None
    if mid <= 0:
        raise WorkflowResolutionError("Выберите модель в ноде «Модель»")
    return mid


def _generation_id_from_node(node: dict[str, Any]) -> int | None:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    raw = data.get("generationId")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        gid = int(raw)
    except (TypeError, ValueError):
        return None
    return gid if gid > 0 else None


def resolve_upstream_generation_id(
    *,
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    label: str = "изображение",
) -> int:
    sources = _sources_for_target(target_id, target_handle, edges, node_map)
    if not sources:
        raise WorkflowResolutionError(f"Подключите вход {label}")
    for src in sources:
        ntype = str(src.get("type") or "")
        if ntype not in _IMAGE_OUTPUT_NODE_TYPES:
            raise WorkflowResolutionError(
                f"К входу {label} можно подключить ноду с результатом генерации изображения"
            )
        gid = _generation_id_from_node(src)
        if gid is not None:
            return gid
    raise WorkflowResolutionError(
        f"Сначала выполните генерацию upstream-ноды для {label} (нет generationId)"
    )


def resolve_upstream_generation_id_optional(
    *,
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    label: str = "изображение",
) -> int | None:
    """Как resolve_upstream_generation_id, но None если вход не подключён или нода отключена."""
    sources = _sources_for_target(target_id, target_handle, edges, node_map)
    if not sources:
        return None
    for src in sources:
        ntype = str(src.get("type") or "")
        if ntype not in _IMAGE_OUTPUT_NODE_TYPES:
            raise WorkflowResolutionError(
                f"К входу {label} можно подключить ноду с результатом генерации изображения"
            )
        gid = _generation_id_from_node(src)
        if gid is not None:
            return gid
    raise WorkflowResolutionError(
        f"Сначала выполните генерацию upstream-ноды для {label} (нет generationId)"
    )


def resolve_workflow_turnaround_plan(
    *,
    target_node_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> WorkflowTurnaroundPlan:
    node_map = _node_map(nodes)
    target_id = (target_node_id or "").strip()
    target = node_map.get(target_id)
    if not target:
        raise WorkflowResolutionError("Целевая нода не найдена в графе")
    _require_enabled_target(target)
    if str(target.get("type") or "") != "turnaroundSheet":
        raise WorkflowResolutionError("Неверный тип ноды для развёртки")

    source_gid = resolve_upstream_generation_id(
        target_id=target_id,
        target_handle=HANDLE["first_frame_in"],
        edges=edges,
        node_map=node_map,
        label="первый кадр",
    )

    model_nodes = _sources_for_target(target_id, HANDLE["gen_model_in"], edges, node_map)
    model_id = _parse_model_id_from_node(model_nodes[0] if model_nodes else None)

    prompt_nodes = _sources_for_target(target_id, HANDLE["gen_prompt_in"], edges, node_map)
    prompt_extra = ""
    if prompt_nodes and str(prompt_nodes[0].get("type") or "") == "prompt":
        pdata = prompt_nodes[0].get("data") if isinstance(prompt_nodes[0].get("data"), dict) else {}
        prompt_extra = str(pdata.get("prompt") or "").strip()

    return WorkflowTurnaroundPlan(
        source_generation_id=source_gid,
        model_id=model_id,
        prompt_extra=prompt_extra,
    )


def resolve_workflow_video_plan(
    *,
    target_node_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> WorkflowVideoPlan:
    node_map = _node_map(nodes)
    target_id = (target_node_id or "").strip()
    target = node_map.get(target_id)
    if not target:
        raise WorkflowResolutionError("Целевая нода не найдена в графе")
    _require_enabled_target(target)
    if str(target.get("type") or "") != "videoGeneration":
        raise WorkflowResolutionError("Неверный тип ноды для видео")

    gen_data = target.get("data") if isinstance(target.get("data"), dict) else {}

    ff_gid = resolve_upstream_generation_id_optional(
        target_id=target_id,
        target_handle=HANDLE["first_frame_in"],
        edges=edges,
        node_map=node_map,
        label="первый кадр",
    )
    sheet_gid = resolve_upstream_generation_id_optional(
        target_id=target_id,
        target_handle=HANDLE["sheet_in"],
        edges=edges,
        node_map=node_map,
        label="развёртка",
    )

    prompt_text, prompt_source = resolve_upstream_prompt_text(
        target_id=target_id,
        target_handle=HANDLE["gen_prompt_in"],
        edges=edges,
        node_map=node_map,
    )
    prompt_from_compose = prompt_source == "videoPromptCompose"

    motion_nodes = _sources_for_target(target_id, HANDLE["motion_video_in"], edges, node_map)
    motion_video_file_id = ""
    if motion_nodes:
        mnode = motion_nodes[0]
        if str(mnode.get("type") or "") != "motionVideo":
            raise WorkflowResolutionError(
                "К входу motion video можно подключить только ноду «Motion-видео»"
            )
        mdata = mnode.get("data") if isinstance(mnode.get("data"), dict) else {}
        motion_video_file_id = str(mdata.get("motionVideoFileId") or "").strip()
    if not motion_video_file_id:
        motion_video_file_id = str(gen_data.get("motionVideoFileId") or "").strip()

    video_provider = str(gen_data.get("videoProvider") or "seedance_t2v").strip().lower()
    if video_provider not in ("seedance_t2v", "grok_imagine_i2v"):
        video_provider = "seedance_t2v"

    model_nodes = _sources_for_target(target_id, HANDLE["gen_model_in"], edges, node_map)
    model_id = _parse_model_id_from_node(model_nodes[0] if model_nodes else None)

    boardstory_mode = False
    if video_provider == "grok_imagine_i2v":
        if ff_gid is None:
            raise WorkflowResolutionError("Для Grok Imagine Video подключите первый кадр")
        if not prompt_text.strip():
            raise WorkflowResolutionError(
                "Добавьте промпт с описанием движения и сцены"
            )
        motion_video_file_id = ""
    elif ff_gid is None:
        boardstory_mode = True
        if model_id is None:
            raise WorkflowResolutionError(
                "BoardStory: подключите ноду «Модель» с фото из кабинета"
            )
        if not motion_video_file_id and not prompt_text.strip():
            raise WorkflowResolutionError(
                "Подключите motion-видео, ноду «Промпт по видео» или добавьте промпт с описанием движения"
            )
    elif not motion_video_file_id and not prompt_text.strip():
        raise WorkflowResolutionError(
            "Подключите motion-видео, ноду «Промпт по видео» или добавьте промпт с описанием движения"
        )

    clothing_ref = _resolve_boardstory_slot_for_handle(
        target_id=target_id,
        target_handle=HANDLE["clothing_in"],
        default_kind="clothing",
        edges=edges,
        node_map=node_map,
    )
    environment_ref = _resolve_boardstory_slot_for_handle(
        target_id=target_id,
        target_handle=HANDLE["environment_in"],
        default_kind="environment",
        edges=edges,
        node_map=node_map,
    )
    extra_refs = _resolve_workflow_references_for_target(
        target_id=target_id,
        edges=edges,
        node_map=node_map,
    )

    if boardstory_mode:
        sheet_gid = None

    output_aspect = str(gen_data.get("outputAspect") or "9:16").strip() or "9:16"

    try:
        duration_seconds = int(gen_data.get("durationSeconds") or 5)
    except (TypeError, ValueError):
        duration_seconds = 5

    seedance_variant = str(gen_data.get("seedanceVariant") or "standard").strip().lower()
    if seedance_variant not in ("standard", "mini"):
        seedance_variant = "standard"

    video_resolution = str(gen_data.get("videoResolution") or "720p").strip().lower()
    if video_provider == "grok_imagine_i2v":
        if video_resolution not in ("480p", "720p"):
            video_resolution = "720p"
        duration_seconds = max(1, min(15, duration_seconds))
    elif video_resolution not in ("480p", "720p", "1080p"):
        video_resolution = "720p"

    if video_provider == "grok_imagine_i2v":
        generate_audio = False
        auto_motion_prompt = False
    elif prompt_from_compose:
        generate_audio = gen_data.get("generateAudio") is not False
        auto_motion_prompt = False
    else:
        generate_audio = gen_data.get("generateAudio") is not False
        auto_motion_prompt = gen_data.get("autoMotionPrompt") is not False and bool(motion_video_file_id)
    negative_prompt = str(gen_data.get("negativePrompt") or "").strip()

    return WorkflowVideoPlan(
        model_id=model_id,
        first_frame_generation_id=ff_gid,
        sheet_generation_id=sheet_gid if video_provider != "grok_imagine_i2v" and not boardstory_mode else None,
        motion_video_file_id=motion_video_file_id,
        prompt=prompt_text,
        output_aspect=output_aspect,
        duration_seconds=duration_seconds,
        seedance_variant=seedance_variant,
        video_resolution=video_resolution,
        generate_audio=generate_audio,
        auto_motion_prompt=auto_motion_prompt,
        negative_prompt=negative_prompt,
        video_provider=video_provider,
        prompt_from_compose=prompt_from_compose,
        boardstory_mode=boardstory_mode,
        clothing_ref=clothing_ref,
        environment_ref=environment_ref,
        extra_refs=extra_refs,
    )


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
    "image_out": "image-out",
    "first_frame_in": "first-frame-in",
    "sheet_in": "sheet-in",
    "motion_video_in": "motion-video-in",
    "clothing_in": "clothing-in",
    "environment_in": "environment-in",
    "video_out": "video-out",
}

_IMAGE_OUTPUT_NODE_TYPES = frozenset({"imageGeneration", "firstFrameGeneration", "turnaroundSheet"})


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
        if node is not None and _is_node_enabled(node):
            seen.add(src_id)
            out.append(node)
    return out


def _motion_video_file_id_from_node(node: dict[str, Any] | None) -> str:
    if node is None:
        return ""
    if str(node.get("type") or "") != "motionVideo":
        return ""
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    return str(data.get("motionVideoFileId") or "").strip()


def _first_frame_has_motion_video_wire(
    target_id: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> bool:
    if _sources_for_target(target_id, HANDLE["motion_video_in"], edges, node_map):
        return True
    for edge in edges:
        if str(edge.get("source") or "") != target_id:
            continue
        if edge.get("sourceHandle") is not None and str(edge.get("sourceHandle")) != HANDLE[
            "image_out"
        ]:
            continue
        if edge.get("targetHandle") is not None and str(edge.get("targetHandle")) != HANDLE[
            "first_frame_in"
        ]:
            continue
        video_id = str(edge.get("target") or "").strip()
        video_node = node_map.get(video_id)
        if not _is_node_enabled(video_node):
            continue
        if str((video_node or {}).get("type") or "") != "videoGeneration":
            continue
        if _sources_for_target(video_id, HANDLE["motion_video_in"], edges, node_map):
            return True
    return False


def _first_frame_motion_video_file_id(
    target_id: str,
    gen_data: dict[str, Any],
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> str:
    """Motion-видео: прямой вход на «Первый кадр» или та же нода, что и у «Видео» downstream."""
    motion_nodes = _sources_for_target(target_id, HANDLE["motion_video_in"], edges, node_map)
    if motion_nodes:
        mnode = motion_nodes[0]
        if str(mnode.get("type") or "") != "motionVideo":
            raise WorkflowResolutionError(
                "К входу motion video можно подключить только ноду «Motion-видео»"
            )
        mid = _motion_video_file_id_from_node(mnode)
        if mid:
            return mid

    mid = str(gen_data.get("motionVideoFileId") or "").strip()
    if mid:
        return mid

    for edge in edges:
        if str(edge.get("source") or "") != target_id:
            continue
        if edge.get("sourceHandle") is not None and str(edge.get("sourceHandle")) != HANDLE[
            "image_out"
        ]:
            continue
        if edge.get("targetHandle") is not None and str(edge.get("targetHandle")) != HANDLE[
            "first_frame_in"
        ]:
            continue
        video_id = str(edge.get("target") or "").strip()
        video_node = node_map.get(video_id)
        if not _is_node_enabled(video_node):
            continue
        if str((video_node or {}).get("type") or "") != "videoGeneration":
            continue
        for mnode in _sources_for_target(video_id, HANDLE["motion_video_in"], edges, node_map):
            if str(mnode.get("type") or "") != "motionVideo":
                raise WorkflowResolutionError(
                    "К входу motion video можно подключить только ноду «Motion-видео»"
                )
            mid = _motion_video_file_id_from_node(mnode)
            if mid:
                return mid
    return ""


def _resolve_boardstory_slot_for_handle(
    *,
    target_id: str,
    target_handle: str,
    default_kind: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> BoardStoryImageSlot | None:
    """Первый источник на typed handle: reference (refId) или image generation (generationId)."""
    sources = _sources_for_target(target_id, target_handle, edges, node_map)
    if not sources:
        return None
    src = sources[0]
    ntype = str(src.get("type") or "")
    role, description = _reference_description_for_node(src, edges, node_map)
    kind = classify_boardstory_ref_role(role) if role else default_kind
    if kind == "other":
        kind = default_kind

    if ntype == "reference":
        ref_data = src.get("data") if isinstance(src.get("data"), dict) else {}
        ref_id = str(ref_data.get("refId") or "").strip()
        if not ref_id:
            raise WorkflowResolutionError(
                f"Загрузите изображение в ноду «Референс» ({default_kind})"
            )
        return BoardStoryImageSlot(
            kind=kind,
            ref_id=ref_id,
            role=role or default_kind,
            description=description,
        )

    if ntype in _IMAGE_OUTPUT_NODE_TYPES:
        gid = _generation_id_from_node(src)
        if gid is None:
            raise WorkflowResolutionError(
                f"Сначала выполните генерацию для входа {default_kind} (нет generationId)"
            )
        return BoardStoryImageSlot(
            kind=kind,
            generation_id=gid,
            role=role or default_kind,
            description=description,
        )

    raise WorkflowResolutionError(
        f"К входу {default_kind} можно подключить «Референс» или ноду с результатом генерации"
    )


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
    if desc_node and str(desc_node.get("type") or "") == "refDescription" and _is_node_enabled(desc_node):
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
    _require_enabled_target(target)
    if str(target.get("type") or "") not in ("imageGeneration", "firstFrameGeneration"):
        raise WorkflowResolutionError(
            "Execute поддерживает ноды «Генерация» и «Первый кадр»"
        )

    gen_data = target.get("data") if isinstance(target.get("data"), dict) else {}

    if str(target.get("type") or "") == "firstFrameGeneration":
        wave_model = str(gen_data.get("waveModelId") or "nano-banana-pro").strip().lower()
        if wave_model == "gpt-image-2":
            raise WorkflowResolutionError(
                "Для первого кадра используйте Wan / Nano Banana — GPT Image 2 только для развёртки"
            )

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
    is_first_frame = str(target.get("type") or "") == "firstFrameGeneration"

    references: list[WorkflowReferenceItem] = []
    for ref_node in ref_nodes:
        if str(ref_node.get("type") or "") != "reference":
            raise WorkflowResolutionError("К входу reference можно подключить только ноды «Референс»")
        if not _is_node_enabled(ref_node):
            continue
        ref_data = ref_node.get("data") if isinstance(ref_node.get("data"), dict) else {}
        ref_id = str(ref_data.get("refId") or "").strip()
        if not ref_id:
            if is_first_frame:
                continue
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

    motion_video_file_id = ""
    if is_first_frame:
        motion_video_file_id = _first_frame_motion_video_file_id(
            target_id, gen_data, edges, node_map
        )
        if _first_frame_has_motion_video_wire(target_id, edges, node_map) and not motion_video_file_id:
            raise WorkflowResolutionError(
                "Загрузите видео в ноду «Motion-видео» — по нему Grok соберёт первый кадр"
            )
    elif not ref_nodes:
        raise WorkflowResolutionError("Подключите хотя бы одну ноду «Референс» к входу reference")
    elif not references:
        raise WorkflowResolutionError("Загрузите изображение во все подключённые ноды «Референс»")

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
    if is_first_frame:
        if (
            not references
            and not motion_video_file_id
            and model_id is None
            and not prompt_text.strip()
        ):
            raise WorkflowResolutionError(
                "Подключите motion-видео, загрузите кадр в «Референс», "
                "или укажите модель и промпт"
            )
        if not references and not motion_video_file_id and model_id is None:
            raise WorkflowResolutionError(
                "Без motion-видео и референса выберите модель в ноде «Модель»"
            )
        if (references or motion_video_file_id) and model_id is None:
            raise WorkflowResolutionError(
                "Для первого кадра из видео или референса выберите модель в ноде «Модель»"
            )
        if (
            not references
            and not motion_video_file_id
            and model_id is not None
            and not prompt_text.strip()
        ):
            raise WorkflowResolutionError(
                "Добавьте промпт для генерации первого кадра по модели (без motion-видео)"
            )
    elif model_id is None and not (prompt_text.strip() or has_ref_context):
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
        motion_video_file_id=motion_video_file_id,
    )
