"""Тесты разбора графа workflow → план генерации."""

from __future__ import annotations

import pytest

from app.services.studio_workflow_resolver import (
    WorkflowReferenceItem,
    WorkflowResolutionError,
    assemble_workflow_grok_notes,
    resolve_workflow_generation_plan,
)


def _base_graph(*, realism_enabled: bool = True, prompt: str = "sunset beach"):
    return {
        "nodes": [
            {
                "id": "model-1",
                "type": "model",
                "data": {"modelId": 42},
            },
            {
                "id": "ref-1",
                "type": "reference",
                "data": {"refId": "abc123", "fileName": "scene.jpg"},
            },
            {
                "id": "desc-1",
                "type": "refDescription",
                "data": {
                    "role": "pose donor",
                    "description": "sitting on couch, evening light",
                },
            },
            {
                "id": "prompt-1",
                "type": "prompt",
                "data": {"prompt": prompt},
            },
            {
                "id": "realism-1",
                "type": "realism",
                "data": {"enabled": realism_enabled},
            },
            {
                "id": "gen-1",
                "type": "imageGeneration",
                "data": {
                    "outputAspect": "3:4",
                    "waveModelId": "wan-2.7",
                    "nsfwEnabled": True,
                    "exifCamera": "iphone15",
                },
            },
        ],
        "edges": [
            {
                "source": "model-1",
                "target": "gen-1",
                "targetHandle": "model-in",
            },
            {
                "source": "ref-1",
                "target": "gen-1",
                "targetHandle": "reference-in",
            },
            {
                "source": "desc-1",
                "target": "ref-1",
                "targetHandle": "description-in",
            },
            {
                "source": "prompt-1",
                "target": "gen-1",
                "targetHandle": "prompt-in",
            },
            {
                "source": "realism-1",
                "target": "gen-1",
                "targetHandle": "realism-in",
            },
        ],
    }


def test_assemble_workflow_grok_notes():
    notes = assemble_workflow_grok_notes(
        prompt_text="smile at camera",
        references=[
            WorkflowReferenceItem(
                ref_id="abc",
                role="pose donor",
                description="casual hoodie",
                file_name="ref.png",
            )
        ],
    )
    assert "SCENE_DIRECTION:" in notes
    assert "smile at camera" in notes
    assert "REFERENCE_CONTEXT" in notes
    assert "pose donor" in notes
    assert "ref.png" in notes


def test_assemble_workflow_grok_notes_multi_ref():
    notes = assemble_workflow_grok_notes(
        prompt_text="swap outfit",
        references=[
            WorkflowReferenceItem(
                ref_id="a",
                role="photo base",
                description="person to edit",
                file_name="model.jpg",
            ),
            WorkflowReferenceItem(
                ref_id="b",
                role="clothes",
                description="outfit donor",
                file_name="outfit.jpg",
            ),
        ],
    )
    assert "Reference 1:" in notes
    assert "Reference 2:" in notes
    assert "photo base" in notes
    assert "clothes" in notes


def test_resolve_workflow_generation_plan_ok():
    g = _base_graph()
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.model_id == 42
    assert "SCENE_DIRECTION:" in plan.description
    assert "sunset beach" in plan.description
    assert "pose donor" in plan.description
    assert plan.reference_ref_id == "abc123"
    assert plan.reference_role == "pose donor"
    assert plan.output_aspect == "3:4"
    assert plan.studio_wave_profile == "nsfw"
    assert plan.workflow_wave_model == "wan-2.7"
    assert plan.exif_camera == "iphone15"
    assert plan.realism_enabled is True


def test_resolve_workflow_nsfw_off():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "gen-1":
            n["data"]["nsfwEnabled"] = False
            n["data"]["waveModelId"] = "nano-banana-pro"
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.studio_wave_profile == "regular"
    assert plan.workflow_wave_model == "nano-banana-pro"


def test_resolve_workflow_nsfw_only_wan():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "gen-1":
            n["data"]["waveModelId"] = "gpt-image-2"
    with pytest.raises(WorkflowResolutionError, match="Wan"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


def test_resolve_workflow_realism_disabled():
    g = _base_graph(realism_enabled=False)
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.realism_enabled is False


def test_resolve_workflow_without_model_ok():
    g = _base_graph()
    g["edges"] = [e for e in g["edges"] if e.get("targetHandle") != "model-in"]
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.model_id is None
    assert "sunset beach" in plan.description


def test_resolve_workflow_without_model_needs_prompt():
    g = _base_graph(prompt="")
    g["edges"] = [e for e in g["edges"] if e.get("targetHandle") != "model-in"]
    for n in g["nodes"]:
        if n["id"] == "desc-1":
            n["data"] = {"role": "", "description": ""}
    with pytest.raises(WorkflowResolutionError, match="Без модели"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


def test_resolve_workflow_connected_model_empty():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "model-1":
            n["data"] = {"modelId": None}
    with pytest.raises(WorkflowResolutionError, match="Выберите модель"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


def test_resolve_workflow_missing_reference_ref_id():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "ref-1":
            n["data"] = {}
    with pytest.raises(WorkflowResolutionError, match="Загрузите"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


def test_resolve_workflow_multiple_references():
    g = _base_graph()
    g["nodes"].append(
        {
            "id": "ref-2",
            "type": "reference",
            "data": {"refId": "def456", "fileName": "outfit.jpg"},
        }
    )
    g["nodes"].append(
        {
            "id": "desc-2",
            "type": "refDescription",
            "data": {"role": "clothes", "description": "outfit donor"},
        }
    )
    g["edges"].extend(
        [
            {
                "source": "ref-2",
                "target": "gen-1",
                "targetHandle": "reference-in",
            },
            {
                "source": "desc-2",
                "target": "ref-2",
                "targetHandle": "description-in",
            },
        ]
    )
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert len(plan.references) == 2
    assert plan.references[0].role == "pose donor"
    assert plan.references[1].role == "clothes"
    assert "Reference 1:" in plan.description
    assert "Reference 2:" in plan.description


def _motion_pipeline_graph(*, ff_gen_id: int = 10, sheet_gen_id: int = 20, motion_id: str = "mv1"):
    return {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 1}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "She dances slowly."}},
            {
                "id": "ff-1",
                "type": "firstFrameGeneration",
                "data": {"generationId": ff_gen_id, "imageUrl": "https://x/ff.png"},
            },
            {
                "id": "sheet-1",
                "type": "turnaroundSheet",
                "data": {"generationId": sheet_gen_id, "imageUrl": "https://x/sheet.png"},
            },
            {"id": "mv-1", "type": "motionVideo", "data": {"motionVideoFileId": motion_id}},
            {
                "id": "video-1",
                "type": "videoGeneration",
                "data": {
                    "durationSeconds": 5,
                    "seedanceVariant": "mini",
                    "videoResolution": "720p",
                },
            },
        ],
        "edges": [
            {"source": "model-1", "target": "sheet-1", "targetHandle": "model-in"},
            {"source": "ff-1", "target": "sheet-1", "targetHandle": "first-frame-in"},
            {"source": "model-1", "target": "video-1", "targetHandle": "model-in"},
            {"source": "prompt-1", "target": "video-1", "targetHandle": "prompt-in"},
            {"source": "ff-1", "target": "video-1", "targetHandle": "first-frame-in"},
            {"source": "sheet-1", "target": "video-1", "targetHandle": "sheet-in"},
            {
                "source": "mv-1",
                "target": "video-1",
                "sourceHandle": "motion-video-out",
                "targetHandle": "motion-video-in",
            },
        ],
    }


def test_resolve_turnaround_plan():
    from app.services.studio_workflow_resolver import resolve_workflow_turnaround_plan

    g = _motion_pipeline_graph()
    plan = resolve_workflow_turnaround_plan(
        target_node_id="sheet-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.source_generation_id == 10
    assert plan.model_id == 1


def test_resolve_video_plan():
    from app.services.studio_workflow_resolver import resolve_workflow_video_plan

    g = _motion_pipeline_graph()
    plan = resolve_workflow_video_plan(
        target_node_id="video-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.first_frame_generation_id == 10
    assert plan.sheet_generation_id == 20
    assert plan.motion_video_file_id == "mv1"
    assert plan.seedance_variant == "mini"


def test_resolve_video_plan_without_disabled_sheet():
    from app.services.studio_workflow_resolver import resolve_workflow_video_plan

    g = _motion_pipeline_graph()
    for n in g["nodes"]:
        if n["id"] == "sheet-1":
            n["data"] = {**n["data"], "disabled": True}
    plan = resolve_workflow_video_plan(
        target_node_id="video-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.first_frame_generation_id == 10
    assert plan.sheet_generation_id is None


def test_resolve_video_plan_without_disabled_motion():
    from app.services.studio_workflow_resolver import resolve_workflow_video_plan

    g = _motion_pipeline_graph()
    for n in g["nodes"]:
        if n["id"] == "mv-1":
            n["data"] = {**n["data"], "disabled": True}
    plan = resolve_workflow_video_plan(
        target_node_id="video-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.motion_video_file_id == ""
    assert plan.first_frame_generation_id == 10


def test_resolve_video_plan_grok_imagine_i2v():
    from app.services.studio_workflow_resolver import resolve_workflow_video_plan

    g = _motion_pipeline_graph()
    for n in g["nodes"]:
        if n["id"] == "video-1":
            n["data"] = {
                **n["data"],
                "videoProvider": "grok_imagine_i2v",
                "durationSeconds": 6,
                "videoResolution": "720p",
            }
    plan = resolve_workflow_video_plan(
        target_node_id="video-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.video_provider == "grok_imagine_i2v"
    assert plan.motion_video_file_id == ""
    assert plan.sheet_generation_id is None
    assert plan.generate_audio is False
    assert plan.auto_motion_prompt is False
    assert plan.duration_seconds == 6


def test_resolve_video_plan_grok_requires_prompt():
    from app.services.studio_workflow_resolver import WorkflowResolutionError, resolve_workflow_video_plan

    g = _motion_pipeline_graph()
    for n in g["nodes"]:
        if n["id"] == "video-1":
            n["data"] = {**n["data"], "videoProvider": "grok_imagine_i2v"}
        if n["id"] == "prompt-1":
            n["data"] = {"prompt": ""}
    try:
        resolve_workflow_video_plan(
            target_node_id="video-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )
        assert False, "expected WorkflowResolutionError"
    except WorkflowResolutionError as e:
        assert "промпт" in str(e).lower()


def test_first_frame_motion_without_reference():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 7}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "Dancing in studio"}},
            {"id": "mv-1", "type": "motionVideo", "data": {"motionVideoFileId": "mv-workflow"}},
            {
                "id": "ff-1",
                "type": "firstFrameGeneration",
                "data": {"waveModelId": "nano-banana-pro", "nsfwEnabled": False},
            },
            {"id": "ref-empty", "type": "reference", "data": {}},
        ],
        "edges": [
            {"source": "model-1", "target": "ff-1", "targetHandle": "model-in"},
            {"source": "prompt-1", "target": "ff-1", "targetHandle": "prompt-in"},
            {
                "source": "mv-1",
                "target": "ff-1",
                "sourceHandle": "motion-video-out",
                "targetHandle": "motion-video-in",
            },
            {"source": "ref-empty", "target": "ff-1", "targetHandle": "reference-in"},
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="ff-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.motion_video_file_id == "mv-workflow"
    assert plan.references == ()
    assert plan.model_id == 7


def test_first_frame_model_prompt_without_reference():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 3}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "Sunset beach walk"}},
            {
                "id": "ff-1",
                "type": "firstFrameGeneration",
                "data": {"waveModelId": "nano-banana-pro", "nsfwEnabled": False},
            },
        ],
        "edges": [
            {"source": "model-1", "target": "ff-1", "targetHandle": "model-in"},
            {"source": "prompt-1", "target": "ff-1", "targetHandle": "prompt-in"},
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="ff-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.motion_video_file_id == ""
    assert plan.references == ()
    assert plan.model_id == 3
    assert "Sunset beach walk" in plan.description


def test_first_frame_motion_model_without_prompt():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 9}},
            {"id": "mv-1", "type": "motionVideo", "data": {"motionVideoFileId": "mv9"}},
            {"id": "ff-1", "type": "firstFrameGeneration", "data": {}},
        ],
        "edges": [
            {"source": "model-1", "target": "ff-1", "targetHandle": "model-in"},
            {
                "source": "mv-1",
                "target": "ff-1",
                "sourceHandle": "motion-video-out",
                "targetHandle": "motion-video-in",
            },
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="ff-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.motion_video_file_id == "mv9"
    assert plan.model_id == 9


def test_first_frame_motion_from_downstream_video_node():
    """Motion только на «Видео» — первый кадр всё равно идёт через motion_first_frame."""
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 5}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "Slow dance"}},
            {"id": "mv-1", "type": "motionVideo", "data": {"motionVideoFileId": "mv-shared"}},
            {
                "id": "ff-1",
                "type": "firstFrameGeneration",
                "data": {"waveModelId": "nano-banana-pro", "nsfwEnabled": False},
            },
            {"id": "video-1", "type": "videoGeneration", "data": {}},
        ],
        "edges": [
            {"source": "model-1", "target": "ff-1", "targetHandle": "model-in"},
            {"source": "prompt-1", "target": "ff-1", "targetHandle": "prompt-in"},
            {
                "source": "ff-1",
                "target": "video-1",
                "sourceHandle": "image-out",
                "targetHandle": "first-frame-in",
            },
            {
                "source": "mv-1",
                "target": "video-1",
                "sourceHandle": "motion-video-out",
                "targetHandle": "motion-video-in",
            },
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="ff-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.motion_video_file_id == "mv-shared"
    assert plan.references == ()


def test_first_frame_motion_wire_without_upload_raises():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 1}},
            {"id": "mv-1", "type": "motionVideo", "data": {}},
            {"id": "ff-1", "type": "firstFrameGeneration", "data": {}},
        ],
        "edges": [
            {"source": "model-1", "target": "ff-1", "targetHandle": "model-in"},
            {
                "source": "mv-1",
                "target": "ff-1",
                "sourceHandle": "motion-video-out",
                "targetHandle": "motion-video-in",
            },
        ],
    }
    with pytest.raises(WorkflowResolutionError, match="Motion-видео"):
        resolve_workflow_generation_plan(
            target_node_id="ff-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


def test_first_frame_motion_requires_model():
    g = {
        "nodes": [
            {"id": "mv-1", "type": "motionVideo", "data": {"motionVideoFileId": "mv1"}},
            {"id": "ff-1", "type": "firstFrameGeneration", "data": {}},
        ],
        "edges": [
            {
                "source": "mv-1",
                "target": "ff-1",
                "sourceHandle": "motion-video-out",
                "targetHandle": "motion-video-in",
            },
        ],
    }
    with pytest.raises(WorkflowResolutionError, match="модель"):
        resolve_workflow_generation_plan(
            target_node_id="ff-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


def test_resolve_workflow_skips_disabled_model_node():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "model-1":
            n["data"] = {"modelId": 42, "disabled": True}
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.model_id is None
    assert "sunset beach" in plan.description


def test_resolve_workflow_skips_disabled_prompt_node():
    g = _base_graph(prompt="sunset beach")
    for n in g["nodes"]:
        if n["id"] == "prompt-1":
            n["data"] = {"prompt": "sunset beach", "disabled": True}
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert "sunset beach" not in plan.description
    assert "SCENE_DIRECTION" not in plan.description


def test_resolve_workflow_skips_disabled_reference_node():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "ref-1":
            n["data"] = {"refId": "abc123", "fileName": "scene.jpg", "disabled": True}
    with pytest.raises(WorkflowResolutionError, match="Референс"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


def test_resolve_workflow_disabled_target_rejected():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "gen-1":
            n["data"] = {**n["data"], "disabled": True}
    with pytest.raises(WorkflowResolutionError, match="отключена"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )
