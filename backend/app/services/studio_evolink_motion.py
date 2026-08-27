"""Исполнение motion_render_video через EvoLink (Seedance Sale)."""

from __future__ import annotations

import logging
import math
from typing import Any
from urllib.parse import quote

import anyio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import StudioGeneration, StudioJob, StudioMotionRender, User, UserStudioModel
from app.services.credits import ensure_can_consume_credits, record_usage
from app.services.evolink_client import format_evolink_user_error, seedance_evolink_video_url
from app.services.studio_aspect import aspect_ratio_for_seedance_i2v
from app.services.studio_evolink_motion_pricing import (
    apply_seedance_sale_credit_cost,
    evolink_video_credit_cost,
    evolink_video_duration_seconds,
    normalize_evolink_resolution,
    normalize_evolink_seedance_variant,
)
from app.services.studio_generation_placeholders import find_studio_generation_by_job_id
from app.services.studio_generation_storage import (
    ensure_studio_generation_image_archived_for_external_fetch,
    mark_studio_generation_failed,
    studio_finish_video_generation,
)
from app.services.studio_jobs import job_params
from app.services.studio_keys import load_owner_studio_billing, studio_wavespeed_api_key
from app.services.studio_image_token import (
    create_generation_image_access_token,
    create_model_image_access_token,
    create_motion_video_access_token,
)
from app.services.studio_motion_video import resolve_motion_audio_file, resolve_motion_video_file
from app.services.studio_seedance_t2v import (
    MAX_SEEDANCE_REFERENCE_IMAGES,
    build_seedance_t2v_prompt,
    filter_model_images_for_seedance_motion_swap,
    filter_model_images_for_seedance_video,
    generation_still_fetch_url,
    generation_still_public_url,
    model_reference_public_urls,
)
from app.services.studio_motion_pricing import normalize_seedance_t2v_variant
from app.services.workspace import workspace_owner_id

log = logging.getLogger(__name__)

VIDEO_BACKEND_EVOLINK = "evolink"


def _truthy_flag(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


async def execute_evolink_motion_render_video(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    """Seedance Sale: EvoLink reference/T2V/I2V, всегда кредиты."""
    from app.schemas import StudioMotionVideoOut
    from app.services.studio_image_token import (
        create_generation_image_access_token,
        create_motion_video_access_token,
    )
    from app.services.workspace_model_access import assert_studio_generation_access
    from app.api.studio_routes import _require_studio_subscription

    params = job_params(job)
    oid = workspace_owner_id(user)
    mid = int(params["model_id"])
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
    prompt_only_mode = _truthy_flag(str(params.get("prompt_only_mode") or ""))
    motion_control_wizard = _truthy_flag(str(params.get("motion_control_wizard") or ""))
    turnaround_gid_raw = str(params.get("turnaround_generation_id") or "").strip()

    if not prompt.strip() and not (_truthy_flag(auto_motion_prompt) and mv_id):
        if not (motion_control_wizard and mv_id and turnaround_gid_raw):
            raise RuntimeError("Опишите сцену и движение для видео.")

    sub_b, _llm, ws_row, plan, _credits, _demo = await load_owner_studio_billing(session, oid)
    _require_studio_subscription(user, sub_b, credits_balance=_credits, demo_generations_remaining=_demo)
    ws_key: str | None = None
    try:
        ws_key = studio_wavespeed_api_key(
            plan=plan,
            ws_row=ws_row,
            owner_subscription=sub_b,
            demo_generations_remaining=_demo,
        )
    except Exception:
        ws_key = None

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise RuntimeError("Нужен PUBLIC_APP_URL=https://… для публичных ref URL.")

    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.id == mid, UserStudioModel.user_id == oid)
        .options(selectinload(UserStudioModel.images))
    )
    sm = (await session.execute(stmt)).scalar_one_or_none()
    if not sm:
        raise RuntimeError("Модель не найдена")

    seedance_v = normalize_evolink_seedance_variant(seedance_variant)
    ds_effective = evolink_video_duration_seconds(duration_seconds, variant=seedance_v)
    video_res = normalize_evolink_resolution(video_resolution, variant=seedance_v)

    first_frame_gen_id: int | None = None
    ff_url: str | None = None
    n_start = 0
    if first_frame_gid is not None:
        try:
            first_frame_gen_id = int(first_frame_gid)
        except (TypeError, ValueError):
            first_frame_gen_id = None
    if first_frame_gen_id is not None:
        ff_row = await session.get(StudioGeneration, first_frame_gen_id)
        if not ff_row or ff_row.user_id != oid:
            raise RuntimeError("Первый кадр не найден")
        await ensure_studio_generation_image_archived_for_external_fetch(
            session,
            ff_row,
            wavespeed_api_key=ws_key,
            label="Первый кадр",
        )
        ff_url = generation_still_fetch_url(
            row=ff_row,
            owner_id=oid,
            public_app_base=pub,
            token_factory=create_generation_image_access_token,
        )
        if not ff_url:
            raise RuntimeError("Не удалось подготовить URL первого кадра")
        n_start = 1
    elif params.get("first_frame_path"):
        first_frame_bytes = __import__("app.services.studio_jobs", fromlist=["load_studio_job_file"]).load_studio_job_file(
            str(params["first_frame_path"])
        )
        if len(first_frame_bytes) < 64:
            raise RuntimeError("Загруженный первый кадр пустой")
        from app.services.studio_generation_storage import persist_studio_generation_from_uploaded_bytes

        gen_row = await persist_studio_generation_from_uploaded_bytes(
            session,
            owner_id=oid,
            data=first_frame_bytes,
            content_type=str(params.get("first_frame_mime") or "image/jpeg"),
            output_aspect=output_aspect,
            studio_model_id=mid,
            refined_prompt=None,
            motion_video_prompt_auto=None,
            studio_job_id=job.id,
        )
        if gen_row is None:
            raise RuntimeError("Не удалось сохранить первый кадр")
        first_frame_gen_id = gen_row.id
        await ensure_studio_generation_image_archived_for_external_fetch(
            session,
            gen_row,
            wavespeed_api_key=ws_key,
            label="Загруженный первый кадр",
        )
        ff_url = generation_still_fetch_url(
            row=gen_row,
            owner_id=oid,
            public_app_base=pub,
            token_factory=create_generation_image_access_token,
        )
        n_start = 1

    motion_vid_url: str | None = None
    motion_aud_url: str | None = None
    motion_summary = motion_timeline or None
    vpath = None
    ref_video_duration: int | None = None
    if mv_id:
        if settings.motion_outline_enabled:
            from app.services.motion_video_outline import ensure_motion_outline_ready

            await ensure_motion_outline_ready(oid, mv_id)
        vpath = resolve_motion_video_file(oid, mv_id)
        if vpath is None or not vpath.is_file():
            raise RuntimeError("Референс-видео не найдено.")
        from app.services.studio_motion_video import prepare_motion_video_file_for_duration, save_motion_video_bytes

        if (
            motion_control_wizard
            and str(params.get("trim_mode") or "full").strip().lower() == "part"
            and params.get("trim_start_sec") is not None
            and params.get("trim_end_sec") is not None
        ):
            from app.services.studio_motion_control import trim_motion_video_segment

            trim_start_mc = float(params.get("trim_start_sec"))
            trim_end_mc = float(params.get("trim_end_sec"))
            trimmed_path, is_temp = await anyio.to_thread.run_sync(
                lambda vp=vpath, ts=trim_start_mc, te=trim_end_mc: trim_motion_video_segment(
                    vp, start_sec=ts, end_sec=te
                )
            )
            try:
                mv_id = save_motion_video_bytes(
                    owner_id=oid,
                    raw=trimmed_path.read_bytes(),
                    filename="motion_trim.mp4",
                )
                vpath = resolve_motion_video_file(oid, mv_id)
                duration_seconds = str(int(math.ceil(max(0.5, trim_end_mc - trim_start_mc))))
                ds_effective = evolink_video_duration_seconds(duration_seconds, variant=seedance_v)
            finally:
                if is_temp:
                    trimmed_path.unlink(missing_ok=True)

        mv_id_eff, _vpath_eff, ref_video_duration = prepare_motion_video_file_for_duration(
            owner_id=oid,
            file_id=mv_id,
            source_path=vpath,
            target_sec=ds_effective,
        )
        vid_tok = create_motion_video_access_token(user_id=oid, file_id=mv_id_eff)
        motion_vid_url = f"{pub}/api/studio/public-motion-video?t={quote(vid_tok, safe='')}"
        if _truthy_flag(generate_audio) and resolve_motion_audio_file(oid, mv_id_eff) is not None:
            motion_aud_url = f"{pub}/api/studio/public-motion-audio?t={quote(vid_tok, safe='')}"

    ref_images: list[str] = []
    ref_videos = [motion_vid_url] if motion_vid_url else []
    n_model = 0
    n_outfit = 0
    prompt_source = "template"
    ar_t2v = aspect_ratio_for_seedance_i2v(output_aspect)

    if motion_control_wizard and turnaround_gid_raw and motion_vid_url:
        from app.services.studio_motion_control import MOTION_CONTROL_VIDEO_EDIT_PROMPT

        try:
            turnaround_gid = int(turnaround_gid_raw)
        except ValueError as e:
            raise RuntimeError("Некорректный turnaround_generation_id") from e
        ta_row = await session.get(StudioGeneration, turnaround_gid)
        if not ta_row or ta_row.user_id != oid:
            raise RuntimeError("Развёртка не найдена")
        await ensure_studio_generation_image_archived_for_external_fetch(
            session,
            ta_row,
            wavespeed_api_key=ws_key,
            label="Развёртка Motion Control",
        )
        turnaround_url = generation_still_fetch_url(
            row=ta_row,
            owner_id=oid,
            public_app_base=pub,
            token_factory=create_generation_image_access_token,
        )
        if not turnaround_url:
            raise RuntimeError("Не удалось подготовить URL развёртки")
        ref_images = [turnaround_url]
        seed_prompt = MOTION_CONTROL_VIDEO_EDIT_PROMPT
        prompt_source = "motion_control_video_edit"
    else:
        if motion_vid_url:
            model_imgs = filter_model_images_for_seedance_motion_swap(list(sm.images))
            if not model_imgs and not ff_url:
                raise RuntimeError(
                    "У модели нет фото лица для motion control. Добавьте face или первый кадр."
                )
        elif prompt_only_mode and ff_url:
            # Prompt-only: анимируем приложенный кадр, без подмены лицом из кабинета модели.
            model_imgs = []
        else:
            model_imgs = filter_model_images_for_seedance_video(
                list(sm.images),
                minimal=False,
                include_body=False,
            )

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

        outfit_gen_id: int | None = None
        if outfit_gid is not None:
            try:
                outfit_gen_id = int(outfit_gid)
            except (TypeError, ValueError):
                outfit_gen_id = None
        if outfit_gen_id is not None and outfit_gen_id != first_frame_gen_id:
            row_outfit = await session.get(StudioGeneration, outfit_gen_id)
            if not row_outfit or row_outfit.user_id != oid:
                raise RuntimeError("Снимок наряда не найден")
            await assert_studio_generation_access(session, user, row_outfit.studio_model_id)
            await ensure_studio_generation_image_archived_for_external_fetch(
                session,
                row_outfit,
                wavespeed_api_key=ws_key,
                label="Снимок наряда",
            )
            outfit_url = generation_still_fetch_url(
                row=row_outfit,
                owner_id=oid,
                public_app_base=pub,
                token_factory=create_generation_image_access_token,
            )
            if outfit_url:
                ref_images.append(outfit_url)
                n_outfit = 1

        if len(ref_images) > MAX_SEEDANCE_REFERENCE_IMAGES:
            ref_images = ref_images[:MAX_SEEDANCE_REFERENCE_IMAGES]

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
            reference_only=False,
            remove_face_grid=False,
            soft_identity=False,
        )

    if motion_aud_url:
        from app.services.motion_video_outline import append_motion_original_audio_prompt

        seed_prompt = append_motion_original_audio_prompt(seed_prompt)

    image_to_video = prompt_only_mode and ff_url and not mv_id and not (
        motion_control_wizard and turnaround_gid_raw
    )
    evolink_images = [ff_url] if image_to_video and ff_url else ref_images

    cost = apply_seedance_sale_credit_cost(
        plan,
        evolink_video_credit_cost(
            ds_effective,
            variant=seedance_v,
            resolution=video_res,
            has_motion_reference_video=bool(mv_id),
            reference_video_duration=ref_video_duration,
            reference_image_count=len(evolink_images or []),
        ),
    )
    billing = await ensure_can_consume_credits(session, user, cost)

    video_url: str | None = None
    msg: str | None = None
    try:
        video_url = await seedance_evolink_video_url(
            prompt=seed_prompt,
            variant=seedance_v,
            image_urls=evolink_images or None,
            video_urls=ref_videos or None,
            audio_urls=[motion_aud_url] if motion_aud_url else None,
            aspect_ratio=ar_t2v,
            resolution=video_res,
            duration=ds_effective,
            generate_audio=_truthy_flag(generate_audio),
            session=session,
        )
        log.info(
            "evolink motion_render ok job=%s variant=%s imgs=%s vids=%s src=%s",
            job.id,
            seedance_v,
            len(evolink_images or []),
            len(ref_videos),
            prompt_source,
        )
    except RuntimeError as e:
        msg = str(e)
        video_url = None
        log.warning("evolink motion_render failed job=%s: %s", job.id, msg[:240])

    gen_placeholder = await find_studio_generation_by_job_id(session, job.id)
    ph_id = params.get("placeholder_generation_id")
    if gen_placeholder is None and ph_id is not None:
        try:
            gen_placeholder = await session.get(StudioGeneration, int(ph_id))
        except (TypeError, ValueError):
            gen_placeholder = None

    if gen_placeholder is not None:
        gen_placeholder.video_backend = VIDEO_BACKEND_EVOLINK

    if video_url:
        vu = video_url.strip()
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
                    else first_frame_gen_id,
                    video_url=vu,
                    video_backend=VIDEO_BACKEND_EVOLINK,
                )
            )
        except Exception as e:
            log.warning("evolink motion_render history insert failed: %s", e)
    elif gen_placeholder is not None:
        await mark_studio_generation_failed(
            session,
            gen_placeholder,
            message=msg or format_evolink_user_error("не вернул видео"),
            step="evolink",
        )

    if video_url and cost > 0:
        await record_usage(
            session,
            user,
            billing,
            "studio_seedance_sale",
            cost,
            {
                "studio_model_id": mid,
                "video_backend": VIDEO_BACKEND_EVOLINK,
                "seedance_variant": seedance_v,
                "duration": ds_effective,
                "resolution": video_res,
                "reference_videos": len(ref_videos),
                "reference_images": len(evolink_images or []),
                "prompt_source": prompt_source,
                "ok": True,
            },
        )
    await session.commit()

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
