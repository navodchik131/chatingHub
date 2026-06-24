"""Workflow editor API — граф → studio job, рабочие пространства."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import User, WorkflowWorkspace
from app.db.session import get_session
from app.schemas import StudioJobAcceptedOut
from app.services.studio_aspect import ASPECT_PRESETS, aspect_presets_public
from app.services.studio_workflow_refs import load_workflow_reference, save_workflow_reference
from app.services.studio_workflow_resolver import (
    WORKFLOW_WAVE_MODELS,
    WorkflowResolutionError,
    resolve_workflow_generation_plan,
)
from app.services.workspace import (
    PERM_STUDIO_GENERATE,
    assert_permission,
    workspace_owner_id,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["studio-workflow"])

_ALLOWED_REF_MIME = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)

_NANO_BANANA_ASPECTS = frozenset(
    {"1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
)
_WAN_ASPECTS = frozenset(ASPECT_PRESETS.keys())
_GPT_IMAGE_ASPECTS = _NANO_BANANA_ASPECTS

_MODEL_UI: dict[str, dict[str, Any]] = {
    "nano-banana-2": {
        "label": "Nano Banana 2",
        "nsfw_only": False,
        "aspect_keys": sorted(_NANO_BANANA_ASPECTS),
    },
    "nano-banana-pro": {
        "label": "Nano Banana Pro",
        "nsfw_only": False,
        "aspect_keys": sorted(_NANO_BANANA_ASPECTS),
    },
    "gpt-image-2": {
        "label": "GPT Image 2",
        "nsfw_only": False,
        "aspect_keys": sorted(_GPT_IMAGE_ASPECTS),
    },
    "wan-2.7": {
        "label": "Wan 2.7",
        "nsfw_only": True,
        "aspect_keys": sorted(_WAN_ASPECTS),
    },
}


class WorkflowWorkspaceCreateIn(BaseModel):
    name: str = Field(default="Новый проект", min_length=1, max_length=120)


class WorkflowWorkspaceUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    graph: dict[str, Any] | None = None


class WorkflowWorkspaceOut(BaseModel):
    id: int
    name: str
    graph: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkflowWorkspaceListItem(BaseModel):
    id: int
    name: str
    updated_at: datetime


def _empty_graph() -> dict[str, list]:
    return {"nodes": [], "edges": []}


def _parse_graph_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return _empty_graph()
    if not isinstance(parsed, dict):
        return _empty_graph()
    nodes = parsed.get("nodes")
    edges = parsed.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return _empty_graph()
    return {"nodes": nodes, "edges": edges}


def _workspace_out(row: WorkflowWorkspace) -> WorkflowWorkspaceOut:
    return WorkflowWorkspaceOut(
        id=row.id,
        name=row.name,
        graph=_parse_graph_json(row.graph_json),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _get_workspace_or_404(
    session: AsyncSession, *, owner_id: int, workspace_id: int
) -> WorkflowWorkspace:
    row = await session.scalar(
        select(WorkflowWorkspace).where(
            WorkflowWorkspace.id == workspace_id,
            WorkflowWorkspace.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="Рабочее пространство не найдено")
    return row


@router.get("/studio/workflow/model-options")
async def api_workflow_model_options() -> dict:
    """Модели генерации и поддерживаемые форматы кадра для UI workflow."""
    aspect_labels = {a["key"]: a for a in aspect_presets_public()}
    models: list[dict[str, Any]] = []
    for model_id in sorted(WORKFLOW_WAVE_MODELS):
        meta = _MODEL_UI.get(model_id, {})
        aspect_keys = meta.get("aspect_keys") or sorted(_WAN_ASPECTS)
        aspects: list[dict[str, str]] = []
        for key in aspect_keys:
            preset = aspect_labels.get(key)
            if preset:
                aspects.append(preset)
            elif key in ASPECT_PRESETS:
                w, h = ASPECT_PRESETS[key]
                aspects.append({"key": key, "label": key, "size": f"{w}x{h}"})
        models.append(
            {
                "id": model_id,
                "label": meta.get("label") or model_id,
                "nsfw_only": bool(meta.get("nsfw_only")),
                "aspects": aspects,
            }
        )
    return {"models": models}


@router.get("/studio/workflow/workspaces", response_model=list[WorkflowWorkspaceListItem])
async def api_workflow_list_workspaces(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[WorkflowWorkspaceListItem]:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    rows = (
        await session.scalars(
            select(WorkflowWorkspace)
            .where(WorkflowWorkspace.user_id == oid)
            .order_by(WorkflowWorkspace.updated_at.desc())
        )
    ).all()
    return [
        WorkflowWorkspaceListItem(id=r.id, name=r.name, updated_at=r.updated_at)
        for r in rows
    ]


@router.post("/studio/workflow/workspaces", response_model=WorkflowWorkspaceOut)
async def api_workflow_create_workspace(
    body: WorkflowWorkspaceCreateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> WorkflowWorkspaceOut:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    name = (body.name or "Новый проект").strip()[:120] or "Новый проект"
    row = WorkflowWorkspace(
        user_id=oid,
        name=name,
        graph_json=json.dumps(_empty_graph(), ensure_ascii=False),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _workspace_out(row)


@router.get("/studio/workflow/workspaces/{workspace_id}", response_model=WorkflowWorkspaceOut)
async def api_workflow_get_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> WorkflowWorkspaceOut:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    row = await _get_workspace_or_404(session, owner_id=oid, workspace_id=workspace_id)
    return _workspace_out(row)


@router.put("/studio/workflow/workspaces/{workspace_id}", response_model=WorkflowWorkspaceOut)
async def api_workflow_update_workspace(
    workspace_id: int,
    body: WorkflowWorkspaceUpdateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> WorkflowWorkspaceOut:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    row = await _get_workspace_or_404(session, owner_id=oid, workspace_id=workspace_id)

    if body.name is not None:
        row.name = body.name.strip()[:120] or row.name
    if body.graph is not None:
        nodes = body.graph.get("nodes")
        edges = body.graph.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            raise HTTPException(status_code=400, detail="graph.nodes и graph.edges обязательны")
        row.graph_json = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    return _workspace_out(row)


@router.delete("/studio/workflow/workspaces/{workspace_id}")
async def api_workflow_delete_workspace(
    workspace_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    row = await _get_workspace_or_404(session, owner_id=oid, workspace_id=workspace_id)
    await session.delete(row)
    await session.commit()
    return {"status": "deleted"}


@router.post("/studio/workflow/reference")
async def api_workflow_upload_reference(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    if not (file.filename or "").strip():
        raise HTTPException(status_code=400, detail="Пустой файл")
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    mime = (file.content_type or "image/jpeg").split(";")[0].strip().lower()
    if mime not in _ALLOWED_REF_MIME:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются PNG, JPEG, WEBP, GIF",
        )
    try:
        ref_id = save_workflow_reference(oid, raw, content_type=mime)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "ref_id": ref_id,
        "file_name": (file.filename or "reference").strip()[:200],
    }


@router.get("/studio/workflow/reference/{ref_id}")
async def api_workflow_get_reference(
    ref_id: str,
    user: User = Depends(get_current_user),
) -> Response:
    """Превью загруженного референса workflow (для UI после перезагрузки страницы)."""
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    try:
        raw, mime = load_workflow_reference(oid, ref_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Референс не найден") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return Response(content=raw, media_type=mime)


@router.post(
    "/studio/workflow/execute",
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_workflow_execute(
    graph: str = Form(...),
    target_node_id: str = Form(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> JSONResponse:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)

    try:
        payload = json.loads(graph)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Некорректный JSON графа") from e
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Граф должен быть объектом")

    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise HTTPException(status_code=400, detail="nodes и edges обязательны")

    try:
        plan = resolve_workflow_generation_plan(
            target_node_id=target_node_id,
            nodes=nodes,
            edges=edges,
        )
    except WorkflowResolutionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    loaded_refs: list[tuple[bytes, str, Any]] = []

    for ref_item in plan.references:
        try:
            ref_bytes, ref_mime = load_workflow_reference(oid, ref_item.ref_id)
        except FileNotFoundError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Референс «{ref_item.file_name or ref_item.ref_id}» не найден",
            ) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        loaded_refs.append((ref_bytes, ref_mime, ref_item))

    from app.api.studio_routes import _accept_studio_refine_job_from_workflow

    try:
        return await _accept_studio_refine_job_from_workflow(
            session,
            user,
            plan=plan,
            reference_images=loaded_refs,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("workflow execute failed")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось запустить генерацию: {e}",
        ) from e
