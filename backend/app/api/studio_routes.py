from __future__ import annotations

import logging
import mimetypes
import shutil
import uuid
from pathlib import Path
from urllib.parse import quote

import anyio

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.config import BACKEND_DIR, settings
from app.db.models import (
    StudioGeneration,
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
    StudioModelImageOut,
    StudioModelImagePatchIn,
    StudioModelProfileGenerateOut,
    StudioMotionFirstFrameOut,
    StudioMotionVideoOut,
    StudioRefinePromptOut,
    StudioUpscaleGenerationIn,
    StudioUpscaleGenerationOut,
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
from app.services.crypto_secret import decrypt_secret
from app.services.studio_aspect import (
    aspect_presets_public,
    normalize_aspect_key,
    wavespeed_size_string,
)
from app.services.studio_generation_storage import (
    download_and_create_generation,
    safe_delete_generation_file,
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
    describe_motion_video_frames_openai,
    describe_reference_image_openai,
    finalize_nano_banana_studio_prompt,
    finalize_wavespeed_studio_prompt,
    generate_model_profile_json_from_images,
    load_image_studio_system,
    prepare_studio_prompt_skeleton,
    refine_prompt_via_openai,
)
from app.services.studio_camera_presets import get_camera_preset_by_id, list_camera_presets
from app.services.studio_carousel import build_carousel_wave_prompt
from app.services.studio_model_images import (
    assert_studio_image_kind,
    model_images_for_wavespeed_profile,
    model_reference_photos_block,
    parse_image_export_selfies_json,
    parse_image_kinds_json,
    sort_model_images_for_studio,
)
from app.services.studio_pose_reference import (
    resolve_pose_reference_file,
    save_pose_reference_bytes,
)
from app.services.studio_motion_video import (
    extract_first_frame_jpeg,
    extract_video_sample_frames_jpeg,
    resolve_motion_video_file,
    save_motion_video_bytes,
)
from app.services.wavespeed_client import (
    kling_motion_control_video_url,
    nano_banana_pro_edit_image_url,
    seedream_v45_edit_image_url,
    wavespeed_image_upscale_url,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["studio"])

MAX_MODEL_IMAGES = 5


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
        if not imgs_ok and mode_n in ("model", "no_face"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "В режиме «Обычные фотографии» нельзя использовать только снимки с типом «интимная анатомия» — "
                    "они не отправляются в этот API (ограничения провайдера). Добавьте фото лица или тела к модели "
                    "или переключите тип генерации на «NSFW (WAN / Seedream)»."
                ),
            )
    if mode_n == "model":
        if mid is None or sm_loaded is None:
            raise HTTPException(
                status_code=400,
                detail="В режиме «Модель» выберите сохранённую модель с фотографиями.",
            )
        if not imgs_model:
            raise HTTPException(
                status_code=400,
                detail="У выбранной модели нет загруженных фото — добавьте снимки к модели.",
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
    return ws_key


@router.get("/studio/output-aspects")
async def api_output_aspects() -> dict:
    """Список пресетов соотношения сторон для студии (UI и WaveSpeed size)."""
    return {"aspects": aspect_presets_public()}


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


_ALLOWED_STUDIO_MODES = frozenset({"model", "photo_edit", "no_face"})


def _normalize_studio_mode(raw: str | None) -> str:
    m = (raw or "model").strip().lower().replace("-", "_")
    if m in ("edit", "refine", "enhance"):
        return "photo_edit"
    if m in _ALLOWED_STUDIO_MODES:
        return m
    return "model"


def _normalize_wan_edit_tier(raw: str | None) -> str:
    """standard | pro для FormData UI; прочее → standard."""
    t = (raw or "standard").strip().lower()
    return "pro" if t == "pro" else "standard"


def _normalize_studio_wave_profile(raw: str | None) -> str:
    """regular = Nano Banana Pro (обычные фото); nsfw = WAN/Seedream из .env."""
    p = (raw or "nsfw").strip().lower()
    return "regular" if p == "regular" else "nsfw"


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


def _model_dir(user_id: int, model_id: int) -> Path:
    return (BACKEND_DIR / "data" / "studio_user_models" / str(user_id) / str(model_id)).resolve()


def _studio_model_to_out(user_id: int, m: UserStudioModel) -> UserStudioModelOut:
    ordered = sort_model_images_for_studio(list(m.images))
    images = [
        StudioModelImageOut(
            id=im.id,
            url="/api/studio/public-model-image?t="
            + quote(create_model_image_access_token(user_id=user_id, image_id=im.id), safe=""),
            kind=(im.image_kind or "other").strip().lower(),
            export_selfie=bool(im.export_selfie),
        )
        for im in ordered
    ]
    return UserStudioModelOut(
        id=m.id,
        name=m.name,
        profile_text=m.profile_text or "",
        image_count=len(ordered),
        images=images,
        camera_preset_id=(m.camera_preset_id or "").strip() or None,
        export_lat=m.export_lat,
        export_lon=m.export_lon,
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


@router.get("/studio/generations", response_model=StudioGenerationsPageOut)
async def api_list_studio_generations(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0, le=50_000),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioGenerationsPageOut:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    take = int(limit) + 1
    stmt = (
        select(StudioGeneration)
        .where(StudioGeneration.user_id == oid)
        .order_by(StudioGeneration.created_at.desc(), StudioGeneration.id.desc())
        .offset(int(skip))
        .limit(take)
    )
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
        tok = create_generation_image_access_token(user_id=oid, generation_id=r.id)
        url = f"{base}/api/studio/public-generation-image?t={quote(tok, safe='')}"
        out_items.append(
            StudioGenerationOut(
                id=r.id,
                created_at=r.created_at,
                output_aspect=r.output_aspect,
                studio_model_id=r.studio_model_id,
                model_name=name_by_id.get(r.studio_model_id) if r.studio_model_id else None,
                prompt_excerpt=r.prompt_excerpt,
                image_url=url,
            )
        )
    return StudioGenerationsPageOut(items=out_items, has_more=has_more)


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
    rel = row.relative_path
    await session.delete(row)
    await session.commit()
    safe_delete_generation_file(rel)
    return {"ok": True}


@router.post(
    "/studio/generations/{gen_id}/upscale",
    response_model=StudioUpscaleGenerationOut,
)
async def api_upscale_studio_generation(
    gen_id: int,
    request: Request,
    payload: StudioUpscaleGenerationIn | None = Body(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioUpscaleGenerationOut:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    row = await session.get(StudioGeneration, gen_id)
    if not row or row.user_id != oid:
        raise HTTPException(status_code=404, detail="Не найдено")

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
        )

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
            )
            if gen is None:
                msg = "Не удалось сохранить результат апскейла — повторите позже."
            else:
                new_id = gen.id
                arch_base = _public_app_base(request)
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
        )

    await session.rollback()
    return StudioUpscaleGenerationOut(
        generated_image_url=None,
        generation_id=None,
        message=msg or "Апскейл не выполнен.",
        target_resolution=tr,
    )


@router.post("/studio/generations/{gen_id}/carousel", response_model=StudioCarouselOut)
async def api_studio_carousel(
    gen_id: int,
    request: Request,
    payload: StudioCarouselIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioCarouselOut:
    """Несколько вариантов кадра (ракурс/поза) от той же мастер-генерации — тот же промпт + шаблоны в data/prompts."""
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    row = await session.get(StudioGeneration, gen_id)
    if not row or row.user_id != oid:
        raise HTTPException(status_code=404, detail="Не найдено")

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
        ws_key = studio_wavespeed_api_key(
            plan=plan, ws_row=ws_row, owner_subscription=sub_b
        )
    except HTTPException as e:
        return StudioCarouselOut(message=str(e.detail))

    wave_profile_n = _normalize_studio_wave_profile(payload.studio_wave_profile)
    wan_tier_n = _normalize_wan_edit_tier(payload.wan_edit_tier)
    try:
        aspect_key = normalize_aspect_key(row.output_aspect or "9:16")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    count = int(payload.count)
    cost_one = apply_studio_credit_cost(plan, settings.credit_cost_studio_carousel_shot)
    tok = create_generation_image_access_token(user_id=oid, generation_id=gen_id)
    master_url = f"{pub}/api/studio/public-generation-image?t={quote(tok, safe='')}"

    items: list[StudioCarouselItemOut] = []
    last_msg: str | None = None
    arch_base = _public_app_base(request)

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
                raw_url = await nano_banana_pro_edit_image_url(
                    api_key=ws_key,
                    image_urls=[master_url],
                    prompt=wavespeed_prompt,
                    aspect_ratio=aspect_key,
                )
            else:
                raw_url = await seedream_v45_edit_image_url(
                    api_key=ws_key,
                    image_urls=[master_url],
                    prompt=wavespeed_prompt,
                    size=size_for_ws,
                    wan_edit_tier=wan_tier_n,
                )
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

        excerpt = f"[carousel {shot_i + 1}/{count} from gen {gen_id}]"
        gen = await download_and_create_generation(
            session,
            owner_id=oid,
            source_url=raw_url,
            refined_prompt=excerpt,
            output_aspect=aspect_key,
            studio_model_id=row.studio_model_id,
            refined_prompt_full=wavespeed_prompt,
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
            gtok = create_generation_image_access_token(
                user_id=oid, generation_id=gen.id
            )
            out_u = f"{arch_base}/api/studio/public-generation-image?t={quote(gtok, safe='')}"
        else:
            out_u = raw_url
        items.append(StudioCarouselItemOut(generation_id=gen.id, image_url=out_u))

    return StudioCarouselOut(items=items, message=last_msg)


@router.get("/studio/models", response_model=list[UserStudioModelOut])
async def api_list_studio_models(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[UserStudioModelOut]:
    if not has_any_studio_access(user):
        raise HTTPException(status_code=403, detail="Нет доступа к студии")
    oid = workspace_owner_id(user)
    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.user_id == oid)
        .options(selectinload(UserStudioModel.images))
        .order_by(UserStudioModel.id.desc())
    )
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
    image_export_selfies: str | None = Form(None),
    camera_preset_id: str | None = Form(None),
    export_lat: str | None = Form(None),
    export_lon: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserStudioModelOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    uploads = images or []
    kinds_list = parse_image_kinds_json(image_kinds, len(uploads))
    selfies_list = parse_image_export_selfies_json(image_export_selfies, len(uploads), kinds_list)
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
        selfie_b = selfies_list[i] if i < len(selfies_list) else (kind == "face")
        session.add(
            UserStudioModelImage(
                studio_model_id=m.id,
                relative_path=rel,
                original_name=(up.filename or "")[:255] or None,
                image_kind=kind,
                export_selfie=selfie_b,
            )
        )

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
    m = await _load_studio_model_owned(session, oid, model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Модель не найдена")
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
    m2 = await _load_studio_model_owned(session, oid, model_id)
    assert m2 is not None
    return _studio_model_to_out(oid, m2)


@router.post("/studio/models/{model_id}/images", response_model=UserStudioModelOut)
async def api_add_studio_model_images(
    model_id: int,
    images: list[UploadFile] | None = File(None),
    image_kinds: str | None = Form(None),
    image_export_selfies: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserStudioModelOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    sub_b, _, _, _, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)
    m = await _load_studio_model_owned(session, oid, model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    uploads = [u for u in (images or []) if u is not None]
    kinds_list = parse_image_kinds_json(image_kinds, len(uploads))
    selfies_list = parse_image_export_selfies_json(image_export_selfies, len(uploads), kinds_list)
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
        selfie_b = selfies_list[i] if i < len(selfies_list) else (kind == "face")
        session.add(
            UserStudioModelImage(
                studio_model_id=m.id,
                relative_path=rel,
                original_name=(up.filename or "")[:255] or None,
                image_kind=kind,
                export_selfie=selfie_b,
            )
        )
    await session.commit()
    m2 = await _load_studio_model_owned(session, oid, model_id)
    assert m2 is not None
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
    m = await session.get(UserStudioModel, model_id)
    if not m or m.user_id != oid:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    img = await session.get(UserStudioModelImage, image_id)
    if not img or img.studio_model_id != model_id:
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Передайте kind и/или export_selfie")
    if "kind" in data:
        img.image_kind = assert_studio_image_kind(data["kind"])
    if "export_selfie" in data:
        img.export_selfie = bool(data["export_selfie"])
    await session.commit()
    m2 = await _load_studio_model_owned(session, oid, model_id)
    assert m2 is not None
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
    m = await session.get(UserStudioModel, model_id)
    if not m or m.user_id != oid:
        raise HTTPException(status_code=404, detail="Модель не найдена")
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


@router.post("/studio/refine-prompt", response_model=StudioRefinePromptOut)
async def api_studio_refine_prompt(
    request: Request,
    description: str = Form(""),
    model_id: str | None = Form(None),
    image: UploadFile | None = File(None),
    output_aspect: str = Form("9:16"),
    studio_mode: str = Form("model"),
    wan_edit_tier: str = Form("standard"),
    studio_wave_profile: str = Form("nsfw"),
    generate_wavespeed: str | None = Form(None),
    wavespeed_single_reference: str | None = Form(None),
    lock_model_hairstyle: str | None = Form("1"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioRefinePromptOut:
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

    desc = (description or "").strip()
    mid = _parse_optional_model_id(model_id)
    try:
        aspect_key = normalize_aspect_key(output_aspect)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

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
    if image is not None and (image.filename or "").strip():
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Референс слишком большой (макс. {MAX_IMAGE_BYTES // (1024 * 1024)} МБ)",
            )
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Пустой файл изображения")
        image_mime = image.content_type

    sm_loaded: UserStudioModel | None = None
    model_profile_text: str | None = None
    if mid is not None:
        stmt = (
            select(UserStudioModel)
            .where(UserStudioModel.id == mid, UserStudioModel.user_id == oid)
            .options(selectinload(UserStudioModel.images))
        )
        sm_loaded = (await session.execute(stmt)).scalar_one_or_none()
        if not sm_loaded:
            raise HTTPException(status_code=404, detail="Модель не найдена")
        model_profile_text = (sm_loaded.profile_text or "").strip() or None

    mode_n = _normalize_studio_mode(studio_mode)
    if mode_n == "photo_edit" and not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="В режиме «Доработать фото» загрузите изображение.",
        )
    if mode_n == "no_face" and mid is None and not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="В режиме «Без лица» выберите сохранённую модель или загрузите референс.",
        )

    if not desc and not image_bytes and not model_profile_text:
        raise HTTPException(
            status_code=400,
            detail="Добавьте описание, референс и/или выберите сохранённую модель",
        )

    imgs_model: list[UserStudioModelImage] = []
    if sm_loaded is not None:
        imgs_model = sort_model_images_for_studio(list(sm_loaded.images))
    imgs_for_ws = model_images_for_wavespeed_profile(imgs_model, wave_profile_n)

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

    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_prompt_refine)
    billing = await ensure_can_consume_credits(session, user, cost)

    lock_hair_req = _truthy_lock_model_hairstyle(lock_model_hairstyle)
    effective_lock_hairstyle = bool(lock_hair_req) if image_bytes else True

    reference_scene: str | None = None
    try:
        if image_bytes:
            reference_scene = await describe_reference_image_openai(
                image_bytes=image_bytes,
                image_media_type=image_mime,
                hairstyle_from_pose_reference=not effective_lock_hairstyle,
                credentials=llm_creds,
            )
        ref_photo_block = (
            model_reference_photos_block(imgs_for_ws) if imgs_for_ws else None
        )
        refined = await refine_prompt_via_openai(
            system_instruction=system_instr,
            skeleton=skeleton,
            user_text=desc,
            reference_scene_description=reference_scene,
            model_profile_text=model_profile_text,
            model_reference_photos=ref_photo_block,
            output_aspect_key=aspect_key,
            studio_mode=mode_n,
            lock_model_hairstyle=effective_lock_hairstyle,
            credentials=llm_creds,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    if do_wavespeed:
        pub = (settings.public_app_url or "").strip().rstrip("/")
        image_urls: list[str] = []
        user_pose_ref_prepended = False
        if image_bytes:
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

        if not wavespeed_message:
            attach_model_urls = False
            if mode_n == "model":
                attach_model_urls = bool(imgs_model)
            elif mode_n == "no_face":
                attach_model_urls = bool(sm_loaded and imgs_model)
            elif mode_n == "photo_edit":
                attach_model_urls = bool(sm_loaded and imgs_model)

            if attach_model_urls:
                for im in imgs_for_ws[:10]:
                    tok = create_model_image_access_token(
                        user_id=oid, image_id=im.id
                    )
                    image_urls.append(
                        f"{pub}/api/studio/public-model-image?t={quote(tok, safe='')}"
                    )

            if not image_urls:
                wavespeed_message = (
                    "Нет изображений для WaveSpeed — проверьте режим, модель и файлы."
                )

        if not wavespeed_message and image_urls:
            if wave_profile_n == "nsfw" and _truthy_wavespeed_flag(
                wavespeed_single_reference
            ):
                if user_pose_ref_prepended and len(image_urls) >= 2:
                    image_urls = image_urls[:2]
                else:
                    image_urls = image_urls[:1]

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
                wavespeed_prompt = finalize_nano_banana_studio_prompt(
                    refined,
                    studio_mode=mode_n,
                    user_photo_edit_first=bool(
                        user_pose_ref_prepended and mode_n == "photo_edit"
                    ),
                    user_pose_reference_is_last=pose_is_last_after_reorder,
                    lock_model_hairstyle=effective_lock_hairstyle,
                )
            else:
                wavespeed_prompt = finalize_wavespeed_studio_prompt(
                    refined,
                    studio_mode=mode_n,
                    user_image_first=user_pose_ref_prepended,
                    lock_model_hairstyle=effective_lock_hairstyle,
                )
            size_for_ws: str | None
            if settings.wavespeed_seedream_omit_size:
                size_for_ws = None
            else:
                size_for_ws = wavespeed_size_string(aspect_key)
            try:
                if wave_profile_n == "regular":
                    generated_image_url = await nano_banana_pro_edit_image_url(
                        api_key=ws_key,
                        image_urls=image_urls,
                        prompt=wavespeed_prompt,
                        aspect_ratio=aspect_key,
                    )
                else:
                    generated_image_url = await seedream_v45_edit_image_url(
                        api_key=ws_key,
                        image_urls=image_urls,
                        prompt=wavespeed_prompt,
                        size=size_for_ws,
                        wan_edit_tier=wan_tier_n,
                    )
            except RuntimeError as e:
                wavespeed_message = str(e)
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
    if generated_image_url:
        gen = await download_and_create_generation(
            session,
            owner_id=oid,
            source_url=generated_image_url,
            refined_prompt=refined,
            output_aspect=aspect_key,
            studio_model_id=mid,
            refined_prompt_full=refined,
        )
        if gen is not None:
            generation_id = gen.id
            arch_base = _public_app_base(request)
            if arch_base:
                gtok = create_generation_image_access_token(user_id=oid, generation_id=gen.id)
                generated_image_url = (
                    f"{arch_base}/api/studio/public-generation-image?t={quote(gtok, safe='')}"
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
        },
    )
    await session.commit()

    return StudioRefinePromptOut(
        refined_prompt=refined,
        reference_scene_description=reference_scene,
        generated_image_url=generated_image_url,
        wavespeed_message=wavespeed_message,
        generation_id=generation_id,
    )


@router.post("/studio/motion/first-frame", response_model=StudioMotionFirstFrameOut)
async def api_studio_motion_first_frame(
    request: Request,
    video: UploadFile = File(...),
    model_id: str = Form(...),
    description: str = Form(""),
    output_aspect: str = Form("9:16"),
    wan_edit_tier: str = Form("standard"),
    studio_wave_profile: str = Form("nsfw"),
    auto_motion_prompt: str = Form("1"),
    lock_model_hairstyle: str = Form("1"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioMotionFirstFrameOut:
    skeleton = prepare_studio_prompt_skeleton()
    system_instr = load_image_studio_system()
    if not skeleton or not system_instr:
        raise HTTPException(
            status_code=503,
            detail="Шаблон промпта студии не настроен (skeleton / system).",
        )

    mid = _parse_optional_model_id(model_id)
    if mid is None:
        raise HTTPException(status_code=400, detail="Выберите сохранённую модель.")

    try:
        aspect_key = normalize_aspect_key(output_aspect)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    sub_b, llm_row, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)

    if not (video.filename or "").strip():
        raise HTTPException(status_code=400, detail="Загрузите видео (MP4, WebM или MOV).")
    raw_video = await video.read()
    max_b = max(1, int(settings.studio_motion_max_upload_mb)) * 1024 * 1024
    if len(raw_video) > max_b:
        raise HTTPException(
            status_code=400,
            detail=f"Видео слишком большое (макс. {settings.studio_motion_max_upload_mb} МБ).",
        )
    if not raw_video:
        raise HTTPException(status_code=400, detail="Пустой файл видео.")

    sm_loaded = await _load_studio_model_owned(session, oid, mid)
    if not sm_loaded:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    imgs_model = sort_model_images_for_studio(list(sm_loaded.images))
    if not imgs_model:
        raise HTTPException(status_code=400, detail="У модели нет фотографий.")

    motion_video_file_id = save_motion_video_bytes(
        owner_id=oid, raw=raw_video, filename=video.filename
    )
    video_path = resolve_motion_video_file(oid, motion_video_file_id)
    if video_path is None:
        raise HTTPException(status_code=500, detail="Не удалось сохранить видео.")

    try:
        first_frame = await anyio.to_thread.run_sync(
            lambda vp=video_path: extract_first_frame_jpeg(vp)
        )
    except Exception as e:
        log.warning("motion first frame ffmpeg: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Не удалось прочитать видео. Нужен формат MP4/WebM/MOV и утилита ffmpeg на сервере.",
        ) from e

    if len(first_frame) < 64:
        raise HTTPException(status_code=400, detail="Не удалось извлечь кадр из видео.")

    llm_creds = studio_llm_credentials(plan=plan, llm_row=llm_row)
    wan_tier_n = _normalize_wan_edit_tier(wan_edit_tier)
    wave_profile_n = _normalize_studio_wave_profile(studio_wave_profile)
    lock_hair_req = _truthy_lock_model_hairstyle(lock_model_hairstyle)
    effective_lock_hairstyle = bool(lock_hair_req)

    motion_video_prompt_auto: str | None = None
    if _truthy_wavespeed_flag(auto_motion_prompt):
        try:
            frames = await anyio.to_thread.run_sync(
                lambda vp=video_path: extract_video_sample_frames_jpeg(vp, max_frames=4)
            )
            motion_video_prompt_auto = await describe_motion_video_frames_openai(
                frames_jpeg=frames,
                credentials=llm_creds,
            )
        except Exception as e:
            log.warning("motion auto prompt failed: %s", e)
            raise HTTPException(
                status_code=502,
                detail="Не удалось разобрать видео через vision-модель. Отключите авто-промпт или проверьте OPENAI_API_KEY / OPENAI_STUDIO_MODEL_VISION.",
            ) from e

    model_profile_text = (sm_loaded.profile_text or "").strip() or None
    desc_base = (description or "").strip()
    if motion_video_prompt_auto:
        extra = (
            "## Motion reference (English summary from reference video frames)\n"
            + motion_video_prompt_auto.strip()
        )
        user_text_for_refine = "\n\n".join(x for x in (desc_base, extra) if x).strip()
    else:
        user_text_for_refine = desc_base

    if not user_text_for_refine and not model_profile_text:
        raise HTTPException(
            status_code=400,
            detail="Добавьте описание, включите авто-промпт по видео или заполните текстовый профиль модели.",
        )

    try:
        reference_scene = await describe_reference_image_openai(
            image_bytes=first_frame,
            image_media_type="image/jpeg",
            hairstyle_from_pose_reference=not effective_lock_hairstyle,
            credentials=llm_creds,
        )
        imgs_for_ws = model_images_for_wavespeed_profile(imgs_model, wave_profile_n)
        ref_photo_block = model_reference_photos_block(imgs_for_ws)
        refined = await refine_prompt_via_openai(
            system_instruction=system_instr,
            skeleton=skeleton,
            user_text=user_text_for_refine,
            reference_scene_description=reference_scene,
            model_profile_text=model_profile_text,
            model_reference_photos=ref_photo_block,
            output_aspect_key=aspect_key,
            studio_mode="model",
            lock_model_hairstyle=effective_lock_hairstyle,
            credentials=llm_creds,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    mode_n = "model"
    ws_key = _studio_refine_wavespeed_preflight(
        do_wavespeed=True,
        plan=plan,
        ws_row=ws_row,
        owner_subscription=sub_b,
        mode_n=mode_n,
        mid=mid,
        sm_loaded=sm_loaded,
        imgs_model=imgs_model,
        image_bytes=first_frame,
        wave_profile=wave_profile_n,
    )

    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_prompt_refine)
    billing = await ensure_can_consume_credits(session, user, cost)

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Генерация недоступна: у сервиса не настроен публичный HTTPS-адрес (PUBLIC_APP_URL).",
        )

    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    image_urls: list[str] = []
    user_pose_ref_prepended = False
    try:
        fid_pose = save_pose_reference_bytes(
            owner_id=oid,
            raw=first_frame,
            content_type="image/jpeg",
        )
        ptok = create_pose_reference_access_token(user_id=oid, file_id=fid_pose)
        image_urls.append(
            f"{pub}/api/studio/public-pose-reference?t={quote(ptok, safe='')}"
        )
        user_pose_ref_prepended = True
    except Exception as e:
        log.warning("motion: pose ref save failed: %s", e)
        wavespeed_message = "Не удалось подготовить кадр из видео для WaveSpeed."

    if not wavespeed_message:
        for im in imgs_for_ws[:10]:
            tok = create_model_image_access_token(user_id=oid, image_id=im.id)
            image_urls.append(
                f"{pub}/api/studio/public-model-image?t={quote(tok, safe='')}"
            )

    if not image_urls:
        wavespeed_message = "Нет изображений для WaveSpeed."

    if not wavespeed_message:
        pose_is_last_after_reorder = False
        if wave_profile_n == "regular":
            pose_is_last_after_reorder = bool(user_pose_ref_prepended and len(image_urls) >= 2)
            image_urls = _nano_banana_reorder_image_urls(
                image_urls,
                studio_mode=mode_n,
                user_pose_ref_prepended=user_pose_ref_prepended,
            )
            wavespeed_prompt = finalize_nano_banana_studio_prompt(
                refined,
                studio_mode=mode_n,
                user_photo_edit_first=False,
                user_pose_reference_is_last=pose_is_last_after_reorder,
                lock_model_hairstyle=effective_lock_hairstyle,
            )
        else:
            wavespeed_prompt = finalize_wavespeed_studio_prompt(
                refined,
                studio_mode=mode_n,
                user_image_first=user_pose_ref_prepended,
                lock_model_hairstyle=effective_lock_hairstyle,
            )
        if settings.wavespeed_seedream_omit_size:
            size_for_ws: str | None = None
        else:
            size_for_ws = wavespeed_size_string(aspect_key)
        try:
            if wave_profile_n == "regular":
                generated_image_url = await nano_banana_pro_edit_image_url(
                    api_key=ws_key,
                    image_urls=image_urls,
                    prompt=wavespeed_prompt,
                    aspect_ratio=aspect_key,
                )
            else:
                generated_image_url = await seedream_v45_edit_image_url(
                    api_key=ws_key,
                    image_urls=image_urls,
                    prompt=wavespeed_prompt,
                    size=size_for_ws,
                    wan_edit_tier=wan_tier_n,
                )
        except RuntimeError as e:
            wavespeed_message = str(e)

    generation_id: int | None = None
    if generated_image_url:
        gen = await download_and_create_generation(
            session,
            owner_id=oid,
            source_url=generated_image_url,
            refined_prompt=refined,
            output_aspect=aspect_key,
            studio_model_id=mid,
            refined_prompt_full=refined,
        )
        if gen is not None:
            generation_id = gen.id
            arch_base = _public_app_base(request)
            if arch_base:
                gtok = create_generation_image_access_token(user_id=oid, generation_id=gen.id)
                generated_image_url = (
                    f"{arch_base}/api/studio/public-generation-image?t={quote(gtok, safe='')}"
                )

    await record_usage(
        session,
        user,
        billing,
        "studio_motion_first_frame",
        cost,
        {
            "motion_video_file_id": motion_video_file_id,
            "studio_model_id": mid,
            "generation_id": generation_id,
            "auto_motion_prompt": bool(motion_video_prompt_auto),
            "studio_wave_profile": wave_profile_n,
        },
    )
    await session.commit()

    return StudioMotionFirstFrameOut(
        refined_prompt=refined,
        reference_scene_description=reference_scene,
        motion_video_prompt_auto=motion_video_prompt_auto,
        generated_image_url=generated_image_url,
        wavespeed_message=wavespeed_message,
        generation_id=generation_id,
        motion_video_file_id=motion_video_file_id,
    )


@router.post("/studio/motion/render-video", response_model=StudioMotionVideoOut)
async def api_studio_motion_render_video(
    request: Request,
    generation_id: str = Form(...),
    motion_video_file_id: str = Form(...),
    character_orientation: str = Form("video"),
    prompt: str = Form(""),
    negative_prompt: str = Form(""),
    keep_original_sound: str = Form("1"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioMotionVideoOut:
    _ = request
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    sub_b, _llm, ws_row, plan, _credits = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits)

    try:
        gid = int(str(generation_id).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный generation_id")

    mv_id = str(motion_video_file_id).strip()
    if not mv_id:
        raise HTTPException(status_code=400, detail="Укажите motion_video_file_id.")

    orient = (character_orientation or "video").strip().lower()
    if orient not in ("image", "video"):
        raise HTTPException(status_code=400, detail="character_orientation: image или video.")

    row = await session.get(StudioGeneration, gid)
    if not row or row.user_id != oid:
        raise HTTPException(status_code=404, detail="Генерация не найдена")

    vpath = resolve_motion_video_file(oid, mv_id)
    if vpath is None or not vpath.is_file():
        raise HTTPException(
            status_code=404,
            detail="Исходное видео не найдено. Снова выполните шаг «Сгенерировать кадр».",
        )

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Нужен публичный HTTPS (PUBLIC_APP_URL) для WaveSpeed.",
        )

    ws_key = studio_wavespeed_api_key(plan=plan, ws_row=ws_row, owner_subscription=sub_b)

    cost = apply_studio_credit_cost(plan, settings.credit_cost_studio_motion_control)
    billing = await ensure_can_consume_credits(session, user, cost)

    img_tok = create_generation_image_access_token(user_id=oid, generation_id=gid, days=30)
    image_pub = f"{pub}/api/studio/public-generation-image?t={quote(img_tok, safe='')}"
    vid_tok = create_motion_video_access_token(user_id=oid, file_id=mv_id)
    video_pub = f"{pub}/api/studio/public-motion-video?t={quote(vid_tok, safe='')}"

    keep_snd = _truthy_wavespeed_flag(keep_original_sound)
    msg: str | None = None
    video_url: str | None = None
    prompt_txt = (prompt or "").strip()
    if not prompt_txt:
        prompt_txt = (row.refined_prompt or row.prompt_excerpt or "").strip()
    try:
        video_url = await kling_motion_control_video_url(
            api_key=ws_key,
            image_url=image_pub,
            video_url=video_pub,
            character_orientation=orient,
            prompt=prompt_txt,
            negative_prompt=negative_prompt.strip(),
            keep_original_sound=keep_snd,
        )
    except RuntimeError as e:
        msg = str(e)

    await record_usage(
        session,
        user,
        billing,
        "studio_motion_control",
        cost,
        {
            "generation_id": gid,
            "motion_video_file_id": mv_id,
            "character_orientation": orient,
            "ok": bool(video_url),
        },
    )
    await session.commit()

    return StudioMotionVideoOut(video_url=video_url, message=msg)
