"""Workflow editor API — фаза 0: граф → studio job (model_scene)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas import StudioJobAcceptedOut
from app.services.studio_workflow_refs import load_workflow_reference, save_workflow_reference
from app.services.studio_workflow_resolver import (
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

    try:
        ref_bytes, ref_mime = load_workflow_reference(oid, plan.reference_ref_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    from app.api.studio_routes import _accept_studio_refine_job_from_workflow

    try:
        return await _accept_studio_refine_job_from_workflow(
            session,
            user,
            plan=plan,
            image_bytes=ref_bytes,
            image_mime=ref_mime,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("workflow execute failed")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось запустить генерацию: {e}",
        ) from e
