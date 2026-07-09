"""Тесты разбора графа workflow → план генерации."""

from __future__ import annotations

import pytest

from app.services.studio_workflow_resolver import (
    WorkflowReferenceItem,
    WorkflowResolutionError,
    _generation_id_from_studio_media_url,
    _normalize_media_url,
    assemble_workflow_grok_notes,
    resolve_workflow_generation_plan,
    resolve_workflow_video_upscale_plan,
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


def test_resolve_workflow_wan_pro_ui_id():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "gen-1":
            n["data"]["waveModelId"] = "wan-2.7-pro"
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.workflow_wave_model == "wan-2.7"
    assert plan.wan_edit_tier == "pro"


def test_resolve_workflow_regular_rejects_wan():
    g = _base_graph()
    for n in g["nodes"]:
        if n["id"] == "gen-1":
            n["data"]["nsfwEnabled"] = False
            n["data"]["waveModelId"] = "wan-2.7-pro"
    with pytest.raises(WorkflowResolutionError, match="Wan 2.7"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


def test_resolve_workflow_seedream_v5_in_regular_and_nsfw():
    for nsfw_enabled in (False, True):
        g = _base_graph()
        for n in g["nodes"]:
            if n["id"] == "gen-1":
                n["data"]["nsfwEnabled"] = nsfw_enabled
                n["data"]["waveModelId"] = "seedream-v5.0-pro"
        plan = resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )
        assert plan.workflow_wave_model == "seedream-v5.0-pro"
        assert plan.studio_wave_profile == ("nsfw" if nsfw_enabled else "regular")


def test_resolve_workflow_realism_disabled():
    g = _base_graph(realism_enabled=False)
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.realism_enabled is False


def test_resolve_workflow_selfie_enabled():
    g = _base_graph()
    g["nodes"].append(
        {
            "id": "selfie-1",
            "type": "selfie",
            "data": {"enabled": True},
        }
    )
    g["edges"].append(
        {
            "source": "selfie-1",
            "target": "gen-1",
            "targetHandle": "selfie-in",
        }
    )
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.selfie_capture_enabled is True
    assert "ARM-LENGTH FRONT-CAMERA SELFIE" in plan.description
    assert plan.exif_camera == "selfie"


def test_resolve_workflow_selfie_disabled():
    g = _base_graph()
    g["nodes"].append(
        {
            "id": "selfie-1",
            "type": "selfie",
            "data": {"enabled": False},
        }
    )
    g["edges"].append(
        {
            "source": "selfie-1",
            "target": "gen-1",
            "targetHandle": "selfie-in",
        }
    )
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.selfie_capture_enabled is False
    assert "ARM-LENGTH FRONT-CAMERA SELFIE" not in plan.description


def test_build_grok_json_selfie_photography():
    import json

    from app.services.studio_prompt_bundle import build_grok_text_scene_positive_json

    positive, negative = build_grok_text_scene_positive_json(
        "She holds phone, friend took photo from across room with rear camera.",
        model_profile_text=None,
        selfie_capture=True,
    )
    data = json.loads(positive)
    photo = data["photography"]
    assert "selfie" in photo["capture_type"].lower()
    assert "front" in photo["camera_style"].lower()
    assert any("selfie" in line.lower() for line in data["constraints"]["must_keep"])
    assert "friend photographing" in negative.lower()


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


def test_resolve_video_prompt_compose_plan():
    from app.services.studio_workflow_resolver import resolve_workflow_video_prompt_compose_plan

    g = _motion_pipeline_graph()
    for n in g["nodes"]:
        if n["id"] == "video-1":
            n["type"] = "videoPromptCompose"
            n["data"] = {"prompt": ""}
    g["edges"].append(
        {
            "source": "prompt-1",
            "target": "video-1",
            "sourceHandle": "prompt-out",
            "targetHandle": "prompt-in",
        }
    )
    plan = resolve_workflow_video_prompt_compose_plan(
        target_node_id="video-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.model_id == 1
    assert plan.motion_video_file_id == "mv1"
    assert plan.first_frame_generation_id == 10
    assert plan.sheet_generation_id == 20
    assert plan.user_notes == "She dances slowly."


def test_resolve_video_plan_accepts_compose_prompt():
    from app.services.studio_workflow_resolver import resolve_workflow_video_plan

    g = _motion_pipeline_graph()
    g["nodes"].append(
        {
            "id": "vp-1",
            "type": "videoPromptCompose",
            "data": {"prompt": "Full cinematic motion prompt from Grok."},
        }
    )
    for e in g["edges"]:
        if e.get("target") == "video-1" and e.get("targetHandle") == "prompt-in":
            e["source"] = "vp-1"
    for n in g["nodes"]:
        if n["id"] == "mv-1":
            n["data"] = {**n["data"], "disabled": True}
    plan = resolve_workflow_video_plan(
        target_node_id="video-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert "Grok" in plan.prompt
    assert plan.auto_motion_prompt is False
    assert plan.prompt_from_compose is True


def test_resolve_video_plan_boardstory_without_first_frame():
    from app.services.studio_workflow_resolver import resolve_workflow_video_plan

    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 1}},
            {"id": "mv-1", "type": "motionVideo", "data": {"motionVideoFileId": "mv1"}},
            {
                "id": "ref-cloth",
                "type": "reference",
                "data": {"refId": "cloth1", "fileName": "outfit.jpg"},
            },
            {
                "id": "ref-env",
                "type": "reference",
                "data": {"refId": "env1", "fileName": "room.jpg"},
            },
            {
                "id": "vp-1",
                "type": "videoPromptCompose",
                "data": {"prompt": "Cinematic motion with @Image1 identity."},
            },
            {
                "id": "video-1",
                "type": "videoGeneration",
                "data": {"durationSeconds": 5, "autoMotionPrompt": False},
            },
        ],
        "edges": [
            {"source": "model-1", "target": "video-1", "targetHandle": "model-in"},
            {"source": "vp-1", "target": "video-1", "sourceHandle": "prompt-out", "targetHandle": "prompt-in"},
            {
                "source": "mv-1",
                "target": "video-1",
                "sourceHandle": "motion-video-out",
                "targetHandle": "motion-video-in",
            },
            {
                "source": "ref-cloth",
                "target": "video-1",
                "sourceHandle": "reference-out",
                "targetHandle": "clothing-in",
            },
            {
                "source": "ref-env",
                "target": "video-1",
                "sourceHandle": "reference-out",
                "targetHandle": "environment-in",
            },
        ],
    }
    plan = resolve_workflow_video_plan(
        target_node_id="video-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.boardstory_mode is True
    assert plan.first_frame_generation_id is None
    assert plan.sheet_generation_id is None
    assert plan.clothing_ref is not None
    assert plan.clothing_ref.ref_id == "cloth1"
    assert plan.environment_ref is not None
    assert plan.prompt_from_compose is True


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


def test_image_generation_model_prompt_without_reference():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 42}},
            {
                "id": "prompt-1",
                "type": "prompt",
                "data": {"prompt": "Сидит на диване, листает телефон"},
            },
            {
                "id": "gen-1",
                "type": "imageGeneration",
                "data": {
                    "waveModelId": "gpt-image-2",
                    "nsfwEnabled": False,
                    "outputAspect": "9:16",
                },
            },
        ],
        "edges": [
            {"source": "model-1", "target": "gen-1", "targetHandle": "model-in"},
            {"source": "prompt-1", "target": "gen-1", "targetHandle": "prompt-in"},
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.model_id == 42
    assert plan.references == ()
    assert plan.studio_wave_profile == "regular"
    assert plan.workflow_wave_model == "gpt-image-2"
    assert "диване" in plan.description


def test_image_generation_prompt_only_without_model_or_reference():
    g = {
        "nodes": [
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "Sunset beach"}},
            {"id": "gen-1", "type": "imageGeneration", "data": {}},
        ],
        "edges": [
            {"source": "prompt-1", "target": "gen-1", "targetHandle": "prompt-in"},
        ],
    }
    with pytest.raises(WorkflowResolutionError, match="модель"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )


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


def test_first_frame_gpt_image_model_prompt_without_reference():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 3}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "Sunset beach walk"}},
            {
                "id": "ff-1",
                "type": "firstFrameGeneration",
                "data": {
                    "waveModelId": "gpt-image-2",
                    "nsfwEnabled": False,
                    "outputAspect": "9:16",
                },
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
    assert plan.studio_wave_profile == "regular"
    assert plan.workflow_wave_model == "gpt-image-2"
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


def test_resolve_video_upscale_plan():
    g = {
        "nodes": [
            {
                "id": "video-1",
                "type": "videoGeneration",
                "data": {"generationId": 42, "outputAspect": "9:16"},
            },
            {
                "id": "up-1",
                "type": "videoUpscale",
                "data": {"targetResolution": "4k"},
            },
        ],
        "edges": [
            {
                "id": "e1",
                "source": "video-1",
                "target": "up-1",
                "sourceHandle": "video-out",
                "targetHandle": "video-in",
            },
        ],
    }
    plan = resolve_workflow_video_upscale_plan(
        target_node_id="up-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.source_generation_id == 42
    assert plan.target_resolution == "4k"
    assert plan.output_aspect == "9:16"


def test_normalize_media_url_strips_query():
    assert (
        _normalize_media_url("https://cdn.example.com/v/a.mp4?token=abc")
        == "https://cdn.example.com/v/a.mp4"
    )


def test_generation_id_from_studio_media_url_invalid():
    assert _generation_id_from_studio_media_url("https://cdn.example.com/v.mp4") is None
    assert _generation_id_from_studio_media_url("") is None


def test_scenario_outfit_change_enriches_description():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 1}},
            {"id": "ref-base", "type": "reference", "data": {"refId": "base1"}},
            {"id": "ref-cloth", "type": "reference", "data": {"refId": "cloth1"}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "swap outfit"}},
            {
                "id": "scenario-1",
                "type": "scenarioOutfitChange",
                "data": {},
            },
            {
                "id": "gen-1",
                "type": "imageGeneration",
                "data": {"waveModelId": "wan-2.7", "nsfwEnabled": True},
            },
        ],
        "edges": [
            {"source": "model-1", "target": "scenario-1", "targetHandle": "model-in"},
            {"source": "ref-base", "target": "scenario-1", "targetHandle": "reference-in"},
            {"source": "ref-cloth", "target": "scenario-1", "targetHandle": "reference-in"},
            {"source": "prompt-1", "target": "scenario-1", "targetHandle": "prompt-in"},
            {
                "source": "scenario-1",
                "target": "gen-1",
                "sourceHandle": "pipeline-out",
                "targetHandle": "pipeline-in",
            },
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.scenario_type == "scenarioOutfitChange"
    assert "outfit change" in plan.description.lower()
    assert len(plan.references) == 2


def test_scenario_location_change_enriches_description():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 1}},
            {"id": "ref-base", "type": "reference", "data": {"refId": "base1"}},
            {"id": "ref-loc1", "type": "reference", "data": {"refId": "loc1"}},
            {"id": "ref-loc2", "type": "reference", "data": {"refId": "loc2"}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "swap location"}},
            {
                "id": "scenario-1",
                "type": "scenarioLocationChange",
                "data": {},
            },
            {
                "id": "gen-1",
                "type": "imageGeneration",
                "data": {"waveModelId": "wan-2.7", "nsfwEnabled": True},
            },
        ],
        "edges": [
            {"source": "model-1", "target": "scenario-1", "targetHandle": "model-in"},
            {"source": "ref-base", "target": "scenario-1", "targetHandle": "reference-in"},
            {"source": "ref-loc1", "target": "scenario-1", "targetHandle": "reference-in"},
            {"source": "ref-loc2", "target": "scenario-1", "targetHandle": "reference-in"},
            {"source": "prompt-1", "target": "scenario-1", "targetHandle": "prompt-in"},
            {
                "source": "scenario-1",
                "target": "gen-1",
                "sourceHandle": "pipeline-out",
                "targetHandle": "pipeline-in",
            },
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.scenario_type == "scenarioLocationChange"
    assert "location change" in plan.description.lower()
    assert len(plan.references) == 3


def test_location_change_ref_sort_order():
    from app.services.studio_workflow_resolver import (
        WorkflowReferenceItem,
        sort_workflow_references,
    )

    refs = [
        WorkflowReferenceItem(ref_id="loc", role="location / environment", description="", file_name=""),
        WorkflowReferenceItem(ref_id="base", role="photo base / subject", description="", file_name=""),
    ]
    sorted_refs = sort_workflow_references(refs)
    assert sorted_refs[0].ref_id == "base"
    assert sorted_refs[1].ref_id == "loc"


def test_location_change_enrich_description_strict():
    from app.services.studio_workflow_scenarios import enrich_description_for_location_change

    hint = enrich_description_for_location_change("")
    assert "FORBIDDEN" in hint
    assert "photo-base" in hint.lower()


def test_scenario_face_swap_enriches_and_requires_model():
    g = {
        "nodes": [
            {"id": "ref-scene", "type": "reference", "data": {"refId": "scene1"}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "swap model"}},
            {"id": "scenario-1", "type": "scenarioFaceSwap", "data": {}},
            {
                "id": "gen-1",
                "type": "imageGeneration",
                "data": {"waveModelId": "wan-2.7", "nsfwEnabled": True},
            },
        ],
        "edges": [
            {"source": "ref-scene", "target": "scenario-1", "targetHandle": "reference-in"},
            {"source": "prompt-1", "target": "scenario-1", "targetHandle": "prompt-in"},
            {
                "source": "scenario-1",
                "target": "gen-1",
                "sourceHandle": "pipeline-out",
                "targetHandle": "pipeline-in",
            },
        ],
    }
    with pytest.raises(WorkflowResolutionError, match="identity"):
        resolve_workflow_generation_plan(
            target_node_id="gen-1",
            nodes=g["nodes"],
            edges=g["edges"],
        )

    g["nodes"].insert(0, {"id": "model-1", "type": "model", "data": {"modelId": 3}})
    g["edges"].insert(0, {"source": "model-1", "target": "scenario-1", "targetHandle": "model-in"})
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.scenario_type == "scenarioFaceSwap"
    assert plan.model_id == 3
    assert "model swap" in plan.description.lower()


def test_scenario_face_swap_dual_ref_without_model():
    from app.services.studio_workflow_resolver import (
        is_workflow_dual_ref_identity_mode,
        order_workflow_references_for_wavespeed,
    )

    g = {
        "nodes": [
            {
                "id": "desc-id",
                "type": "refDescription",
                "data": {"role": "model / identity", "description": "WHO"},
            },
            {"id": "ref-id", "type": "reference", "data": {"refId": "id1"}},
            {
                "id": "desc-scene",
                "type": "refDescription",
                "data": {"role": "pose + camera", "description": "geometry"},
            },
            {"id": "ref-scene", "type": "reference", "data": {"refId": "scene1"}},
            {"id": "prompt-1", "type": "prompt", "data": {"prompt": "swap model"}},
            {"id": "scenario-1", "type": "scenarioFaceSwap", "data": {}},
            {
                "id": "gen-1",
                "type": "imageGeneration",
                "data": {"waveModelId": "wan-2.7", "nsfwEnabled": True},
            },
        ],
        "edges": [
            {"source": "desc-id", "target": "ref-id", "targetHandle": "description-in"},
            {"source": "desc-scene", "target": "ref-scene", "targetHandle": "description-in"},
            {"source": "ref-id", "target": "scenario-1", "targetHandle": "identity-ref-in"},
            {"source": "ref-scene", "target": "scenario-1", "targetHandle": "reference-in"},
            {"source": "prompt-1", "target": "scenario-1", "targetHandle": "prompt-in"},
            {
                "source": "scenario-1",
                "target": "gen-1",
                "sourceHandle": "pipeline-out",
                "targetHandle": "pipeline-in",
            },
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.model_id is None
    assert plan.scenario_type == "scenarioFaceSwap"
    assert is_workflow_dual_ref_identity_mode(
        scenario_type=plan.scenario_type,
        model_id=plan.model_id,
        references=plan.references,
    )
    assert plan.references[0].ref_id == "scene1"
    assert plan.references[1].ref_id == "id1"
    ordered = order_workflow_references_for_wavespeed(
        scenario_type=plan.scenario_type,
        model_id=plan.model_id,
        references=plan.references,
    )
    assert ordered[0].ref_id == "scene1"
    assert ordered[1].ref_id == "id1"


def test_scenario_motion_video_pipeline_reads_scenario_settings():
    from app.services.studio_workflow_resolver import resolve_workflow_video_plan

    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 5}},
            {"id": "motion-1", "type": "motionVideo", "data": {"motionVideoFileId": "mv123"}},
            {
                "id": "scenario-1",
                "type": "scenarioMotionVideo",
                "data": {
                    "prompt": "composed prompt @Video1",
                    "generateAudio": False,
                    "autoMotionPrompt": True,
                    "negativePrompt": "blur",
                    "sendVideoReference": True,
                },
            },
            {
                "id": "video-1",
                "type": "videoGeneration",
                "data": {
                    "durationSeconds": 5,
                    "generateAudio": True,
                    "autoMotionPrompt": False,
                },
            },
        ],
        "edges": [
            {"source": "model-1", "target": "scenario-1", "targetHandle": "model-in"},
            {"source": "motion-1", "target": "scenario-1", "targetHandle": "motion-video-in"},
            {
                "source": "scenario-1",
                "target": "video-1",
                "sourceHandle": "pipeline-out",
                "targetHandle": "pipeline-in",
            },
        ],
    }
    plan = resolve_workflow_video_plan(
        target_node_id="video-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.scenario_type == "scenarioMotionVideo"
    assert plan.prompt == "composed prompt @Video1"
    assert plan.motion_video_file_id == "mv123"
    assert plan.model_id == 5
    assert plan.generate_audio is False
    assert plan.auto_motion_prompt is True
    assert plan.negative_prompt == "blur"
    assert plan.prompt_from_compose is True


def test_preview_node_as_reference_via_generation_id():
    g = {
        "nodes": [
            {"id": "model-1", "type": "model", "data": {"modelId": 42}},
            {
                "id": "gen-src",
                "type": "imageGeneration",
                "data": {"generationId": 9001, "imageUrl": "https://x/a.png"},
            },
            {
                "id": "preview-1",
                "type": "preview",
                "data": {"imageUrl": "https://x/a.png", "generationId": 9001},
            },
            {
                "id": "desc-1",
                "type": "refDescription",
                "data": {"role": "clothes", "description": "red dress"},
            },
            {"id": "gen-1", "type": "imageGeneration", "data": {}},
        ],
        "edges": [
            {"source": "gen-src", "target": "preview-1", "targetHandle": "image-in"},
            {"source": "desc-1", "target": "preview-1", "targetHandle": "description-in"},
            {"source": "preview-1", "target": "gen-1", "targetHandle": "reference-in", "sourceHandle": "reference-out"},
            {"source": "model-1", "target": "gen-1", "targetHandle": "model-in"},
        ],
    }
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert len(plan.references) == 1
    assert plan.references[0].generation_id == 9001
    assert plan.references[0].role == "clothes"
    assert plan.references[0].ref_id == ""
