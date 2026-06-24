"""Тесты разбора графа workflow → план генерации."""

from __future__ import annotations

import pytest

from app.services.studio_workflow_resolver import (
    WorkflowResolutionError,
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
                "data": {"refId": "abc123"},
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
                    "waveProfile": "nsfw",
                    "wanEditTier": "standard",
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


def test_resolve_workflow_generation_plan_ok():
    g = _base_graph()
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.model_id == 42
    assert plan.description == "sunset beach"
    assert plan.reference_ref_id == "abc123"
    assert plan.output_aspect == "3:4"
    assert plan.studio_wave_profile == "nsfw"
    assert plan.wan_edit_tier == "standard"
    assert plan.exif_camera == "iphone15"
    assert plan.realism_enabled is True


def test_resolve_workflow_realism_disabled():
    g = _base_graph(realism_enabled=False)
    plan = resolve_workflow_generation_plan(
        target_node_id="gen-1",
        nodes=g["nodes"],
        edges=g["edges"],
    )
    assert plan.realism_enabled is False


def test_resolve_workflow_missing_model():
    g = _base_graph()
    g["edges"] = [e for e in g["edges"] if e["targetHandle"] != "model-in"]
    with pytest.raises(WorkflowResolutionError, match="Модель"):
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
