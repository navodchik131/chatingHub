"""Тесты шаблонных workflow-рабочих пространств."""

from __future__ import annotations

from app.services.studio_workflow_defaults import (
    DEMO_WORKFLOW_NAME,
    default_workflow_template_names,
    demo_workflow_template_files,
    load_default_workflow_templates,
    load_workflow_templates,
)


def test_load_default_workflow_templates():
    templates = load_default_workflow_templates()
    assert len(templates) == 12
    names = [t.name for t in templates]
    assert names[0] == "По рефу"
    assert "BoardStory Seedance" in names
    assert "Motion pipeline" in names
    assert "Генерация видео с одеждой Seedance" in names
    assert "Развертка" in names
    assert "Создание Лица" in names
    assert "Смена одежды" in names
    assert "Смена локации" in names
    assert "Смена модели" in names
    assert "Замена деталей" in names
    assert "Одежда с картинки" in names
    assert "Генерация видео" in names
    assert "По рефу" in names
    for tpl in templates:
        assert isinstance(tpl.graph.get("nodes"), list)
        assert isinstance(tpl.graph.get("edges"), list)


def test_default_workflow_template_names():
    names = default_workflow_template_names()
    assert len(names) == 12
    assert names == frozenset(
        {
            "BoardStory Seedance",
            "Motion pipeline",
            "Генерация видео с одеждой Seedance",
            "Развертка",
            "Создание Лица",
            "Смена одежды",
            "Смена локации",
            "Смена модели",
            "Замена деталей",
            "Одежда с картинки",
            "Генерация видео",
            "По рефу",
        }
    )


def test_demo_workflow_template_is_smena_modeli():
    demo = load_workflow_templates(demo_workflow_template_files())
    assert len(demo) == 1
    assert demo[0].name == DEMO_WORKFLOW_NAME == "Смена модели"
