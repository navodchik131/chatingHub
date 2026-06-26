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
    resolve_workflow_turnaround_plan,
    resolve_workflow_video_plan,
    resolve_workflow_video_prompt_compose_plan,
)
from app.services.studio_workflow_defaults import (
    DEMO_WORKFLOW_NAME,
    provision_full_workflow_workspaces,
)
from app.services.workflow_entitlements import (
    assert_workflow_full_access,
    assert_workflow_workspace_allowed,
    is_workflow_demo_limited,
)
from app.services.workspace import (
    PERM_STUDIO_GENERATE,
    assert_permission,
    resolve_billing_user,
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


async def _workflow_owner_billing(session: AsyncSession, user: User):
    billing = await resolve_billing_user(session, user)
    return billing.subscription, billing.credit_account


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
    return {"models": models, "video": _workflow_video_options()}


def _workflow_video_options() -> dict[str, Any]:
    from app.services.studio_motion_pricing import motion_video_pricing_public

    return motion_video_pricing_public()


@router.get("/studio/workflow/workspaces", response_model=list[WorkflowWorkspaceListItem])
async def api_workflow_list_workspaces(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[WorkflowWorkspaceListItem]:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    sub, cr = await _workflow_owner_billing(session, user)
    demo_limited = is_workflow_demo_limited(sub, cr)
    await provision_full_workflow_workspaces(session, owner_id=oid)
    await session.commit()
    rows = (
        await session.scalars(
            select(WorkflowWorkspace)
            .where(WorkflowWorkspace.user_id == oid)
            .order_by(WorkflowWorkspace.updated_at.desc())
        )
    ).all()
    if demo_limited:
        rows = [r for r in rows if (r.name or "").strip() == DEMO_WORKFLOW_NAME]
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
    sub, cr = await _workflow_owner_billing(session, user)
    assert_workflow_full_access(sub, cr)
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
    sub, cr = await _workflow_owner_billing(session, user)
    row = await _get_workspace_or_404(session, owner_id=oid, workspace_id=workspace_id)
    assert_workflow_workspace_allowed(row, sub, cr)
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
    sub, cr = await _workflow_owner_billing(session, user)
    row = await _get_workspace_or_404(session, owner_id=oid, workspace_id=workspace_id)
    assert_workflow_workspace_allowed(row, sub, cr)

    if body.name is not None:
        if is_workflow_demo_limited(sub, cr):
            raise HTTPException(status_code=403, detail="Переименование недоступно на демо-тарифе.")
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
    sub, cr = await _workflow_owner_billing(session, user)
    assert_workflow_full_access(sub, cr)
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
    workspace_id: int | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> JSONResponse:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    sub, cr = await _workflow_owner_billing(session, user)
    if is_workflow_demo_limited(sub, cr):
        if workspace_id is None:
            raise HTTPException(
                status_code=400,
                detail="Укажите workspace_id для генерации на демо-тарифе.",
            )
        ws_row = await _get_workspace_or_404(session, owner_id=oid, workspace_id=workspace_id)
        assert_workflow_workspace_allowed(ws_row, sub, cr)

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
        target = next(
            (n for n in nodes if str(n.get("id") or "").strip() == (target_node_id or "").strip()),
            None,
        )
        target_type = str(target.get("type") or "") if target else ""

        if target_type in ("imageGeneration", "firstFrameGeneration"):
            plan = resolve_workflow_generation_plan(
                target_node_id=target_node_id,
                nodes=nodes,
                edges=edges,
            )
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

            if target_type == "firstFrameGeneration" and (
                plan.motion_video_file_id or loaded_refs
            ):
                return await _accept_workflow_motion_first_frame_job(
                    session,
                    user,
                    plan=plan,
                    reference_images=loaded_refs,
                )

            from app.api.studio_routes import _accept_studio_refine_job_from_workflow

            return await _accept_studio_refine_job_from_workflow(
                session,
                user,
                plan=plan,
                reference_images=loaded_refs,
                workflow_first_frame=(target_type == "firstFrameGeneration"),
            )

        if target_type == "turnaroundSheet":
            plan = resolve_workflow_turnaround_plan(
                target_node_id=target_node_id,
                nodes=nodes,
                edges=edges,
            )
            return await _accept_workflow_turnaround_job(session, user, plan=plan)

        if target_type == "videoGeneration":
            plan = resolve_workflow_video_plan(
                target_node_id=target_node_id,
                nodes=nodes,
                edges=edges,
            )
            return await _accept_workflow_video_job(session, user, plan=plan)

        if target_type == "videoPromptCompose":
            plan = resolve_workflow_video_prompt_compose_plan(
                target_node_id=target_node_id,
                nodes=nodes,
                edges=edges,
            )
            return await _accept_workflow_video_prompt_compose_job(session, user, plan=plan)

        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемый тип ноды для запуска",
        )
    except WorkflowResolutionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        log.exception("workflow execute failed")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось запустить генерацию: {e}",
        ) from e


async def _accept_workflow_motion_first_frame_job(
    session: AsyncSession,
    user: User,
    *,
    plan,
    reference_images: list[tuple[bytes, str, Any]],
) -> JSONResponse:
    from app.api.studio_routes import grok_scene_compose_configured, normalize_exif_camera
    from app.services.studio_aspect import normalize_aspect_key
    from app.services.studio_generation_placeholders import reserve_studio_generation_for_job
    from app.services.studio_jobs import create_studio_job, schedule_studio_job, update_studio_job_params
    from app.services import studio_jobs

    if not grok_scene_compose_configured():
        raise HTTPException(
            status_code=503,
            detail="Grok не настроен: задайте GROK_API_KEY в .env на сервере.",
        )
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)

    if plan.model_id is None:
        raise HTTPException(
            status_code=400,
            detail="Для первого кадра из видео или референса выберите модель в ноде «Модель»",
        )

    for ref_bytes, _ref_mime, ref_item in reference_images:
        from app.api.studio_routes import MAX_IMAGE_BYTES

        if len(ref_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Референс «{ref_item.file_name or ref_item.ref_id}» слишком большой "
                    f"(макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)"
                ),
            )

    try:
        aspect_reserve = normalize_aspect_key(plan.output_aspect)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    motion_id = str(plan.motion_video_file_id or "").strip()
    default_motion_notes = (
        "Движение как в реф-видео. Сохранить сцену, одежду и свет с первого кадра."
    )
    description = (plan.description or "").strip()
    if motion_id and not description:
        description = default_motion_notes

    params: dict[str, Any] = {
        "model_id": str(plan.model_id),
        "description": description,
        "output_aspect": plan.output_aspect,
        "wan_edit_tier": plan.wan_edit_tier,
        "studio_wave_profile": plan.studio_wave_profile,
        "auto_motion_prompt": "1" if motion_id else "0",
        "lock_model_hairstyle": "1",
        "use_still_as_final": "0",
        "exif_camera": normalize_exif_camera(plan.exif_camera),
        "workflow_source": "1",
        "workflow_first_frame": "1",
    }
    if motion_id:
        params["motion_video_file_id"] = motion_id

    job = await create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="motion_first_frame",
        params=params,
    )

    if reference_images:
        ref_bytes, ref_mime, _ref_item = reference_images[0]
        params["first_frame_path"] = studio_jobs.save_studio_job_file(
            job.id, "first_frame.bin", ref_bytes
        )
        params["first_frame_mime"] = (ref_mime or "image/jpeg").split(";")[0].strip()

    await update_studio_job_params(session, job, params)

    gen_row = await reserve_studio_generation_for_job(
        session,
        owner_id=oid,
        studio_job_id=job.id,
        studio_model_id=plan.model_id,
        output_aspect=aspect_reserve,
        content_type="image/png",
        prompt_excerpt=(plan.description or "")[:2000] or None,
        exif_camera=normalize_exif_camera(plan.exif_camera),
    )
    params["placeholder_generation_id"] = gen_row.id
    await update_studio_job_params(session, job, params)

    schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type="motion_first_frame",
            generation_id=gen_row.id,
        ).model_dump(),
    )


async def _accept_workflow_turnaround_job(
    session: AsyncSession,
    user: User,
    *,
    plan,
) -> JSONResponse:
    from app.api.studio_routes import _require_public_https_for_wavespeed
    from app.services.studio_generation_placeholders import reserve_studio_generation_for_job
    from app.services.studio_jobs import create_studio_job, schedule_studio_job, update_studio_job_params
    from app.services.studio_model_bootstrap import (
        MODEL_SHEET_ASPECT_KEY,
        resolve_workflow_model_sheet_prompt,
    )

    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    _require_public_https_for_wavespeed()

    resolved_prompt = resolve_workflow_model_sheet_prompt(plan.prompt_extra)
    dedupe_key = f"wf-sheet:gen:{plan.source_generation_id}"

    from app.services import studio_jobs

    existing = await studio_jobs.find_recent_inflight_studio_job(
        session,
        owner_id=oid,
        job_type="model_bootstrap_sheet",
        dedupe_key=dedupe_key,
    )
    if existing is not None:
        ex_params = studio_jobs.job_params(existing)
        return JSONResponse(
            status_code=202,
            content=StudioJobAcceptedOut(
                job_id=existing.id,
                job_type="model_bootstrap_sheet",
                generation_id=ex_params.get("placeholder_generation_id"),
                message="Такая развёртка уже выполняется — дождитесь завершения.",
            ).model_dump(),
        )

    params: dict[str, Any] = {
        "output_aspect": MODEL_SHEET_ASPECT_KEY,
        "prompt": resolved_prompt,
        "model_id": plan.model_id,
        "source_generation_id": plan.source_generation_id,
        "dedupe_key": dedupe_key,
        "workflow_turnaround": "1",
        "prompt_extra": plan.prompt_extra or "",
    }
    job = await create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="model_bootstrap_sheet",
        params=params,
    )
    gen_row = await reserve_studio_generation_for_job(
        session,
        owner_id=oid,
        studio_job_id=job.id,
        studio_model_id=plan.model_id,
        output_aspect=MODEL_SHEET_ASPECT_KEY,
        content_type="image/png",
        prompt_excerpt=resolved_prompt[:2000],
    )
    params["placeholder_generation_id"] = gen_row.id
    await update_studio_job_params(session, job, params)
    schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type="model_bootstrap_sheet",
            generation_id=gen_row.id,
        ).model_dump(),
    )


async def _accept_workflow_video_job(
    session: AsyncSession,
    user: User,
    *,
    plan,
) -> JSONResponse:
    from app.api.studio_routes import _accept_studio_job, _public_https_base_runtime
    from app.db.models import StudioGeneration
    from app.services.studio_generation_storage import generation_has_archive_file
    from app.services.studio_seedance_t2v import generation_still_public_url
    from app.services.studio_aspect import normalize_aspect_key
    from app.services.studio_image_token import create_generation_image_access_token
    from app.services.studio_motion_pricing import (
        grok_imagine_i2v_credit_cost,
        grok_imagine_i2v_duration_seconds,
        motion_video_credit_cost,
        motion_video_duration_seconds,
        normalize_grok_imagine_i2v_resolution,
        normalize_seedance_t2v_resolution,
        normalize_seedance_t2v_variant,
        normalize_workflow_video_provider,
    )
    from app.services.studio_motion_video import resolve_motion_video_file
    from app.services.credits import ensure_can_consume_credits
    from app.services.studio_keys import (
        apply_studio_credit_cost,
        load_owner_studio_billing,
        studio_wavespeed_api_key,
    )

    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    pub = _public_https_base_runtime()
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Нужен публичный HTTPS (PUBLIC_APP_URL) для WaveSpeed.",
        )

    sub_b, _llm, ws_row, billing_plan, credits, demo = await load_owner_studio_billing(session, oid)
    from app.api.studio_routes import _require_studio_subscription

    _require_studio_subscription(user, sub_b, credits_balance=credits, demo_generations_remaining=demo)
    try:
        studio_wavespeed_api_key(
            plan=billing_plan, ws_row=ws_row, owner_subscription=sub_b, demo_generations_remaining=demo
        )
    except HTTPException:
        raise

    video_provider = normalize_workflow_video_provider(plan.video_provider)

    if (
        video_provider != "grok_imagine_i2v"
        and plan.motion_video_file_id
        and resolve_motion_video_file(oid, plan.motion_video_file_id) is None
    ):
        raise HTTPException(status_code=404, detail="Motion-видео не найдено. Загрузите снова.")

    ff_row = await session.get(StudioGeneration, plan.first_frame_generation_id)
    if not ff_row or ff_row.user_id != oid:
        raise HTTPException(status_code=404, detail="Первый кадр не найден")
    if not generation_has_archive_file(ff_row):
        raise HTTPException(status_code=400, detail="Первый кадр ещё не сохранён на сервере.")

    sheet_row = None
    if video_provider != "grok_imagine_i2v" and plan.sheet_generation_id is not None:
        sheet_row = await session.get(StudioGeneration, plan.sheet_generation_id)
        if not sheet_row or sheet_row.user_id != oid:
            raise HTTPException(status_code=404, detail="Развёртка не найдена")
        if not generation_has_archive_file(sheet_row):
            raise HTTPException(status_code=400, detail="Развёртка ещё не сохранена на сервере.")

    mid = plan.model_id
    if mid is None:
        mid = ff_row.studio_model_id or (sheet_row.studio_model_id if sheet_row else None)
    if mid is None:
        raise HTTPException(
            status_code=400,
            detail="Подключите ноду «Модель» или укажите модель при генерации первого кадра.",
        )

    try:
        aspect_key = normalize_aspect_key(plan.output_aspect)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if video_provider == "grok_imagine_i2v":
        ds_effective = grok_imagine_i2v_duration_seconds(plan.duration_seconds)
        video_res = normalize_grok_imagine_i2v_resolution(plan.video_resolution)
        motion_cost = grok_imagine_i2v_credit_cost(ds_effective, resolution=video_res)
    else:
        ds_effective = motion_video_duration_seconds(plan.duration_seconds)
        seedance_v = normalize_seedance_t2v_variant(plan.seedance_variant)
        video_res = normalize_seedance_t2v_resolution(plan.video_resolution)
        has_motion_ref = bool(str(plan.motion_video_file_id or "").strip())
        motion_cost = motion_video_credit_cost(
            ds_effective,
            variant=seedance_v,
            resolution=video_res,
            has_motion_reference_video=has_motion_ref,
        )
    seedance_v = normalize_seedance_t2v_variant(plan.seedance_variant)
    motion_cost_billed = apply_studio_credit_cost(billing_plan, motion_cost)
    await ensure_can_consume_credits(session, user, motion_cost_billed)

    preview_url = generation_still_public_url(
        owner_id=oid,
        generation_id=plan.first_frame_generation_id,
        public_app_base=pub,
        token_factory=create_generation_image_access_token,
    )

    return await _accept_studio_job(
        session,
        user,
        job_type="motion_render_video",
        params={
            "model_id": mid,
            "prompt": plan.prompt.strip(),
            "output_aspect": aspect_key,
            "motion_video_file_id": plan.motion_video_file_id,
            "first_frame_generation_id": plan.first_frame_generation_id,
            "sheet_generation_id": plan.sheet_generation_id,
            "motion_timeline": "",
            "outfit_generation_id": None,
            "negative_prompt": plan.negative_prompt,
            "generate_audio": "1" if plan.generate_audio else "0",
            "duration_seconds": str(ds_effective),
            "seedance_variant": seedance_v,
            "video_resolution": video_res,
            "auto_motion_prompt": "1" if plan.auto_motion_prompt else "0",
            "remove_face_grid": "1",
            "workflow_source": "1",
            "video_provider": video_provider,
        },
        placeholder={
            "studio_model_id": mid,
            "output_aspect": aspect_key,
            "content_type": "video/mp4",
            "prompt_excerpt": plan.prompt.strip()[:2000] or None,
            "preview_source_url": preview_url,
        },
    )


async def _accept_workflow_video_prompt_compose_job(
    session: AsyncSession,
    user: User,
    *,
    plan,
) -> JSONResponse:
    from dataclasses import asdict

    from app.services.studio_grok_motion import grok_motion_api_configured
    from app.services.studio_jobs import create_studio_job, schedule_studio_job
    from app.services.studio_keys import load_owner_studio_billing
    from app.services.studio_motion_video import resolve_motion_video_file

    assert_permission(user, PERM_STUDIO_GENERATE)
    if not grok_motion_api_configured():
        raise HTTPException(
            status_code=503,
            detail="Grok не настроен: задайте GROK_API_KEY для генерации промпта по видео.",
        )

    oid = workspace_owner_id(user)
    sub_b, _llm, _ws, _billing_plan, credits, demo = await load_owner_studio_billing(session, oid)
    from app.api.studio_routes import _require_studio_subscription

    _require_studio_subscription(user, sub_b, credits_balance=credits, demo_generations_remaining=demo)

    if resolve_motion_video_file(oid, plan.motion_video_file_id) is None:
        raise HTTPException(status_code=404, detail="Motion-видео не найдено. Загрузите снова.")

    if plan.first_frame_generation_id is not None:
        from app.db.models import StudioGeneration
        from app.services.studio_generation_storage import generation_has_archive_file

        ff_row = await session.get(StudioGeneration, plan.first_frame_generation_id)
        if not ff_row or ff_row.user_id != oid:
            raise HTTPException(status_code=404, detail="Первый кадр не найден")
        if not generation_has_archive_file(ff_row):
            raise HTTPException(status_code=400, detail="Первый кадр ещё не сохранён на сервере.")

    if plan.sheet_generation_id is not None:
        from app.db.models import StudioGeneration
        from app.services.studio_generation_storage import generation_has_archive_file

        sheet_row = await session.get(StudioGeneration, plan.sheet_generation_id)
        if not sheet_row or sheet_row.user_id != oid:
            raise HTTPException(status_code=404, detail="Развёртка не найдена")
        if not generation_has_archive_file(sheet_row):
            raise HTTPException(status_code=400, detail="Развёртка ещё не сохранена на сервере.")

    refs_payload = [asdict(r) for r in plan.references]
    params: dict[str, Any] = {
        "model_id": str(plan.model_id),
        "motion_video_file_id": plan.motion_video_file_id,
        "first_frame_generation_id": str(plan.first_frame_generation_id or ""),
        "sheet_generation_id": str(plan.sheet_generation_id or ""),
        "user_notes": plan.user_notes,
        "references_json": json.dumps(refs_payload, ensure_ascii=False),
        "workflow_source": "1",
    }

    job = await create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="workflow_compose_video_prompt",
        params=params,
    )
    schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type="workflow_compose_video_prompt",
        ).model_dump(),
    )
