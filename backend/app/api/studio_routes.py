from __future__ import annotations

import logging
import mimetypes
import shutil
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
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
    StudioModelImageOut,
    StudioRefinePromptOut,
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
    decode_generation_image_access_token,
    decode_model_image_access_token,
)
from app.services.studio_openai import (
    MAX_IMAGE_BYTES,
    describe_reference_image_openai,
    load_image_studio_system,
    prepare_studio_prompt_skeleton,
    refine_prompt_via_openai,
)
from app.services.wavespeed_client import seedream_v45_edit_image_url

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


@router.get("/studio/generations", response_model=list[StudioGenerationOut])
async def api_list_studio_generations(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[StudioGenerationOut]:
    assert_permission(user, PERM_STUDIO_GENERATE)
    oid = workspace_owner_id(user)
    stmt = (
        select(StudioGeneration)
        .where(StudioGeneration.user_id == oid)
        .order_by(StudioGeneration.created_at.desc())
        .limit(80)
    )
    rows = (await session.execute(stmt)).scalars().all()
    base = _public_app_base(request)
    if not base:
        return []
    model_ids = {r.studio_model_id for r in rows if r.studio_model_id}
    name_by_id: dict[int, str] = {}
    if model_ids:
        qm = await session.execute(select(UserStudioModel).where(UserStudioModel.id.in_(model_ids)))
        for m in qm.scalars().all():
            name_by_id[m.id] = m.name
    out: list[StudioGenerationOut] = []
    for r in rows:
        tok = create_generation_image_access_token(user_id=oid, generation_id=r.id)
        url = f"{base}/api/studio/public-generation-image?t={quote(tok, safe='')}"
        out.append(
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
    return out


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
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    generated_image_url: str | None = None
    wavespeed_message: str | None = None
    if _truthy_wavespeed_flag(generate_wavespeed) and mid is not None and sm_loaded is not None:
        ws_row = await session.scalar(
            select(WavespeedConnection).where(WavespeedConnection.user_id == oid)
        )
        imgs = sorted(sm_loaded.images, key=lambda x: x.id)
        if not ws_row or not (ws_row.api_key_encrypted or "").strip():
            wavespeed_message = "Сохраните API-ключ WaveSpeed в кабинете (интеграции)."
        elif not imgs:
            wavespeed_message = "У выбранной модели нет загруженных фото — добавьте снимки к модели."
        else:
            pub = (settings.public_app_url or "").strip().rstrip("/")
            if not pub.lower().startswith("https://"):
                wavespeed_message = (
                    "WaveSpeed скачивает референс по публичному URL. Укажите в backend/.env "
                    "PUBLIC_APP_URL=https://… (например ngrok на порт бэкенда) и перезапустите сервер."
                )
            else:
                try:
                    ws_key = decrypt_secret(ws_row.api_key_encrypted)
                except ValueError:
                    ws_key = ""
                    wavespeed_message = "Не удалось расшифровать ключ WaveSpeed — сохраните ключ снова."
                if ws_key:
                    image_urls: list[str] = []
                    for im in imgs[:10]:
                        tok = create_model_image_access_token(user_id=oid, image_id=im.id)
                        image_urls.append(
                            f"{pub}/api/studio/public-model-image?t={quote(tok, safe='')}"
                        )
                    if _truthy_wavespeed_flag(wavespeed_single_reference):
                        image_urls = image_urls[:1]
                    size_for_ws: str | None
                    if settings.wavespeed_seedream_omit_size:
                        size_for_ws = None
                    else:
                        size_for_ws = wavespeed_size_string(aspect_key)
                    try:
                        generated_image_url = await seedream_v45_edit_image_url(
                            api_key=ws_key,
                            image_urls=image_urls,
                            prompt=refined,
                            size=size_for_ws,
                        )
                    except RuntimeError as e:
                        wavespeed_message = str(e)
                        low = wavespeed_message.lower()
                        if "something went wrong" in low or "try again" in low:
                            wavespeed_message = (
                                f"{wavespeed_message} "
                                "Часто это: баланс/лимит на wavespeed.ai, кратковременный сбой API "
                                "(см. status.wavespeed.ai) или слишком тяжёлый/нестандартный запрос. "
                                "Повторите позже. Если сбой стабилен — в backend/.env поставьте "
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
