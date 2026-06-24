"""Тесты разбора графа workflow → план генерации."""

from __future__ import annotations

import pytest

from app.services.studio_workflow_resolver import (
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
        reference_role="pose donor",
        reference_description="casual hoodie",
        reference_file_name="ref.png",
    )
    assert "SCENE_DIRECTION:" in notes
    assert "smile at camera" in notes
    assert "REFERENCE_CONTEXT:" in notes
    assert "pose donor" in notes
    assert "ref.png" in notes


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
