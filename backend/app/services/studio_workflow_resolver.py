"""Разбор графа workflow → план генерации."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.studio_workflow_boardstory import (
    BoardStoryImageSlot,
    classify_boardstory_ref_role,
)
from app.services.studio_workflow_scenarios import (
    enrich_description_for_face_swap,
    enrich_description_for_first_frame,
    enrich_description_for_location_change,
    enrich_description_for_outfit_change,
    resolve_plan_target_id,
    scenario_data,
    scenario_type_of,
)

WORKFLOW_WAVE_MODELS = frozenset(
    {
        "nano-banana-2",
        "nano-banana-pro",
        "gpt-image-2",
        "wan-2.7",
        "wan-2.7-pro",
        "seedream-v5.0-pro",
    }
)

WORKFLOW_CROSS_PROFILE_MODELS = frozenset({"seedream-v5.0-pro"})
WORKFLOW_NSFW_ONLY_MODELS = frozenset({"wan-2.7", "wan-2.7-pro"})
WORKFLOW_REGULAR_MODELS = frozenset(
    {"nano-banana-2", "nano-banana-pro", "gpt-image-2", "seedream-v5.0-pro"}
)

_PRIMARY_REF_ROLE_HINTS = (
    "photo base",
    "photo_base",
    "base",
    "model",
    "subject",
    "identity",
    "pose",
    "scene",
    "photo edit",
    "photo_edit",
)

_IDENTITY_REF_ROLE_HINTS = (
    "identity",
    "photo base",
    "photo_base",
    "subject",
    "who",
)

_SCENE_DONOR_REF_ROLE_HINTS = (
    "pose",
    "camera",
    "framing",
    "geometry",
    "scene donor",
    "scene /",
    "light donor",
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
    generation_id: int | None = None


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
    selfie_capture_enabled: bool = False
    motion_video_file_id: str = ""
    scenario_type: str | None = None

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
    send_video_reference: bool = True
    scenario_type: str | None = None


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
    generate_clothing_from_video: bool = False
    generate_environment_from_video: bool = False
    send_video_reference: bool = True
    output_aspect: str = "9:16"


@dataclass(frozen=True)
class WorkflowVideoUpscalePlan:
    source_generation_id: int
    target_resolution: str
    studio_model_id: int | None = None
    output_aspect: str | None = None


_PROMPT_SOURCE_NODE_TYPES = frozenset({"prompt", "videoPromptCompose", "scenarioMotionVideo"})


def _plan_input_target(
    target_id: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    return resolve_plan_target_id(target_id, edges, node_map)


def _sources_for_plan_target(
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    plan_target, _scenario = _plan_input_target(target_id, edges, node_map)
    return _sources_for_target(plan_target, target_handle, edges, node_map)


def resolve_upstream_prompt_text(
    *,
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> tuple[str, str | None]:
    """Текст промпта с upstream-ноды (prompt, videoPromptCompose или scenario)."""
    sources = _sources_for_plan_target(target_id, target_handle, edges, node_map)
    for src in sources:
        ntype = str(src.get("type") or "")
        if ntype not in _PROMPT_SOURCE_NODE_TYPES:
            raise WorkflowResolutionError(
                "К входу prompt можно подключить «Промпт», «Промпт по видео» или сценарий motion"
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
    ref_nodes = _sources_for_plan_target(target_id, HANDLE["gen_reference_in"], edges, node_map)
    references: list[WorkflowReferenceItem] = []
    for ref_node in ref_nodes:
        ntype = str(ref_node.get("type") or "")
        if ntype not in _REFERENCE_IMAGE_SOURCE_TYPES:
            raise WorkflowResolutionError(
                "К входу reference можно подключить «Images ref», «Просмотр» или ноду с результатом генерации"
            )
        if not _is_node_enabled(ref_node):
            continue
        item = _reference_item_from_source_node(ref_node, edges, node_map)
        if item is None:
            raise WorkflowResolutionError(
                "Загрузите изображение во все подключённые референсы или выполните upstream-генерацию"
            )
        references.append(item)
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
    if str(target.get("type") or "") not in ("videoPromptCompose", "scenarioMotionVideo"):
        raise WorkflowResolutionError("Неверный тип ноды для промпта по видео")

    model_nodes = _sources_for_plan_target(target_id, HANDLE["gen_model_in"], edges, node_map)
    model_id = _parse_model_id_from_node(model_nodes[0] if model_nodes else None)
    if model_id is None:
        raise WorkflowResolutionError("Подключите ноду «Модель» и выберите модель")

    motion_nodes = _sources_for_plan_target(target_id, HANDLE["motion_video_in"], edges, node_map)
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
    note_nodes = _sources_for_plan_target(target_id, HANDLE["gen_prompt_in"], edges, node_map)
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
    compose_data = target.get("data") if isinstance(target.get("data"), dict) else {}
    generate_clothing = compose_data.get("generateClothingFromVideo") is True
    generate_environment = compose_data.get("generateEnvironmentFromVideo") is True
    send_video_reference = compose_data.get("sendVideoReference") is not False
    if compose_data.get("sendReferenceImages") is False:
        send_video_reference = False
    output_aspect = str(compose_data.get("outputAspect") or "9:16").strip() or "9:16"
    for edge in edges:
        if str(edge.get("source") or "") != target_id:
            continue
        sh = edge.get("sourceHandle")
        if sh is not None and str(sh) != HANDLE["prompt_out"]:
            continue
        downstream = node_map.get(str(edge.get("target") or "").strip())
        if downstream and str(downstream.get("type") or "") == "videoGeneration":
            ddata = downstream.get("data") if isinstance(downstream.get("data"), dict) else {}
            asp = str(ddata.get("outputAspect") or "").strip()
            if asp:
                output_aspect = asp
            break
    if str(target.get("type") or "") == "scenarioMotionVideo":
        for edge in edges:
            if str(edge.get("source") or "") != target_id:
                continue
            if edge.get("sourceHandle") is not None and str(edge.get("sourceHandle")) != HANDLE[
                "pipeline_out"
            ]:
                continue
            downstream = node_map.get(str(edge.get("target") or "").strip())
            if downstream and str(downstream.get("type") or "") == "videoGeneration":
                ddata = downstream.get("data") if isinstance(downstream.get("data"), dict) else {}
                asp = str(ddata.get("outputAspect") or "").strip()
                if asp:
                    output_aspect = asp
                break

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
        generate_clothing_from_video=generate_clothing and clothing_ref is None,
        generate_environment_from_video=generate_environment and environment_ref is None,
        send_video_reference=send_video_reference,
        output_aspect=output_aspect,
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
    sources = _sources_for_plan_target(target_id, target_handle, edges, node_map)
    if not sources:
        raise WorkflowResolutionError(f"Подключите вход {label}")
    for src in sources:
        ntype = str(src.get("type") or "")
        if ntype not in _IMAGE_OUTPUT_NODE_TYPES and ntype != "preview":
            raise WorkflowResolutionError(
                f"К входу {label} можно подключить ноду с результатом генерации или «Просмотр»"
            )
        gid = _generation_id_from_node(src)
        if gid is None and ntype == "preview":
            gid = _generation_id_from_preview_upstream(src, edges, node_map)
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
    sources = _sources_for_plan_target(target_id, target_handle, edges, node_map)
    if not sources:
        return None
    for src in sources:
        ntype = str(src.get("type") or "")
        if ntype not in _IMAGE_OUTPUT_NODE_TYPES and ntype != "preview":
            raise WorkflowResolutionError(
                f"К входу {label} можно подключить ноду с результатом генерации или «Просмотр»"
            )
        gid = _generation_id_from_node(src)
        if gid is None and ntype == "preview":
            gid = _generation_id_from_preview_upstream(src, edges, node_map)
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
    prompt_from_compose = prompt_source in ("videoPromptCompose", "scenarioMotionVideo")

    _, scenario = _plan_input_target(target_id, edges, node_map)
    scenario_type = scenario_type_of(scenario)
    sdata = scenario_data(scenario)
    if scenario_type == "scenarioMotionVideo":
        scenario_prompt = str(sdata.get("prompt") or "").strip()
        if scenario_prompt:
            prompt_text = scenario_prompt
            prompt_from_compose = True

    motion_nodes = _sources_for_plan_target(target_id, HANDLE["motion_video_in"], edges, node_map)
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

    model_nodes = _sources_for_plan_target(target_id, HANDLE["gen_model_in"], edges, node_map)
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

    extra_refs = _resolve_workflow_references_for_target(
        target_id=target_id,
        edges=edges,
        node_map=node_map,
    )

    compose_upstream = _upstream_compose_node_for_video(target_id, edges, node_map)
    clothing_from_compose = _boardstory_slot_from_compose_data(
        compose_upstream,
        kind="clothing",
        gen_key="clothingGenerationId",
        url_key="clothingImageUrl",
    )
    environment_from_compose = _boardstory_slot_from_compose_data(
        compose_upstream,
        kind="environment",
        gen_key="environmentGenerationId",
        url_key="environmentImageUrl",
    )

    if boardstory_mode:
        sheet_gid = None

    clothing_ref = _merge_boardstory_slot(
        _resolve_boardstory_slot_for_handle(
            target_id=target_id,
            target_handle=HANDLE["clothing_in"],
            default_kind="clothing",
            edges=edges,
            node_map=node_map,
        ),
        clothing_from_compose,
    )
    environment_ref = _merge_boardstory_slot(
        _resolve_boardstory_slot_for_handle(
            target_id=target_id,
            target_handle=HANDLE["environment_in"],
            default_kind="environment",
            edges=edges,
            node_map=node_map,
        ),
        environment_from_compose,
    )

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
    elif scenario_type == "scenarioMotionVideo":
        generate_audio = sdata.get("generateAudio") is not False
        auto_motion_prompt = (
            sdata.get("autoMotionPrompt") is not False and bool(motion_video_file_id)
        )
    elif prompt_from_compose:
        generate_audio = gen_data.get("generateAudio") is not False
        auto_motion_prompt = False
    else:
        generate_audio = gen_data.get("generateAudio") is not False
        auto_motion_prompt = gen_data.get("autoMotionPrompt") is not False and bool(motion_video_file_id)
    negative_prompt = str(gen_data.get("negativePrompt") or "").strip()
    if scenario_type == "scenarioMotionVideo":
        negative_prompt = str(sdata.get("negativePrompt") or negative_prompt).strip()

    send_video_reference = True
    if compose_upstream:
        cdata = compose_upstream.get("data") if isinstance(compose_upstream.get("data"), dict) else {}
        send_video_reference = cdata.get("sendVideoReference") is not False
        if cdata.get("sendReferenceImages") is False:
            send_video_reference = False

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
        send_video_reference=send_video_reference,
        scenario_type=scenario_type,
    )


HANDLE = {
    "prompt_out": "prompt-out",
    "reference_out": "reference-out",
    "description_out": "description-out",
    "model_out": "model-out",
    "realism_out": "realism-out",
    "pipeline_in": "pipeline-in",
    "pipeline_out": "pipeline-out",
    "ref_description_in": "description-in",
    "gen_prompt_in": "prompt-in",
    "gen_reference_in": "reference-in",
    "identity_ref_in": "identity-ref-in",
    "gen_model_in": "model-in",
    "gen_realism_in": "realism-in",
    "gen_selfie_in": "selfie-in",
    "selfie_out": "selfie-out",
    "image_out": "image-out",
    "first_frame_in": "first-frame-in",
    "sheet_in": "sheet-in",
    "motion_video_in": "motion-video-in",
    "clothing_in": "clothing-in",
    "environment_in": "environment-in",
    "video_in": "video-in",
    "video_out": "video-out",
}

_VIDEO_OUTPUT_NODE_TYPES = frozenset({"videoGeneration", "videoUpscale"})

_IMAGE_OUTPUT_NODE_TYPES = frozenset({"imageGeneration", "firstFrameGeneration", "turnaroundSheet"})

_REFERENCE_IMAGE_SOURCE_TYPES = frozenset(
    {"reference", "preview", *_IMAGE_OUTPUT_NODE_TYPES}
)

_UPSTREAM_IMAGE_SOURCE_TYPES = frozenset({*_IMAGE_OUTPUT_NODE_TYPES, "preview"})


def _node_map(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for n in nodes:
        nid = str(n.get("id") or "").strip()
        if nid:
            out[nid] = n
    return out


def _generation_id_from_preview_upstream(
    preview_node: dict[str, Any],
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> int | None:
    preview_id = str(preview_node.get("id") or "").strip()
    for edge in edges:
        if str(edge.get("target") or "") != preview_id:
            continue
        if edge.get("targetHandle") is not None and str(edge.get("targetHandle")) != "image-in":
            continue
        src_id = str(edge.get("source") or "").strip()
        src = node_map.get(src_id)
        if src is None or not _is_node_enabled(src):
            continue
        ntype = str(src.get("type") or "")
        if ntype in _IMAGE_OUTPUT_NODE_TYPES:
            gid = _generation_id_from_node(src)
            if gid is not None:
                return gid
        if ntype == "preview":
            pdata = src.get("data") if isinstance(src.get("data"), dict) else {}
            gid = _generation_id_from_node(src)
            if gid is not None:
                return gid
            nested = _generation_id_from_preview_upstream(src, edges, node_map)
            if nested is not None:
                return nested
    return None


def _reference_item_from_source_node(
    src: dict[str, Any],
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    *,
    default_role: str = "",
) -> WorkflowReferenceItem | None:
    ntype = str(src.get("type") or "")
    if ntype not in _REFERENCE_IMAGE_SOURCE_TYPES:
        return None
    ref_role, ref_description = _reference_description_for_node(src, edges, node_map)
    if not (ref_role or "").strip() and (default_role or "").strip():
        ref_role = default_role.strip()
    data = src.get("data") if isinstance(src.get("data"), dict) else {}
    node_id = str(src.get("id") or "").strip()

    if ntype == "reference":
        ref_id = str(data.get("refId") or "").strip()
        if not ref_id:
            return None
        return WorkflowReferenceItem(
            ref_id=ref_id,
            role=ref_role,
            description=ref_description,
            file_name=str(data.get("fileName") or "").strip(),
            node_id=node_id,
        )

    gid = _generation_id_from_node(src)
    if ntype == "preview" and gid is None:
        gid = _generation_id_from_preview_upstream(src, edges, node_map)
    if gid is None:
        return None
    return WorkflowReferenceItem(
        ref_id="",
        role=ref_role,
        description=ref_description,
        file_name="",
        node_id=node_id,
        generation_id=gid,
    )


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


def _collect_plan_reference_items(
    *,
    target_id: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    scenario_type: str | None,
    is_first_frame: bool,
) -> list[WorkflowReferenceItem]:
    references: list[WorkflowReferenceItem] = []
    seen_node_ids: set[str] = set()

    def ingest_handle(handle_key: str, *, default_role: str = "") -> None:
        for ref_node in _sources_for_plan_target(target_id, HANDLE[handle_key], edges, node_map):
            node_id = str(ref_node.get("id") or "").strip()
            if node_id and node_id in seen_node_ids:
                continue
            ntype = str(ref_node.get("type") or "")
            if ntype not in _REFERENCE_IMAGE_SOURCE_TYPES:
                raise WorkflowResolutionError(
                    "К входу reference можно подключить «Images ref», «Просмотр» "
                    "или ноду с результатом генерации"
                )
            if not _is_node_enabled(ref_node):
                continue
            item = _reference_item_from_source_node(
                ref_node, edges, node_map, default_role=default_role
            )
            if item is None:
                if is_first_frame:
                    continue
                raise WorkflowResolutionError(
                    "Загрузите изображение во все подключённые референсы "
                    "или выполните upstream-генерацию"
                )
            references.append(item)
            if node_id:
                seen_node_ids.add(node_id)

    ingest_handle("gen_reference_in")
    if scenario_type == "scenarioFaceSwap":
        ingest_handle("identity_ref_in", default_role="model / identity")
    return references


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
    if _sources_for_plan_target(target_id, HANDLE["motion_video_in"], edges, node_map):
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
    motion_nodes = _sources_for_plan_target(target_id, HANDLE["motion_video_in"], edges, node_map)
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


def _upstream_compose_node_for_video(
    target_id: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    from app.services.studio_workflow_scenarios import find_upstream_scenario_for_target

    scenario = find_upstream_scenario_for_target(target_id, edges, node_map)
    if scenario and scenario_type_of(scenario) == "scenarioMotionVideo":
        return scenario
    for edge in edges:
        if str(edge.get("target") or "") != target_id:
            continue
        if edge.get("targetHandle") is not None and str(edge.get("targetHandle")) != HANDLE["gen_prompt_in"]:
            continue
        src_id = str(edge.get("source") or "").strip()
        node = node_map.get(src_id)
        if node and str(node.get("type") or "") in (
            "videoPromptCompose",
            "scenarioMotionVideo",
        ) and _is_node_enabled(node):
            return node
    return None


def _boardstory_slot_from_compose_data(
    compose_node: dict[str, Any] | None,
    *,
    kind: str,
    gen_key: str,
    url_key: str,
) -> BoardStoryImageSlot | None:
    if compose_node is None:
        return None
    data = compose_node.get("data") if isinstance(compose_node.get("data"), dict) else {}
    raw_gid = data.get(gen_key)
    gid: int | None = None
    if raw_gid is not None and str(raw_gid).strip():
        try:
            gid = int(raw_gid)
        except (TypeError, ValueError):
            gid = None
    if gid is None or gid <= 0:
        return None
    return BoardStoryImageSlot(
        kind=kind,
        generation_id=gid,
        role=kind,
        description=str(data.get(url_key) or ""),
    )


def _merge_boardstory_slot(
    handle_slot: BoardStoryImageSlot | None,
    compose_slot: BoardStoryImageSlot | None,
) -> BoardStoryImageSlot | None:
    return handle_slot if handle_slot is not None else compose_slot


def _resolve_boardstory_slot_for_handle(
    *,
    target_id: str,
    target_handle: str,
    default_kind: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
) -> BoardStoryImageSlot | None:
    """Первый источник на typed handle: reference (refId) или image generation (generationId)."""
    sources = _sources_for_plan_target(target_id, target_handle, edges, node_map)
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
            return None
        return BoardStoryImageSlot(
            kind=kind,
            ref_id=ref_id,
            role=role or default_kind,
            description=description,
        )

    if ntype == "preview":
        gid = _generation_id_from_node(src)
        if gid is None:
            gid = _generation_id_from_preview_upstream(src, edges, node_map)
        if gid is None:
            return None
        return BoardStoryImageSlot(
            kind=kind,
            generation_id=gid,
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
        f"К входу {default_kind} можно подключить «Images ref», «Просмотр» или ноду с результатом генерации"
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


_LOCATION_REF_ROLE_HINTS = (
    "location",
    "environment",
    "background",
    "scene donor",
    "scene_donor",
)


def _role_sort_key(role: str) -> tuple[int, str]:
    r = (role or "").strip().lower()
    for hint in _PRIMARY_REF_ROLE_HINTS:
        if hint in r:
            return (0, r)
    for hint in _LOCATION_REF_ROLE_HINTS:
        if hint in r:
            return (1, r)
    return (2, r)


def sort_workflow_references(
    references: tuple[WorkflowReferenceItem, ...] | list[WorkflowReferenceItem],
) -> tuple[WorkflowReferenceItem, ...]:
    """Primary ref (photo base / pose / model) first — остальные по роли."""
    if not references:
        return ()
    return tuple(sorted(references, key=lambda ref: _role_sort_key(ref.role)))


def is_identity_ref_role(role: str | None) -> bool:
    r = (role or "").strip().lower()
    if not r:
        return False
    if any(h in r for h in _IDENTITY_REF_ROLE_HINTS):
        return True
    if "model" in r and not any(h in r for h in ("pose", "camera", "scene", "framing")):
        return True
    return False


def is_scene_donor_ref_role(role: str | None) -> bool:
    r = (role or "").strip().lower()
    if not r:
        return False
    if any(h in r for h in _LOCATION_REF_ROLE_HINTS):
        return False
    if any(h in r for h in _SCENE_DONOR_REF_ROLE_HINTS):
        return True
    if "scene" in r and not is_identity_ref_role(role):
        return True
    return False


def is_workflow_dual_ref_identity_mode(
    *,
    scenario_type: str | None,
    model_id: int | None,
    references: tuple[WorkflowReferenceItem, ...] | list[WorkflowReferenceItem],
) -> bool:
    """Два ref без модели из кабинета: identity-фото + scene/pose-фото."""
    if model_id is not None:
        return False
    refs = list(references)
    if len(refs) < 2:
        return False
    has_identity = any(is_identity_ref_role(r.role) for r in refs)
    has_scene = any(is_scene_donor_ref_role(r.role) for r in refs)
    if not (has_identity and has_scene):
        return False
    return scenario_type in (None, "scenarioFaceSwap")


def workflow_ref_items_from_meta(
    refs_meta: list[dict[str, str]],
) -> list[WorkflowReferenceItem]:
    return [
        WorkflowReferenceItem(
            ref_id=str(item.get("ref_id") or ""),
            role=str(item.get("role") or ""),
            description=str(item.get("description") or ""),
            file_name=str(item.get("file_name") or ""),
        )
        for item in refs_meta
    ]


def workflow_dual_ref_face_swap_allowed(
    *,
    scenario_type: str | None,
    model_id: int | None,
    refs_meta: list[dict[str, str]],
    workflow_source: bool,
) -> bool:
    """Face swap из workflow без model_id: identity ref + scene ref."""
    if not workflow_source or model_id is not None or not refs_meta:
        return False
    return is_workflow_dual_ref_identity_mode(
        scenario_type=scenario_type,
        model_id=None,
        references=workflow_ref_items_from_meta(refs_meta),
    )


def order_workflow_references_for_wavespeed(
    *,
    scenario_type: str | None,
    model_id: int | None,
    references: tuple[WorkflowReferenceItem, ...] | list[WorkflowReferenceItem],
) -> tuple[WorkflowReferenceItem, ...]:
    """WaveSpeed / face_swap: scene bitmap first, identity ref second when no cabinet model."""
    refs = list(references)
    if not refs:
        return ()
    if model_id is not None:
        return sort_workflow_references(refs)
    identity = [r for r in refs if is_identity_ref_role(r.role)]
    scene = [r for r in refs if is_scene_donor_ref_role(r.role)]
    if identity and scene and scenario_type in (None, "scenarioFaceSwap"):
        ordered = scene + identity
        seen = {id(r) for r in ordered}
        for r in refs:
            if id(r) not in seen:
                ordered.append(r)
        return tuple(ordered)
    return sort_workflow_references(refs)


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


def _normalize_workflow_wave_selection(
    wave_model: str,
    wan_tier: str,
) -> tuple[str, str]:
    """UI id wan-2.7-pro → API wan-2.7 + tier pro."""
    mid = (wave_model or "wan-2.7").strip().lower()
    tier = (wan_tier or "standard").strip().lower()
    if mid == "wan-2.7-pro":
        return "wan-2.7", "pro"
    if mid == "wan-2.7":
        return "wan-2.7", "pro" if tier == "pro" else "standard"
    if mid in WORKFLOW_WAVE_MODELS:
        return mid, "standard"
    return "wan-2.7", "standard"


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

    model_node = _sources_for_plan_target(target_id, HANDLE["gen_model_in"], edges, node_map)
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

    _, scenario = _plan_input_target(target_id, edges, node_map)
    scenario_type = scenario_type_of(scenario)
    is_first_frame = str(target.get("type") or "") == "firstFrameGeneration"

    references = _collect_plan_reference_items(
        target_id=target_id,
        edges=edges,
        node_map=node_map,
        scenario_type=scenario_type,
        is_first_frame=is_first_frame,
    )
    ref_nodes = _sources_for_plan_target(target_id, HANDLE["gen_reference_in"], edges, node_map)
    if scenario_type == "scenarioFaceSwap":
        ref_nodes = ref_nodes + _sources_for_plan_target(
            target_id, HANDLE["identity_ref_in"], edges, node_map
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
    elif ref_nodes and not references:
        raise WorkflowResolutionError(
            "Загрузите изображение во все подключённые ноды «Референс»"
        )

    sorted_refs = sort_workflow_references(references)

    prompt_node = _sources_for_plan_target(target_id, HANDLE["gen_prompt_in"], edges, node_map)
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
    elif not references:
        if model_id is None and not prompt_text.strip():
            raise WorkflowResolutionError(
                "Добавьте промпт, подключите референс или выберите модель в ноде «Модель»"
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
    realism_nodes = _sources_for_plan_target(target_id, HANDLE["gen_realism_in"], edges, node_map)
    realism_node = realism_nodes[0] if realism_nodes else None
    if realism_node and str(realism_node.get("type") or "") == "realism":
        rdata = realism_node.get("data") if isinstance(realism_node.get("data"), dict) else {}
        if rdata.get("enabled") is False:
            realism_enabled = False

    selfie_capture_enabled = False
    selfie_nodes = _sources_for_plan_target(target_id, HANDLE["gen_selfie_in"], edges, node_map)
    selfie_node = selfie_nodes[0] if selfie_nodes else None
    if selfie_node and str(selfie_node.get("type") or "") == "selfie":
        sdata = selfie_node.get("data") if isinstance(selfie_node.get("data"), dict) else {}
        if sdata.get("enabled") is not False:
            from app.services.studio_workflow_selfie import append_selfie_capture_grok_notes

            selfie_capture_enabled = True
            description = append_selfie_capture_grok_notes(description)

    output_aspect = str(gen_data.get("outputAspect") or "3:4").strip() or "3:4"

    wave_model_raw = str(gen_data.get("waveModelId") or "wan-2.7").strip().lower()
    wan_tier_raw = str(gen_data.get("wanEditTier") or "standard").strip().lower()
    wave_model, wan_tier = _normalize_workflow_wave_selection(wave_model_raw, wan_tier_raw)

    nsfw_enabled = gen_data.get("nsfwEnabled")
    if nsfw_enabled is False:
        wave_profile = "regular"
    else:
        wave_profile = "nsfw"

    if wave_profile == "nsfw" and wave_model_raw not in (
        *WORKFLOW_NSFW_ONLY_MODELS,
        *WORKFLOW_CROSS_PROFILE_MODELS,
    ):
        raise WorkflowResolutionError(
            "В режиме NSFW доступны Wan 2.7, Wan 2.7 Pro и Seedream V5 Pro"
        )
    if wave_profile == "regular" and wave_model_raw in WORKFLOW_NSFW_ONLY_MODELS:
        raise WorkflowResolutionError(
            "Wan 2.7 доступна только в режиме NSFW — отключите Regular или выберите другую модель"
        )
    if wave_profile == "regular" and wave_model not in WORKFLOW_REGULAR_MODELS:
        raise WorkflowResolutionError(
            "В обычном режиме доступны Nano Banana, Nano Banana Pro, GPT Image и Seedream V5 Pro"
        )

    if wan_tier not in ("standard", "pro"):
        wan_tier = "standard"
    exif_camera = str(gen_data.get("exifCamera") or "main").strip() or "main"
    if selfie_capture_enabled:
        exif_camera = "selfie"

    if wave_profile == "regular":
        wan_tier = "standard"

    if scenario_type == "scenarioOutfitChange":
        description = enrich_description_for_outfit_change(description)
    elif scenario_type == "scenarioLocationChange":
        description = enrich_description_for_location_change(description)
    elif scenario_type == "scenarioFaceSwap":
        description = enrich_description_for_face_swap(description)
        if model_id is None and not any(is_identity_ref_role(r.role) for r in sorted_refs):
            raise WorkflowResolutionError(
                "Сценарий «смена модели»: выберите модель в ноде «Модель» "
                "или подключите identity ref (вход identity ref)"
            )
        if not sorted_refs:
            raise WorkflowResolutionError(
                "Сценарий «смена модели»: подключите референс сцены с человеком"
            )
        if model_id is None and not any(is_scene_donor_ref_role(r.role) for r in sorted_refs):
            raise WorkflowResolutionError(
                "Сценарий «смена модели»: у ref сцены укажите роль pose / camera / scene"
            )
    elif scenario_type == "scenarioFirstFrame":
        description = enrich_description_for_first_frame(description)

    output_refs = order_workflow_references_for_wavespeed(
        scenario_type=scenario_type,
        model_id=model_id,
        references=sorted_refs,
    )

    return WorkflowGenerationPlan(
        model_id=model_id,
        description=description,
        references=output_refs,
        output_aspect=output_aspect,
        studio_wave_profile=wave_profile,
        workflow_wave_model=wave_model,
        wan_edit_tier=wan_tier,
        exif_camera=exif_camera,
        realism_enabled=realism_enabled,
        selfie_capture_enabled=selfie_capture_enabled,
        motion_video_file_id=motion_video_file_id,
        scenario_type=scenario_type,
    )


def _node_has_video_url(node: dict[str, Any]) -> bool:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    return bool(str(data.get("videoUrl") or "").strip())


def _video_upstream_sources(
    *,
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    label: str,
) -> list[dict[str, Any]]:
    sources = _sources_for_target(target_id, target_handle, edges, node_map)
    if not sources:
        raise WorkflowResolutionError(f"Подключите вход {label} от ноды «Видео» или «Апскейл видео»")
    for src in sources:
        ntype = str(src.get("type") or "")
        if ntype not in _VIDEO_OUTPUT_NODE_TYPES:
            raise WorkflowResolutionError(
                f"К входу {label} можно подключить ноду «Видео» или «Апскейл видео»"
            )
    return sorted(sources, key=lambda node: (0 if _node_has_video_url(node) else 1))


def resolve_upstream_video_generation_id(
    *,
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    label: str = "видео",
) -> int:
    """generationId с upstream videoGeneration / videoUpscale (без проверки БД)."""
    sources = _video_upstream_sources(
        target_id=target_id,
        target_handle=target_handle,
        edges=edges,
        node_map=node_map,
        label=label,
    )
    for src in sources:
        gid = _generation_id_from_node(src)
        if gid is not None:
            return gid
    raise WorkflowResolutionError(
        f"Сначала выполните генерацию upstream-ноды для {label} (нет generationId)"
    )


def _normalize_media_url(url: str) -> str:
    from urllib.parse import urlparse, urlunparse

    u = (url or "").strip()
    if not u:
        return ""
    parsed = urlparse(u)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _generation_id_from_studio_media_url(url: str) -> int | None:
    from urllib.parse import parse_qs, urlparse

    from app.services.studio_image_token import decode_generation_image_access_token

    u = (url or "").strip()
    if "public-generation-video" not in u and "public-generation-image" not in u:
        return None
    parsed = urlparse(u)
    tok = (parse_qs(parsed.query).get("t") or [""])[0]
    if not tok:
        return None
    try:
        _uid, gid = decode_generation_image_access_token(tok)
        return gid if gid > 0 else None
    except ValueError:
        return None


def _video_generation_row_is_usable(row) -> bool:
    from app.services.studio_generation_placeholders import generation_media_kind
    from app.services.studio_generation_storage import generation_has_archive_file

    if generation_media_kind(row) != "video":
        return False
    src = (row.source_url or "").strip()
    if src.startswith("https://"):
        return True
    return generation_has_archive_file(row)


async def resolve_video_generation_id_for_upstream_node(
    session,
    *,
    owner_id: int,
    node: dict[str, Any],
) -> int | None:
    """Готовое видео upstream-ноды: generationId, archive URL, source_url или motion history."""
    from sqlalchemy import select

    from app.db.models import StudioGeneration, StudioMotionRender

    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    video_url = str(data.get("videoUrl") or "").strip()

    async def _validate_gid(gid: int) -> int | None:
        row = await session.get(StudioGeneration, gid)
        if not row or row.user_id != owner_id:
            return None
        if not _video_generation_row_is_usable(row):
            return None
        return gid

    gid = _generation_id_from_node(node)
    if gid is not None:
        ok = await _validate_gid(gid)
        if ok is not None:
            return ok

    if not video_url:
        return None

    tok_gid = _generation_id_from_studio_media_url(video_url)
    if tok_gid is not None:
        ok = await _validate_gid(tok_gid)
        if ok is not None:
            return ok

    stmt = (
        select(StudioGeneration)
        .where(
            StudioGeneration.user_id == owner_id,
            StudioGeneration.content_type.like("video/%"),
            StudioGeneration.source_url == video_url,
        )
        .order_by(StudioGeneration.id.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is not None and _video_generation_row_is_usable(row):
        return row.id

    norm = _normalize_media_url(video_url)
    if norm:
        recent = (
            select(StudioGeneration)
            .where(
                StudioGeneration.user_id == owner_id,
                StudioGeneration.content_type.like("video/%"),
                StudioGeneration.source_url.isnot(None),
            )
            .order_by(StudioGeneration.id.desc())
            .limit(40)
        )
        for candidate in (await session.execute(recent)).scalars():
            if _normalize_media_url(candidate.source_url or "") == norm:
                if _video_generation_row_is_usable(candidate):
                    return candidate.id

    mr_stmt = (
        select(StudioMotionRender)
        .where(
            StudioMotionRender.user_id == owner_id,
            StudioMotionRender.video_url == video_url,
        )
        .order_by(StudioMotionRender.id.desc())
        .limit(1)
    )
    motion_row = (await session.execute(mr_stmt)).scalar_one_or_none()
    if motion_row is not None and motion_row.studio_generation_id:
        ok = await _validate_gid(int(motion_row.studio_generation_id))
        if ok is not None:
            return ok

    if norm:
        mr_recent = (
            select(StudioMotionRender)
            .where(StudioMotionRender.user_id == owner_id)
            .order_by(StudioMotionRender.id.desc())
            .limit(40)
        )
        for motion_row in (await session.execute(mr_recent)).scalars():
            if _normalize_media_url(motion_row.video_url or "") != norm:
                continue
            if motion_row.studio_generation_id:
                ok = await _validate_gid(int(motion_row.studio_generation_id))
                if ok is not None:
                    return ok

    return None


async def resolve_upstream_video_generation_id_validated(
    session,
    *,
    owner_id: int,
    target_id: str,
    target_handle: str,
    edges: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    label: str = "видео",
) -> int:
    """generationId готового видео с проверкой content_type в БД."""
    sources = _video_upstream_sources(
        target_id=target_id,
        target_handle=target_handle,
        edges=edges,
        node_map=node_map,
        label=label,
    )
    for src in sources:
        gid = await resolve_video_generation_id_for_upstream_node(
            session,
            owner_id=owner_id,
            node=src,
        )
        if gid is not None:
            return gid

    if any(_node_has_video_url(src) for src in sources):
        raise WorkflowResolutionError(
            "Видео отображается, но сервер не нашёл generationId. "
            "Перегенерируйте ролик на ноде «Видео» и повторите апскейл."
        )
    if any(_generation_id_from_node(src) is not None for src in sources):
        raise WorkflowResolutionError(
            "Подключён источник изображения, а не видео. "
            "Подключите выход «video» с ноды «Видео» после генерации ролика."
        )
    raise WorkflowResolutionError(
        f"Сначала выполните генерацию upstream-ноды для {label} (нет generationId)"
    )


def _build_workflow_video_upscale_plan(
    *,
    target_id: str,
    target: dict[str, Any],
    node_map: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    source_gid: int,
) -> WorkflowVideoUpscalePlan:
    gen_data = target.get("data") if isinstance(target.get("data"), dict) else {}
    target_resolution = str(gen_data.get("targetResolution") or "1080p").strip().lower() or "1080p"

    output_aspect: str | None = None
    for edge in edges:
        if str(edge.get("target") or "") != target_id:
            continue
        if edge.get("targetHandle") is not None and str(edge.get("targetHandle")) != HANDLE["video_in"]:
            continue
        src = node_map.get(str(edge.get("source") or "").strip())
        if not src:
            continue
        sdata = src.get("data") if isinstance(src.get("data"), dict) else {}
        asp = str(sdata.get("outputAspect") or "").strip()
        if asp:
            output_aspect = asp
        break

    return WorkflowVideoUpscalePlan(
        source_generation_id=source_gid,
        target_resolution=target_resolution,
        studio_model_id=None,
        output_aspect=output_aspect,
    )


def resolve_workflow_video_upscale_plan(
    *,
    target_node_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> WorkflowVideoUpscalePlan:
    node_map = _node_map(nodes)
    target_id = (target_node_id or "").strip()
    target = node_map.get(target_id)
    if not target:
        raise WorkflowResolutionError("Целевая нода не найдена в графе")
    _require_enabled_target(target)
    if str(target.get("type") or "") != "videoUpscale":
        raise WorkflowResolutionError("Неверный тип ноды для апскейла видео")

    source_gid = resolve_upstream_video_generation_id(
        target_id=target_id,
        target_handle=HANDLE["video_in"],
        edges=edges,
        node_map=node_map,
        label="видео",
    )
    return _build_workflow_video_upscale_plan(
        target_id=target_id,
        target=target,
        node_map=node_map,
        edges=edges,
        source_gid=source_gid,
    )


async def resolve_workflow_video_upscale_plan_async(
    session,
    *,
    owner_id: int,
    target_node_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> WorkflowVideoUpscalePlan:
    node_map = _node_map(nodes)
    target_id = (target_node_id or "").strip()
    target = node_map.get(target_id)
    if not target:
        raise WorkflowResolutionError("Целевая нода не найдена в графе")
    _require_enabled_target(target)
    if str(target.get("type") or "") != "videoUpscale":
        raise WorkflowResolutionError("Неверный тип ноды для апскейла видео")

    source_gid = await resolve_upstream_video_generation_id_validated(
        session,
        owner_id=owner_id,
        target_id=target_id,
        target_handle=HANDLE["video_in"],
        edges=edges,
        node_map=node_map,
        label="видео",
    )
    return _build_workflow_video_upscale_plan(
        target_id=target_id,
        target=target,
        node_map=node_map,
        edges=edges,
        source_gid=source_gid,
    )
