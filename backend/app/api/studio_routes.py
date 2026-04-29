from __future__ import annotations

import logging
import mimetypes
import shutil
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.config import BACKEND_DIR, settings
from app.db.models import (
    StudioGeneration,
    User,
    UserStudioModel,
    UserStudioModelImage,
    WavespeedConnection,
)
from app.db.session import get_session
from app.schemas import (
    StudioGenerationOut,
    StudioGenerationsPageOut,
    StudioModelImageOut,
    StudioModelProfileGenerateOut,
    StudioRefinePromptOut,
    StudioUpscaleGenerationIn,
    StudioUpscaleGenerationOut,
    UserStudioModelOut,
    UserStudioModelPatchIn,
)
from app.services.credits import ensure_can_consume_credits, record_usage
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
    create_pose_reference_access_token,
    decode_generation_image_access_token,
    decode_model_image_access_token,
    decode_pose_reference_access_token,
)
from app.services.studio_openai import (
    MAX_IMAGE_BYTES,
    describe_reference_image_openai,
    finalize_nano_banana_studio_prompt,
    finalize_wavespeed_studio_prompt,
    generate_model_profile_json_from_images,
    load_image_studio_system,
    prepare_studio_prompt_skeleton,
    refine_prompt_via_openai,
)
from app.services.studio_pose_reference import (
    resolve_pose_reference_file,
    save_pose_reference_bytes,
)
from app.services.wavespeed_client import (
    nano_banana_pro_edit_image_url,
    seedream_v45_edit_image_url,
    wavespeed_image_upscale_url,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["studio"])

MAX_MODEL_IMAGES = 5


def _public_app_base(request: Request | None) -> str:
    p = (settings.public_app_url or "").strip().rstrip("/")
    if p:
        return p
    if request is not None:
        return str(request.base_url).rstrip("/")
    return ""


_ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _parse_optional_model_id(raw: str | None) -> int | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный model_id") from None


@router.get("/studio/output-aspects")
async def api_output_aspects() -> dict:
    """Список пресетов соотношения сторон для студии (UI и WaveSpeed size)."""
    return {"aspects": aspect_presets_public()}


def _truthy_wavespeed_flag(raw: str | None) -> bool:
    if raw is None:
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "")


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
    ordered = sorted(m.images, key=lambda x: x.id)
    images = [
        StudioModelImageOut(
            id=im.id,
            url="/api/studio/public-model-image?t="
            + quote(create_model_image_access_token(user_id=user_id, image_id=im.id), safe=""),
        )
        for im in ordered
    ]
    return UserStudioModelOut(
        id=m.id,
        name=m.name,
        profile_text=m.profile_text or "",
        image_count=len(ordered),
        images=images,
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

    ws_row = await session.scalar(
        select(WavespeedConnection).where(WavespeedConnection.user_id == oid)
    )
    if not ws_row or not (ws_row.api_key_encrypted or "").strip():
        return StudioUpscaleGenerationOut(
            generated_image_url=None,
            generation_id=None,
            message="Сохраните API-ключ WaveSpeed в кабинете (интеграции).",
            target_resolution=tr,
        )

    cost = settings.credit_cost_studio_upscale
    billing = await ensure_can_consume_credits(session, user, cost)
    msg: str | None = None
    out_url: str | None = None
    new_id: int | None = None
    try:
        ws_key = decrypt_secret(ws_row.api_key_encrypted)
    except ValueError:
        ws_key = ""
        msg = "Не удалось расшифровать ключ WaveSpeed — сохраните ключ снова."

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
    if not (settings.openai_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="OpenAI не настроен: задайте OPENAI_API_KEY в backend/.env",
        )
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
    cost = settings.credit_cost_studio_model_profile_generate
    billing = await ensure_can_consume_credits(session, user, cost)
    try:
        text = await generate_model_profile_json_from_images(image_items=image_items)
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
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserStudioModelOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    uploads = images or []
    if len(uploads) > MAX_MODEL_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Не больше {MAX_MODEL_IMAGES} изображений на модель",
        )

    m = UserStudioModel(
        user_id=oid,
        name=name.strip(),
        profile_text=(profile_text or "").strip(),
    )
    session.add(m)
    await session.flush()

    d = _model_dir(oid, m.id)
    d.mkdir(parents=True, exist_ok=True)

    for up in uploads:
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
        session.add(
            UserStudioModelImage(
                studio_model_id=m.id,
                relative_path=rel,
                original_name=(up.filename or "")[:255] or None,
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
    await session.commit()
    m2 = await _load_studio_model_owned(session, oid, model_id)
    assert m2 is not None
    return _studio_model_to_out(oid, m2)


@router.post("/studio/models/{model_id}/images", response_model=UserStudioModelOut)
async def api_add_studio_model_images(
    model_id: int,
    images: list[UploadFile] | None = File(None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> UserStudioModelOut:
    assert_permission(user, PERM_STUDIO_MODELS)
    oid = workspace_owner_id(user)
    m = await _load_studio_model_owned(session, oid, model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    uploads = [u for u in (images or []) if u is not None]
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
    for up in uploads:
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
        session.add(
            UserStudioModelImage(
                studio_model_id=m.id,
                relative_path=rel,
                original_name=(up.filename or "")[:255] or None,
            )
        )
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
    m = await session.get(UserStudioModel, model_id)
    if not m or m.user_id != oid:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    d = _model_dir(oid, model_id)
    await session.delete(m)
    await session.commit()
    if d.is_dir() and str(d).startswith(str(BACKEND_DIR.resolve())):
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
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> StudioRefinePromptOut:
    if not (settings.openai_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="OpenAI не настроен: задайте OPENAI_API_KEY в backend/.env",
        )

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
    wan_tier_n = _normalize_wan_edit_tier(wan_edit_tier)
    wave_profile_n = _normalize_studio_wave_profile(studio_wave_profile)

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

    cost = settings.credit_cost_studio_prompt_refine
    billing = await ensure_can_consume_credits(session, user, cost)

    reference_scene: str | None = None
    try:
        if image_bytes:
            reference_scene = await describe_reference_image_openai(
                image_bytes=image_bytes,
                image_media_type=image_mime,
            )
        refined = await refine_prompt_via_openai(
            system_instruction=system_instr,
            skeleton=skeleton,
            user_text=desc,
            reference_scene_description=reference_scene,
            model_profile_text=model_profile_text,
            output_aspect_key=aspect_key,
            studio_mode=mode_n,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    if _truthy_wavespeed_flag(generate_wavespeed):
        ws_row = await session.scalar(
            select(WavespeedConnection).where(WavespeedConnection.user_id == oid)
        )
        imgs_model: list[UserStudioModelImage] = []
        if sm_loaded is not None:
            imgs_model = sorted(sm_loaded.images, key=lambda x: x.id)

        if not ws_row or not (ws_row.api_key_encrypted or "").strip():
            wavespeed_message = "Сохраните API-ключ WaveSpeed в кабинете (интеграции)."
        else:
            pub = (settings.public_app_url or "").strip().rstrip("/")
            if not pub.lower().startswith("https://"):
                wavespeed_message = (
                    "WaveSpeed скачивает референс по публичному URL. Укажите в backend/.env "
                    "PUBLIC_APP_URL=https://… (например ngrok на порт бэкенда) и перезапустите сервер."
                )
            else:
                if mode_n == "model":
                    if mid is None or sm_loaded is None:
                        wavespeed_message = (
                            "В нормальном режиме «Модель» выберите сохранённую модель с фотографиями."
                        )
                    elif not imgs_model:
                        wavespeed_message = (
                            "У выбранной модели нет загруженных фото — добавьте снимки к модели."
                        )
                elif mode_n == "photo_edit":
                    if not image_bytes:
                        wavespeed_message = "Для доработки фото загрузите изображение."
                elif mode_n == "no_face":
                    if not image_bytes and (
                        mid is None or sm_loaded is None or not imgs_model
                    ):
                        wavespeed_message = (
                            "В режиме «Без лица» выберите модель с фото или загрузите референс."
                        )

                if not wavespeed_message:
                    try:
                        ws_key = decrypt_secret(ws_row.api_key_encrypted)
                    except ValueError:
                        ws_key = ""
                        wavespeed_message = (
                            "Не удалось расшифровать ключ WaveSpeed — сохраните ключ снова."
                        )
                    if ws_key and not wavespeed_message:
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
                                for im in imgs_model[:10]:
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
                                )
                            else:
                                wavespeed_prompt = finalize_wavespeed_studio_prompt(
                                    refined,
                                    studio_mode=mode_n,
                                    user_image_first=user_pose_ref_prepended,
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
