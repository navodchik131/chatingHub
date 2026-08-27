"""Motion Control wizard: dress outfit, turnaround, job handlers."""
from __future__ import annotations
import logging
from typing import Any
from urllib.parse import quote
import anyio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import StudioGeneration, User, UserStudioModel, UserStudioModelImage
from app.db.session import get_session
from app.schemas import StudioJobAcceptedOut, StudioModelBootstrapOut
from app.services.credits import ensure_can_consume_credits
from app.services.demo_generations import (
    prepare_bootstrap_image_billing,
    record_studio_image_billing,
)
from app.services.studio_generation_placeholders import reserve_studio_generation_for_job
from app.services.studio_generation_storage import (
    attach_studio_generation_wavespeed_task,
    find_studio_generation_by_job_id,
    mark_studio_generation_failed,
    studio_finish_image_generation,
    try_recover_studio_generation_from_wavespeed,
)
from app.services.studio_generation_status import StudioGenerationStatus
from app.services.studio_image_token import create_model_image_access_token
from app.services.studio_keys import (
    load_owner_studio_billing,
    studio_wavespeed_api_key,
)
from app.services.studio_motion_control import (
    MOTION_CONTROL_SHEET_ASPECT,
    MOTION_CONTROL_TURNAROUND_PROMPT,
)
from app.services.studio_motion_video import (
    extract_first_frame_jpeg,
    resolve_motion_video_uploaded,
)
from app.services.studio_openai import MAX_IMAGE_BYTES
from app.services.workspace import PERM_STUDIO_GENERATE, assert_permission, resolve_billing_user, workspace_owner_id
from app.services import studio_jobs
log = logging.getLogger(__name__)
router = APIRouter()
def _public_https_base() -> str:
    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Нужен публичный HTTPS (PUBLIC_APP_URL) для WaveSpeed.",
        )
    return pub
def _parse_int(raw: str | None, *, field: str) -> int | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(str(raw).strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Некорректный {field}") from e
def _pick_model_image(
    images: list[UserStudioModelImage],
    image_id: int | None,
    *,
    prefer_kind: str | None = None,
) -> UserStudioModelImage | None:
    if image_id is not None:
        for im in images:
            if int(im.id) == int(image_id):
                return im
        return None
    if prefer_kind:
        for im in images:
            if str(im.image_kind or "").lower() == prefer_kind:
                return im
    return images[0] if images else None
def _model_image_public_url(owner_id: int, image_id: int, pub: str) -> str:
    tok = create_model_image_access_token(user_id=owner_id, image_id=image_id)
    return f"{pub}/api/studio/public-model-image?t={quote(tok, safe='')}"
def _require_studio_subscription(user, sub_b, *, credits_balance: int, demo_generations_remaining: int) -> None:
    from app.api.studio_routes import _require_studio_subscription as _sync_require

    _sync_require(
        user, sub_b, credits_balance=credits_balance, demo_generations_remaining=demo_generations_remaining
    )
async def _accept_motion_control_job(
    session: AsyncSession,
    user: User,
    *,
    job_type: str,
    params: dict[str, Any],
    placeholder: dict[str, Any] | None = None,
    job_files: dict[str, tuple[bytes, str]] | None = None,
) -> JSONResponse:
    from app.api.studio_routes import _accept_studio_job
    return await _accept_studio_job(
        session,
        user,
        job_type=job_type,
        params=params,
        placeholder=placeholder,
        job_files=job_files,
    )
async def _preflight_image_job_cost(
    session: AsyncSession,
    user: User,
    *,
    plan: str,
    usage_kind: str,
    wave_model_id: str,
) -> None:
    """Проверяем баланс до постановки задачи в очередь."""
    billing_owner = await resolve_billing_user(session, user)
    _billing, cost, _used_demo = await prepare_bootstrap_image_billing(
        session,
        user,
        billing_owner,
        plan=plan,
        usage_kind=usage_kind,
        wave_model_id=wave_model_id,
    )
    if cost > 0:
        await ensure_can_consume_credits(session, user, cost)
@router.post(
    "/studio/motion-control/dress-outfit",
    response_model=StudioModelBootstrapOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_motion_control_dress_outfit(
    model_id: str = Form(...),
    base_image_id: str = Form(...),
    outfit_route: str = Form("video"),
    motion_video_file_id: str = Form(""),
    wave_model_id: str = Form(""),
    studio_wave_profile: str = Form("nsfw"),
    wan_edit_tier: str = Form("standard"),
    output_aspect: str = Form("9:16"),
    clothing_image: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioModelBootstrapOut | JSONResponse:
    """Одеть выбранное фото модели: из реф-видео (первый кадр) или своей одежды."""
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    _public_https_base()
    sub_b, _, _, plan, credits, demo = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=credits, demo_generations_remaining=demo)
    mid = _parse_int(model_id, field="model_id")
    base_id = _parse_int(base_image_id, field="base_image_id")
    if mid is None or base_id is None:
        raise HTTPException(status_code=400, detail="Укажите model_id и base_image_id")
    route = (outfit_route or "video").strip().lower()
    mv_id = (motion_video_file_id or "").strip()
    if route == "video" and not mv_id:
        raise HTTPException(status_code=400, detail="Загрузите референс-видео для одежды с видео.")
    clothing_bytes: bytes | None = None
    clothing_mime = "image/jpeg"
    if route == "own":
        if clothing_image is None or not (clothing_image.filename or "").strip():
            raise HTTPException(status_code=400, detail="Загрузите фото одежды.")
        clothing_bytes = await clothing_image.read()
        if len(clothing_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Файл одежды слишком большой.")
        if not clothing_bytes:
            raise HTTPException(status_code=400, detail="Пустой файл одежды.")
        ct = (clothing_image.content_type or "").strip().lower()
        if ct.startswith("image/"):
            clothing_mime = ct.split(";")[0]
    wave_profile = (studio_wave_profile or "nsfw").strip().lower()
    wave_model = (wave_model_id or "").strip().lower()
    if not wave_model:
        wave_model = "wan-2.7" if wave_profile == "nsfw" else "nano-banana-pro"
    await _preflight_image_job_cost(
        session,
        user,
        plan=plan,
        usage_kind="studio_motion_control_dress",
        wave_model_id=wave_model,
    )
    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.id == mid, UserStudioModel.user_id == oid)
        .options(selectinload(UserStudioModel.images))
    )
    sm = (await session.execute(stmt)).scalar_one_or_none()
    if not sm:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    imgs = list(sm.images or [])
    body_im = _pick_model_image(imgs, base_id)
    face_im = _pick_model_image(imgs, None, prefer_kind="face")
    if body_im is None:
        raise HTTPException(status_code=400, detail="Фото персонажа не найдено.")
    if face_im is None:
        face_im = body_im
    params: dict[str, Any] = {
        "model_id": mid,
        "base_image_id": base_id,
        "face_image_id": int(face_im.id),
        "outfit_route": route,
        "motion_video_file_id": mv_id,
        "wave_model_id": wave_model,
        "studio_wave_profile": wave_profile,
        "wan_edit_tier": (wan_edit_tier or "standard").strip().lower(),
        "output_aspect": (output_aspect or "9:16").strip(),
    }
    job_files: dict[str, tuple[bytes, str]] | None = None
    if clothing_bytes:
        job_files = {"clothing": (clothing_bytes, clothing_mime)}
    return await _accept_motion_control_job(
        session,
        user,
        job_type="motion_control_dress",
        params=params,
        placeholder={
            "studio_model_id": mid,
            "output_aspect": output_aspect,
            "content_type": "image/jpeg",
            "prompt_excerpt": "Motion Control · образ",
        },
        job_files=job_files,
    )
@router.post(
    "/studio/motion-control/turnaround",
    response_model=StudioModelBootstrapOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_motion_control_turnaround(
    model_id: str = Form(...),
    outfit_generation_id: str = Form(...),
    face_image_id: str = Form(...),
    wave_model_id: str = Form("gpt-image-2"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioModelBootstrapOut | JSONResponse:
    """Развёртка: образ + лицо (face tag) → character sheet."""
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    _public_https_base()
    sub_b, _, _, plan, credits, demo = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=credits, demo_generations_remaining=demo)
    mid = _parse_int(model_id, field="model_id")
    outfit_gid = _parse_int(outfit_generation_id, field="outfit_generation_id")
    face_id = _parse_int(face_image_id, field="face_image_id")
    if mid is None or outfit_gid is None or face_id is None:
        raise HTTPException(status_code=400, detail="Укажите model_id, outfit и face image.")
    outfit_row = await session.get(StudioGeneration, outfit_gid)
    if not outfit_row or outfit_row.user_id != oid:
        raise HTTPException(status_code=404, detail="Образ (outfit) не найден")
    wave_model = (wave_model_id or "gpt-image-2").strip().lower()
    await _preflight_image_job_cost(
        session,
        user,
        plan=plan,
        usage_kind="studio_motion_control_turnaround",
        wave_model_id=wave_model,
    )
    params = {
        "model_id": mid,
        "outfit_generation_id": outfit_gid,
        "face_image_id": face_id,
        "wave_model_id": wave_model,
        "prompt": MOTION_CONTROL_TURNAROUND_PROMPT,
        "output_aspect": MOTION_CONTROL_SHEET_ASPECT,
    }
    return await _accept_motion_control_job(
        session,
        user,
        job_type="motion_control_turnaround",
        params=params,
        placeholder={
            "studio_model_id": mid,
            "output_aspect": MOTION_CONTROL_SHEET_ASPECT,
            "content_type": "image/png",
            "prompt_excerpt": "Motion Control · развёртка",
        },
    )
async def execute_motion_control_dress(
    session: AsyncSession,
    job: studio_jobs.StudioJob,
    user: User,
) -> dict[str, Any]:
    """Anchor wardrobe prep: body ref + outfit donor (video frame или upload)."""
    from app.api.studio_routes import _public_app_base, _studio_archive_image_url
    from app.services.studio_anchor_runner import _dress_body_via_wavespeed
    from app.services.workspace_model_access import require_studio_model_access
    p = studio_jobs.job_params(job)
    oid = workspace_owner_id(user)
    mid = int(p["model_id"])
    pub = _public_https_base()
    sub_b, _, ws_row, plan, _credits, _demo = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits, demo_generations_remaining=_demo)
    ws_key = studio_wavespeed_api_key(
        plan=plan, ws_row=ws_row, owner_subscription=sub_b, demo_generations_remaining=_demo
    )
    sm = await require_studio_model_access(session, user, mid, load_images=True)
    imgs = list(sm.images or [])
    body_im = _pick_model_image(imgs, int(p["base_image_id"]))
    if body_im is None:
        raise RuntimeError("Фото персонажа для образа не найдено")
    route = str(p.get("outfit_route") or "video").strip().lower()
    scene_bytes: bytes
    scene_mime = "image/jpeg"
    if route == "own":
        if not p.get("clothing_path"):
            raise RuntimeError("Нет загруженного фото одежды")
        scene_bytes = studio_jobs.load_studio_job_file(str(p["clothing_path"]))
        scene_mime = str(p.get("clothing_mime") or "image/jpeg")
    else:
        mv_id = str(p.get("motion_video_file_id") or "").strip()
        vpath = resolve_motion_video_uploaded(oid, mv_id)
        if vpath is None:
            raise RuntimeError("Референс-видео не найдено")
        scene_bytes = await anyio.to_thread.run_sync(
            lambda vp=vpath: extract_first_frame_jpeg(vp)
        )
        if len(scene_bytes) < 64:
            raise RuntimeError("Не удалось извлечь кадр из видео")
    from app.services.studio_pose_reference import save_pose_reference_bytes
    from app.services.studio_image_token import create_pose_reference_access_token
    scene_id = save_pose_reference_bytes(owner_id=oid, raw=scene_bytes, mime=scene_mime)
    body_url = _model_image_public_url(oid, int(body_im.id), pub)
    scene_tok = create_pose_reference_access_token(user_id=oid, ref_id=scene_id)
    scene_url = f"{pub}/api/studio/public-pose-reference?t={quote(scene_tok, safe='')}"
    wave_profile = str(p.get("studio_wave_profile") or "nsfw")
    wan_tier = str(p.get("wan_edit_tier") or "standard")
    wave_model = str(p.get("wave_model_id") or "").strip().lower()
    if not wave_model:
        wave_model = "wan-2.7" if wave_profile == "nsfw" else "nano-banana-pro"
    aspect = str(p.get("output_aspect") or "9:16")
    gen_row = await find_studio_generation_by_job_id(session, job.id)
    try:
        dressed = await _dress_body_via_wavespeed(
            api_key=ws_key,
            body_url=body_url,
            scene_url=scene_url,
            wave_profile=wave_profile,
            wan_edit_tier=wan_tier,
            wave_model_id=wave_model,
            aspect_ratio=aspect,
        )
    except RuntimeError as e:
        if gen_row is not None:
            await mark_studio_generation_failed(session, gen_row, message=str(e), step="dress")
            await session.commit()
        raise
    billing_owner = await resolve_billing_user(session, user)
    billing, cost, used_demo = await prepare_bootstrap_image_billing(
        session,
        user,
        billing_owner,
        plan=plan,
        usage_kind="studio_motion_control_dress",
        wave_model_id=wave_model,
        lock_account=True,
    )
    if used_demo and gen_row is not None:
        gen_row.is_demo = True
        session.add(gen_row)
        await session.flush()
    arch = _public_app_base(None)
    _, preview_url = await studio_finish_image_generation(
        session,
        gen_row=gen_row,
        owner_id=oid,
        studio_model_id=mid,
        output_aspect=aspect,
        refined_prompt="Motion Control dress",
        uploaded_bytes=dressed,
        uploaded_content_type="image/jpeg",
    )
    gid = gen_row.id if gen_row is not None else None
    out_url = _studio_archive_image_url(oid, gid, arch) if gid else preview_url
    await record_studio_image_billing(
        session,
        user,
        billing,
        usage_kind="studio_motion_control_dress",
        cost=cost,
        used_demo=used_demo,
        meta={"model_id": mid, "outfit_route": route, "generation_id": gid},
    )
    await session.commit()
    return {
        "generation_id": gid,
        "generated_image_url": out_url,
        "status": "ready",
    }
async def execute_motion_control_turnaround(
    session: AsyncSession,
    job: studio_jobs.StudioJob,
    user: User,
) -> dict[str, Any]:
    from app.api.studio_routes import _public_app_base, _studio_archive_image_url
    from app.services.studio_seedance_t2v import generation_still_public_url
    from app.services.studio_image_token import create_generation_image_access_token
    from app.services.wavespeed_client import gpt_image_2_edit_image_url
    from app.services.workspace_model_access import require_studio_model_access
    p = studio_jobs.job_params(job)
    oid = workspace_owner_id(user)
    mid = int(p["model_id"])
    pub = _public_https_base()
    sub_b, _, ws_row, plan, _credits, _demo = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits, demo_generations_remaining=_demo)
    ws_key = studio_wavespeed_api_key(
        plan=plan, ws_row=ws_row, owner_subscription=sub_b, demo_generations_remaining=_demo
    )
    await require_studio_model_access(session, user, mid, load_images=True)
    outfit_gid = int(p["outfit_generation_id"])
    face_id = int(p["face_image_id"])
    outfit_url = generation_still_public_url(
        owner_id=oid,
        generation_id=outfit_gid,
        public_app_base=pub,
        token_factory=create_generation_image_access_token,
    )
    face_url = _model_image_public_url(oid, face_id, pub)
    if not outfit_url:
        raise RuntimeError("URL образа недоступен")
    prompt = str(p.get("prompt") or MOTION_CONTROL_TURNAROUND_PROMPT)
    aspect = str(p.get("output_aspect") or MOTION_CONTROL_SHEET_ASPECT)
    wave_model = str(p.get("wave_model_id") or "gpt-image-2").strip().lower()
    gen_row = await find_studio_generation_by_job_id(session, job.id)
    async def _on_task(task_id: str) -> None:
        if gen_row is not None:
            await attach_studio_generation_wavespeed_task(session, gen_row, task_id=task_id)
            await session.commit()
    try:
        ws_res = await gpt_image_2_edit_image_url(
            api_key=ws_key,
            image_urls=[face_url, outfit_url],
            prompt=prompt,
            aspect_ratio=aspect,
            resolution="1k",
            quality="medium",
            output_format="png",
            max_polls=300,
            poll_interval=2.5,
            on_task_submitted=_on_task,
        )
    except RuntimeError as e:
        if gen_row is not None and (gen_row.wavespeed_task_id or "").strip():
            if await try_recover_studio_generation_from_wavespeed(
                session, gen_row, api_key=ws_key, refined_prompt=prompt
            ):
                await session.commit()
                arch_base = _public_app_base(None)
                out_url = _studio_archive_image_url(oid, gen_row.id, arch_base)
                billing_owner = await resolve_billing_user(session, user)
                billing, cost, used_demo = await prepare_bootstrap_image_billing(
                    session,
                    user,
                    billing_owner,
                    plan=plan,
                    usage_kind="studio_motion_control_turnaround",
                    wave_model_id=wave_model,
                    lock_account=True,
                )
                await record_studio_image_billing(
                    session,
                    user,
                    billing,
                    usage_kind="studio_motion_control_turnaround",
                    cost=cost,
                    used_demo=used_demo,
                    meta={"model_id": mid, "outfit_generation_id": outfit_gid},
                )
                await session.commit()
                return {
                    "generation_id": gen_row.id,
                    "generated_image_url": out_url,
                    "status": "ready",
                }
        if gen_row is not None:
            await mark_studio_generation_failed(session, gen_row, message=str(e), step="turnaround")
            await session.commit()
        raise
    billing_owner = await resolve_billing_user(session, user)
    billing, cost, used_demo = await prepare_bootstrap_image_billing(
        session,
        user,
        billing_owner,
        plan=plan,
        usage_kind="studio_motion_control_turnaround",
        wave_model_id=wave_model,
        lock_account=True,
    )
    if used_demo and gen_row is not None:
        gen_row.is_demo = True
        session.add(gen_row)
        await session.flush()
    arch_base = _public_app_base(None)
    _, preview_url = await studio_finish_image_generation(
        session,
        gen_row=gen_row,
        owner_id=oid,
        studio_model_id=mid,
        output_aspect=aspect,
        refined_prompt=prompt,
        source_url=ws_res.url,
        wavespeed_task_id=ws_res.task_id,
    )
    gid = gen_row.id if gen_row is not None else None
    out_url = _studio_archive_image_url(oid, gid, arch_base) if gid else preview_url
    if gen_row is not None and gen_row.status != StudioGenerationStatus.READY:
        out_url = (gen_row.source_url or "").strip() or out_url
    await record_studio_image_billing(
        session,
        user,
        billing,
        usage_kind="studio_motion_control_turnaround",
        cost=cost,
        used_demo=used_demo,
        meta={"model_id": mid, "outfit_generation_id": outfit_gid, "generation_id": gid},
    )
    await session.commit()
    return {
        "generation_id": gid,
        "generated_image_url": out_url,
        "status": "ready",
    }
