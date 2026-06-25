"""Шаблоны workflow-рабочих пространств по умолчанию для всех пользователей."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BACKEND_DIR
from app.db.models import WorkflowWorkspace

log = logging.getLogger(__name__)

_TEMPLATES_DIR = (BACKEND_DIR / "data" / "workflow_templates").resolve()
_BUNDLED_TEMPLATES_DIR = (BACKEND_DIR / "_bundled_workflow_templates").resolve()

# Порядок отображения в sidebar (сверху — первый шаблон).
_DEFAULT_TEMPLATE_FILES: tuple[str, ...] = (
    "motion_pipeline.json",
    "razvertka.json",
    "sozdanie-litsa.json",
    "smena-odezhdy.json",
    "po-refu.json",
)

DEMO_WORKFLOW_TEMPLATE_FILE = "po-refu.json"
DEMO_WORKFLOW_NAME = "По рефу"


@dataclass(frozen=True)
class WorkflowTemplate:
    name: str
    graph: dict[str, Any]


def _sanitize_graph_for_seed(graph: dict[str, Any]) -> dict[str, list]:
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {"nodes": [], "edges": []}
    return {"nodes": nodes, "edges": edges}


def _parse_template_file(path: Path) -> WorkflowTemplate | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("workflow template %s: %s", path.name, e)
        return None
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or path.stem).strip()[:120] or path.stem
    graph_raw = raw.get("graph") if isinstance(raw.get("graph"), dict) else raw
    if not isinstance(graph_raw, dict):
        return None
    return WorkflowTemplate(name=name, graph=_sanitize_graph_for_seed(graph_raw))


def demo_workflow_template_files() -> tuple[str, ...]:
    return (DEMO_WORKFLOW_TEMPLATE_FILE,)


def load_workflow_templates(
    template_files: tuple[str, ...] | None = None,
) -> list[WorkflowTemplate]:
    """Загрузить шаблоны; None — все встроенные по умолчанию."""
    files = template_files if template_files is not None else _DEFAULT_TEMPLATE_FILES
    out: list[WorkflowTemplate] = []
    for fname in files:
        path: Path | None = None
        for root in (_TEMPLATES_DIR, _BUNDLED_TEMPLATES_DIR):
            candidate = (root / fname).resolve()
            if candidate.is_file():
                path = candidate
                break
        if path is None:
            log.warning("workflow template missing: %s", fname)
            continue
        tpl = _parse_template_file(path)
        if tpl is not None:
            out.append(tpl)
    return out


def load_default_workflow_templates() -> list[WorkflowTemplate]:
    """Загрузить все встроенные шаблоны (порядок фиксирован)."""
    return load_workflow_templates(None)


def default_workflow_template_names() -> frozenset[str]:
    return frozenset(t.name for t in load_default_workflow_templates())


async def ensure_default_workflow_workspaces(
    session: AsyncSession,
    *,
    owner_id: int,
    template_files: tuple[str, ...] | None = None,
) -> list[WorkflowWorkspace]:
    """
    Создать недостающие шаблонные рабочие пространства для владельца аккаунта.
    Идемпотентно: если проект с таким именем уже есть — не дублируем.
    template_files: подмножество шаблонов; None — все по умолчанию.
    """
    templates = load_workflow_templates(template_files)
    if not templates:
        return []

    existing_names = set(
        (
            await session.scalars(
                select(WorkflowWorkspace.name).where(WorkflowWorkspace.user_id == owner_id)
            )
        ).all()
    )

    created: list[WorkflowWorkspace] = []
    now = datetime.now(timezone.utc)
    for i, tpl in enumerate(templates):
        if tpl.name in existing_names:
            continue
        row = WorkflowWorkspace(
            user_id=owner_id,
            name=tpl.name,
            graph_json=json.dumps(tpl.graph, ensure_ascii=False),
            created_at=now - timedelta(seconds=len(templates) - i),
            updated_at=now - timedelta(seconds=len(templates) - i),
        )
        session.add(row)
        created.append(row)
        existing_names.add(tpl.name)

    if created:
        await session.flush()
    return created


async def provision_full_workflow_workspaces(
    session: AsyncSession,
    *,
    owner_id: int,
) -> list[WorkflowWorkspace]:
    """
    Все встроенные шаблоны (идемпотентно).
    Вызывается при регистрации, оплате и когда демо-ограничение снято —
    недостающие проекты появятся без ручной догрузки.
    """
    return await ensure_default_workflow_workspaces(session, owner_id=owner_id, template_files=None)
