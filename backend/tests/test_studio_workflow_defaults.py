"""Тесты шаблонных workflow-рабочих пространств."""

from __future__ import annotations

from app.services.studio_workflow_defaults import (
    default_workflow_template_names,
    load_default_workflow_templates,
)


def test_load_default_workflow_templates():
    templates = load_default_workflow_templates()
    assert len(templates) == 6
    names = [t.name for t in templates]
    assert "BoardStory Seedance" in names
    assert "Motion pipeline" in names
    assert "Развертка" in names
    assert "Создание Лица" in names
    assert "Смена одежды" in names
    assert "По рефу" in names
    for tpl in templates:
        assert isinstance(tpl.graph.get("nodes"), list)
        assert isinstance(tpl.graph.get("edges"), list)


def test_default_workflow_template_names():
    names = default_workflow_template_names()
    assert len(names) == 6
    assert names == frozenset(
        {
            "BoardStory Seedance",
            "Motion pipeline",
            "Развертка",
            "Создание Лица",
            "Смена одежды",
            "По рефу",
        }
    )
