from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import shutil
import uuid
from functools import partial
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import anyio
import httpx

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.config import BACKEND_DIR, settings
from app.db.models import (
    StudioGeneration,
    StudioJob,
    StudioMotionRender,
    Subscription,
    SubscriptionStatus,
    User,
    UserStudioModel,
    UserStudioModelImage,
    WavespeedConnection,
)
from app.db.session import get_session
from app.schemas import (
    StudioCameraPresetOut,
    StudioCarouselIn,
    StudioCarouselItemOut,
    StudioCarouselOut,
    StudioGenerationOut,
    StudioGenerationsPageOut,
    StudioGenerationsPendingOut,
    StudioImportArchiveImageIn,
    StudioImportArchiveImageOut,
    StudioJobAcceptedOut,
    StudioJobStatusOut,
    StudioModelImageOut,
    StudioModelImagePatchIn,
    StudioModelProfileGenerateOut,
    StudioMotionDrivingVideoUploadOut,
    StudioMotionComposeVideoPromptOut,
    StudioMotionFirstFrameOut,
    StudioMotionRenderOut,
    StudioMotionRendersPageOut,
    StudioModelBootstrapOut,
    StudioMotionVideoOut,
    StudioRefinePromptOut,
    StudioUpscaleGenerationIn,
    StudioUpscaleGenerationOut,
    PhoneExifReferenceOut,
    UserStudioModelOut,
    UserStudioModelPatchIn,
)
from app.services.credits import ensure_can_consume_credits, record_usage
from app.services.entitlements import subscription_active
from app.services.admin_access import user_is_platform_admin
from app.services.studio_keys import (
    apply_studio_credit_cost,
    load_owner_studio_billing,
    studio_llm_credentials,
    studio_wavespeed_api_key,
)
from app.services.workspace import (
    PERM_STUDIO_GENERATE,
    PERM_STUDIO_MODELS,
    assert_permission,
    has_any_studio_access,
    workspace_owner_id,
)
from app.services.workspace_model_access import (
    apply_studio_model_id_filter,
    assert_studio_generation_access,
    member_allowed_studio_model_ids,
    require_studio_model_access,
    require_workspace_owner,
)
from app.services.crypto_secret import decrypt_secret
from app.services.studio_aspect import (
    aspect_presets_public,
    aspect_ratio_for_seedance_i2v,
    normalize_aspect_key,
    wavespeed_size_string,
)
from app.services.studio_generation_placeholders import (
    find_studio_generation_by_job_id,
    generation_is_pending_in_ui,
    reconcile_stuck_studio_generations,
    generation_media_kind,
    reserve_studio_generation_for_job,
)
from app.services.studio_generation_status import StudioGenerationStatus
from app.services.studio_generation_storage import (
    attach_studio_generation_wavespeed_task,
    begin_studio_generation_run,
    download_and_create_generation,
    generation_has_archive_file,
    mark_studio_generation_failed,
    persist_studio_generation_from_uploaded_bytes,
    safe_delete_generation_file,
    studio_finish_image_generation,
    try_recover_studio_generation_from_wavespeed,
    studio_finish_video_generation,
    user_message_when_archive_download_failed,
)
from app.services.studio_image_token import (
    create_generation_image_access_token,
    create_model_image_access_token,
    create_motion_video_access_token,
    create_pose_reference_access_token,
    decode_generation_image_access_token,
    decode_model_image_access_token,
    decode_motion_video_access_token,
    decode_pose_reference_access_token,
)
from app.services.studio_openai import (
    MAX_IMAGE_BYTES,
    describe_motion_video_first_frame_scene_openai,
    describe_motion_video_frames_openai,
    describe_reference_image_openai,
    finalize_masked_fullframe_nano_prompt,
    finalize_masked_fullframe_wan_prompt,
    finalize_nano_banana_studio_prompt,
    finalize_wavespeed_studio_prompt,
    generate_model_profile_json_from_images,
    load_image_studio_system,
    assemble_wavespeed_image_edit_prompt,
    prepare_studio_prompt_skeleton,
    prepare_studio_prompt_skeleton_for_brief,
    refine_prompt_via_openai,
    resolve_studio_prompt_brief_mode,
)
from app.services.studio_camera_presets import get_camera_preset_by_id, list_camera_presets
from app.services.studio_carousel import build_carousel_wave_prompt
from app.services.studio_grok_scene_compose import (
    grok_compose_studio_main_scene,
    grok_compose_studio_scene,
    grok_compose_studio_text_scene,
    grok_scene_compose_configured,
)
from app.services.studio_workflow_resolver import WorkflowGenerationPlan
from app.services.studio_motion_grok_pipeline import (
    assemble_motion_grok_wavespeed_prompt,
    describe_motion_still_for_ui,
    extract_video_first_frame_or_raise,
    grok_compose_motion_first_frame,
    motion_grok_timeline_from_video_path,
    motion_model_scene_wavespeed_image_urls,
)
from app.services.studio_model_images import (
    assert_studio_image_kind,
    model_images_for_wavespeed_profile,
    model_reference_photos_block,
    select_grok_compose_wavespeed_identity_images,
    select_model_scene_wavespeed_identity_images,
    select_prompt_only_wavespeed_identity_images,
    select_wan_identity_images_with_pose_ref,
    sort_model_images_for_wan_identity,
    normalize_exif_camera,
    parse_image_kinds_json,
    sort_model_images_for_studio,
    wavespeed_identity_image_legend,
)
from app.services.studio_prompt_bundle import reference_pose_is_nude_or_minimal_coverage
from app.services.studio_pose_reference import (
    resolve_pose_reference_file,
    save_pose_reference_bytes,
)
from app.services.studio_grok_motion import (
    grok_motion_studio_credentials,
    grok_two_step_motion_prompt_for_studio,
)
from app.services import studio_jobs
from app.services.studio_motion_video import (
    extract_first_frame_jpeg,
    extract_video_sample_frames_jpeg,
    resolve_motion_video_file,
    save_motion_video_bytes,
)
from app.services.studio_seedance_t2v import (
    MAX_SEEDANCE_REFERENCE_IMAGES,
    build_seedance_t2v_prompt,
    filter_model_images_for_seedance_video,
    generation_still_public_url,
    model_reference_public_urls,
    sort_model_images_for_seedance_t2v,
)
from app.services.studio_model_bootstrap import (
    MODEL_SHEET_ASPECT_KEY,
    humanize_wavespeed_provider_error,
    resolve_face_merge_prompt,
    resolve_model_sheet_prompt,
    wavespeed_image_url_for_bootstrap,
    wavespeed_url_for_bootstrap_generation,
)
from app.services.wavespeed_client import (
    gpt_image_2_edit_image_url,
    nano_banana_pro_edit_image_url,
    seedance_20_text_to_video_url,
    seedream_v45_bootstrap_edit_image_url,
    seedream_v45_edit_image_url,
    wavespeed_image_upscale_url,
    z_image_turbo_inpaint_image_url,
)

router = APIRouter(tags=["studio"])

log = logging.getLogger(__name__)

MAX_MODEL_IMAGES = 8


async def _download_image_bytes_best_effort(url: str) -> tuple[bytes | None, str | None]:
    u = (url or "").strip()
    if not u:
        return None, "Пустая ссылка на изображение"
    timeout = float(settings.studio_archive_download_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(u)
            resp.raise_for_status()
            content = resp.content
    except Exception as e:
        log.warning("studio: download bytes failed (%s): %s", u[:260], e)
        return None, str(e)
    if not content:
        return None, "Пустой ответ провайдера"
    return content, None


def _coerce_camera_preset_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if get_camera_preset_by_id(s) is None:
        raise HTTPException(
            status_code=400,
            detail="Неизвестный пресет камеры для экспорта. Выберите значение из списка.",
        )
    return s


def _parse_optional_lat_lon_form(lat_s: str | None, lon_s: str | None) -> tuple[float | None, float | None]:
    def one(label: str, v: str | None) -> float | None:
        if v is None or not str(v).strip():
            return None
        try:
            return float(str(v).strip().replace(",", "."))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"{label} должна быть числом (например 55.7558).",
            ) from None

    lat_e = one("Широта", lat_s)
    lon_e = one("Долгота", lon_s)
    if (lat_e is None) ^ (lon_e is None):
        raise HTTPException(
            status_code=400,
            detail="Укажите и широту, и долготу для ГЕО, или оставьте оба поля пустыми.",
        )
    if lat_e is not None and lon_e is not None:
        if not (-90 <= lat_e <= 90 and -180 <= lon_e <= 180):
            raise HTTPException(status_code=400, detail="Координаты вне допустимого диапазона.")
    return lat_e, lon_e


def _require_studio_subscription(
    user: User,
    owner_subscription: Subscription | None,
    *,
    credits_balance: int = 0,
) -> None:
    if not settings.billing_require_active_subscription:
        return
    if user_is_platform_admin(user):
        return
    if not subscription_active(owner_subscription):
        raise HTTPException(
            status_code=402,
            detail=(
                "Оформите подписку: личный кабинет → «Тариф и баланс», выберите Managed или BYOK и оплатите."
            ),
        )
    if owner_subscription and owner_subscription.status == SubscriptionStatus.trialing:
        if credits_balance <= 0:
            raise HTTPException(
                status_code=402,
                detail=(
                    "Бонусные кредиты закончились. Оформите подписку Managed или BYOK в разделе «Тариф и баланс»."
                ),
            )


def _public_app_base(request: Request | None) -> str:
    p = (settings.public_app_url or "").strip().rstrip("/")
    if p:
        return p
    if request is not None:
        return str(request.base_url).rstrip("/")
    return ""


def _studio_archive_image_url(owner_id: int, generation_id: int, arch_base: str) -> str:
    tok = create_generation_image_access_token(user_id=owner_id, generation_id=generation_id)
    return f"{arch_base.rstrip('/')}/api/studio/public-generation-image?t={quote(tok, safe='')}"


def _studio_archive_video_url(owner_id: int, generation_id: int, arch_base: str) -> str:
    tok = create_generation_image_access_token(user_id=owner_id, generation_id=generation_id)
    return f"{arch_base.rstrip('/')}/api/studio/public-generation-video?t={quote(tok, safe='')}"


def _studio_generation_to_out(
    row: StudioGeneration,
    *,
    arch_base: str,
    owner_id: int,
    name_by_id: dict[int, str],
) -> StudioGenerationOut | None:
    media = generation_media_kind(row)
    st = (row.status or StudioGenerationStatus.READY).strip()
    image_url = ""
    video_url: str | None = None

    if st == StudioGenerationStatus.FAILED:
        pass
    elif media == "video":
        src = (row.source_url or "").strip()
        if st == StudioGenerationStatus.READY and generation_has_archive_file(row):
            video_url = _studio_archive_video_url(owner_id, row.id, arch_base)
        elif src.startswith("https://"):
            video_url = src
        elif st in (
            StudioGenerationStatus.PROCESSING,
            StudioGenerationStatus.ARCHIVING,
        ) and src.startswith("https://"):
            image_url = src
    elif generation_has_archive_file(row) and st == StudioGenerationStatus.READY:
        image_url = _studio_archive_image_url(owner_id, row.id, arch_base)
    elif st == StudioGenerationStatus.PROVIDER_READY:
        src = (row.source_url or "").strip()
        if src.startswith("https://"):
            image_url = src
        elif generation_has_archive_file(row):
            image_url = _studio_archive_image_url(owner_id, row.id, arch_base)

    if (
        st == StudioGenerationStatus.READY
        and media == "image"
        and not image_url
        and not generation_has_archive_file(row)
    ):
        return None

    return StudioGenerationOut(
        id=row.id,
        created_at=row.created_at,
        output_aspect=row.output_aspect,
        studio_model_id=row.studio_model_id,
        model_name=name_by_id.get(row.studio_model_id) if row.studio_model_id else None,
        prompt_excerpt=row.prompt_excerpt,
        status=st,
        media_kind=media,
        error_message=(row.error_message or "").strip()[:500] or None,
        job_id=row.studio_job_id,
        image_url=image_url,
        video_url=video_url,
    )


def _studio_job_status_out(job: StudioJob) -> StudioJobStatusOut:
    return StudioJobStatusOut(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        error_message=job.error_message,
        result=studio_jobs.job_result_dict(job),
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


async def _accept_studio_job(
    session: AsyncSession,
    user: User,
    *,
    job_type: str,
    params: dict[str, Any],
    placeholder: dict[str, Any] | None = None,
) -> JSONResponse:
    oid = workspace_owner_id(user)
    job = await studio_jobs.create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type=job_type,
        params=params,
    )
    generation_id: int | None = None
    if placeholder:
        gen_row = await reserve_studio_generation_for_job(
            session,
            owner_id=oid,
            studio_job_id=job.id,
            studio_model_id=placeholder.get("studio_model_id"),
            output_aspect=placeholder.get("output_aspect"),
            content_type=str(placeholder.get("content_type") or "image/png"),
            prompt_excerpt=placeholder.get("prompt_excerpt"),
            preview_source_url=placeholder.get("preview_source_url"),
        )
        generation_id = gen_row.id
        params = {**params, "placeholder_generation_id": generation_id}
        await studio_jobs.update_studio_job_params(session, job, params)
    studio_jobs.schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type=job_type,
            generation_id=generation_id,
        ).model_dump(),
    )


@router.get("/studio/jobs/{job_id}", response_model=StudioJobStatusOut)
async def api_get_studio_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioJobStatusOut:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    job = await studio_jobs.get_owned_studio_job(session, job_id, oid)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return _studio_job_status_out(job)


@router.get("/studio/camera-presets", response_model=list[StudioCameraPresetOut])
async def api_list_camera_presets(user: User = Depends(get_current_user)) -> list[StudioCameraPresetOut]:
    if not has_any_studio_access(user):
        raise HTTPException(status_code=403, detail="Нет доступа к студии")
    return [StudioCameraPresetOut(id=x["id"], label=x["label"]) for x in list_camera_presets()]


_ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _parse_optional_model_id(raw: str | None) -> int | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный model_id") from None


def _studio_refine_wavespeed_preflight(
    *,
    do_wavespeed: bool,
    plan: str,
    ws_row: WavespeedConnection | None,
    owner_subscription: Subscription | None,
    mode_n: str,
    mid: int | None,
    sm_loaded: UserStudioModel | None,
    imgs_model: list[UserStudioModelImage],
    image_bytes: bytes | None,
    wave_profile: str,
) -> str:
    """Перед списанием кредитов: ключ WaveSpeed и условия вызова API (иначе HTTPException)."""
    if not do_wavespeed:
        return ""
    ws_key = studio_wavespeed_api_key(
        plan=plan, ws_row=ws_row, owner_subscription=owner_subscription
    )
    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Генерация изображения недоступна: у сервиса не настроен публичный HTTPS-адрес. Обратитесь к администратору.",
        )
    wp = _normalize_studio_wave_profile(wave_profile)
    if wp == "regular" and imgs_model:
        imgs_ok = model_images_for_wavespeed_profile(imgs_model, wp)
        if not imgs_ok and mode_n in ("model", "model_scene", "no_face"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "В режиме «Обычные фотографии» нельзя использовать только снимки с типом «интимная анатомия» — "
                    "они не отправляются в этот API (ограничения провайдера). Добавьте фото лица или тела к модели "
                    "или переключите тип генерации на «NSFW (WAN / Seedream)»."
                ),
            )
    if mode_n in ("model", "model_scene"):
        if mid is None or sm_loaded is None:
            label = "«Модель + промпт»" if mode_n == "model_scene" else "«По промту»"
            raise HTTPException(
                status_code=400,
                detail=f"В режиме {label} выберите сохранённую модель с фотографиями.",
            )
        if not imgs_model:
            raise HTTPException(
                status_code=400,
                detail="У выбранной модели нет загруженных фото — добавьте снимки к модели.",
            )
        if not image_bytes:
            if mode_n == "model_scene":
                ws_body = select_model_scene_wavespeed_identity_images(
                    imgs_model, wave_profile=wp
                )
                if not ws_body:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "В режиме «Модель + промпт» у модели нужны снимки: развёртка (turnaround) "
                            "и/или лицо/тело."
                        ),
                    )
            else:
                ws_body = select_prompt_only_wavespeed_identity_images(
                    imgs_model, wave_profile=wp
                )
                if not ws_body:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "В режиме «По промту» у модели нужен снимок «Тело целиком» (body). "
                            "Для NSFW при необходимости добавьте «Интимная анатомия» (genitals)."
                        ),
                    )
    elif mode_n == "face_swap":
        if mid is None or sm_loaded is None:
            raise HTTPException(
                status_code=400,
                detail='В режиме «Face swap» выберите модель‑эталон для подмены внешности.',
            )
        if not imgs_model:
            raise HTTPException(
                status_code=400,
                detail="У выбранной модели нет загруженных фото.",
            )
        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail='В режиме «Face swap» загрузите исходную фотографию со сценой.',
            )
    elif mode_n == "photo_edit":
        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="Для доработки фото загрузите изображение.",
            )
    elif mode_n == "no_face":
        if not image_bytes and (mid is None or sm_loaded is None or not imgs_model):
            raise HTTPException(
                status_code=400,
                detail="В режиме «Без лица» выберите модель с фото или загрузите референс.",
            )
    elif mode_n in ("grok_compose", "model_scene"):
        label = "«Модель + промпт»" if mode_n == "model_scene" else "«Grok: сцена»"
        if mid is None or sm_loaded is None:
            raise HTTPException(
                status_code=400,
                detail=f"В режиме {label} выберите сохранённую модель с фотографиями.",
            )
        if not imgs_model:
            raise HTTPException(
                status_code=400,
                detail="У модели нет снимков — добавьте развёртку или лицо/тело в кабинете.",
            )
        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"В режиме {label} загрузите референс сцены (поза, свет, кадр) — для Grok.",
            )
        if mode_n == "model_scene":
            id_for_ws = select_model_scene_wavespeed_identity_images(
                imgs_model, wave_profile=wp
            )
            if not id_for_ws:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "В режиме «Модель + промпт» у модели нужны снимки: развёртка (turnaround) "
                        "и/или лицо/тело."
                    ),
                )
        else:
            id_for_ws = select_grok_compose_wavespeed_identity_images(imgs_model)
            if not id_for_ws:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "В режиме «Grok: сцена» у модели нужен снимок тела (body) и/или лица (face) — "
                        "для переноса фигуры и внешности в WaveSpeed."
                    ),
                )
    return ws_key


def _z_image_inpaint_studio_prompt(*, refined: str, user_description: str) -> str:
    """Текст для Z-Image Inpaint: указание по маске + суть правки."""
    d = (user_description or "").strip()
    core = d if len(d) >= 8 else (refined or "").strip()[:12000]
    return (
        "Edit only the white region of the inpaint mask; keep black regions unchanged. "
        + core
    )


@router.get("/studio/output-aspects")
async def api_output_aspects() -> dict:
    """Список пресетов соотношения сторон для студии (UI и WaveSpeed size)."""
    return {"aspects": aspect_presets_public()}


def _build_wan_22_animate_prompt(
    *,
    motion_summary: str | None,
    user_extra: str | None,
    negative: str | None,
) -> str | None:
    """Короткий текст для WAN 2.2 Animate или общий motion-prompt для Kling (negative отдельным полем API)."""
    parts: list[str] = []
    ms = (motion_summary or "").strip()
    if ms:
        parts.append(
            "Match performance rhythm and expressions from the driving video. Scene/action: " + ms
        )
    ux = (user_extra or "").strip()
    if ux:
        parts.append(ux)
    neg = (negative or "").strip()
    if neg:
        parts.append("Avoid: " + neg)
    out = " ".join(parts).strip()
    return out or None


# Тот же маркер, что в api_studio_motion_first_frame (слияние с БД).
_CLIP_MOTION_MARKER = "[Clip motion — sampled frames]"
_GROK_MOTION_MARKER = "[Grok motion timeline]"


def _merge_clip_motion_into_studio_generation_prompt(
    existing: str | None,
    clip_summary: str,
) -> str:
    clip_summary = (clip_summary or "").strip()
    base = (existing or "").strip()
    if not clip_summary:
        return base
    block = f"{_CLIP_MOTION_MARKER}\n{clip_summary}"
    if not base:
        return block
    if _CLIP_MOTION_MARKER in base or _GROK_MOTION_MARKER in base:
        return base
    return f"{base}\n\n{block}"


def _truthy_wavespeed_flag(raw: str | None) -> bool:
    if raw is None:
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "")


def _effective_generate_wavespeed(generate_wavespeed: str | None) -> bool:
    """Отключение WaveSpeed (только JSON-промпт) разрешено лишь при STUDIO_ALLOW_PROMPT_ONLY."""
    want = _truthy_wavespeed_flag(generate_wavespeed)
    if not want and not settings.studio_allow_prompt_only:
        return True
    return want


def _truthy_lock_model_hairstyle(raw: str | None) -> bool:
    """True — причёска с профиля модели (MODEL_LOCK); False — с загруженного референса (POSE_REFERENCE)."""
    if raw is None:
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _truthy_send_pose_reference_to_wavespeed(raw: str | None) -> bool:
    """True — референс позы/сцены уходит в WaveSpeed (как сейчас); False — только LLM → промпт, в API только фото модели."""
    if raw is None:
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


_ALLOWED_STUDIO_MODES = frozenset(
    {"model", "model_scene", "photo_edit", "no_face", "face_swap", "grok_compose"}
)


def _studio_mode_prompt_only(mode: str) -> bool:
    """Без референса сцены пользователя в промпте и WaveSpeed."""
    return mode in ("model", "model_scene")


def _normalize_studio_mode(raw: str | None) -> str:
    m = (raw or "model_scene").strip().lower().replace("-", "_")
    if m in ("edit", "refine", "enhance"):
        return "photo_edit"
    if m in _ALLOWED_STUDIO_MODES:
        return m
    return "model_scene"


def _normalize_wan_edit_tier(raw: str | None) -> str:
    """standard | pro для FormData UI; прочее → standard."""
    t = (raw or "standard").strip().lower()
    return "pro" if t == "pro" else "standard"


def _normalize_studio_wave_profile(raw: str | None) -> str:
    """regular = Nano Banana Pro (обычные фото); nsfw = WAN/Seedream из .env."""
    p = (raw or "nsfw").strip().lower()
    return "regular" if p == "regular" else "nsfw"


def _append_nano_banana_error_hint(message: str, *, wave_profile: str) -> str:
    """Расшифровка типичной ошибки Google «check your input parameters»."""
    if (wave_profile or "").strip().lower() != "regular":
        return message
    low = (message or "").lower()
    if "input parameter" not in low and "invalid parameter" not in low:
        return message
    return (
        f"{message} "
        "Для «Обычные фотографии» (Nano Banana): часто nude-референс или откровенный промпт "
        "(переключите «NSFW»), недоступные HTTPS-ссылки на картинки (PUBLIC_APP_URL), "
        "слишком длинный JSON-промпт или неверный формат кадра."
    )


def _nano_banana_reorder_image_urls(
    image_urls: list[str],
    *,
    studio_mode: str,
    user_pose_ref_prepended: bool,
) -> list[str]:
    """
    WAN ожидает: [поза пользователя, …фото модели]. Nano Banana стабильнее держит лицо, если
    сначала идут кадры личности, загруженный референс позы — последним.
    «Доработать фото»: первый URL = редактируемое фото — не трогаем порядок.
    """
    if not image_urls or studio_mode == "photo_edit":
        return image_urls
    if user_pose_ref_prepended and len(image_urls) >= 2:
        return image_urls[1:] + [image_urls[0]]
    return image_urls


def _masked_full_frame_wan_image_urls(
    base_url: str,
    mask_url: str,
    identity_urls: list[str],
    *,
    wave_profile_n: str,
    wavespeed_single_reference: str | None,
) -> list[str]:
    wan_cap = 9
    urls = [base_url, mask_url] + identity_urls
    urls = urls[:wan_cap]
    # wavespeed_single_reference = один pose-кадр (base), не обрезка identity после маски
    return urls


def _masked_full_frame_nano_image_urls_from_wan_list(
    wan_ordered: list[str],
    *,
    studio_mode: str,
    nano_cap: int = 14,
) -> list[str]:
    if len(wan_ordered) < 2:
        return wan_ordered[:nano_cap]
    if studio_mode == "photo_edit":
        return wan_ordered[:nano_cap]
    base_u, mask_u, *identity_rest = (
        wan_ordered[0],
        wan_ordered[1],
        wan_ordered[2:],
    )
    nano_list = [*identity_rest, base_u, mask_u]
    return nano_list[:nano_cap]


def _model_dir(user_id: int, model_id: int) -> Path:
    return (BACKEND_DIR / "data" / "studio_user_models" / str(user_id) / str(model_id)).resolve()


def _studio_model_to_out(user_id: int, m: UserStudioModel) -> UserStudioModelOut:
    from app.services.studio_exif_profile import (
        phone_exif_profile_from_json,
        phone_exif_profile_summary,
    )

    ordered = sort_model_images_for_studio(list(m.images))
    images = [
        StudioModelImageOut(
            id=im.id,
            url="/api/studio/public-model-image?t="
            + quote(create_model_image_access_token(user_id=user_id, image_id=im.id), safe=""),
            kind=(im.image_kind or "other").strip().lower(),
        )
        for im in ordered
    ]
    selfie_prof = phone_exif_profile_from_json(m.phone_exif_selfie_json)
    main_prof = phone_exif_profile_from_json(m.phone_exif_main_json)
    return UserStudioModelOut(
        id=m.id,
        name=m.name,
        profile_text=m.profile_text or "",
        image_count=len(ordered),
        images=images,
        camera_preset_id=(m.camera_preset_id or "").strip() or None,
        export_lat=m.export_lat,
        export_lon=m.export_lon,
        phone_exif_selfie_ready=selfie_prof is not None,
        phone_exif_main_ready=main_prof is not None,
        phone_exif_selfie_summary=phone_exif_profile_summary(selfie_prof),
        phone_exif_main_summary=phone_exif_profile_summary(main_prof),
    )


async def _load_studio_model_owned(
    session: AsyncSession, user_id: int, model_id: int
) -> UserStudioModel | None:
    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.id == model_id, UserStudioModel.user_id == user_id)
        .options(selectinload(UserStudioModel.images))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


@router.get("/studio/public-model-image")
async def public_studio_model_image(
    t: str,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Публичная выдача файла модели по JWT — URL забирает WaveSpeed."""
    try:
        uid, iid = decode_model_image_access_token(t)
    except ValueError:
        raise HTTPException(status_code=404, detail="Недействительная ссылка") from None
    img = await session.get(UserStudioModelImage, iid)
    if not img:
        raise HTTPException(status_code=404, detail="Не найдено")
    sm = await session.get(UserStudioModel, img.studio_model_id)
    if not sm or sm.user_id != uid:
        raise HTTPException(status_code=404, detail="Не найдено")
    abs_path = (BACKEND_DIR / img.relative_path).resolve()
    try:
        abs_path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Не найдено") from None
    if not abs_path.is_file():
        # Файл пропал (например контейнер без volume) — убираем «сироту» из БД, иначе UI и WaveSpeed держат мёртвые ссылки
        await session.delete(img)
        await session.commit()
        raise HTTPException(
            status_code=404, detail="Файл изображения отсутствует на сервере"
        ) from None
    mime = mimetypes.guess_type(abs_path.name)[0] or "application/octet-stream"
    return FileResponse(abs_path, media_type=mime)


@router.get("/studio/public-pose-reference")
async def public_studio_pose_reference(t: str) -> FileResponse:
    """Разовый референс позы/кадра из multipart — публичный URL для WaveSpeed (JWT)."""
    try:
        uid, fid = decode_pose_reference_access_token(t)
    except ValueError:
        raise HTTPException(status_code=404, detail="Недействительная ссылка") from None
    path = resolve_pose_reference_file(uid, fid)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Не найдено") from None
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return FileResponse(path, media_type=mime)


@router.get("/studio/public-generation-video")
async def public_studio_generation_video(
    t: str,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Видео из архива: локальный файл или редирект на CDN (provider_ready)."""
    try:
        uid, gid = decode_generation_image_access_token(t)
    except ValueError:
        raise HTTPException(status_code=404, detail="Недействительная ссылка") from None
    row = await session.get(StudioGeneration, gid)
    if not row or row.user_id != uid:
        raise HTTPException(status_code=404, detail="Не найдено") from None
    if not (row.content_type or "").startswith("video/"):
        raise HTTPException(status_code=404, detail="Не видео") from None
    rel = (row.relative_path or "").strip()
    if rel:
        abs_path = (BACKEND_DIR / rel).resolve()
        try:
            abs_path.relative_to(BACKEND_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Не найдено") from None
        if abs_path.is_file():
            mime = row.content_type or mimetypes.guess_type(abs_path.name)[0] or "video/mp4"
            return FileResponse(abs_path, media_type=mime)
    src = (row.source_url or "").strip()
    if src.startswith("https://"):
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url=src, status_code=302)
    raise HTTPException(status_code=404, detail="Видео ещё не готово") from None


@router.get("/studio/public-generation-image")
async def public_studio_generation_image(
    t: str,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Публичная выдача архивной картинки студии по JWT (для <img src>)."""
    try:
        uid, gid = decode_generation_image_access_token(t)
    except ValueError:
        raise HTTPException(status_code=404, detail="Недействительная ссылка") from None
    row = await session.get(StudioGeneration, gid)
    if not row or row.user_id != uid:
        raise HTTPException(status_code=404, detail="Не найдено") from None
    abs_path = (BACKEND_DIR / row.relative_path).resolve()
    try:
        abs_path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Не найдено") from None
    if not abs_path.is_file():
        src = (row.source_url or "").strip()
        if row.status == StudioGenerationStatus.PROVIDER_READY and src.startswith("https://"):
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url=src, status_code=302)
        if row.status == StudioGenerationStatus.READY:
            await session.delete(row)
            await session.commit()
        raise HTTPException(status_code=404, detail="Файл отсутствует на сервере") from None
    mime = row.content_type or mimetypes.guess_type(abs_path.name)[0] or "image/png"
    return FileResponse(abs_path, media_type=mime)


@router.get("/studio/public-motion-video")
async def public_studio_motion_video(t: str) -> FileResponse:
    """Временный driving-video по JWT — URL забирает WaveSpeed Kling API."""
    try:
        uid, fid = decode_motion_video_access_token(t)
    except ValueError:
        raise HTTPException(status_code=404, detail="Недействительная ссылка") from None
    path = resolve_motion_video_file(uid, fid)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Не найдено") from None
    mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
    return FileResponse(path, media_type=mime)


@router.post(
    "/studio/motion/upload-driving-video",
    response_model=StudioMotionDrivingVideoUploadOut,
)
async def api_studio_motion_upload_driving_video(
    video: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioMotionDrivingVideoUploadOut:
    """Сохраняет референс-видео на диск без шага «Создать кадр» — для прямого «Сделать видео» с архивным кадром."""
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    sub_b, _llm, _ws, _plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    max_v = max(1, int(settings.studio_motion_max_upload_mb)) * 1024 * 1024
    if video is None or not (video.filename or "").strip():
        raise HTTPException(status_code=400, detail="Выберите файл видео (MP4/WebM/MOV).")
    raw_video = await video.read()
    if len(raw_video) > max_v:
        raise HTTPException(
            status_code=400,
            detail=f"Видео слишком большое (макс. {settings.studio_motion_max_upload_mb} МБ).",
        )
    if not raw_video:
        raise HTTPException(status_code=400, detail="Пустой файл видео.")
    fid = save_motion_video_bytes(owner_id=oid, raw=raw_video, filename=video.filename)
    return StudioMotionDrivingVideoUploadOut(motion_video_file_id=fid)


@router.get("/studio/motion/renders", response_model=StudioMotionRendersPageOut)
async def api_list_motion_renders(
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    skip: int = Query(0, ge=0, le=50_000),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioMotionRendersPageOut:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    take = int(limit) + 1
    allowed = await member_allowed_studio_model_ids(session, user)
    stmt = (
        select(StudioMotionRender)
        .where(StudioMotionRender.user_id == oid)
        .order_by(StudioMotionRender.created_at.desc(), StudioMotionRender.id.desc())
        .offset(int(skip))
        .limit(take)
    )
    stmt = apply_studio_model_id_filter(stmt, StudioMotionRender.studio_model_id, allowed)
    rows = list((await session.execute(stmt)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    base = _public_app_base(request)
    if not base:
        return StudioMotionRendersPageOut(items=[], has_more=False)
    out_items: list[StudioMotionRenderOut] = []
    for r in rows:
        img = ""
        if r.studio_generation_id is not None:
            tok = create_generation_image_access_token(
                user_id=oid, generation_id=r.studio_generation_id
            )
            img = f"{base}/api/studio/public-generation-image?t={quote(tok, safe='')}"
        url = (r.video_url or "").strip()
        if url:
            out_items.append(
                StudioMotionRenderOut(
                    id=r.id,
                    created_at=r.created_at,
                    studio_generation_id=r.studio_generation_id,
                    studio_model_id=r.studio_model_id,
                    video_url=url,
                    frame_image_url=img or url,
                )
            )
    return StudioMotionRendersPageOut(items=out_items, has_more=has_more)


def _apply_studio_generation_media_kind_filter(stmt, media_kind: str | None):
    if media_kind == "video":
        return stmt.where(StudioGeneration.content_type.like("video/%"))
    if media_kind == "image":
        return stmt.where(
            or_(
                StudioGeneration.content_type.is_(None),
                StudioGeneration.content_type == "",
                ~StudioGeneration.content_type.like("video/%"),
            )
        )
    return stmt


@router.get("/studio/generations", response_model=StudioGenerationsPageOut)
async def api_list_studio_generations(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0, le=50_000),
    media_kind: Literal["image", "video"] | None = Query(
        None,
        description="Фильтр истории: только картинки или только видео",
    ),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioGenerationsPageOut:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    take = int(limit) + 1
    allowed = await member_allowed_studio_model_ids(session, user)
    visible = (
        StudioGenerationStatus.PROCESSING,
        StudioGenerationStatus.ARCHIVING,
        StudioGenerationStatus.PROVIDER_READY,
        StudioGenerationStatus.READY,
        StudioGenerationStatus.FAILED,
    )
    stmt = (
        select(StudioGeneration)
        .where(StudioGeneration.user_id == oid)
        .where(StudioGeneration.status.in_(visible))
        .order_by(StudioGeneration.created_at.desc(), StudioGeneration.id.desc())
        .offset(int(skip))
        .limit(take)
    )
    stmt = _apply_studio_generation_media_kind_filter(stmt, media_kind)
    stmt = apply_studio_model_id_filter(stmt, StudioGeneration.studio_model_id, allowed)
    rows = list((await session.execute(stmt)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    base = _public_app_base(request)
    if not base:
        return StudioGenerationsPageOut(items=[], has_more=False)
    model_ids = {r.studio_model_id for r in rows if r.studio_model_id}
    name_by_id: dict[int, str] = {}
    if model_ids:
        qm = await session.execute(select(UserStudioModel).where(UserStudioModel.id.in_(model_ids)))
        for m in qm.scalars().all():
            name_by_id[m.id] = m.name
    out_items: list[StudioGenerationOut] = []
    for r in rows:
        item = _studio_generation_to_out(r, arch_base=base, owner_id=oid, name_by_id=name_by_id)
        if item is not None:
            out_items.append(item)
    return StudioGenerationsPageOut(items=out_items, has_more=has_more)


@router.get("/studio/generations/pending", response_model=StudioGenerationsPendingOut)
async def api_list_pending_studio_generations(
    request: Request,
    limit: int = Query(30, ge=1, le=50),
    media_kind: Literal["image", "video"] | None = Query(
        None,
        description="Только незавершённые картинки или видео",
    ),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioGenerationsPendingOut:
    """Незавершённые записи архива — для редкого опроса (≈12 с), пока идёт WaveSpeed.

    Восстановление failed-записей с WaveSpeed — только в фоне (retry_pending_studio_archives),
    не на каждом опросе UI.
    """
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    if await reconcile_stuck_studio_generations(session, oid, limit=limit):
        await session.commit()
    allowed = await member_allowed_studio_model_ids(session, user)
    stmt = (
        select(StudioGeneration)
        .where(StudioGeneration.user_id == oid)
        .where(
            StudioGeneration.status.in_(
                (
                    StudioGenerationStatus.PROCESSING,
                    StudioGenerationStatus.ARCHIVING,
                    StudioGenerationStatus.PROVIDER_READY,
                )
            )
        )
        .order_by(StudioGeneration.created_at.desc(), StudioGeneration.id.desc())
        .limit(int(limit))
    )
    stmt = _apply_studio_generation_media_kind_filter(stmt, media_kind)
    stmt = apply_studio_model_id_filter(stmt, StudioGeneration.studio_model_id, allowed)
    rows = list((await session.execute(stmt)).scalars().all())
    base = _public_app_base(request)
    if not base:
        return StudioGenerationsPendingOut(items=[], poll_after_seconds=12)
    model_ids = {r.studio_model_id for r in rows if r.studio_model_id}
    name_by_id: dict[int, str] = {}
    if model_ids:
        qm = await session.execute(select(UserStudioModel).where(UserStudioModel.id.in_(model_ids)))
        for m in qm.scalars().all():
            name_by_id[m.id] = m.name
    out_items: list[StudioGenerationOut] = []
    for r in rows:
        if not generation_is_pending_in_ui(r):
            continue
        item = _studio_generation_to_out(r, arch_base=base, owner_id=oid, name_by_id=name_by_id)
        if item is not None:
            out_items.append(item)
    return StudioGenerationsPendingOut(items=out_items, poll_after_seconds=12)


@router.delete("/studio/generations/{gen_id}")
async def api_delete_studio_generation(
    gen_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    row = await session.get(StudioGeneration, gen_id)
    if not row or row.user_id != oid:
        raise HTTPException(status_code=404, detail="Не найдено")
    await assert_studio_generation_access(session, user, row.studio_model_id)
    rel = row.relative_path
    await session.delete(row)
    await session.commit()
    safe_delete_generation_file(rel)
    return {"ok": True}


@router.post(
    "/studio/generations/{gen_id}/upscale",
    response_model=StudioUpscaleGenerationOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_upscale_studio_generation(
    gen_id: int,
    request: Request,
    payload: StudioUpscaleGenerationIn | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioUpscaleGenerationOut | JSONResponse:
    _ = request
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    row = await session.get(StudioGeneration, gen_id)
    if not row or row.user_id != oid:
        raise HTTPException(status_code=404, detail="Не найдено")
    await assert_studio_generation_access(session, user, row.studio_model_id)

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="Для апскейла WaveSpeed нужен публичный HTTPS (PUBLIC_APP_URL=https://…).",
        )

    tr = "4k"
    if payload and payload.target_resolution:
        tr = payload.target_resolution

    sub_b, _, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    try:
        studio_wavespeed_api_key(plan=plan, ws_row=ws_row, owner_subscription=sub_b)
    except HTTPException as e:
        return StudioUpscaleGenerationOut(
            generated_image_url=None,
            generation_id=None,
            message=str(e.detail),
            target_resolution=tr,
        )

    return await _accept_studio_job(
        session,
        user,
        job_type="upscale",
        params={"gen_id": gen_id, "target_resolution": tr},
    )


async def _studio_job_execute_upscale(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    params = studio_jobs.job_params(job)
    gen_id = int(params["gen_id"])
    tr = str(params.get("target_resolution") or "4k")
    oid = workspace_owner_id(user)
    row = await session.get(StudioGeneration, gen_id)
    if not row or row.user_id != oid:
        raise RuntimeError("Генерация не найдена")

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise RuntimeError("Нужен PUBLIC_APP_URL=https://…")

    sub_b, _, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)

    ws_key: str = ""
    try:
        ws_key = studio_wavespeed_api_key(
            plan=plan, ws_row=ws_row, owner_subscription=sub_b
        )
    except HTTPException as e:
        return StudioUpscaleGenerationOut(
            generated_image_url=None,
            generation_id=None,
            message=str(e.detail),
            target_resolution=tr,
        ).model_dump()

    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_upscale)
    billing = await ensure_can_consume_credits(session, user, cost)
    msg: str | None = None
    out_url: str | None = None
    new_id: int | None = None

    if ws_key and not msg:
        tok = create_generation_image_access_token(user_id=oid, generation_id=gen_id)
        image_pub_url = f"{pub}/api/studio/public-generation-image?t={quote(tok, safe='')}"
        try:
            raw_up = await wavespeed_image_upscale_url(
                api_key=ws_key,
                image_url=image_pub_url,
                target_resolution=tr,
                output_format="png",
            )
        except RuntimeError as e:
            msg = str(e)
            raw_up = None

        if raw_up and not msg:
            excerpt = (row.prompt_excerpt or "").strip()
            up_note = f"[upscale {tr}] {excerpt}"[:2000] if excerpt else f"[upscale {tr}]"
            gen = await download_and_create_generation(
                session,
                owner_id=oid,
                source_url=raw_up,
                refined_prompt=up_note,
                output_aspect=row.output_aspect,
                studio_model_id=row.studio_model_id,
                exif_camera=getattr(row, "exif_camera", None),
            )
            if gen is None:
                msg = user_message_when_archive_download_failed(
                    "Апскейл на стороне провайдера выполнен, но файл не сохранился на сервере."
                )
                out_url = raw_up
            else:
                new_id = gen.id
                arch_base = _public_app_base(None)
                if arch_base:
                    gtok = create_generation_image_access_token(
                        user_id=oid, generation_id=gen.id
                    )
                    out_url = (
                        f"{arch_base}/api/studio/public-generation-image?t={quote(gtok, safe='')}"
                    )
                else:
                    out_url = raw_up

    if out_url and new_id is not None:
        await record_usage(
            session,
            user,
            billing,
            "studio_image_upscale",
            cost,
            {
                "source_generation_id": gen_id,
                "target_resolution": tr,
                "generation_id": new_id,
            },
        )
        await session.commit()
        return StudioUpscaleGenerationOut(
            generated_image_url=out_url,
            generation_id=new_id,
            message=None,
            target_resolution=tr,
        ).model_dump()

    await session.rollback()
    return StudioUpscaleGenerationOut(
        generated_image_url=out_url,
        generation_id=new_id,
        message=msg.strip()
        if msg
        else (None if out_url else "Апскейл не выполнен."),
        target_resolution=tr,
    ).model_dump()


@router.post(
    "/studio/generations/{gen_id}/carousel",
    response_model=StudioCarouselOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_studio_carousel(
    gen_id: int,
    request: Request,
    payload: StudioCarouselIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioCarouselOut | JSONResponse:
    """Несколько вариантов кадра (ракурс/поза) от той же мастер-генерации — тот же промпт + шаблоны в data/prompts."""
    _ = request
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    row = await session.get(StudioGeneration, gen_id)
    if not row or row.user_id != oid:
        raise HTTPException(status_code=404, detail="Не найдено")
    await assert_studio_generation_access(session, user, row.studio_model_id)

    master_text = (row.refined_prompt or row.prompt_excerpt or "").strip()
    if len(master_text) < 80:
        raise HTTPException(
            status_code=400,
            detail="Для карусели нужен сохранённый полный промпт. Сгенерируйте снимок заново в студии.",
        )

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="WaveSpeed скачивает мастер-кадр по HTTPS. Укажите PUBLIC_APP_URL=https://…",
        )

    sub_b, _, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    try:
        studio_wavespeed_api_key(plan=plan, ws_row=ws_row, owner_subscription=sub_b)
    except HTTPException as e:
        return StudioCarouselOut(message=str(e.detail))

    return await _accept_studio_job(
        session,
        user,
        job_type="carousel",
        params={
            "gen_id": gen_id,
            "count": int(payload.count),
            "studio_wave_profile": payload.studio_wave_profile,
            "wan_edit_tier": payload.wan_edit_tier,
        },
    )


async def _studio_job_execute_carousel(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    params = studio_jobs.job_params(job)
    gen_id = int(params["gen_id"])
    count = int(params.get("count") or 4)
    oid = workspace_owner_id(user)
    row = await session.get(StudioGeneration, gen_id)
    if not row or row.user_id != oid:
        raise RuntimeError("Генерация не найдена")

    master_text = (row.refined_prompt or row.prompt_excerpt or "").strip()
    if len(master_text) < 80:
        raise RuntimeError("Для карусели нужен сохранённый полный промпт.")

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise RuntimeError("Нужен PUBLIC_APP_URL=https://…")

    sub_b, _, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    ws_key = studio_wavespeed_api_key(plan=plan, ws_row=ws_row, owner_subscription=sub_b)

    wave_profile_n = _normalize_studio_wave_profile(str(params.get("studio_wave_profile") or "nsfw"))
    wan_tier_n = _normalize_wan_edit_tier(str(params.get("wan_edit_tier") or "standard"))
    aspect_key = normalize_aspect_key(row.output_aspect or "9:16")

    cost_one = apply_studio_credit_cost(plan, settings.credit_cost_studio_carousel_shot)
    tok = create_generation_image_access_token(user_id=oid, generation_id=gen_id)
    master_url = f"{pub}/api/studio/public-generation-image?t={quote(tok, safe='')}"

    items: list[StudioCarouselItemOut] = []
    last_msg: str | None = None
    arch_base = _public_app_base(None)

    for shot_i in range(count):
        billing = await ensure_can_consume_credits(session, user, cost_one)
        carousel_body = build_carousel_wave_prompt(
            master_refined_json=master_text,
            shot_index=shot_i,
        )
        if wave_profile_n == "regular":
            wavespeed_prompt = finalize_nano_banana_studio_prompt(
                carousel_body,
                studio_mode="photo_edit",
                user_photo_edit_first=True,
                user_pose_reference_is_last=False,
            )
        else:
            wavespeed_prompt = finalize_wavespeed_studio_prompt(
                carousel_body,
                studio_mode="photo_edit",
                user_image_first=True,
            )

        if settings.wavespeed_seedream_omit_size:
            size_for_ws: str | None = None
        else:
            size_for_ws = wavespeed_size_string(aspect_key)

        try:
            if wave_profile_n == "regular":
                ws_car = await nano_banana_pro_edit_image_url(
                    api_key=ws_key,
                    image_urls=[master_url],
                    prompt=wavespeed_prompt,
                    aspect_ratio=aspect_key,
                    wave_profile=wave_profile_n,
                )
                raw_url = ws_car.url
            else:
                ws_car = await seedream_v45_edit_image_url(
                    api_key=ws_key,
                    image_urls=[master_url],
                    prompt=wavespeed_prompt,
                    size=size_for_ws,
                    wan_edit_tier=wan_tier_n,
                )
                raw_url = ws_car.url
        except RuntimeError as e:
            last_msg = str(e)
            log.warning(
                "studio carousel shot failed owner=%s gen=%s shot=%s: %s",
                oid,
                gen_id,
                shot_i,
                last_msg,
            )
            break

        gen = await download_and_create_generation(
            session,
            owner_id=oid,
            source_url=raw_url,
            refined_prompt=f"[carousel {shot_i + 1}/{count} from gen {gen_id}]",
            output_aspect=aspect_key,
            studio_model_id=row.studio_model_id,
            refined_prompt_full=wavespeed_prompt,
            exif_camera=getattr(row, "exif_camera", None),
        )
        if gen is None:
            last_msg = "Не удалось сохранить кадр карусели — повторите позже."
            break

        await record_usage(
            session,
            user,
            billing,
            "studio_carousel_shot",
            cost_one,
            {
                "source_generation_id": gen_id,
                "shot_index": shot_i,
                "generation_id": gen.id,
                "studio_wave_profile": wave_profile_n,
                "wan_edit_tier": wan_tier_n,
            },
        )
        await session.commit()

        if arch_base:
            gtok = create_generation_image_access_token(user_id=oid, generation_id=gen.id)
            out_u = f"{arch_base}/api/studio/public-generation-image?t={quote(gtok, safe='')}"
        else:
            out_u = raw_url
        items.append(StudioCarouselItemOut(generation_id=gen.id, image_url=out_u))

    return StudioCarouselOut(items=items, message=last_msg).model_dump()


@router.get("/studio/models", response_model=list[UserStudioModelOut])
async def api_list_studio_models(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[UserStudioModelOut]:
    if not has_any_studio_access(user):
        raise HTTPException(status_code=403, detail="Нет доступа к студии")
    oid = workspace_owner_id(user)
    allowed = await member_allowed_studio_model_ids(session, user)
    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.user_id == oid)
        .options(selectinload(UserStudioModel.images))
        .order_by(UserStudioModel.id.desc())
    )
    stmt = apply_studio_model_id_filter(stmt, UserStudioModel.id, allowed)
    rows = (await session.execute(stmt)).scalars().all()
    return [_studio_model_to_out(oid, m) for m in rows]


@router.post("/studio/models/generate-profile", response_model=StudioModelProfileGenerateOut)
async def api_generate_model_profile(
    images: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioModelProfileGenerateOut:
    """Собрать JSON model_profile по референс-фотографиям (внешность, не поза/сцена)."""
    assert_permission(user, PERM_STUDIO_MODELS)
    require_workspace_owner(user)
    oid = workspace_owner_id(user)
    sub_b, llm_row, _ws_row, plan, _credits = await load_owner_studio_billing(
        session, oid
    )
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    llm_creds = studio_llm_credentials(plan=plan, llm_row=llm_row)
    uploads = list(images or [])
    if not uploads:
        raise HTTPException(
            status_code=400,
            detail="Загрузите хотя бы одно фото",
        )
    if len(uploads) > MAX_MODEL_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Не больше {MAX_MODEL_IMAGES} изображений",
        )
    image_items: list[tuple[bytes, str | None]] = []
    for up in uploads:
        raw = await up.read()
        if not raw:
            continue
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Файл «{up.filename or '?'}» слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
            )
        image_items.append((raw, up.content_type))
    if not image_items:
        raise HTTPException(
            status_code=400,
            detail="Пустые файлы",
        )
    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_model_profile_generate)
    billing = await ensure_can_consume_credits(session, user, cost)
    try:
        text = await generate_model_profile_json_from_images(
            image_items=image_items, credentials=llm_creds
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    await record_usage(
        session,
        user,
        billing,
        "studio_model_profile_generate",
        cost,
        {"image_count": len(image_items)},
    )
    await session.commit()
    return StudioModelProfileGenerateOut(profile_text=text)


@router.post("/studio/models", response_model=UserStudioModelOut)
async def api_create_studio_model(
    name: str = Form(..., min_length=1, max_length=128),
    profile_text: str = Form(""),
    images: list[UploadFile] | None = File(None),
    image_kinds: str | None = Form(None),
    camera_preset_id: str | None = Form(None),
    export_lat: str | None = Form(None),
    export_lon: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserStudioModelOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    require_workspace_owner(user)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    from app.services.plan_entitlements import assert_can_create_studio_model

    await assert_can_create_studio_model(session, oid, sub_b)
    uploads = images or []
    kinds_list = parse_image_kinds_json(image_kinds, len(uploads))
    if len(uploads) > MAX_MODEL_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Не больше {MAX_MODEL_IMAGES} изображений на модель",
        )

    lat, lon = _parse_optional_lat_lon_form(export_lat, export_lon)
    preset_norm = _coerce_camera_preset_id(camera_preset_id)

    m = UserStudioModel(
        user_id=oid,
        name=name.strip(),
        profile_text=(profile_text or "").strip(),
        camera_preset_id=preset_norm,
        export_lat=lat,
        export_lon=lon,
    )
    session.add(m)
    await session.flush()

    d = _model_dir(oid, m.id)
    d.mkdir(parents=True, exist_ok=True)

    for i, up in enumerate(uploads):
        raw = await up.read()
        if not raw:
            continue
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Файл «{up.filename or '?'}» слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
            )
        suf = Path(up.filename or "").suffix.lower()[:8]
        if suf not in _ALLOWED_SUFFIX:
            suf = ".jpg"
        fn = f"{uuid.uuid4().hex}{suf}"
        rel = f"data/studio_user_models/{oid}/{m.id}/{fn}"
        (d / fn).write_bytes(raw)
        kind = kinds_list[i] if i < len(kinds_list) else "other"
        session.add(
            UserStudioModelImage(
                studio_model_id=m.id,
                relative_path=rel,
                original_name=(up.filename or "")[:255] or None,
                image_kind=kind,
                export_selfie=False,
            )
        )

    from app.services.funnel_analytics import record_funnel_event_once

    await record_funnel_event_once(session, user=user, event="model_created")
    await session.commit()
    m2 = await _load_studio_model_owned(session, oid, m.id)
    if not m2:
        raise HTTPException(status_code=500, detail="Модель не найдена после создания")
    return _studio_model_to_out(oid, m2)


@router.patch("/studio/models/{model_id}", response_model=UserStudioModelOut)
async def api_patch_studio_model(
    model_id: int,
    body: UserStudioModelPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserStudioModelOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    m = await require_studio_model_access(session, user, model_id, load_images=True)
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")
    if "name" in data and data["name"] is not None:
        m.name = str(data["name"]).strip()
    if "profile_text" in data:
        m.profile_text = (data["profile_text"] or "").strip()
    if "camera_preset_id" in data:
        raw_c = data["camera_preset_id"]
        if raw_c is None or (isinstance(raw_c, str) and not str(raw_c).strip()):
            m.camera_preset_id = None
        else:
            m.camera_preset_id = _coerce_camera_preset_id(str(raw_c))
    if "export_lat" in data or "export_lon" in data:
        new_lat = data["export_lat"] if "export_lat" in data else m.export_lat
        new_lon = data["export_lon"] if "export_lon" in data else m.export_lon
        if new_lat is None and new_lon is None:
            m.export_lat = None
            m.export_lon = None
        elif new_lat is not None and new_lon is not None:
            if not (-90 <= new_lat <= 90 and -180 <= new_lon <= 180):
                raise HTTPException(
                    status_code=400,
                    detail="Координаты вне допустимого диапазона.",
                )
            m.export_lat, m.export_lon = new_lat, new_lon
        else:
            raise HTTPException(
                status_code=400,
                detail="Передайте export_lat и export_lon вместе или сбросьте оба (null).",
            )
    await session.commit()
    m2 = await require_studio_model_access(session, user, model_id, load_images=True)
    return _studio_model_to_out(oid, m2)


@router.post(
    "/studio/models/{model_id}/phone-exif-reference",
    response_model=PhoneExifReferenceOut,
)
async def api_upload_studio_model_phone_exif_reference(
    model_id: int,
    role: Literal["selfie", "main"] = Form(...),
    image: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> PhoneExifReferenceOut:
    """Эталон с телефона: парсинг EXIF для фронтальной или основной камеры."""
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    m = await require_studio_model_access(session, user, model_id, load_images=False)
    if image is None or not (image.filename or "").strip():
        raise HTTPException(status_code=400, detail="Выберите файл изображения (JPEG).")
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
        )
    from app.services.studio_exif_profile import (
        extract_phone_exif_profile,
        phone_exif_profile_summary,
        phone_exif_profile_to_json,
    )

    try:
        profile = extract_phone_exif_profile(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    blob = phone_exif_profile_to_json(profile)
    if role == "selfie":
        m.phone_exif_selfie_json = blob
    else:
        m.phone_exif_main_json = blob
    await session.commit()
    return PhoneExifReferenceOut(
        role=role,
        ready=True,
        summary=phone_exif_profile_summary(profile),
    )


@router.delete(
    "/studio/models/{model_id}/phone-exif-reference",
    response_model=PhoneExifReferenceOut,
)
async def api_delete_studio_model_phone_exif_reference(
    model_id: int,
    role: Literal["selfie", "main"] = Query(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> PhoneExifReferenceOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    m = await require_studio_model_access(session, user, model_id, load_images=False)
    if role == "selfie":
        m.phone_exif_selfie_json = None
    else:
        m.phone_exif_main_json = None
    await session.commit()
    return PhoneExifReferenceOut(role=role, ready=False, summary=None)


@router.post("/studio/models/{model_id}/images", response_model=UserStudioModelOut)
async def api_add_studio_model_images(
    model_id: int,
    images: list[UploadFile] | None = File(None),
    image_kinds: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserStudioModelOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    m = await require_studio_model_access(session, user, model_id, load_images=True)
    uploads = [u for u in (images or []) if u is not None]
    kinds_list = parse_image_kinds_json(image_kinds, len(uploads))
    current_n = len(m.images)
    if not uploads:
        return _studio_model_to_out(oid, m)
    if current_n + len(uploads) > MAX_MODEL_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Не больше {MAX_MODEL_IMAGES} изображений на модель (сейчас {current_n})",
        )
    d = _model_dir(oid, m.id)
    d.mkdir(parents=True, exist_ok=True)
    for i, up in enumerate(uploads):
        raw = await up.read()
        if not raw:
            continue
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Файл «{up.filename or '?'}» слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
            )
        suf = Path(up.filename or "").suffix.lower()[:8]
        if suf not in _ALLOWED_SUFFIX:
            suf = ".jpg"
        fn = f"{uuid.uuid4().hex}{suf}"
        rel = f"data/studio_user_models/{oid}/{m.id}/{fn}"
        (d / fn).write_bytes(raw)
        kind = kinds_list[i] if i < len(kinds_list) else "other"
        session.add(
            UserStudioModelImage(
                studio_model_id=m.id,
                relative_path=rel,
                original_name=(up.filename or "")[:255] or None,
                image_kind=kind,
                export_selfie=False,
            )
        )
    await session.commit()
    m2 = await require_studio_model_access(session, user, model_id, load_images=True)
    return _studio_model_to_out(oid, m2)


@router.patch("/studio/models/{model_id}/images/{image_id}", response_model=UserStudioModelOut)
async def api_patch_studio_model_image(
    model_id: int,
    image_id: int,
    body: StudioModelImagePatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserStudioModelOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    await require_studio_model_access(session, user, model_id)
    img = await session.get(UserStudioModelImage, image_id)
    if not img or img.studio_model_id != model_id:
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Передайте kind")
    if "kind" in data:
        img.image_kind = assert_studio_image_kind(data["kind"])
    await session.commit()
    m2 = await require_studio_model_access(session, user, model_id, load_images=True)
    return _studio_model_to_out(oid, m2)


@router.delete("/studio/models/{model_id}/images/{image_id}")
async def api_delete_studio_model_image(
    model_id: int,
    image_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    await require_studio_model_access(session, user, model_id)
    img = await session.get(UserStudioModelImage, image_id)
    if not img or img.studio_model_id != model_id:
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    abs_path = (BACKEND_DIR / img.relative_path).resolve()
    try:
        abs_path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный путь файла") from None
    await session.delete(img)
    await session.commit()
    if abs_path.is_file():
        abs_path.unlink(missing_ok=True)
    return {"ok": True}


@router.delete("/studio/models/{model_id}")
async def api_delete_studio_model(
    model_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    assert_permission(user, PERM_STUDIO_MODELS)
    require_workspace_owner(user)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    result = await session.execute(
        select(UserStudioModel)
        .where(UserStudioModel.id == model_id, UserStudioModel.user_id == oid)
        .options(selectinload(UserStudioModel.images))
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    backend_root = BACKEND_DIR.resolve()
    paths_to_unlink: list[Path] = []
    for img in list(m.images):
        abs_path = (BACKEND_DIR / img.relative_path).resolve()
        try:
            abs_path.relative_to(backend_root)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный путь файла") from None
        paths_to_unlink.append(abs_path)
        await session.delete(img)
    await session.delete(m)
    await session.commit()
    d = _model_dir(oid, model_id)
    for p in paths_to_unlink:
        p.unlink(missing_ok=True)
    if d.is_dir() and str(d).startswith(str(backend_root)):
        shutil.rmtree(d, ignore_errors=True)
    return {"ok": True}


@router.post("/studio/import-archive-image", response_model=StudioImportArchiveImageOut)
async def api_import_studio_archive_image(
    request: Request,
    payload: StudioImportArchiveImageIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioImportArchiveImageOut:
    """Повторно скачивает изображение по временному HTTPS URL провайдера и создаёт запись архива (без списания кредитов)."""
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    raw_u = (payload.source_url or "").strip()
    if not raw_u.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Нужна ссылка вида https://… (временный URL результата у провайдера).",
        )
    arch_base = _public_app_base(request)
    pub = (arch_base or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="Нужен публичный HTTPS (PUBLIC_APP_URL) для ссылок на архив.",
        )

    aspect_key: str | None = None
    oa = (payload.output_aspect or "").strip()
    if oa:
        try:
            aspect_key = normalize_aspect_key(oa)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    rp = ((payload.refined_prompt or "").strip() or "[import from CDN URL]")[:65536]

    existing_row: StudioGeneration | None = None
    if payload.generation_id is not None:
        existing_row = await session.get(StudioGeneration, payload.generation_id)
        if (
            not existing_row
            or existing_row.user_id != oid
            or existing_row.status
            not in (
                StudioGenerationStatus.PROVIDER_READY,
                StudioGenerationStatus.PROCESSING,
                StudioGenerationStatus.ARCHIVING,
            )
        ):
            raise HTTPException(status_code=404, detail="Запись генерации не найдена")
        if not (existing_row.source_url or "").strip():
            existing_row.source_url = raw_u[:2000]

    exif_cam = normalize_exif_camera(payload.exif_camera)
    if existing_row is not None and payload.exif_camera is None:
        exif_cam = normalize_exif_camera(getattr(existing_row, "exif_camera", None))
    gen = await download_and_create_generation(
        session,
        owner_id=oid,
        source_url=raw_u,
        refined_prompt=rp,
        output_aspect=aspect_key,
        studio_model_id=payload.studio_model_id or (
            existing_row.studio_model_id if existing_row else None
        ),
        refined_prompt_full=rp,
        existing_row=existing_row,
        exif_camera=exif_cam,
    )
    await session.commit()

    if gen is None or not generation_has_archive_file(gen):
        gid = existing_row.id if existing_row else None
        return StudioImportArchiveImageOut(
            generated_image_url=raw_u,
            generation_id=gid,
            message=user_message_when_archive_download_failed(
                "Повторная загрузка в архив пока не удалась."
            ),
        )

    out_u = _studio_archive_image_url(oid, gen.id, pub)
    return StudioImportArchiveImageOut(
        generated_image_url=out_u,
        generation_id=gen.id,
        message=None,
    )


@router.post(
    "/studio/refine-prompt",
    response_model=StudioRefinePromptOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_studio_refine_prompt(
    request: Request,
    description: str = Form(""),
    model_id: str | None = Form(None),
    image: UploadFile | None = File(None),
    existing_generation_id: str = Form(""),
    output_aspect: str = Form("9:16"),
    studio_mode: str = Form("model_scene"),
    wan_edit_tier: str = Form("standard"),
    studio_wave_profile: str = Form("nsfw"),
    generate_wavespeed: str | None = Form(None),
    wavespeed_single_reference: str | None = Form(None),
    send_pose_reference_to_wavespeed: str | None = Form("1"),
    lock_model_hairstyle: str | None = Form("1"),
    exif_camera: str = Form("main"),
    inpaint_mask: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioRefinePromptOut | JSONResponse:
    _ = request
    mode_early = _normalize_studio_mode(studio_mode)
    ref_upload_early = image is not None and (image.filename or "").strip()
    if mode_early in ("grok_compose", "model_scene") or (
        mode_early == "model" and not ref_upload_early
    ):
        # model_scene: Grok с референсом; model без рефа — только текст
        if not grok_scene_compose_configured():
            raise HTTPException(
                status_code=503,
                detail="Grok не настроен: задайте GROK_API_KEY в .env на сервере.",
            )
    else:
        skeleton = prepare_studio_prompt_skeleton()
        system_instr = load_image_studio_system()
        if not skeleton:
            raise HTTPException(
                status_code=503,
                detail="Шаблон промпта пуст: заполните backend/data/prompts/image_studio_skeleton.txt "
                "или IMAGE_STUDIO_SKELETON_INLINE",
            )
        if not system_instr:
            raise HTTPException(
                status_code=503,
                detail="Системный промпт студии пуст: заполните backend/data/prompts/image_studio_system.txt "
                "или IMAGE_STUDIO_SYSTEM_INLINE",
            )

    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)

    image_bytes: bytes | None = None
    if image is not None and (image.filename or "").strip():
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Референс слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
            )
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Пустой файл изображения")

    mask_bytes: bytes | None = None
    if inpaint_mask is not None and (inpaint_mask.filename or "").strip():
        mask_bytes = await inpaint_mask.read()
        if len(mask_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Маска слишком большая (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
            )
        if not mask_bytes:
            raise HTTPException(status_code=400, detail="Пустой файл маски")

    params: dict[str, Any] = {
        "description": (description or "").strip(),
        "model_id": model_id,
        "existing_generation_id": (existing_generation_id or "").strip(),
        "output_aspect": output_aspect,
        "studio_mode": studio_mode,
        "wan_edit_tier": wan_edit_tier,
        "studio_wave_profile": studio_wave_profile,
        "generate_wavespeed": generate_wavespeed,
        "wavespeed_single_reference": wavespeed_single_reference,
        "send_pose_reference_to_wavespeed": send_pose_reference_to_wavespeed,
        "lock_model_hairstyle": lock_model_hairstyle,
        "exif_camera": normalize_exif_camera(exif_camera),
    }
    job = await studio_jobs.create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="refine_prompt",
        params=params,
    )
    if image_bytes:
        params["image_path"] = studio_jobs.save_studio_job_file(job.id, "image.bin", image_bytes)
        params["image_mime"] = (image.content_type or "").strip() if image else ""
    if mask_bytes:
        params["mask_path"] = studio_jobs.save_studio_job_file(job.id, "mask.bin", mask_bytes)
        params["mask_mime"] = (inpaint_mask.content_type or "").strip() if inpaint_mask else ""
    if params != studio_jobs.job_params(job):
        await studio_jobs.update_studio_job_params(session, job, params)

    generation_id: int | None = None
    if _effective_generate_wavespeed(generate_wavespeed):
        try:
            mid_reserve = int(str(model_id).strip()) if model_id else None
        except ValueError:
            mid_reserve = None
        try:
            aspect_reserve = normalize_aspect_key(output_aspect)
        except ValueError:
            aspect_reserve = None
        gen_row = await reserve_studio_generation_for_job(
            session,
            owner_id=oid,
            studio_job_id=job.id,
            studio_model_id=mid_reserve,
            output_aspect=aspect_reserve,
            content_type="image/png",
            prompt_excerpt=(description or "").strip()[:2000] or None,
            exif_camera=normalize_exif_camera(exif_camera),
        )
        generation_id = gen_row.id
        params["placeholder_generation_id"] = generation_id
        await studio_jobs.update_studio_job_params(session, job, params)

    studio_jobs.schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type="refine_prompt",
            generation_id=generation_id,
        ).model_dump(),
    )


async def _accept_studio_refine_job_from_workflow(
    session: AsyncSession,
    user: User,
    *,
    plan: WorkflowGenerationPlan,
    image_bytes: bytes,
    image_mime: str,
) -> JSONResponse:
    """Workflow execute → фоновый refine_prompt (model_scene)."""
    if not grok_scene_compose_configured():
        raise HTTPException(
            status_code=503,
            detail="Grok не настроен: задайте GROK_API_KEY в .env на сервере.",
        )
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Референс слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
        )

    try:
        aspect_reserve = normalize_aspect_key(plan.output_aspect)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    params: dict[str, Any] = {
        "description": plan.description,
        "model_id": str(plan.model_id) if plan.model_id is not None else "",
        "existing_generation_id": "",
        "output_aspect": plan.output_aspect,
        "studio_mode": "model_scene" if plan.model_id is not None else "no_face",
        "wan_edit_tier": plan.wan_edit_tier,
        "studio_wave_profile": plan.studio_wave_profile,
        "generate_wavespeed": "1",
        "wavespeed_single_reference": "1",
        "send_pose_reference_to_wavespeed": "0" if plan.model_id is not None else "1",
        "lock_model_hairstyle": "0",
        "exif_camera": normalize_exif_camera(plan.exif_camera),
        "include_realism_engine": "1" if plan.realism_enabled else "0",
        "workflow_source": "1",
        "workflow_wave_model": plan.workflow_wave_model,
    }
    job = await studio_jobs.create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="refine_prompt",
        params=params,
    )
    params["image_path"] = studio_jobs.save_studio_job_file(
        job.id, "image.bin", image_bytes
    )
    params["image_mime"] = (image_mime or "image/jpeg").split(";")[0].strip()
    await studio_jobs.update_studio_job_params(session, job, params)

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
    await studio_jobs.update_studio_job_params(session, job, params)

    studio_jobs.schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type="refine_prompt",
            generation_id=gen_row.id,
        ).model_dump(),
    )


async def _studio_job_execute_refine_prompt(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    p = studio_jobs.job_params(job)
    description = str(p.get("description") or "")
    model_id = p.get("model_id")
    existing_generation_id = str(p.get("existing_generation_id") or "")
    output_aspect = str(p.get("output_aspect") or "9:16")
    studio_mode = str(p.get("studio_mode") or "model")
    wan_edit_tier = str(p.get("wan_edit_tier") or "standard")
    studio_wave_profile = str(p.get("studio_wave_profile") or "nsfw")
    generate_wavespeed = p.get("generate_wavespeed")
    wavespeed_single_reference = p.get("wavespeed_single_reference")
    send_pose_reference_to_wavespeed = p.get("send_pose_reference_to_wavespeed")
    lock_model_hairstyle = p.get("lock_model_hairstyle")
    exif_camera_job = normalize_exif_camera(str(p.get("exif_camera") or "main"))
    include_realism_engine = str(p.get("include_realism_engine") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    workflow_source = str(p.get("workflow_source") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    workflow_wave_model = str(p.get("workflow_wave_model") or "").strip().lower()

    system_instr = load_image_studio_system()
    if not system_instr:
        raise RuntimeError(
            "Системный промпт студии пуст: заполните backend/data/prompts/image_studio_system.txt "
            "или IMAGE_STUDIO_SYSTEM_INLINE"
        )

    desc = (description or "").strip()
    parsed_mid = _parse_optional_model_id(model_id if model_id is not None else None)
    try:
        aspect_key = normalize_aspect_key(output_aspect)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    mode_n = _normalize_studio_mode(studio_mode)
    raw_model_id_photo_edit: int | None = None
    if mode_n == "photo_edit":
        raw_model_id_photo_edit = parsed_mid
        mid = None
    else:
        mid = parsed_mid

    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    sub_b, llm_row, ws_row, plan, _credits = await load_owner_studio_billing(
        session, oid
    )
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    llm_creds = studio_llm_credentials(plan=plan, llm_row=llm_row)
    wan_tier_n = _normalize_wan_edit_tier(wan_edit_tier)
    wave_profile_n = _normalize_studio_wave_profile(studio_wave_profile)
    do_wavespeed = _effective_generate_wavespeed(generate_wavespeed)

    image_bytes: bytes | None = None
    image_mime: str | None = None
    if p.get("image_path"):
        image_bytes = studio_jobs.load_studio_job_file(str(p["image_path"]))
        raw_mime = str(p.get("image_mime") or "").strip()
        image_mime = raw_mime or None

    mask_bytes: bytes | None = None
    mask_mime: str | None = None
    if p.get("mask_path"):
        mask_bytes = studio_jobs.load_studio_job_file(str(p["mask_path"]))
        raw_mm = str(p.get("mask_mime") or "").strip()
        mask_mime = raw_mm or None

    if (
        mode_n == "photo_edit"
        and mask_bytes
        and settings.studio_regional_masked_edit
        and raw_model_id_photo_edit is not None
    ):
        mid = raw_model_id_photo_edit

    existing_gen_from_archive: int | None = None
    if mode_n == "photo_edit":
        raw_arch = (existing_generation_id or "").strip()
        if raw_arch:
            try:
                existing_gen_from_archive = int(raw_arch)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Некорректный номер генерации из архива.",
                ) from None

    if (
        mode_n == "photo_edit"
        and image_bytes
        and existing_gen_from_archive is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="Для доработки выберите либо файл с устройства, либо снимок из архива — не оба.",
        )

    if mode_n == "photo_edit" and existing_gen_from_archive is not None:
        _garch, arch_bytes, arch_mime = await _load_owned_generation_still_for_motion(
            session,
            owner_id=oid,
            generation_id=existing_gen_from_archive,
            actor=user,
        )
        image_bytes = arch_bytes
        image_mime = arch_mime

    sm_loaded: UserStudioModel | None = None
    model_profile_text: str | None = None
    if mid is not None:
        sm_loaded = await require_studio_model_access(
            session, user, mid, load_images=True
        )
        model_profile_text = (sm_loaded.profile_text or "").strip() or None

    if mode_n == "photo_edit" and not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="В режиме «Доработать фото» загрузите файл или выберите снимок из архива вкладки «Картинки».",
        )
    if mode_n == "photo_edit" and not desc.strip():
        raise HTTPException(
            status_code=400,
            detail="Опишите, что нужно изменить или исправить на фото.",
        )
    if mode_n == "no_face" and mid is None and not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="В режиме «Без лица» выберите сохранённую модель или загрузите референс.",
        )
    if mode_n == "face_swap" and not image_bytes:
        raise HTTPException(
            status_code=400,
            detail='Режим «Face swap»: загрузите фото‑исходник (сцена + человек для замены).',
        )
    if mode_n == "face_swap" and mid is None:
        raise HTTPException(
            status_code=400,
            detail='Режим «Face swap»: выберите сохранённую модель студии.',
        )
    if mode_n == "model_scene":
        if not grok_scene_compose_configured():
            raise HTTPException(
                status_code=503,
                detail="Режим «Основная» использует Grok: задайте GROK_API_KEY на сервере.",
            )
        if mid is None:
            raise HTTPException(
                status_code=400,
                detail="В режиме «Основная» выберите сохранённую модель.",
            )
        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="В режиме «Основная» загрузите референс сцены — для Grok (поза, свет, кадр).",
            )
        if mask_bytes:
            raise HTTPException(
                status_code=400,
                detail="Режим «Основная» не поддерживает маску inpaint — снимите маску.",
            )
    if mode_n == "model" and not image_bytes:
        if not (desc or "").strip():
            raise HTTPException(
                status_code=400,
                detail="В режиме «По промту» опишите сцену в поле промпта.",
            )
        if not grok_scene_compose_configured():
            raise HTTPException(
                status_code=503,
                detail="Режим «По промту» использует Grok (как «Основная»): задайте GROK_API_KEY на сервере.",
            )
    if mode_n == "grok_compose":
        if not grok_scene_compose_configured():
            raise HTTPException(
                status_code=503,
                detail="Grok не настроен: задайте GROK_API_KEY в .env на сервере.",
            )
        if mid is None:
            raise HTTPException(
                status_code=400,
                detail="В режиме «Grok: сцена» выберите сохранённую модель.",
            )
        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="В режиме «Grok: сцена» загрузите референс сцены.",
            )
        if mask_bytes:
            raise HTTPException(
                status_code=400,
                detail="Режим «Grok: сцена» не поддерживает маску inpaint — снимите маску.",
            )

    if mode_n != "grok_compose" and not desc and not image_bytes and not model_profile_text:
        raise HTTPException(
            status_code=400,
            detail="Добавьте описание, референс и/или выберите сохранённую модель",
        )

    if mask_bytes and not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Маска задаёт область на изображении — загрузите файл референса или в режиме "
            "«Доработать фото» выберите снимок из архива вкладки «Картинки».",
        )

    imgs_model: list[UserStudioModelImage] = []
    if sm_loaded is not None:
        imgs_model = sort_model_images_for_studio(list(sm_loaded.images))
    imgs_for_ws = model_images_for_wavespeed_profile(imgs_model, wave_profile_n)

    if (
        mode_n == "face_swap"
        and imgs_model
        and not imgs_for_ws
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "В режиме «Face swap» для «Обычных фото» нужны хотя бы подходящие для API снимки модели "
                "(не только тип «интимная анатомия»). Добавьте портрет/тело к модели "
                "или переключите тип генерации на «NSFW (WAN / Seedream)»."
            ),
        )

    photo_edit_regional_identity_requested = bool(
        mode_n == "photo_edit"
        and bool(mask_bytes)
        and settings.studio_regional_masked_edit
        and raw_model_id_photo_edit is not None
        and bool(imgs_for_ws)
    )

    ws_key = _studio_refine_wavespeed_preflight(
        do_wavespeed=do_wavespeed,
        plan=plan,
        ws_row=ws_row,
        owner_subscription=sub_b,
        mode_n=mode_n,
        mid=mid,
        sm_loaded=sm_loaded,
        imgs_model=imgs_model,
        image_bytes=image_bytes,
        wave_profile=wave_profile_n,
    )

    base_studio_credit = (
        settings.credit_cost_studio_inpaint
        if mask_bytes
        else settings.credit_cost_studio_prompt_refine
    )
    cost = apply_studio_credit_cost(plan, base_studio_credit)
    billing = await ensure_can_consume_credits(session, user, cost)

    gen_row: StudioGeneration | None = None
    wavespeed_task_id: str | None = None
    if do_wavespeed:
        gen_row = await find_studio_generation_by_job_id(session, job.id)
        if gen_row is None:
            gen_row = await begin_studio_generation_run(
                session,
                owner_id=oid,
                output_aspect=aspect_key,
                studio_model_id=mid,
                studio_job_id=job.id,
                exif_camera=exif_camera_job,
            )
        else:
            gen_row.exif_camera = exif_camera_job
            session.add(gen_row)
            await session.flush()

    lock_hair_req = _truthy_lock_model_hairstyle(lock_model_hairstyle)
    effective_lock_hairstyle = bool(lock_hair_req) if image_bytes else True
    if mode_n == "model_scene":
        send_pose_to_ws = False
    elif mode_n == "grok_compose":
        send_pose_to_ws = True
    else:
        send_pose_to_ws = _truthy_send_pose_reference_to_wavespeed(
            send_pose_reference_to_wavespeed
        )

    reference_scene: str | None = None
    prompt_brief_mode = "full"
    grok_negative_extra: str | None = None
    try:
        if mode_n == "model_scene":
            assert image_bytes is not None
            from app.services.plan_entitlements import assert_grok_allowed, record_grok_usage

            await assert_grok_allowed(session, oid, sub_b)
            await record_grok_usage(session, oid, source="model_scene")
            grok_creds = grok_motion_studio_credentials()
            composed = await grok_compose_studio_main_scene(
                user_ref_bytes=image_bytes,
                user_ref_mime=image_mime,
                model_images=imgs_model,
                model_profile_text=model_profile_text,
                wave_profile=wave_profile_n,
                user_notes=desc,
                lock_hairstyle=effective_lock_hairstyle,
                credentials=grok_creds,
            )
            refined = composed.wavespeed_scene_prompt
            reference_scene = composed.reference_scene_lock or None
            grok_negative_extra = composed.negative_prompt or None
            prompt_brief_mode = "grok_main_prose"
            if gen_row is not None:
                gen_row.refined_prompt = refined
                gen_row.prompt_excerpt = (refined[:2000] if refined else None) or None
                session.add(gen_row)
                await session.flush()
        elif mode_n == "grok_compose":
            assert image_bytes is not None
            from app.services.plan_entitlements import assert_grok_allowed, record_grok_usage

            await assert_grok_allowed(session, oid, sub_b)
            await record_grok_usage(session, oid, source="grok_compose")
            grok_creds = grok_motion_studio_credentials()
            composed = await grok_compose_studio_scene(
                user_ref_bytes=image_bytes,
                user_ref_mime=image_mime,
                model_images=imgs_model,
                model_profile_text=model_profile_text,
                wave_profile=wave_profile_n,
                user_notes=desc,
                lock_hairstyle=effective_lock_hairstyle,
                credentials=grok_creds,
                standalone_scene_prompt=False,
            )
            refined = composed.wavespeed_scene_prompt
            reference_scene = composed.reference_scene_lock or None
            grok_negative_extra = composed.negative_prompt or None
            prompt_brief_mode = "grok_composed"
            if gen_row is not None:
                gen_row.refined_prompt = refined
                gen_row.prompt_excerpt = (refined[:2000] if refined else None) or None
                session.add(gen_row)
                await session.flush()
        elif mode_n == "model" and not image_bytes:
            from app.services.plan_entitlements import assert_grok_allowed, record_grok_usage

            await assert_grok_allowed(session, oid, sub_b)
            await record_grok_usage(session, oid, source="model_prompt")
            grok_creds = grok_motion_studio_credentials()
            composed = await grok_compose_studio_text_scene(
                model_images=imgs_model,
                model_profile_text=model_profile_text,
                wave_profile=wave_profile_n,
                user_notes=desc,
                credentials=grok_creds,
            )
            refined = composed.wavespeed_scene_prompt
            reference_scene = composed.reference_scene_lock or None
            grok_negative_extra = composed.negative_prompt or None
            prompt_brief_mode = "grok_composed_text"
            if gen_row is not None:
                gen_row.refined_prompt = refined
                gen_row.prompt_excerpt = (refined[:2000] if refined else None) or None
                session.add(gen_row)
                await session.flush()
        else:
            if image_bytes:
                reference_scene = await describe_reference_image_openai(
                    image_bytes=image_bytes,
                    image_media_type=image_mime,
                    hairstyle_from_pose_reference=not effective_lock_hairstyle,
                    no_face_framing=(mode_n == "no_face"),
                    credentials=llm_creds,
                )
            ref_photo_block = (
                None
                if mode_n == "photo_edit" and not photo_edit_regional_identity_requested
                else (model_reference_photos_block(imgs_for_ws) if imgs_for_ws else None)
            )
            prompt_brief_mode = resolve_studio_prompt_brief_mode(
                studio_mode=mode_n,
                has_reference_scene=bool(reference_scene),
                has_uploaded_reference_bytes=bool(image_bytes),
                send_pose_reference_to_wavespeed=send_pose_to_ws,
            )
            skeleton = prepare_studio_prompt_skeleton_for_brief(prompt_brief_mode)
            if not skeleton:
                raise RuntimeError(
                    "Шаблон промпта пуст: заполните backend/data/prompts/image_studio_skeleton.txt "
                    "или IMAGE_STUDIO_SKELETON_INLINE"
                )
            refined = await refine_prompt_via_openai(
                system_instruction=system_instr,
                skeleton=skeleton,
                user_text=desc,
                reference_scene_description=reference_scene,
                model_profile_text=(
                    None
                    if mode_n == "photo_edit" and not photo_edit_regional_identity_requested
                    else model_profile_text
                ),
                model_reference_photos=ref_photo_block,
                output_aspect_key=aspect_key,
                studio_mode=mode_n,
                lock_model_hairstyle=effective_lock_hairstyle,
                prompt_brief_mode=prompt_brief_mode,
                credentials=llm_creds,
            )
            if gen_row is not None:
                gen_row.refined_prompt = refined
                gen_row.prompt_excerpt = (refined[:2000] if refined else None) or None
                session.add(gen_row)
                await session.flush()
    except RuntimeError as e:
        if gen_row is not None:
            await mark_studio_generation_failed(
                session, gen_row, message=str(e), step="llm"
            )
        raise HTTPException(status_code=502, detail=str(e)) from e

    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    regional_composed_png: bytes | None = None
    if do_wavespeed:
        pub = (settings.public_app_url or "").strip().rstrip("/")
        if mask_bytes:
            assert image_bytes is not None
            try:
                from app.services.studio_masked_regional_edit import (
                    composite_fullframe_edit_preserving_unmasked,
                    studio_mask_png_bytes_aligned_to_reference,
                )

                try:
                    mask_bytes_upload = studio_mask_png_bytes_aligned_to_reference(
                        image_bytes, mask_bytes
                    )
                    mask_upload_mime = "image/png"
                except Exception as e_align:
                    log.warning("studio inpaint mask align skipped: %s", e_align)
                    mask_bytes_upload = mask_bytes
                    mask_upload_mime = mask_mime or "image/png"

                if settings.studio_regional_masked_edit:
                    fid_base = save_pose_reference_bytes(
                        owner_id=oid,
                        raw=image_bytes,
                        content_type=(image_mime or "image/jpeg"),
                    )
                    btok = create_pose_reference_access_token(
                        user_id=oid, file_id=fid_base
                    )
                    base_url_wm = (
                        f"{pub}/api/studio/public-pose-reference?t={quote(btok, safe='')}"
                    )

                    fid_mask_wm = save_pose_reference_bytes(
                        owner_id=oid,
                        raw=mask_bytes_upload,
                        content_type=mask_upload_mime,
                    )
                    mtk = create_pose_reference_access_token(
                        user_id=oid, file_id=fid_mask_wm
                    )
                    mask_url_wm = (
                        f"{pub}/api/studio/public-pose-reference?t={quote(mtk, safe='')}"
                    )

                    attach_mask_mr = False
                    if mode_n in ("model", "model_scene"):
                        attach_mask_mr = bool(imgs_model)
                    elif mode_n == "face_swap":
                        attach_mask_mr = bool(imgs_model)
                    elif mode_n == "no_face":
                        attach_mask_mr = bool(sm_loaded and imgs_model)
                    elif photo_edit_regional_identity_requested:
                        attach_mask_mr = True

                    identity_urls_wm: list[str] = []
                    if attach_mask_mr:
                        imgs_wm_order = (
                            sort_model_images_for_wan_identity(imgs_for_ws)
                            if wave_profile_n == "nsfw"
                            else imgs_for_ws
                        )
                        for im_wm in imgs_wm_order:
                            if len(identity_urls_wm) >= 7:
                                break
                            tk_wm = create_model_image_access_token(
                                user_id=oid, image_id=im_wm.id
                            )
                            identity_urls_wm.append(
                                f"{pub}/api/studio/public-model-image?t={quote(tk_wm, safe='')}"
                            )

                    wan_image_urls_wm = _masked_full_frame_wan_image_urls(
                        base_url_wm,
                        mask_url_wm,
                        identity_urls_wm,
                        wave_profile_n=wave_profile_n,
                        wavespeed_single_reference=wavespeed_single_reference,
                    )

                    nano_image_urls_wm = _masked_full_frame_nano_image_urls_from_wan_list(
                        wan_image_urls_wm,
                        studio_mode=mode_n,
                    )

                    if wave_profile_n == "regular":
                        ws_mask_prompt = finalize_masked_fullframe_nano_prompt(
                            refined,
                            studio_mode=mode_n,
                            lock_model_hairstyle=effective_lock_hairstyle,
                            attach_identity_refs=attach_mask_mr,
                        )
                    else:
                        ws_mask_prompt = finalize_masked_fullframe_wan_prompt(
                            refined,
                            studio_mode=mode_n,
                            lock_model_hairstyle=effective_lock_hairstyle,
                            attach_identity_refs=attach_mask_mr,
                        )

                    if settings.wavespeed_seedream_omit_size:
                        size_for_wm: str | None = None
                    else:
                        size_for_wm = wavespeed_size_string(aspect_key)

                    if wave_profile_n == "regular":
                        ws_res = await nano_banana_pro_edit_image_url(
                            api_key=ws_key,
                            image_urls=nano_image_urls_wm,
                            prompt=ws_mask_prompt,
                            aspect_ratio=aspect_key,
                            wave_profile=wave_profile_n,
                            reference_scene_description=reference_scene,
                        )
                    else:
                        ws_res = await seedream_v45_edit_image_url(
                            api_key=ws_key,
                            image_urls=wan_image_urls_wm,
                            prompt=ws_mask_prompt,
                            size=size_for_wm,
                            wan_edit_tier=wan_tier_n,
                        )
                    generated_image_url = ws_res.url
                    wavespeed_task_id = ws_res.task_id or wavespeed_task_id

                    if (
                        generated_image_url
                        and settings.studio_masked_fullframe_preserve_unmasked
                    ):
                        ed_blend, dl_blend_err = await _download_image_bytes_best_effort(
                            generated_image_url
                        )
                        if ed_blend:
                            try:
                                blend_fn = partial(
                                    composite_fullframe_edit_preserving_unmasked,
                                    feather_radius=float(
                                        settings.studio_masked_fullframe_blend_feather_radius
                                    ),
                                )
                                regional_composed_png = await anyio.to_thread.run_sync(
                                    blend_fn,
                                    image_bytes,
                                    ed_blend,
                                    mask_bytes_upload,
                                )
                                generated_image_url = None
                            except Exception as e_blend:
                                log.warning(
                                    "studio mask fullframe preserve-unmasked blend failed, keeping CDN URL: %s",
                                    e_blend,
                                    exc_info=True,
                                )
                        elif dl_blend_err:
                            log.warning(
                                "studio mask fullframe blend skipped (download failed): %s",
                                dl_blend_err,
                            )
                else:
                    fid_img = save_pose_reference_bytes(
                        owner_id=oid,
                        raw=image_bytes,
                        content_type=image_mime,
                    )
                    ptok = create_pose_reference_access_token(
                        user_id=oid, file_id=fid_img
                    )
                    src_url = f"{pub}/api/studio/public-pose-reference?t={quote(ptok, safe='')}"
                    fid_mask = save_pose_reference_bytes(
                        owner_id=oid,
                        raw=mask_bytes_upload,
                        content_type=mask_upload_mime,
                    )
                    mtok = create_pose_reference_access_token(
                        user_id=oid, file_id=fid_mask
                    )
                    mask_url = (
                        f"{pub}/api/studio/public-pose-reference?t={quote(mtok, safe='')}"
                    )
                    inpaint_prompt = _z_image_inpaint_studio_prompt(
                        refined=refined, user_description=desc
                    )
                    size_inpaint: str | None = (
                        None
                        if settings.wavespeed_z_image_inpaint_omit_size
                        else wavespeed_size_string(aspect_key)
                    )
                    ws_res = await z_image_turbo_inpaint_image_url(
                        api_key=ws_key,
                        image_url=src_url,
                        mask_image_url=mask_url,
                        prompt=inpaint_prompt,
                        size=size_inpaint,
                    )
                    generated_image_url = ws_res.url
                    wavespeed_task_id = ws_res.task_id or wavespeed_task_id
            except RuntimeError as e:
                wavespeed_message = str(e)
                low = wavespeed_message.lower()
                used_z = not settings.studio_regional_masked_edit
                if used_z:
                    if "something went wrong" in low or "try again" in low:
                        wavespeed_message = (
                            f"{wavespeed_message} "
                            "Проверьте баланс wavespeed.ai, что маска того же размера что и изображение "
                            "(белое = зона правки, чёрное = без изменений) и публичный HTTPS PUBLIC_APP_URL."
                        )
                    log.warning(
                        "WaveSpeed Z-Image inpaint failed (owner_id=%s actor=%s): %s",
                        oid,
                        user.id,
                        wavespeed_message,
                    )
                else:
                    if wave_profile_n == "regular" and (
                        "safety" in low
                        or "guideline" in low
                        or "nsfw" in low
                        or "policy" in low
                    ):
                        wavespeed_message = (
                            f"{wavespeed_message} "
                            "Для режима «Обычные фотографии» действуют ограничения Google; "
                            "для контента без этих лимитов переключите тип генерации на «NSFW» "
                            "(редактор из настроек сервера)."
                        )
                    if "something went wrong" in low or "try again" in low:
                        common = (
                            f"{wavespeed_message} "
                            "Часто это: баланс/лимит на wavespeed.ai, кратковременный сбой API "
                            "(см. status.wavespeed.ai) или слишком тяжёлый запрос. "
                            "Повторите позже. "
                        )
                        if wave_profile_n == "regular":
                            wavespeed_message = common + (
                                "При таймаутах Nano Banana Pro попробуйте "
                                "WAVESPEED_NANO_BANANA_PRO_SYNC=false в backend/.env."
                            )
                        else:
                            wavespeed_message = common + (
                                "Если сбой стабилен — в backend/.env поставьте "
                                "WAVESPEED_SEEDREAM_SYNC=false (режим с опросом вместо sync); "
                                "проверьте WAVESPEED_SEEDREAM_OMIT_SIZE."
                            )
                    log.warning(
                        "WaveSpeed full-frame mask edit failed (owner_id=%s actor=%s): %s",
                        oid,
                        user.id,
                        wavespeed_message,
                    )
            except httpx.RequestError as e:
                log.warning(
                    "WaveSpeed HTTP client failure (masked studio owner_id=%s): %s",
                    oid,
                    e,
                    exc_info=True,
                )
                wavespeed_message = (
                    f"Не удалось связаться с WaveSpeed из-за сети или таймаута ({type(e).__name__}). "
                    "Проверьте выход сервера в интернет (и прокси, если есть) и повторите позже; "
                    "детали см. в логах backend."
                )
            except Exception as e:
                if settings.studio_regional_masked_edit and mask_bytes:
                    log.exception(
                        "studio masked fullframe pipeline failed (owner_id=%s)",
                        oid,
                    )
                    raw = str(e).strip().replace("\n", " ")
                    slim = raw[:220] + ("…" if len(raw) > 220 else "") if raw else ""
                    wavespeed_message = (
                        "Редактирование с маской (полный кадр + второй вход — маска для Nano/WAN) не удалось. "
                        + (
                            f"Техника: {type(e).__name__}: {slim}. "
                            if slim
                            else ""
                        )
                        + "Частые причины: маска не совпадает по размеру с фото, слишком большой файл, "
                        "или сбой на стороне API. Если сообщение повторится — см. трассировку в логе сервера."
                    )
                elif mask_bytes:
                    log.warning(
                        "studio inpaint: не удалось сохранить файлы или вызвать API: %s",
                        e,
                    )
                    wavespeed_message = (
                        "Не удалось подготовить inpaint (референс или маска). "
                        "Повторите или уберите маску."
                    )
        else:
            image_urls: list[str] = []
            user_pose_ref_prepended = False
            ws_identity_legend: str | None = None
            if image_bytes and send_pose_to_ws:
                try:
                    fid = save_pose_reference_bytes(
                        owner_id=oid,
                        raw=image_bytes,
                        content_type=image_mime,
                    )
                    ptok = create_pose_reference_access_token(
                        user_id=oid, file_id=fid
                    )
                    image_urls.append(
                        f"{pub}/api/studio/public-pose-reference?t={quote(ptok, safe='')}"
                    )
                    user_pose_ref_prepended = True
                except Exception as e:
                    log.warning(
                        "studio: не удалось сохранить референс для WaveSpeed: %s",
                        e,
                    )
                    wavespeed_message = (
                        "Не удалось подготовить загруженный референс для WaveSpeed. "
                        "Повторите или уберите файл."
                    )
            elif image_bytes and not send_pose_to_ws and mode_n in (
                "face_swap",
                "photo_edit",
            ):
                wavespeed_message = (
                    "В режимах «Подмена лица» и «Доработать фото» загруженный снимок "
                    "обязательно уходит в WaveSpeed — отключить референс нельзя."
                )

            if not wavespeed_message:
                attach_model_urls = False
                grok_ws_identity: list[UserStudioModelImage] = []
                if mode_n == "grok_compose":
                    grok_ws_identity = select_grok_compose_wavespeed_identity_images(
                        imgs_for_ws,
                        pose_reference_nude=reference_pose_is_nude_or_minimal_coverage(
                            reference_scene
                        ),
                    )
                    attach_model_urls = bool(grok_ws_identity)
                elif mode_n == "model_scene":
                    attach_model_urls = bool(
                        select_model_scene_wavespeed_identity_images(
                            imgs_for_ws, wave_profile=wave_profile_n
                        )
                    )
                elif mode_n == "model":
                    if image_bytes:
                        attach_model_urls = bool(imgs_model)
                    else:
                        prompt_only_ws = select_prompt_only_wavespeed_identity_images(
                            imgs_for_ws, wave_profile=wave_profile_n
                        )
                        attach_model_urls = bool(prompt_only_ws)
                elif mode_n == "face_swap":
                    attach_model_urls = bool(imgs_model)
                elif mode_n == "no_face":
                    attach_model_urls = bool(sm_loaded and imgs_model)

                if attach_model_urls:
                    if mode_n == "grok_compose":
                        imgs_ws_order = grok_ws_identity
                    elif mode_n == "model_scene":
                        imgs_ws_order = select_model_scene_wavespeed_identity_images(
                            imgs_for_ws, wave_profile=wave_profile_n
                        )
                        ws_identity_legend = wavespeed_identity_image_legend(imgs_ws_order)
                    elif mode_n == "model" and not image_bytes:
                        imgs_ws_order = select_prompt_only_wavespeed_identity_images(
                            imgs_for_ws, wave_profile=wave_profile_n
                        )
                    elif wave_profile_n == "nsfw" and user_pose_ref_prepended:
                        imgs_ws_order = select_wan_identity_images_with_pose_ref(
                            imgs_for_ws,
                            max_count=3,
                            pose_reference_nude=reference_pose_is_nude_or_minimal_coverage(
                                reference_scene
                            ),
                        )
                    else:
                        imgs_ws_order = (
                            sort_model_images_for_wan_identity(imgs_for_ws)
                            if wave_profile_n == "nsfw"
                            else imgs_for_ws
                        )
                    for im in imgs_ws_order[:10]:
                        tok = create_model_image_access_token(
                            user_id=oid, image_id=im.id
                        )
                        image_urls.append(
                            f"{pub}/api/studio/public-model-image?t={quote(tok, safe='')}"
                        )

                if not image_urls:
                    if mode_n == "model_scene":
                        wavespeed_message = (
                            "Нет фото модели для WaveSpeed — добавьте развёртку, тело или лицо в кабинете модели."
                        )
                    elif image_bytes and not send_pose_to_ws:
                        wavespeed_message = (
                            "Референс в WaveSpeed отключён — нужна модель с фото в кабинете "
                            "или включите «Отправить референс в генерацию»."
                        )
                    else:
                        wavespeed_message = (
                            "Нет изображений для WaveSpeed — проверьте режим, модель и файлы."
                        )

            if not wavespeed_message and image_urls:
                if wave_profile_n == "nsfw" and _truthy_wavespeed_flag(
                    wavespeed_single_reference
                ):
                    if user_pose_ref_prepended and len(image_urls) >= 2:
                        image_urls = image_urls[:4]
                    else:
                        image_urls = image_urls[:9]

                pose_is_last_after_reorder = False
                if wave_profile_n == "regular":
                    pose_is_last_after_reorder = bool(
                        user_pose_ref_prepended
                        and mode_n != "photo_edit"
                        and len(image_urls) >= 2
                    )
                    image_urls = _nano_banana_reorder_image_urls(
                        image_urls,
                        studio_mode=mode_n,
                        user_pose_ref_prepended=user_pose_ref_prepended,
                    )
                wavespeed_prompt = assemble_wavespeed_image_edit_prompt(
                    refined,
                    studio_mode=mode_n,
                    user_pose_in_api=user_pose_ref_prepended,
                    user_pose_is_last=pose_is_last_after_reorder,
                    lock_model_hairstyle=effective_lock_hairstyle,
                    prompt_brief_mode=prompt_brief_mode,
                    model_profile_text=model_profile_text,
                    wave_profile=wave_profile_n,
                    reference_scene_description=reference_scene,
                    extra_negative=grok_negative_extra,
                    output_aspect_key=aspect_key,
                    wavespeed_identity_legend=ws_identity_legend,
                    include_realism_engine=include_realism_engine,
                )
                size_for_ws: str | None
                if settings.wavespeed_seedream_omit_size:
                    size_for_ws = None
                else:
                    size_for_ws = wavespeed_size_string(aspect_key)
                try:
                    if workflow_source and workflow_wave_model:
                        from app.services.wavespeed_client import workflow_edit_image_url

                        ws_res = await workflow_edit_image_url(
                            api_key=ws_key,
                            wave_model_id=workflow_wave_model,
                            image_urls=image_urls,
                            prompt=wavespeed_prompt,
                            aspect_ratio=aspect_key,
                            wan_edit_tier=wan_tier_n,
                            wave_profile=wave_profile_n,
                            reference_scene_description=reference_scene,
                            size=size_for_ws,
                        )
                    elif wave_profile_n == "regular":
                        ws_res = await nano_banana_pro_edit_image_url(
                            api_key=ws_key,
                            image_urls=image_urls,
                            prompt=wavespeed_prompt,
                            aspect_ratio=aspect_key,
                            wave_profile=wave_profile_n,
                            reference_scene_description=reference_scene,
                        )
                    else:
                        ws_res = await seedream_v45_edit_image_url(
                            api_key=ws_key,
                            image_urls=image_urls,
                            prompt=wavespeed_prompt,
                            size=size_for_ws,
                            wan_edit_tier=wan_tier_n,
                        )
                    generated_image_url = ws_res.url
                    wavespeed_task_id = ws_res.task_id or wavespeed_task_id
                except RuntimeError as e:
                    wavespeed_message = _append_nano_banana_error_hint(
                        str(e), wave_profile=wave_profile_n
                    )
                    low = wavespeed_message.lower()
                    if wave_profile_n == "regular" and (
                        "safety" in low
                        or "guideline" in low
                        or "nsfw" in low
                        or "policy" in low
                    ):
                        wavespeed_message = (
                            f"{wavespeed_message} "
                            "Для режима «Обычные фотографии» действуют ограничения Google; "
                            "для контента без этих лимитов переключите тип генерации на «NSFW» "
                            "(редактор из настроек сервера)."
                        )
                    if "something went wrong" in low or "try again" in low:
                        common = (
                            f"{wavespeed_message} "
                            "Часто это: баланс/лимит на wavespeed.ai, кратковременный сбой API "
                            "(см. status.wavespeed.ai) или слишком тяжёлый/нестандартный запрос. "
                            "Повторите позже. "
                        )
                        if wave_profile_n == "regular":
                            wavespeed_message = common + (
                                "При таймаутах Nano Banana Pro попробуйте "
                                "WAVESPEED_NANO_BANANA_PRO_SYNC=false в backend/.env."
                            )
                        else:
                            wavespeed_message = common + (
                                "Если сбой стабилен — в backend/.env поставьте "
                                "WAVESPEED_SEEDREAM_SYNC=false (режим с опросом вместо sync) и перезапустите API. "
                                f"Публичный референс: {pub}/api/studio/public-model-image?… (без логина — 200 и картинка). "
                                "Если в Playground тот же JSON срабатывает, а в интеграции нет — "
                                "попробуйте WAVESPEED_SEEDREAM_OMIT_SIZE=true (как пустой size на сайте)."
                            )
                    log.warning(
                        "WaveSpeed generation failed (owner_id=%s actor=%s): %s",
                        oid,
                        user.id,
                        wavespeed_message,
                    )

    generation_id: int | None = None
    gen_mid = mid
    if do_wavespeed or regional_composed_png or generated_image_url:
        finished_row, cdn_preview = await studio_finish_image_generation(
            session,
            gen_row=gen_row,
            owner_id=oid,
            studio_model_id=gen_mid,
            output_aspect=aspect_key,
            refined_prompt=refined,
            source_url=generated_image_url,
            wavespeed_task_id=wavespeed_task_id,
            uploaded_bytes=regional_composed_png,
            uploaded_content_type="image/png",
        )
        if finished_row is not None:
            generation_id = finished_row.id
            arch_base = _public_app_base(None)
            if generation_has_archive_file(finished_row) and arch_base:
                generated_image_url = _studio_archive_image_url(
                    oid, finished_row.id, arch_base
                )
            elif cdn_preview:
                generated_image_url = cdn_preview
            elif finished_row.source_url:
                generated_image_url = finished_row.source_url.strip()
            if (
                finished_row.status == StudioGenerationStatus.PROVIDER_READY
                and not generation_has_archive_file(finished_row)
            ):
                wavespeed_message = user_message_when_archive_download_failed(
                    wavespeed_message
                )

    if do_wavespeed and not (generated_image_url or "").strip():
        if gen_row is not None:
            await mark_studio_generation_failed(
                session,
                gen_row,
                message=wavespeed_message or "WaveSpeed не вернул изображение",
                step="wavespeed",
            )
        raise RuntimeError(
            wavespeed_message or "WaveSpeed не вернул изображение"
        )

    await record_usage(
        session,
        user,
        billing,
        "studio_prompt_refine",
        cost,
        {
            "has_image": bool(image_bytes),
            "studio_model_id": mid,
            "two_step": bool(image_bytes),
            "wavespeed": bool(generated_image_url),
            "generation_id": generation_id,
            "studio_mode": mode_n,
            "wan_edit_tier": wan_tier_n,
            "studio_wave_profile": wave_profile_n,
            "lock_model_hairstyle": effective_lock_hairstyle,
            "lock_model_hairstyle_requested": lock_hair_req,
            "send_pose_reference_to_wavespeed": send_pose_to_ws,
            "prompt_brief_mode": prompt_brief_mode,
            "inpaint_mask": bool(mask_bytes),
            "regional_masked_compose_ready": regional_composed_png is not None,
            "masked_edit_engine": (
                (
                    "z_image_inpaint"
                    if not settings.studio_regional_masked_edit
                    else (
                        "nano_wan_multimage_mask_pair_blend"
                        if regional_composed_png is not None
                        else "nano_wan_multimage_mask_pair"
                    )
                )
                if mask_bytes
                else None
            ),
        },
    )
    await session.commit()

    return StudioRefinePromptOut(
        refined_prompt=refined,
        reference_scene_description=reference_scene,
        generated_image_url=generated_image_url,
        wavespeed_message=wavespeed_message,
        generation_id=generation_id,
    ).model_dump()


async def _load_owned_generation_still_for_motion(
    session: AsyncSession,
    *,
    owner_id: int,
    generation_id: int,
    actor: User | None = None,
) -> tuple[StudioGeneration, bytes, str]:
    row = await session.get(StudioGeneration, generation_id)
    if not row or row.user_id != owner_id:
        raise HTTPException(status_code=404, detail="Генерация не найдена")
    if actor is not None:
        await assert_studio_generation_access(session, actor, row.studio_model_id)
    if not generation_has_archive_file(row):
        raise HTTPException(
            status_code=404,
            detail="Файл изображения ещё не сохранён на сервере. Нажмите «Сохранить в архив» или дождитесь фоновой загрузки.",
        )
    abs_path = (BACKEND_DIR / row.relative_path).resolve()
    try:
        abs_path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Не найдено") from None
    if not abs_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Файл изображения отсутствует на сервере",
        )
    data = await anyio.to_thread.run_sync(abs_path.read_bytes)
    ct = (row.content_type or "").strip() or mimetypes.guess_type(abs_path.name)[0] or "image/png"
    if not ct.startswith("image/"):
        ct = "image/png"
    return row, data, ct


@router.post(
    "/studio/motion/first-frame",
    response_model=StudioMotionFirstFrameOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_studio_motion_first_frame(
    request: Request,
    video: UploadFile | None = File(None),
    first_frame_image: UploadFile | None = File(None),
    existing_generation_id: str = Form(""),
    model_id: str = Form(""),
    description: str = Form(""),
    output_aspect: str = Form("9:16"),
    wan_edit_tier: str = Form("standard"),
    studio_wave_profile: str = Form("regular"),
    auto_motion_prompt: str = Form("1"),
    lock_model_hairstyle: str = Form("1"),
    use_still_as_final: str = Form("0"),
    exif_camera: str = Form("main"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioMotionFirstFrameOut | JSONResponse:
    _ = request
    if not grok_scene_compose_configured():
        raise HTTPException(
            status_code=503,
            detail="Grok не настроен (OPENAI_API_KEY / GROK_API_KEY с vision).",
        )

    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    max_v = max(1, int(settings.studio_motion_max_upload_mb)) * 1024 * 1024

    video_bytes: bytes | None = None
    video_filename: str | None = None
    if video is not None and (video.filename or "").strip():
        video_bytes = await video.read()
        if len(video_bytes) > max_v:
            raise HTTPException(
                status_code=400,
                detail=f"Видео слишком большое (макс. {settings.studio_motion_max_upload_mb} МБ).",
            )
        if not video_bytes:
            raise HTTPException(status_code=400, detail="Пустой файл видео.")
        video_filename = video.filename or "video.mp4"

    still_bytes: bytes | None = None
    still_mime = "image/jpeg"
    if first_frame_image is not None and (first_frame_image.filename or "").strip():
        still_bytes = await first_frame_image.read()
        if len(still_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Файл первого кадра слишком большой (макс. 12 МБ).",
            )
        if not still_bytes:
            raise HTTPException(status_code=400, detail="Пустой файл первого кадра.")
        ct = (first_frame_image.content_type or "").strip().lower()
        if ct and ct.startswith("image/"):
            still_mime = ct.split(";")[0].strip()
        else:
            still_mime = (
                mimetypes.guess_type(first_frame_image.filename or "")[0] or "image/jpeg"
            )

    if not (existing_generation_id or "").strip() and not video_bytes and not still_bytes:
        raise HTTPException(
            status_code=400,
            detail="Загрузите референс-видео, файл первого кадра или выберите снимок из архива.",
        )

    params: dict[str, Any] = {
        "existing_generation_id": (existing_generation_id or "").strip(),
        "model_id": (model_id or "").strip(),
        "description": (description or "").strip(),
        "output_aspect": output_aspect,
        "wan_edit_tier": wan_edit_tier,
        "studio_wave_profile": studio_wave_profile,
        "auto_motion_prompt": auto_motion_prompt,
        "lock_model_hairstyle": lock_model_hairstyle,
        "use_still_as_final": use_still_as_final,
        "exif_camera": normalize_exif_camera(exif_camera),
    }
    job = await studio_jobs.create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="motion_first_frame",
        params=params,
    )
    if video_bytes:
        params["video_path"] = studio_jobs.save_studio_job_file(job.id, "video.bin", video_bytes)
        params["video_filename"] = video_filename or "video.mp4"
    if still_bytes:
        params["first_frame_path"] = studio_jobs.save_studio_job_file(
            job.id, "first_frame.bin", still_bytes
        )
        params["first_frame_mime"] = still_mime
    if params != studio_jobs.job_params(job):
        await studio_jobs.update_studio_job_params(session, job, params)

    try:
        mid_ff = int(str(model_id).strip()) if (model_id or "").strip() else None
    except ValueError:
        mid_ff = None
    try:
        aspect_ff = normalize_aspect_key(output_aspect)
    except ValueError:
        aspect_ff = None
    gen_row = await reserve_studio_generation_for_job(
        session,
        owner_id=oid,
        studio_job_id=job.id,
        studio_model_id=mid_ff,
        output_aspect=aspect_ff,
        content_type="image/png",
        prompt_excerpt=(description or "").strip()[:2000] or None,
        exif_camera=normalize_exif_camera(exif_camera),
    )
    params["placeholder_generation_id"] = gen_row.id
    await studio_jobs.update_studio_job_params(session, job, params)

    studio_jobs.schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type="motion_first_frame",
            generation_id=gen_row.id,
        ).model_dump(),
    )


async def _studio_job_execute_motion_first_frame(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    p = studio_jobs.job_params(job)
    existing_generation_id = str(p.get("existing_generation_id") or "")
    model_id = str(p.get("model_id") or "")
    description = str(p.get("description") or "")
    output_aspect = str(p.get("output_aspect") or "9:16")
    wan_edit_tier = str(p.get("wan_edit_tier") or "standard")
    studio_wave_profile = str(p.get("studio_wave_profile") or "regular")
    auto_motion_prompt = str(p.get("auto_motion_prompt") or "1")
    lock_model_hairstyle = str(p.get("lock_model_hairstyle") or "1")
    use_still_as_final = str(p.get("use_still_as_final") or "0")
    exif_camera_job = normalize_exif_camera(str(p.get("exif_camera") or "main"))

    if not grok_scene_compose_configured():
        raise RuntimeError(
            "Grok не настроен: задайте OPENAI_API_KEY (xAI) с vision для motion."
        )

    try:
        aspect_key = normalize_aspect_key(output_aspect)
    except ValueError as e:
        raise RuntimeError(str(e)) from e

    oid = workspace_owner_id(user)
    sub_b, llm_row, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)

    raw_ex = existing_generation_id.strip()
    existing_gid: int | None = None
    if raw_ex:
        try:
            existing_gid = int(raw_ex)
        except ValueError:
            raise RuntimeError("Некорректный номер генерации из архива.") from None

    gen_arch_row: StudioGeneration | None = None
    first_frame: bytes = b""
    first_frame_media = "image/jpeg"
    motion_video_file_id: str | None = None
    video_path: Path | None = None
    max_v = max(1, int(settings.studio_motion_max_upload_mb)) * 1024 * 1024

    explicit_still_file_upload = False
    has_still_upload = bool(p.get("first_frame_path"))
    has_video_upload = bool(p.get("video_path"))

    if has_still_upload:
        first_frame = studio_jobs.load_studio_job_file(str(p["first_frame_path"]))
        first_frame_media = str(p.get("first_frame_mime") or "image/jpeg")
        explicit_still_file_upload = True
    elif has_video_upload:
        raw_video = studio_jobs.load_studio_job_file(str(p["video_path"]))
        if len(raw_video) > max_v:
            raise RuntimeError(
                f"Видео слишком большое (макс. {settings.studio_motion_max_upload_mb} МБ)."
            )
        motion_video_file_id = save_motion_video_bytes(
            owner_id=oid,
            raw=raw_video,
            filename=str(p.get("video_filename") or "video.mp4"),
        )
        video_path = resolve_motion_video_file(oid, motion_video_file_id)
        if video_path is None:
            raise RuntimeError("Не удалось сохранить видео.")
        try:
            first_frame = await anyio.to_thread.run_sync(
                lambda vp=video_path: extract_first_frame_jpeg(vp)
            )
        except Exception as e:
            log.warning("motion first frame ffmpeg: %s", e)
            raise RuntimeError(
                "Не удалось прочитать видео. Нужен MP4/WebM/MOV и ffmpeg на сервере."
            ) from e
        if len(first_frame) < 64:
            raise RuntimeError("Не удалось извлечь кадр из видео.")
        first_frame_media = "image/jpeg"
    elif existing_gid is not None:
        gen_arch_row, first_frame, first_frame_media = await _load_owned_generation_still_for_motion(
            session, owner_id=oid, generation_id=existing_gid, actor=user
        )
    else:
        raise RuntimeError(
            "Загрузите референс-видео, файл первого кадра или выберите снимок из архива."
        )

    from_archive_or_still_upload = gen_arch_row is not None or has_still_upload
    if from_archive_or_still_upload and has_video_upload:
        raw_v2 = studio_jobs.load_studio_job_file(str(p["video_path"]))
        if len(raw_v2) > max_v:
            raise RuntimeError(
                f"Видео слишком большое (макс. {settings.studio_motion_max_upload_mb} МБ)."
            )
        if raw_v2:
            motion_video_file_id = save_motion_video_bytes(
                owner_id=oid,
                raw=raw_v2,
                filename=str(p.get("video_filename") or "video.mp4"),
            )
            video_path = resolve_motion_video_file(oid, motion_video_file_id)

    persist_uploaded_final = explicit_still_file_upload and _truthy_wavespeed_flag(
        use_still_as_final
    )

    eff_mid: int | None = (
        gen_arch_row.studio_model_id if gen_arch_row is not None else None
    )
    if eff_mid is None:
        eff_mid = _parse_optional_model_id(model_id)
    if eff_mid is None:
        raise HTTPException(status_code=400, detail="Выберите сохранённую модель.")

    sm_loaded = await require_studio_model_access(session, user, eff_mid, load_images=True)
    imgs_model = sort_model_images_for_studio(list(sm_loaded.images))
    if not imgs_model:
        raise HTTPException(status_code=400, detail="У модели нет фотографий.")

    llm_creds = studio_llm_credentials(plan=plan, llm_row=llm_row)
    wan_tier_n = _normalize_wan_edit_tier(wan_edit_tier)
    wave_profile_n = _normalize_studio_wave_profile(studio_wave_profile)
    lock_hair_req = _truthy_lock_model_hairstyle(lock_model_hairstyle)
    effective_lock_hairstyle = bool(lock_hair_req)

    model_profile_text = (sm_loaded.profile_text or "").strip() or None

    motion_clip_summary: str | None = None
    if _truthy_wavespeed_flag(auto_motion_prompt) and video_path is not None:
        from app.services.plan_entitlements import assert_grok_allowed, record_grok_usage

        await assert_grok_allowed(session, oid, sub_b)
        await record_grok_usage(session, oid, source="motion_timeline")
        try:
            motion_clip_summary = await motion_grok_timeline_from_video_path(
                video_path=video_path,
                model_profile_text=model_profile_text or "",
                first_frame_jpeg=first_frame,
                first_frame_media=first_frame_media,
                credentials=grok_motion_studio_credentials(),
            )
        except HTTPException:
            raise
        except Exception as e:
            log.warning("motion clip summary failed: %s", e)
            raise HTTPException(
                status_code=502,
                detail=f"Не удалось описать движение по ролику (Grok): {e}",
            ) from e

    desc_base = (description or "").strip()
    user_extra_blocks: list[str] = []
    if motion_clip_summary and motion_clip_summary.strip():
        block_title = (
            "## Motion timeline — Grok per-second + target model (English)\n"
            if settings.studio_grok_motion_timeline_enabled
            else "## Motion over reference clip (sampled frames, English)\n"
        )
        user_extra_blocks.append(block_title + motion_clip_summary.strip())
    extra_joined = "\n\n".join(user_extra_blocks) if user_extra_blocks else ""
    user_notes_grok = "\n\n".join(x for x in (desc_base, extra_joined) if x).strip()

    try:
        from app.services.plan_entitlements import assert_grok_allowed, record_grok_usage

        await assert_grok_allowed(session, oid, sub_b)
        await record_grok_usage(session, oid, source="motion_first_frame")
        refined, reference_scene, grok_neg = await grok_compose_motion_first_frame(
            pose_reference_bytes=first_frame,
            pose_reference_mime=first_frame_media,
            sm=sm_loaded,
            wave_profile=wave_profile_n,
            user_notes=user_notes_grok,
            lock_hairstyle=effective_lock_hairstyle,
            credentials=grok_motion_studio_credentials(),
        )
        reference_scene = (reference_scene or "").strip()
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    motion_auto_for_db = (reference_scene or "").strip()
    if motion_clip_summary and motion_clip_summary.strip():
        marker = _GROK_MOTION_MARKER if settings.studio_grok_motion_timeline_enabled else _CLIP_MOTION_MARKER
        motion_auto_for_db += "\n\n" + marker + "\n" + motion_clip_summary.strip()

    mode_n = "model_scene"
    skip_ws = gen_arch_row is not None or persist_uploaded_final
    ws_key = _studio_refine_wavespeed_preflight(
        do_wavespeed=not skip_ws,
        plan=plan,
        ws_row=ws_row,
        owner_subscription=sub_b,
        mode_n=mode_n,
        mid=eff_mid,
        sm_loaded=sm_loaded,
        imgs_model=imgs_model,
        image_bytes=first_frame,
        wave_profile=wave_profile_n,
    )

    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_prompt_refine)
    billing = await ensure_can_consume_credits(session, user, cost)

    arch_base = _public_app_base(None)
    pub = (settings.public_app_url or "").strip().rstrip("/")

    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    generation_id: int | None = None
    gen_row: StudioGeneration | None = None
    wavespeed_task_id: str | None = None
    if not skip_ws:
        gen_row = await find_studio_generation_by_job_id(session, job.id)
        if gen_row is None:
            gen_row = await begin_studio_generation_run(
                session,
                owner_id=oid,
                output_aspect=aspect_key,
                studio_model_id=eff_mid,
                studio_job_id=job.id,
                exif_camera=exif_camera_job,
            )
        else:
            gen_row.exif_camera = exif_camera_job
        gen_row.refined_prompt = refined
        gen_row.prompt_excerpt = (refined[:2000] if refined else None) or None
        gen_row.motion_video_prompt_auto = motion_auto_for_db
        session.add(gen_row)
        await session.flush()

    if skip_ws:
        base = (arch_base or "").strip().rstrip("/")
        if not base.lower().startswith("https://"):
            raise HTTPException(
                status_code=400,
                detail="Нужен публичный HTTPS (PUBLIC_APP_URL) для ссылок на кадр и WaveSpeed.",
            )
        if gen_arch_row is not None:
            gtok = create_generation_image_access_token(
                user_id=oid, generation_id=gen_arch_row.id
            )
            generated_image_url = (
                f"{base}/api/studio/public-generation-image?t={quote(gtok, safe='')}"
            )
            generation_id = gen_arch_row.id
            gen_arch_row.motion_video_prompt_auto = motion_auto_for_db
            gen_arch_row.refined_prompt = refined
            session.add(gen_arch_row)
        else:
            assert persist_uploaded_final
            gen_row = await persist_studio_generation_from_uploaded_bytes(
                session,
                owner_id=oid,
                data=first_frame,
                content_type=first_frame_media,
                output_aspect=aspect_key,
                studio_model_id=eff_mid,
                refined_prompt=refined,
                motion_video_prompt_auto=motion_auto_for_db,
            )
            if gen_row is None:
                raise HTTPException(
                    status_code=500,
                    detail="Не удалось сохранить загруженный кадр в архив.",
                )
            generation_id = gen_row.id
            gtok_new = create_generation_image_access_token(
                user_id=oid, generation_id=gen_row.id
            )
            generated_image_url = (
                f"{base}/api/studio/public-generation-image?t={quote(gtok_new, safe='')}"
            )
    else:
        if not pub.lower().startswith("https://"):
            raise HTTPException(
                status_code=400,
                detail="Генерация недоступна: у сервиса не настроен публичный HTTPS-адрес (PUBLIC_APP_URL).",
            )

        image_urls: list[str] = []
        user_pose_ref_prepended = False
        pose_ct = first_frame_media if first_frame_media.startswith("image/") else "image/jpeg"
        try:
            image_urls = motion_model_scene_wavespeed_image_urls(
                pub=pub,
                owner_id=oid,
                pose_bytes=first_frame,
                pose_mime=pose_ct,
                sm=sm_loaded,
                wave_profile=wave_profile_n,
                save_pose_reference_bytes=save_pose_reference_bytes,
                create_pose_reference_access_token=create_pose_reference_access_token,
                create_model_image_access_token=create_model_image_access_token,
            )
            user_pose_ref_prepended = True
        except Exception as e:
            log.warning("motion: grok pose/identity urls failed: %s", e)
            wavespeed_message = "Не удалось подготовить кадр для WaveSpeed."

        if not image_urls:
            wavespeed_message = wavespeed_message or "Нет изображений для WaveSpeed."

        if not wavespeed_message:
            pose_is_last_after_reorder = False
            if wave_profile_n == "regular":
                pose_is_last_after_reorder = bool(
                    user_pose_ref_prepended and len(image_urls) >= 2
                )
                image_urls = _nano_banana_reorder_image_urls(
                    image_urls,
                    studio_mode=mode_n,
                    user_pose_ref_prepended=user_pose_ref_prepended,
                )
            wavespeed_prompt = assemble_motion_grok_wavespeed_prompt(
                refined=refined,
                model_profile_text=model_profile_text,
                reference_scene=reference_scene or None,
                extra_negative=grok_neg,
                lock_hairstyle=effective_lock_hairstyle,
                wave_profile=wave_profile_n,
                user_pose_first=user_pose_ref_prepended,
                user_pose_last=pose_is_last_after_reorder,
                studio_mode=mode_n,
            )
            if settings.wavespeed_seedream_omit_size:
                size_for_ws: str | None = None
            else:
                size_for_ws = wavespeed_size_string(aspect_key)
            try:
                if wave_profile_n == "regular":
                    ws_res = await nano_banana_pro_edit_image_url(
                        api_key=ws_key,
                        image_urls=image_urls,
                        prompt=wavespeed_prompt,
                        aspect_ratio=aspect_key,
                        wave_profile=wave_profile_n,
                        reference_scene_description=reference_scene,
                    )
                else:
                    ws_res = await seedream_v45_edit_image_url(
                        api_key=ws_key,
                        image_urls=image_urls,
                        prompt=wavespeed_prompt,
                        size=size_for_ws,
                        wan_edit_tier=wan_tier_n,
                    )
                generated_image_url = ws_res.url
                wavespeed_task_id = ws_res.task_id or wavespeed_task_id
            except RuntimeError as e:
                wavespeed_message = _append_nano_banana_error_hint(
                    str(e),
                    wave_profile=wave_profile_n,
                )

        if generated_image_url and gen_row is not None:
            finished_row, cdn_preview = await studio_finish_image_generation(
                session,
                gen_row=gen_row,
                owner_id=oid,
                studio_model_id=eff_mid,
                output_aspect=aspect_key,
                refined_prompt=refined,
                source_url=generated_image_url,
                wavespeed_task_id=wavespeed_task_id,
                motion_video_prompt_auto=motion_auto_for_db,
            )
            if finished_row is not None:
                generation_id = finished_row.id
                if generation_has_archive_file(finished_row) and arch_base:
                    generated_image_url = _studio_archive_image_url(
                        oid, finished_row.id, arch_base
                    )
                elif cdn_preview:
                    generated_image_url = cdn_preview
                elif finished_row.source_url:
                    generated_image_url = finished_row.source_url.strip()
                if (
                    finished_row.status == StudioGenerationStatus.PROVIDER_READY
                    and not generation_has_archive_file(finished_row)
                ):
                    wavespeed_message = user_message_when_archive_download_failed(
                        wavespeed_message
                    )

        if not skip_ws and not (generated_image_url or "").strip():
            if gen_row is not None:
                await mark_studio_generation_failed(
                    session,
                    gen_row,
                    message=wavespeed_message or "WaveSpeed не вернул изображение",
                    step="wavespeed",
                )
            raise RuntimeError(
                wavespeed_message or "WaveSpeed не вернул изображение"
            )

    await record_usage(
        session,
        user,
        billing,
        "studio_motion_first_frame",
        cost,
        {
            "motion_video_file_id": motion_video_file_id,
            "studio_model_id": eff_mid,
            "generation_id": generation_id,
            "auto_motion_prompt": bool(motion_clip_summary and motion_clip_summary.strip()),
            "studio_wave_profile": wave_profile_n,
        },
    )
    await session.commit()

    return StudioMotionFirstFrameOut(
        refined_prompt=refined,
        reference_scene_description=reference_scene,
        motion_video_prompt_auto=(motion_clip_summary or "").strip() or None,
        generated_image_url=generated_image_url,
        wavespeed_message=wavespeed_message,
        generation_id=generation_id,
        motion_video_file_id=motion_video_file_id,
    ).model_dump()


@router.post(
    "/studio/motion/compose-video-prompt",
    response_model=StudioMotionComposeVideoPromptOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_studio_motion_compose_video_prompt(
    request: Request,
    motion_video_file_id: str = Form(...),
    model_id: str = Form(...),
    first_frame_image: UploadFile | None = File(None),
    existing_generation_id: str = Form(""),
    description: str = Form(""),
    lock_model_hairstyle: str = Form("1"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioMotionComposeVideoPromptOut | JSONResponse:
    """Grok: timeline по реф-видео + кадр модели. Без WaveSpeed — для шага «видео» отдельно."""
    _ = request
    if not grok_scene_compose_configured():
        raise HTTPException(
            status_code=503,
            detail="Grok не настроен (OPENAI_API_KEY / GROK_API_KEY с vision).",
        )
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)

    mv_id = str(motion_video_file_id or "").strip()
    if not mv_id:
        raise HTTPException(status_code=400, detail="Загрузите референс-видео на сервер.")
    if resolve_motion_video_file(oid, mv_id) is None:
        raise HTTPException(status_code=404, detail="Референс-видео не найдено. Загрузите снова.")

    still_bytes: bytes | None = None
    still_mime = "image/jpeg"
    if first_frame_image is not None and (first_frame_image.filename or "").strip():
        still_bytes = await first_frame_image.read()
        if len(still_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="Снимок слишком большой.")
        if not still_bytes:
            raise HTTPException(status_code=400, detail="Пустой файл кадра.")
        still_mime = (first_frame_image.content_type or "image/jpeg").split(";")[0].strip()

    params: dict[str, Any] = {
        "motion_video_file_id": mv_id,
        "model_id": model_id,
        "existing_generation_id": (existing_generation_id or "").strip(),
        "description": (description or "").strip(),
        "lock_model_hairstyle": lock_model_hairstyle,
    }
    job = await studio_jobs.create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="motion_compose_video_prompt",
        params=params,
    )
    if still_bytes:
        params["first_frame_path"] = studio_jobs.save_studio_job_file(
            job.id, "first_frame.bin", still_bytes
        )
        params["first_frame_mime"] = still_mime
    if params != studio_jobs.job_params(job):
        await studio_jobs.update_studio_job_params(session, job, params)

    studio_jobs.schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id, job_type="motion_compose_video_prompt"
        ).model_dump(),
    )


async def _studio_job_execute_motion_compose_video_prompt(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    p = studio_jobs.job_params(job)
    mv_id = str(p.get("motion_video_file_id") or "").strip()
    model_id = str(p.get("model_id") or "")
    description = str(p.get("description") or "")
    lock_model_hairstyle = str(p.get("lock_model_hairstyle") or "1")

    oid = workspace_owner_id(user)
    sub_b, llm_row, _ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)

    vpath = resolve_motion_video_file(oid, mv_id)
    if vpath is None:
        raise RuntimeError("Референс-видео не найдено.")

    eff_mid = _parse_optional_model_id(model_id)
    if eff_mid is None:
        raise RuntimeError("Выберите модель.")
    sm_loaded = await require_studio_model_access(session, user, eff_mid, load_images=True)
    if not select_grok_compose_wavespeed_identity_images(
        sort_model_images_for_studio(list(sm_loaded.images))
    ):
        raise RuntimeError(
            "У модели нужен снимок тела (body) и/или лица (face) для Grok и видео."
        )

    first_frame: bytes
    first_frame_media = "image/jpeg"
    generation_id: int | None = None
    raw_ex = str(p.get("existing_generation_id") or "").strip()
    if raw_ex:
        try:
            gid = int(raw_ex)
        except ValueError:
            raise RuntimeError("Некорректный номер генерации из архива.") from None
        _row, first_frame, first_frame_media = await _load_owned_generation_still_for_motion(
            session, owner_id=oid, generation_id=gid, actor=user
        )
        generation_id = gid
    elif p.get("first_frame_path"):
        first_frame = studio_jobs.load_studio_job_file(str(p["first_frame_path"]))
        first_frame_media = str(p.get("first_frame_mime") or "image/jpeg")
        gen_row = await persist_studio_generation_from_uploaded_bytes(
            session,
            owner_id=oid,
            data=first_frame,
            content_type=first_frame_media,
            output_aspect="9:16",
            studio_model_id=eff_mid,
            refined_prompt=None,
            motion_video_prompt_auto=None,
        )
        if gen_row is None:
            raise RuntimeError("Не удалось сохранить кадр в архив.")
        generation_id = gen_row.id
    else:
        first_frame, first_frame_media = await extract_video_first_frame_or_raise(vpath)

    llm_creds = studio_llm_credentials(plan=plan, llm_row=llm_row)
    lock_hair = _truthy_lock_model_hairstyle(lock_model_hairstyle)
    profile = (sm_loaded.profile_text or "").strip() or ""

    try:
        timeline = await motion_grok_timeline_from_video_path(
            video_path=vpath,
            model_profile_text=profile,
            first_frame_jpeg=first_frame,
            first_frame_media=first_frame_media,
            credentials=grok_motion_studio_credentials(),
        )
    except Exception as e:
        raise RuntimeError(f"Не удалось собрать промпт по видео (Grok): {e}") from e

    reference_scene: str | None = None
    try:
        reference_scene = (
            await describe_motion_still_for_ui(
                image_bytes=first_frame,
                image_media_type=first_frame_media,
                lock_hairstyle=lock_hair,
                credentials=llm_creds,
            )
        ).strip() or None
    except RuntimeError as e:
        log.warning("motion compose: still describe skipped: %s", e)

    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_prompt_refine)
    billing = await ensure_can_consume_credits(session, user, cost)
    await record_usage(
        session,
        user,
        billing,
        "studio_motion_compose_video_prompt",
        cost,
        {"motion_video_file_id": mv_id, "studio_model_id": eff_mid, "generation_id": generation_id},
    )
    await session.commit()

    return StudioMotionComposeVideoPromptOut(
        motion_video_prompt_auto=timeline.strip(),
        reference_scene_description=reference_scene,
        generation_id=generation_id,
        motion_video_file_id=mv_id,
        message=None,
    ).model_dump()


@router.post(
    "/studio/motion/render-video",
    response_model=StudioMotionVideoOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_studio_motion_render_video(
    request: Request,
    model_id: str = Form(...),
    prompt: str = Form(""),
    output_aspect: str = Form("9:16"),
    motion_video_file_id: str = Form(""),
    first_frame_generation_id: str = Form(""),
    motion_timeline: str = Form(""),
    outfit_generation_id: str = Form(""),
    negative_prompt: str = Form(""),
    generate_audio: str = Form("1"),
    duration_seconds: str = Form(""),
    seedance_variant: str = Form("standard"),
    video_resolution: str = Form(""),
    auto_motion_prompt: str = Form("0"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioMotionVideoOut | JSONResponse:
    _ = request
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    sub_b, _llm, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)

    try:
        mid = int(str(model_id).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный model_id") from None
    await require_studio_model_access(session, user, mid)

    if not (prompt or "").strip():
        raise HTTPException(status_code=400, detail="Опишите сцену, движение и при необходимости одежду.")

    try:
        aspect_key = normalize_aspect_key(output_aspect)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Нужен публичный HTTPS (PUBLIC_APP_URL) для WaveSpeed.",
        )

    try:
        studio_wavespeed_api_key(plan=plan, ws_row=ws_row, owner_subscription=sub_b)
    except HTTPException:
        raise

    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.id == mid, UserStudioModel.user_id == oid)
        .options(selectinload(UserStudioModel.images))
    )
    sm = (await session.execute(stmt)).scalar_one_or_none()
    if not sm:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    if not sort_model_images_for_seedance_t2v(list(sm.images)):
        raise HTTPException(
            status_code=400,
            detail="У модели нет фото для Seedance. Добавьте развёртку (turnaround) или другие снимки в кабинете модели.",
        )

    from app.services.studio_motion_pricing import (
        motion_video_credit_cost,
        motion_video_duration_seconds,
        normalize_seedance_t2v_resolution,
        normalize_seedance_t2v_variant,
    )

    ds_effective = motion_video_duration_seconds(duration_seconds)
    seedance_v = normalize_seedance_t2v_variant(seedance_variant)
    video_res = normalize_seedance_t2v_resolution(
        video_resolution or settings.wavespeed_seedance_20_t2v_resolution
    )

    outfit_gid: int | None = None
    raw_outfit = (outfit_generation_id or "").strip()
    if raw_outfit:
        try:
            outfit_gid = int(raw_outfit)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Некорректный outfit_generation_id",
            ) from None

    mv_id = str(motion_video_file_id).strip()
    if mv_id:
        vpath = resolve_motion_video_file(oid, mv_id)
        if vpath is None or not vpath.is_file():
            raise HTTPException(status_code=404, detail="Референс-видео не найдено.")

    ff_gid: int | None = None
    raw_ff = (first_frame_generation_id or "").strip()
    if raw_ff:
        try:
            ff_gid = int(raw_ff)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Некорректный first_frame_generation_id",
            ) from None
        ff_row = await session.get(StudioGeneration, ff_gid)
        if not ff_row or ff_row.user_id != oid:
            raise HTTPException(status_code=404, detail="Первый кадр (архив) не найден")
        if not generation_has_archive_file(ff_row):
            raise HTTPException(
                status_code=400,
                detail="Первый кадр ещё не сохранён на сервере. Дождитесь архива или сохраните кадр.",
            )

    timeline_raw = (motion_timeline or "").strip()
    if len(timeline_raw) > 50000:
        raise HTTPException(
            status_code=400,
            detail="motion_timeline слишком длинный — сократите или отключите Grok timeline на шаге 1.",
        )

    motion_cost = motion_video_credit_cost(
        ds_effective,
        variant=seedance_v,
        resolution=video_res,
        has_motion_reference_video=bool(mv_id),
    )
    motion_cost_billed = apply_studio_credit_cost(plan, motion_cost)
    await ensure_can_consume_credits(session, user, motion_cost_billed)

    preview_url: str | None = None
    if ff_gid is not None:
        preview_url = generation_still_public_url(
            owner_id=oid,
            generation_id=ff_gid,
            public_app_base=pub,
            token_factory=create_generation_image_access_token,
        )

    try:
        return await _accept_studio_job(
            session,
            user,
            job_type="motion_render_video",
            params={
                "model_id": mid,
                "prompt": (prompt or "").strip(),
                "output_aspect": aspect_key,
                "motion_video_file_id": mv_id,
                "first_frame_generation_id": ff_gid,
                "motion_timeline": timeline_raw,
                "outfit_generation_id": outfit_gid,
                "negative_prompt": (negative_prompt or "").strip(),
                "generate_audio": (generate_audio or "1").strip(),
                "duration_seconds": str(ds_effective),
                "seedance_variant": seedance_v,
                "video_resolution": video_res,
                "auto_motion_prompt": (auto_motion_prompt or "0").strip(),
            },
            placeholder={
                "studio_model_id": mid,
                "output_aspect": aspect_key,
                "content_type": "video/mp4",
                "prompt_excerpt": (prompt or "").strip()[:2000] or None,
                "preview_source_url": preview_url,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception("motion render-video accept failed")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать задачу видео: {e}",
        ) from e


async def _studio_job_execute_motion_render_video(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    params = studio_jobs.job_params(job)
    oid = workspace_owner_id(user)
    mid = int(params["model_id"])
    await require_studio_model_access(session, user, mid, load_images=True)
    prompt = str(params.get("prompt") or "")
    output_aspect = str(params.get("output_aspect") or "9:16")
    mv_id = str(params.get("motion_video_file_id") or "").strip()
    outfit_gid = params.get("outfit_generation_id")
    first_frame_gid = params.get("first_frame_generation_id")
    motion_timeline = str(params.get("motion_timeline") or "").strip()
    negative_prompt = str(params.get("negative_prompt") or "")
    generate_audio = str(params.get("generate_audio") or "1")
    duration_seconds = str(params.get("duration_seconds") or "")
    seedance_variant = str(params.get("seedance_variant") or "standard")
    video_resolution = str(params.get("video_resolution") or "")
    auto_motion_prompt = str(params.get("auto_motion_prompt") or "0")

    if not prompt.strip():
        raise RuntimeError("Опишите сцену и движение для видео.")

    sub_b, llm_row, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise RuntimeError("Нужен PUBLIC_APP_URL=https://…")

    ws_key = studio_wavespeed_api_key(plan=plan, ws_row=ws_row, owner_subscription=sub_b)

    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.id == mid, UserStudioModel.user_id == oid)
        .options(selectinload(UserStudioModel.images))
    )
    sm = (await session.execute(stmt)).scalar_one_or_none()
    if not sm:
        raise RuntimeError("Модель не найдена")

    if not sort_model_images_for_seedance_t2v(list(sm.images)):
        raise RuntimeError(
            "У модели нет фото для reference_images. Добавьте развёртку (turnaround) в кабинете модели."
        )

    log.info(
        "motion_render_video job=%s model=%s ff=%s mv=%s outfit=%s",
        job.id,
        mid,
        first_frame_gid,
        mv_id or None,
        outfit_gid,
    )

    n_start = 0
    outfit_gen_id: int | None = None
    first_frame_gen_id: int | None = None
    first_frame_bytes: bytes | None = None
    first_frame_media = "image/jpeg"
    ff_url: str | None = None

    if first_frame_gid is not None:
        try:
            first_frame_gen_id = int(first_frame_gid)
        except (TypeError, ValueError):
            first_frame_gen_id = None
    if first_frame_gen_id is not None:
        _ff_row, first_frame_bytes, first_frame_media = await _load_owned_generation_still_for_motion(
            session,
            owner_id=oid,
            generation_id=first_frame_gen_id,
            actor=user,
        )
        ff_url = generation_still_public_url(
            owner_id=oid,
            generation_id=first_frame_gen_id,
            public_app_base=pub,
            token_factory=create_generation_image_access_token,
        )
        if not ff_url:
            raise RuntimeError("Не удалось подготовить URL первого кадра")
        n_start = 1

    if outfit_gid is not None:
        try:
            outfit_gen_id = int(outfit_gid)
        except (TypeError, ValueError):
            outfit_gen_id = None
    if outfit_gen_id is not None:
        if first_frame_gen_id is not None and outfit_gen_id == first_frame_gen_id:
            outfit_gen_id = None
        else:
            row_outfit = await session.get(StudioGeneration, outfit_gen_id)
            if not row_outfit or row_outfit.user_id != oid:
                raise RuntimeError("Снимок наряда (outfit) не найден")
            await assert_studio_generation_access(session, user, row_outfit.studio_model_id)

    motion_vid_url: str | None = None
    motion_summary: str | None = motion_timeline or None
    vpath = None
    if mv_id:
        vpath = resolve_motion_video_file(oid, mv_id)
        if vpath is not None and vpath.is_file():
            vid_tok = create_motion_video_access_token(user_id=oid, file_id=mv_id)
            motion_vid_url = (
                f"{pub}/api/studio/public-motion-video?t={quote(vid_tok, safe='')}"
            )
            if _truthy_wavespeed_flag(auto_motion_prompt) and not motion_summary:
                try:
                    if (
                        settings.studio_grok_motion_timeline_enabled
                        and first_frame_bytes
                        and len(first_frame_bytes) >= 64
                    ):
                        motion_summary = await grok_two_step_motion_prompt_for_studio(
                            video_path=vpath,
                            model_profile_text=(sm.profile_text or "").strip() or "",
                            first_frame_jpeg=first_frame_bytes,
                            first_frame_media=first_frame_media,
                            credentials=grok_motion_studio_credentials(),
                        )
                    else:
                        llm_cr = studio_llm_credentials(plan=plan, llm_row=llm_row)
                        frames = await anyio.to_thread.run_sync(
                            lambda vp=vpath: extract_video_sample_frames_jpeg(vp, max_frames=4)
                        )
                        motion_summary = await describe_motion_video_frames_openai(
                            frames_jpeg=frames,
                            credentials=llm_cr,
                        )
                except Exception as e:
                    log.warning("render-video t2v: auto motion describe failed: %s", e)

    ar_t2v = aspect_ratio_for_seedance_i2v(output_aspect)
    from app.services.studio_motion_pricing import (
        motion_video_credit_cost,
        motion_video_duration_seconds,
        normalize_seedance_t2v_resolution,
        normalize_seedance_t2v_variant,
    )

    ds_effective = motion_video_duration_seconds(duration_seconds)
    seedance_v = normalize_seedance_t2v_variant(seedance_variant)
    video_res = normalize_seedance_t2v_resolution(
        video_resolution or settings.wavespeed_seedance_20_t2v_resolution
    )

    cost = apply_studio_credit_cost(
        plan,
        motion_video_credit_cost(
            ds_effective,
            variant=seedance_v,
            resolution=video_res,
            has_motion_reference_video=bool(mv_id),
        ),
    )
    billing = await ensure_can_consume_credits(session, user, cost)

    msg: str | None = None
    video_url: str | None = None
    seed_prompt = ""
    prompt_source = "template"
    ref_images: list[str] = []
    ref_videos: list[str] = []

    model_imgs = filter_model_images_for_seedance_video(
        list(sm.images),
        minimal=False,
        include_body=False,
    )
    n_outfit = 0
    if ff_url:
        ref_images.append(ff_url)
    ref_images.extend(
        model_reference_public_urls(
            owner_id=oid,
            images=model_imgs,
            public_app_base=pub,
            token_factory=create_model_image_access_token,
        )
    )
    n_model = len(model_imgs)

    if outfit_gen_id is not None:
        outfit_url = generation_still_public_url(
            owner_id=oid,
            generation_id=outfit_gen_id,
            public_app_base=pub,
            token_factory=create_generation_image_access_token,
        )
        if not outfit_url:
            raise RuntimeError("Не удалось подготовить URL снимка наряда")
        ref_images.append(outfit_url)
        n_outfit = 1

    if len(ref_images) > MAX_SEEDANCE_REFERENCE_IMAGES:
        ref_images = ref_images[:MAX_SEEDANCE_REFERENCE_IMAGES]

    ref_videos = [motion_vid_url] if motion_vid_url else []

    seed_prompt, prompt_source = await build_seedance_t2v_prompt(
        user_brief=prompt,
        n_start_frame=n_start,
        n_model_images=n_model,
        n_outfit_images=n_outfit,
        n_motion_videos=len(ref_videos),
        motion_summary=motion_summary,
        model_profile_text=None,
        negative=negative_prompt,
        output_aspect=ar_t2v or output_aspect,
        duration_seconds=ds_effective,
        force_template=False,
    )

    try:
        video_url = await seedance_20_text_to_video_url(
            api_key=ws_key,
            prompt=seed_prompt,
            reference_images=ref_images or None,
            reference_videos=ref_videos or None,
            aspect_ratio=ar_t2v,
            resolution=video_res,
            duration=ds_effective,
            generate_audio=_truthy_wavespeed_flag(generate_audio),
            variant=seedance_v,
        )
        msg = None
        log.info(
            "motion_render_video ok job=%s imgs=%s vids=%s prompt=%s",
            job.id,
            len(ref_images),
            len(ref_videos),
            prompt_source,
        )
    except RuntimeError as e:
        msg = str(e)
        video_url = None
        log.warning(
            "motion_render_video failed job=%s imgs=%s vids=%s: %s",
            job.id,
            len(ref_images),
            len(ref_videos),
            msg[:240],
        )

    gen_placeholder = await find_studio_generation_by_job_id(session, job.id)
    ph_id = params.get("placeholder_generation_id")
    if gen_placeholder is None and ph_id is not None:
        try:
            gen_placeholder = await session.get(StudioGeneration, int(ph_id))
        except (TypeError, ValueError):
            gen_placeholder = None

    if video_url:
        vu = (video_url or "").strip()
        if vu:
            if gen_placeholder is not None:
                await studio_finish_video_generation(
                    session,
                    gen_placeholder,
                    video_url=vu,
                    prompt_excerpt=(seed_prompt or "")[:2000] or None,
                )
            try:
                session.add(
                    StudioMotionRender(
                        user_id=oid,
                        studio_model_id=mid,
                        studio_generation_id=gen_placeholder.id
                        if gen_placeholder is not None
                        else (first_frame_gen_id or outfit_gen_id),
                        video_url=vu,
                    )
                )
            except Exception as e:
                log.warning("motion_render history insert failed (video ok): %s", e)
    elif gen_placeholder is not None:
        await mark_studio_generation_failed(
            session,
            gen_placeholder,
            message=msg or "WaveSpeed не вернул видео",
            step="wavespeed",
        )

    try:
        await record_usage(
            session,
            user,
            billing,
            "studio_motion_control",
            cost,
            {
                "studio_model_id": mid,
                "first_frame_generation_id": first_frame_gen_id,
                "outfit_generation_id": outfit_gen_id,
                "motion_video_file_id": mv_id or None,
                "motion_video_provider": "seedance_t2v",
                "seedance_t2v_variant": seedance_v,
                "seedance_20_t2v_path": (
                    settings.wavespeed_seedance_20_mini_t2v_path
                    if seedance_v == "mini"
                    else settings.wavespeed_seedance_20_t2v_path
                ),
                "seedance_20_t2v_resolution": video_res,
                "seedance_20_t2v_duration": ds_effective,
                "reference_images": len(ref_images),
                "reference_videos": len(ref_videos),
                "seedance_t2v_prompt_source": prompt_source,
                "seedance_t2v_prompt_chars": len(seed_prompt),
                "ok": bool(video_url),
            },
        )
        await session.commit()
    except Exception as e:
        log.exception("motion_render_video commit failed job=%s", job.id)
        raise RuntimeError(f"Не удалось сохранить результат видео: {e}") from e

    if not video_url and msg:
        raise RuntimeError(msg)

    out: dict[str, Any] = StudioMotionVideoOut(
        video_url=video_url,
        message=msg,
        motion_video_prompt_auto=seed_prompt[:4000] if seed_prompt else None,
    ).model_dump()
    if gen_placeholder is not None:
        out["generation_id"] = gen_placeholder.id
    return out


def _require_public_https_for_wavespeed() -> str:
    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=503,
            detail="WaveSpeed скачивает референсы по HTTPS. Укажите PUBLIC_APP_URL=https://…",
        )
    return pub


def _public_https_base_runtime() -> str:
    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise RuntimeError("Нужен PUBLIC_APP_URL=https://… для WaveSpeed.")
    return pub


@router.post(
    "/studio/model-bootstrap/face-merge",
    response_model=StudioModelBootstrapOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_model_bootstrap_face_merge(
    request: Request,
    ref_form: UploadFile = File(..., description="Референс 1: волосы и форма лица"),
    ref_face: UploadFile = File(..., description="Референс 2: лицо для наложения"),
    prompt: str = Form(""),
    output_aspect: str = Form("9:16"),
    model_id: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioModelBootstrapOut | JSONResponse:
    _ = request
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    _require_public_https_for_wavespeed()

    ref1 = await ref_form.read()
    ref2 = await ref_face.read()
    if not ref1 or not ref2:
        raise HTTPException(status_code=400, detail="Загрузите оба референса.")
    if len(ref1) > MAX_IMAGE_BYTES or len(ref2) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
        )

    try:
        aspect_key = normalize_aspect_key(output_aspect)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    mid = _parse_optional_model_id(model_id)
    resolved_prompt = resolve_face_merge_prompt(prompt)

    params: dict[str, Any] = {
        "output_aspect": aspect_key,
        "prompt": resolved_prompt,
        "model_id": mid,
        "ref_form_mime": (ref_form.content_type or "").strip(),
        "ref_face_mime": (ref_face.content_type or "").strip(),
    }
    job = await studio_jobs.create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="model_bootstrap_face_merge",
        params=params,
    )
    params["ref_form_path"] = studio_jobs.save_studio_job_file(job.id, "ref_form.bin", ref1)
    params["ref_face_path"] = studio_jobs.save_studio_job_file(job.id, "ref_face.bin", ref2)
    gen_row = await reserve_studio_generation_for_job(
        session,
        owner_id=oid,
        studio_job_id=job.id,
        studio_model_id=mid,
        output_aspect=aspect_key,
        content_type="image/png",
        prompt_excerpt=resolved_prompt[:2000],
    )
    params["placeholder_generation_id"] = gen_row.id
    await studio_jobs.update_studio_job_params(session, job, params)
    studio_jobs.schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type="model_bootstrap_face_merge",
            generation_id=gen_row.id,
        ).model_dump(),
    )


@router.post(
    "/studio/model-bootstrap/sheet",
    response_model=StudioModelBootstrapOut,
    responses={202: {"model": StudioJobAcceptedOut}},
)
async def api_model_bootstrap_sheet(
    request: Request,
    source_generation_id: str = Form(""),
    image: UploadFile | None = File(None),
    prompt: str = Form(""),
    model_id: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioModelBootstrapOut | JSONResponse:
    _ = request
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    pub = _require_public_https_for_wavespeed()

    gen_id_raw = (source_generation_id or "").strip()
    image_bytes: bytes | None = None
    image_mime = ""
    if image is not None and (image.filename or "").strip():
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Пустой файл изображения")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Файл слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
            )
        image_mime = (image.content_type or "").strip()

    gen_id: int | None = None
    if gen_id_raw:
        try:
            gen_id = int(gen_id_raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный source_generation_id") from None

    if gen_id is None and not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Укажите кадр из шага 1 или загрузите своё изображение.",
        )

    if gen_id is not None:
        row = await session.get(StudioGeneration, gen_id)
        if not row or row.user_id != oid:
            raise HTTPException(status_code=404, detail="Генерация не найдена")
        await assert_studio_generation_access(session, user, row.studio_model_id)

    mid = _parse_optional_model_id(model_id)
    aspect_key = MODEL_SHEET_ASPECT_KEY
    resolved_prompt = resolve_model_sheet_prompt(prompt)

    if gen_id is not None:
        dedupe_key = f"sheet:gen:{gen_id}"
    elif image_bytes:
        dedupe_key = f"sheet:upload:{hashlib.sha256(image_bytes).hexdigest()}"
    else:
        dedupe_key = ""

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
        "output_aspect": aspect_key,
        "prompt": resolved_prompt,
        "model_id": mid,
        "source_generation_id": gen_id,
        "dedupe_key": dedupe_key,
    }
    job = await studio_jobs.create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="model_bootstrap_sheet",
        params=params,
    )
    if image_bytes:
        params["image_path"] = studio_jobs.save_studio_job_file(job.id, "sheet_src.bin", image_bytes)
        params["image_mime"] = image_mime
    preview_url: str | None = None
    if gen_id is not None:
        tok = create_generation_image_access_token(user_id=oid, generation_id=gen_id)
        preview_url = f"{pub}/api/studio/public-generation-image?t={quote(tok, safe='')}"
    gen_row = await reserve_studio_generation_for_job(
        session,
        owner_id=oid,
        studio_job_id=job.id,
        studio_model_id=mid,
        output_aspect=aspect_key,
        content_type="image/png",
        prompt_excerpt=resolved_prompt[:2000],
        preview_source_url=preview_url,
    )
    params["placeholder_generation_id"] = gen_row.id
    await studio_jobs.update_studio_job_params(session, job, params)
    studio_jobs.schedule_studio_job(job.id)
    return JSONResponse(
        status_code=202,
        content=StudioJobAcceptedOut(
            job_id=job.id,
            job_type="model_bootstrap_sheet",
            generation_id=gen_row.id,
        ).model_dump(),
    )


async def _studio_job_execute_model_bootstrap_face_merge(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    p = studio_jobs.job_params(job)
    oid = workspace_owner_id(user)
    pub = _public_https_base_runtime()

    sub_b, _, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    ws_key = studio_wavespeed_api_key(plan=plan, ws_row=ws_row, owner_subscription=sub_b)

    aspect_key = normalize_aspect_key(str(p.get("output_aspect") or "9:16"))
    prompt = resolve_face_merge_prompt(str(p.get("prompt") or ""))
    mid = p.get("model_id")
    if mid is not None:
        try:
            mid = int(mid)
        except (TypeError, ValueError):
            mid = None

    ref1 = studio_jobs.load_studio_job_file(str(p.get("ref_form_path") or ""))
    ref2 = studio_jobs.load_studio_job_file(str(p.get("ref_face_path") or ""))
    if not ref1 or not ref2:
        raise RuntimeError("Файлы референсов не найдены в задаче.")

    url1 = await wavespeed_image_url_for_bootstrap(
        api_key=ws_key,
        owner_id=oid,
        pub=pub,
        raw=ref1,
        content_type=str(p.get("ref_form_mime") or "image/jpeg"),
        label="ref_form",
    )
    url2 = await wavespeed_image_url_for_bootstrap(
        api_key=ws_key,
        owner_id=oid,
        pub=pub,
        raw=ref2,
        content_type=str(p.get("ref_face_mime") or "image/jpeg"),
        label="ref_face",
    )

    gen_row = await find_studio_generation_by_job_id(session, job.id)
    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_prompt_refine)
    billing = await ensure_can_consume_credits(session, user, cost)

    try:
        ws_res = await seedream_v45_bootstrap_edit_image_url(
            api_key=ws_key,
            image_urls=[url1, url2],
            prompt=prompt,
            size=None,
        )
    except RuntimeError as e:
        raise RuntimeError(humanize_wavespeed_provider_error(str(e))) from e

    arch_base = _public_app_base(None)
    _, preview_url = await studio_finish_image_generation(
        session,
        gen_row=gen_row,
        owner_id=oid,
        studio_model_id=mid,
        output_aspect=aspect_key,
        refined_prompt=prompt,
        source_url=ws_res.url,
        wavespeed_task_id=ws_res.task_id,
    )

    out_url = preview_url
    if gen_row is not None and gen_row.status == StudioGenerationStatus.READY:
        out_url = _studio_archive_image_url(oid, gen_row.id, arch_base)

    await record_usage(
        session,
        user,
        billing,
        "studio_model_bootstrap_face_merge",
        cost,
        {"studio_model_id": mid, "generation_id": gen_row.id if gen_row else None},
    )
    await session.commit()

    return StudioModelBootstrapOut(
        refined_prompt=prompt,
        generated_image_url=out_url,
        generation_id=gen_row.id if gen_row else None,
        wavespeed_message=None,
    ).model_dump()


async def _studio_job_execute_model_bootstrap_sheet(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    p = studio_jobs.job_params(job)
    oid = workspace_owner_id(user)
    pub = _public_https_base_runtime()

    sub_b, _, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    ws_key = studio_wavespeed_api_key(plan=plan, ws_row=ws_row, owner_subscription=sub_b)

    prompt = resolve_model_sheet_prompt(str(p.get("prompt") or ""))
    aspect_key = MODEL_SHEET_ASPECT_KEY
    mid = p.get("model_id")
    if mid is not None:
        try:
            mid = int(mid)
        except (TypeError, ValueError):
            mid = None

    image_urls: list[str] = []
    if p.get("image_path"):
        raw = studio_jobs.load_studio_job_file(str(p["image_path"]))
        if raw:
            image_urls.append(
                await wavespeed_image_url_for_bootstrap(
                    api_key=ws_key,
                    owner_id=oid,
                    pub=pub,
                    raw=raw,
                    content_type=str(p.get("image_mime") or "image/jpeg"),
                    label="sheet_upload",
                )
            )
    else:
        gen_src_id = p.get("source_generation_id")
        if gen_src_id is not None:
            try:
                gid = int(gen_src_id)
                row = await session.get(StudioGeneration, gid)
                if not row or row.user_id != oid:
                    raise RuntimeError("Исходная генерация не найдена")
                image_urls.append(
                    await wavespeed_url_for_bootstrap_generation(
                        api_key=ws_key,
                        owner_id=oid,
                        pub=pub,
                        row=row,
                    )
                )
            except (TypeError, ValueError) as e:
                raise RuntimeError("Некорректный идентификатор исходной генерации") from e

    if not image_urls:
        raise RuntimeError("Нет исходного изображения для развёртки.")

    gen_row = await find_studio_generation_by_job_id(session, job.id)
    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_prompt_refine)
    billing = await ensure_can_consume_credits(session, user, cost)

    async def _on_sheet_task_submitted(task_id: str) -> None:
        if gen_row is not None:
            await attach_studio_generation_wavespeed_task(
                session, gen_row, task_id=task_id
            )
            await session.commit()

    try:
        ws_res = await gpt_image_2_edit_image_url(
            api_key=ws_key,
            image_urls=image_urls,
            prompt=prompt,
            aspect_ratio=aspect_key,
            resolution="1k",
            quality="medium",
            output_format="png",
            max_polls=300,
            poll_interval=2.5,
            on_task_submitted=_on_sheet_task_submitted,
        )
    except RuntimeError as e:
        if gen_row is not None and (gen_row.wavespeed_task_id or "").strip():
            if await try_recover_studio_generation_from_wavespeed(
                session, gen_row, api_key=ws_key, refined_prompt=prompt
            ):
                await session.commit()
                arch_base = _public_app_base(None)
                out_url = _studio_archive_image_url(oid, gen_row.id, arch_base)
                if gen_row.status != StudioGenerationStatus.READY:
                    out_url = (gen_row.source_url or "").strip() or out_url
                await record_usage(
                    session,
                    user,
                    billing,
                    "studio_model_bootstrap_sheet",
                    cost,
                    {"studio_model_id": mid, "generation_id": gen_row.id},
                )
                await session.commit()
                return StudioModelBootstrapOut(
                    refined_prompt=prompt,
                    generated_image_url=out_url,
                    generation_id=gen_row.id,
                    wavespeed_message=None,
                ).model_dump()
        raise RuntimeError(humanize_wavespeed_provider_error(str(e))) from e

    arch_base = _public_app_base(None)
    _, preview_url = await studio_finish_image_generation(
        session,
        gen_row=gen_row,
        owner_id=oid,
        studio_model_id=mid,
        output_aspect=aspect_key,
        refined_prompt=prompt,
        source_url=ws_res.url,
        wavespeed_task_id=ws_res.task_id,
    )

    out_url = preview_url
    if gen_row is not None and gen_row.status == StudioGenerationStatus.READY:
        out_url = _studio_archive_image_url(oid, gen_row.id, arch_base)

    await record_usage(
        session,
        user,
        billing,
        "studio_model_bootstrap_sheet",
        cost,
        {"studio_model_id": mid, "generation_id": gen_row.id if gen_row else None},
    )
    await session.commit()

    return StudioModelBootstrapOut(
        refined_prompt=prompt,
        generated_image_url=out_url,
        generation_id=gen_row.id if gen_row else None,
        wavespeed_message=None,
    ).model_dump()
