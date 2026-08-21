"""Step-by-step shot-batch wizard: plan → opening frames → batch videos → stitch."""

from __future__ import annotations

import logging
import math
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import StudioJob, StudioJobStatus, User, UserStudioModel
from app.services.evolink_client import evolink_upload_file_bytes, seedance_evolink_video_url
from app.services.evolink_client import evolink_platform_api_key
from app.services.motion_video_outline import append_motion_original_audio_prompt
from app.services.studio_evolink_motion_pricing import (
    evolink_video_duration_seconds,
    normalize_evolink_resolution,
    normalize_evolink_seedance_variant,
)
from app.services.studio_image_token import (
    create_model_image_access_token,
    create_motion_video_access_token,
    create_shot_batch_output_access_token,
)
from app.services.studio_jobs import (
    create_studio_job,
    job_params,
    job_result_dict,
    load_studio_job_file,
    save_studio_job_file,
    studio_job_dir,
    update_studio_job_params,
    update_studio_job_result,
)
from app.services.studio_motion_video import (
    _ffmpeg_bin,
    prepare_motion_video_file_for_duration,
    resolve_motion_audio_file,
)
from app.services.studio_seedance_t2v import (
    MAX_SEEDANCE_REFERENCE_IMAGES,
    build_seedance_t2v_prompt,
    filter_model_images_for_seedance_motion_swap,
    filter_model_images_for_seedance_video_face_only,
    model_reference_public_urls,
)
from app.services.studio_aspect import aspect_ratio_for_seedance_i2v
from app.services.workspace import workspace_owner_id
from app.services.studio_shot_batch_plan import plan_shot_batches
from app.services.studio_shot_batch_render import (
    _download_url_bytes,
    _extract_last_frame_jpeg,
    _extract_opening_frame_jpeg,
    _generate_synthetic_opening_frame,
    _jpeg_data_url,
    _run_ffmpeg,
    _stitch_video_urls_to_mp4,
    _trim_rendered_video_to_duration,
    _trim_segment_to_motion_root,
    prepare_shot_batch_motion_ref,
    resolve_shot_batch_wave_settings,
    _truthy,
)

log = logging.getLogger(__name__)

WIZARD_JOB_TYPES = frozenset({"shot_batch_render", "shot_batch_wizard"})


def _empty_wizard_state(*, crossfade_ms: int = 0) -> dict[str, Any]:
    return {
        "wizard_phase": "created",
        "crossfade_ms": int(crossfade_ms),
        "use_previous_tail_as_opening": True,
        "identity_anchor_batch_id": None,
        "plan": None,
        "batches": {},
        "stitched": {"status": "pending"},
    }


def _batch_key(batch_id: int | str) -> str:
    return str(int(batch_id))


def _public_media_url(
    *,
    pub: str,
    owner_id: int,
    job_id: int,
    kind: str,
    batch_id: int | None = None,
    frame_name: str | None = None,
    cache_version: int | str | None = None,
) -> str:
    tok = create_shot_batch_output_access_token(
        user_id=owner_id,
        job_id=job_id,
        kind=kind,
        batch_id=batch_id,
        frame_name=frame_name,
    )
    url = f"{pub}/api/studio/public-shot-batch-output?t={quote(tok, safe='')}"
    if cache_version is not None:
        url = f"{url}&v={quote(str(cache_version), safe='')}"
    return url


async def _save_state(session: AsyncSession, job: StudioJob, state: dict[str, Any]) -> dict[str, Any]:
    await update_studio_job_result(
        session,
        job,
        state,
        status=StudioJobStatus.completed.value,
    )
    return state


def _wizard_state(job: StudioJob) -> dict[str, Any]:
    raw = job_result_dict(job)
    if isinstance(raw, dict) and raw.get("wizard_phase"):
        return raw
    return _empty_wizard_state()


def _load_source_video_path(p: dict[str, Any]) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    rel = str(p.get("motion_video_path") or "").strip()
    if not rel:
        raise RuntimeError("motion_video_path missing")
    raw = load_studio_job_file(rel)
    if len(raw) < 64:
        raise RuntimeError("empty motion video")
    suffix = str(p.get("motion_video_suffix") or ".mp4").strip() or ".mp4"
    if not suffix.startswith("."):
        suffix = "." + suffix
    td = tempfile.TemporaryDirectory()
    src_path = Path(td.name) / f"wizard_src{suffix}"
    src_path.write_bytes(raw)
    return src_path, td


async def _load_model_context(
    session: AsyncSession,
    *,
    owner_id: int,
    model_id: int,
    pub: str,
    face_only: bool = False,
) -> tuple[UserStudioModel, list[str]]:
    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.id == model_id, UserStudioModel.user_id == owner_id)
        .options(selectinload(UserStudioModel.images))
    )
    sm = (await session.execute(stmt)).scalar_one_or_none()
    if not sm:
        raise RuntimeError("studio model not found")
    imgs = list(sm.images)
    if face_only:
        model_imgs = filter_model_images_for_seedance_video_face_only(imgs)
        if not model_imgs:
            model_imgs = filter_model_images_for_seedance_motion_swap(imgs)[:1]
    else:
        model_imgs = filter_model_images_for_seedance_motion_swap(imgs)
    if not model_imgs:
        raise RuntimeError("model has no face refs for motion")
    model_urls = model_reference_public_urls(
        owner_id=owner_id,
        images=model_imgs,
        public_app_base=pub,
        token_factory=create_model_image_access_token,
    )
    if not model_urls:
        raise RuntimeError("no model reference urls")
    return sm, model_urls


def _opening_locks_wardrobe(opening: dict[str, Any] | None, *, batch_id: int) -> bool:
    """Approved opening is always wardrobe/scene authority (@Image1), including batch 1."""
    _ = opening
    _ = batch_id
    return True


def _identity_brief(base: str, *, batch_id: int, wardrobe_from_opening: bool = False) -> str:
    brief = (base or "").strip()
    lock = ""
    if batch_id > 1:
        lock += (
            " CRITICAL continuity: same person as the approved previous batch. "
            "Use THIS batch pose, camera and composition from the current segment — "
            "do not copy the previous batch start frame."
        )
    if wardrobe_from_opening:
        lock += (
            " WARDROBE+SCENE LOCK: clothing, shoes, accessories, location and background "
            "must match @Image1 for the ENTIRE clip. Model reference images confirm identity — "
            "ignore any outfit shown on those model photos. Never switch into the outfit or set from @Video1."
        )
    elif batch_id > 1:
        lock += " Keep the same outfit and styling as the approved previous batch."
    return (brief + lock).strip()


def _append_wardrobe_from_opening_lock(prompt: str) -> str:
    lock = (
        "WARDROBE+SCENE LOCK: Keep the exact clothing, shoes, accessories, location and "
        "background from @Image1 in every frame. @Image2+ are identity references — do not copy outfits "
        "from model photos. @Video1 is motion/choreography only — never adopt its wardrobe or location."
    )
    body = (prompt or "").strip()
    if "WARDROBE+SCENE LOCK:" in body or "WARDROBE LOCK:" in body:
        return body
    return f"{body}\n\n{lock}".strip() if body else lock


def _append_character_swap_lock(prompt: str) -> str:
    lock = (
        "CHARACTER SWAP LOCK: The person in every frame must be the same as @Image1 "
        "(identity confirmed by @Image2+). Completely remove the @Video1 performer — "
        "never show their face or body. Keep only motion/camera from @Video1."
    )
    body = (prompt or "").strip()
    if "CHARACTER SWAP LOCK:" in body:
        return body
    return f"{body}\n\n{lock}".strip() if body else lock


async def wizard_create_job(
    session: AsyncSession,
    user: User,
    *,
    motion_bytes: bytes,
    motion_suffix: str,
    params: dict[str, Any],
    crossfade_ms: int = 0,
) -> tuple[StudioJob, dict[str, Any]]:
    oid = workspace_owner_id(user)
    wave_model, wan_tier, wave_profile = resolve_shot_batch_wave_settings(
        params.get("workflow_wave_model"),
        params.get("wan_edit_tier"),
    )
    stored = {
        **params,
        "motion_video_path": "",
        "motion_video_suffix": motion_suffix,
        "workflow_wave_model": wave_model or "",
        "wan_edit_tier": wan_tier,
        "studio_wave_profile": wave_profile,
    }
    job = await create_studio_job(
        session,
        owner_id=oid,
        actor_user_id=user.id,
        job_type="shot_batch_wizard",
        params=stored,
    )
    rel = save_studio_job_file(job.id, "motion_video.bin", motion_bytes)
    p = job_params(job)
    p["motion_video_path"] = rel
    await update_studio_job_params(session, job, p)
    state = _empty_wizard_state(crossfade_ms=crossfade_ms)
    await _save_state(session, job, state)
    return job, state


async def wizard_run_plan(session: AsyncSession, job: StudioJob, user: User) -> dict[str, Any]:
    p = job_params(job)
    state = _wizard_state(job)
    src_path, td = _load_source_video_path(p)
    try:
        plan: dict[str, Any] = await anyio.to_thread.run_sync(
            lambda: plan_shot_batches(
                src_path,
                scene_threshold=float(p.get("scene_threshold") or 0.35),
                max_shots_per_batch=int(p.get("max_shots_per_batch") or 4),
                max_batch_duration_sec=float(p.get("max_batch_duration_sec") or 4),
                min_shot_duration_sec=float(p.get("min_shot_duration_sec") or 0.4),
                face_samples=int(p.get("face_samples") or 6),
                target_batch_duration_sec=float(p.get("target_batch_duration_sec") or p.get("max_batch_duration_sec") or 4),
            )
        )
    finally:
        td.cleanup()

    resolved = plan.get("resolved_batches") or []
    if not isinstance(resolved, list) or not resolved:
        raise RuntimeError("no resolved_batches in plan")

    oid = workspace_owner_id(user)
    pub = (settings.public_app_url or "").strip().rstrip("/")
    out_dir = studio_job_dir(int(job.id))
    out_dir.mkdir(parents=True, exist_ok=True)

    batches: dict[str, Any] = {}
    src_path2, td2 = _load_source_video_path(p)
    try:
        for rb in resolved:
            bid = int(rb.get("id") or 0)
            if bid <= 0:
                continue
            t_start = float(rb.get("effective_t_start") or 0.0)
            seg_jpeg = await anyio.to_thread.run_sync(
                lambda ts=t_start, sp=src_path2: _extract_opening_frame_jpeg(sp, t=ts)
            )
            seg_name = f"segment_preview_batch_{bid}.jpg"
            (out_dir / seg_name).write_bytes(seg_jpeg)
            batches[_batch_key(bid)] = {
                "batch_id": bid,
                "resolved": rb,
                "segment_preview_url": _jpeg_data_url(seg_jpeg),
                "segment_preview_public_url": _public_media_url(
                    pub=pub,
                    owner_id=oid,
                    job_id=int(job.id),
                    kind="frame",
                    frame_name=seg_name,
                ),
                "opening": {
                    "status": "pending",
                    "generation": 0,
                    "mode": None,
                    "source_mode": None,
                    "source_label": None,
                    "preview_url": None,
                    "public_url": None,
                    "evolink_url": None,
                    "local_name": None,
                },
                "video": {
                    "status": "pending",
                    "generation": 0,
                    "start_frame_mode": None,
                    "start_frame_label": None,
                    "start_frame_public_url": None,
                    "preview_public_url": None,
                    "provider_url": None,
                    "local_name": None,
                },
            }
    finally:
        td2.cleanup()

    state["wizard_phase"] = "planned"
    state["plan"] = plan
    state["batches"] = batches
    state["stitched"] = {"status": "pending"}
    return await _save_state(session, job, state)


def _sorted_batch_ids(state: dict[str, Any]) -> list[int]:
    batches = state.get("batches") or {}
    ids: list[int] = []
    for k in batches:
        try:
            ids.append(int(k))
        except (TypeError, ValueError):
            continue
    return sorted(ids)


def _prev_approved_video_path(state: dict[str, Any], batch_id: int, out_dir: Path) -> Path | None:
    for bid in reversed(_sorted_batch_ids(state)):
        if bid >= batch_id:
            continue
        entry = (state.get("batches") or {}).get(_batch_key(bid)) or {}
        video = entry.get("video") or {}
        if video.get("status") != "approved":
            continue
        name = str(video.get("local_name") or "").strip()
        if not name:
            continue
        path = out_dir / name
        if path.is_file():
            return path
    return None


def _opening_source_label(mode: str | None) -> str:
    m = str(mode or "").strip().lower()
    if m == "previous_batch_tail":
        return "last frame of previous approved batch video"
    if m == "manual_upload":
        return "uploaded opening image"
    return "first frame of current segment"


def _set_opening_ready(
    *,
    opening: dict[str, Any],
    status: str,
    generation: int,
    mode: str,
    source_mode: str,
    preview_url: str,
    public_url: str,
    evolink_url: str,
    local_name: str,
) -> dict[str, Any]:
    opening.update(
        {
            "status": status,
            "generation": generation,
            "mode": mode,
            "source_mode": source_mode,
            "source_label": _opening_source_label(source_mode),
            "preview_url": preview_url,
            "public_url": public_url,
            "evolink_url": evolink_url,
            "local_name": local_name,
        }
    )
    return opening


async def _prefill_next_batch_opening_from_previous_video(
    session: AsyncSession,
    job: StudioJob,
    user: User,
    *,
    approved_batch_id: int,
    state: dict[str, Any],
) -> dict[str, Any]:
    next_batch_id = int(approved_batch_id) + 1
    key = _batch_key(next_batch_id)
    entry = (state.get("batches") or {}).get(key)
    if not entry:
        return state
    opening = dict(entry.get("opening") or {})
    # Never overwrite an already approved next opening.
    if opening.get("status") == "approved":
        return state
    # Keep a user-made ready opening (generate/upload) unless it was auto-prefilled.
    mode = str(opening.get("mode") or "").strip().lower()
    if opening.get("status") == "ready" and mode not in ("", "auto_prefilled_tail", "pending"):
        return state

    out_dir = studio_job_dir(int(job.id))
    prev_path = _prev_approved_video_path(state, next_batch_id, out_dir)
    if prev_path is None:
        return state

    oid = workspace_owner_id(user)
    pub = (settings.public_app_url or "").strip().rstrip("/")
    jpeg = await anyio.to_thread.run_sync(lambda pp=prev_path: _extract_last_frame_jpeg(pp))
    gen = max(1, int(opening.get("generation") or 0) + 1)
    local_name = f"opening_batch_{next_batch_id}_g{gen}.jpg"
    (out_dir / local_name).write_bytes(jpeg)
    opening_url = await evolink_upload_file_bytes(
        data=jpeg,
        filename=local_name,
        content_type="image/jpeg",
    )
    entry["opening"] = _set_opening_ready(
        opening=opening,
        status="ready",
        generation=gen,
        mode="auto_prefilled_tail",
        source_mode="previous_batch_tail",
        preview_url=_jpeg_data_url(jpeg),
        public_url=_public_media_url(
            pub=pub,
            owner_id=oid,
            job_id=int(job.id),
            kind="frame",
            frame_name=local_name,
        ),
        evolink_url=opening_url,
        local_name=local_name,
    )
    state["batches"][key] = entry
    if state.get("wizard_phase") == "planned":
        state["wizard_phase"] = "openings"
    return state


def _normalize_uploaded_batch_mp4(video_bytes: bytes, dest: Path) -> None:
    """Remux/re-encode uploads so last-frame extract and stitch stay reliable."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "upload.bin"
        out = Path(td) / "normalized.mp4"
        src.write_bytes(video_bytes)
        base = [_ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
        try:
            _run_ffmpeg(
                [*base, "-c", "copy", "-movflags", "+faststart", str(out)],
                timeout=180,
            )
        except Exception:
            _run_ffmpeg(
                [
                    *base,
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    str(out),
                ],
                timeout=600,
            )
        if not out.is_file() or out.stat().st_size < 1024:
            raise RuntimeError("не удалось нормализовать загруженный клип (ffmpeg)")
        dest.write_bytes(out.read_bytes())


async def wizard_upload_video(
    session: AsyncSession,
    job: StudioJob,
    user: User,
    *,
    batch_id: int,
    video_bytes: bytes,
    filename: str | None = None,
) -> dict[str, Any]:
    """Attach an already-rendered batch clip (skip Seedance render)."""
    state = _wizard_state(job)
    if state.get("wizard_phase") not in ("planned", "openings", "videos", "stitched"):
        raise RuntimeError("run plan first")
    if not video_bytes or len(video_bytes) < 1024:
        raise RuntimeError("uploaded batch video is empty")

    key = _batch_key(batch_id)
    entry = (state.get("batches") or {}).get(key)
    if not entry:
        raise RuntimeError(f"unknown batch {batch_id}")

    oid = workspace_owner_id(user)
    pub = (settings.public_app_url or "").strip().rstrip("/")
    out_dir = studio_job_dir(int(job.id))
    out_dir.mkdir(parents=True, exist_ok=True)

    video = dict(entry.get("video") or {})
    gen = int(video.get("generation") or 0) + 1
    local_name = f"batch_{batch_id}_g{gen}.mp4"
    path = out_dir / local_name
    await anyio.to_thread.run_sync(lambda: _normalize_uploaded_batch_mp4(video_bytes, path))
    rb = entry.get("resolved") or {}
    target = float(rb.get("effective_duration") or 0.0)
    if target > 0.2:
        trimmed = out_dir / f"batch_{batch_id}_g{gen}_trim.mp4"
        probed = await anyio.to_thread.run_sync(
            lambda: _trim_rendered_video_to_duration(
                source_path=path,
                out_path=trimmed,
                duration_sec=target,
            )
        )
        path.write_bytes(trimmed.read_bytes())
        trimmed.unlink(missing_ok=True)
    else:
        probed = None
    canonical = out_dir / f"batch_{batch_id}.mp4"
    canonical.write_bytes(path.read_bytes())

    opening = entry.get("opening") or {}
    video.update(
        {
            "status": "ready",
            "generation": gen,
            "mode": "manual_upload",
            "provider_url": None,
            "local_name": local_name,
            "target_duration_sec": target if target > 0.2 else None,
            "trimmed_duration_sec": probed,
            "start_frame_mode": opening.get("source_mode") or opening.get("mode") or "manual_upload",
            "start_frame_label": opening.get("source_label")
            or "uploaded batch video (opening optional)",
            "start_frame_public_url": opening.get("public_url"),
            "preview_public_url": _public_media_url(
                pub=pub,
                owner_id=oid,
                job_id=int(job.id),
                kind="batch",
                batch_id=batch_id,
                cache_version=gen,
            ),
            "uploaded_filename": (filename or "").strip() or None,
        }
    )
    entry["video"] = video
    state["batches"][key] = entry
    state["wizard_phase"] = "videos"
    return await _save_state(session, job, state)


async def wizard_upload_opening(
    session: AsyncSession,
    job: StudioJob,
    user: User,
    *,
    batch_id: int,
    image_bytes: bytes,
    filename: str | None = None,
) -> dict[str, Any]:
    p = job_params(job)
    state = _wizard_state(job)
    if state.get("wizard_phase") not in ("planned", "openings", "videos", "stitched"):
        raise RuntimeError("run plan first")
    if not image_bytes or len(image_bytes) < 64:
        raise RuntimeError("uploaded opening image is empty")

    key = _batch_key(batch_id)
    entry = (state.get("batches") or {}).get(key)
    if not entry:
        raise RuntimeError(f"unknown batch {batch_id}")

    oid = workspace_owner_id(user)
    pub = (settings.public_app_url or "").strip().rstrip("/")
    opening = dict(entry.get("opening") or {})
    gen = int(opening.get("generation") or 0) + 1
    local_name = f"opening_batch_{batch_id}_g{gen}.jpg"
    out_dir = studio_job_dir(int(job.id))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / local_name).write_bytes(image_bytes)
    opening_url = await evolink_upload_file_bytes(
        data=image_bytes,
        filename=filename or local_name,
        content_type="image/jpeg",
    )
    entry["opening"] = _set_opening_ready(
        opening=opening,
        status="ready",
        generation=gen,
        mode="manual_upload",
        source_mode="manual_upload",
        preview_url=_jpeg_data_url(image_bytes),
        public_url=_public_media_url(
            pub=pub,
            owner_id=oid,
            job_id=int(job.id),
            kind="frame",
            frame_name=local_name,
        ),
        evolink_url=opening_url,
        local_name=local_name,
    )
    state["batches"][key] = entry
    state["wizard_phase"] = "openings"
    return await _save_state(session, job, state)


async def wizard_generate_opening(
    session: AsyncSession,
    job: StudioJob,
    user: User,
    *,
    batch_id: int,
) -> dict[str, Any]:
    p = job_params(job)
    state = _wizard_state(job)
    if state.get("wizard_phase") not in ("planned", "openings", "videos", "stitched"):
        raise RuntimeError("run plan first")

    key = _batch_key(batch_id)
    entry = (state.get("batches") or {}).get(key)
    if not entry:
        raise RuntimeError(f"unknown batch {batch_id}")

    rb = entry.get("resolved") or {}
    oid = workspace_owner_id(user)
    mid = int(str(p.get("model_id") or "").strip())
    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise RuntimeError("PUBLIC_APP_URL must be https://")

    prompt = str(p.get("scene_brief") or p.get("prompt") or "").strip()
    output_aspect = str(p.get("output_aspect") or "9:16")
    out_dir = studio_job_dir(int(job.id))

    opening = dict(entry.get("opening") or {})
    gen = int(opening.get("generation") or 0) + 1
    opening["generation"] = gen
    opening["status"] = "generating"

    src_path, td = _load_source_video_path(p)
    try:
        eff_start = float(rb.get("effective_t_start") or 0.0)
        eff_end = float(rb.get("effective_t_end") or 0.0)

        seg_file_id, seg_path = await anyio.to_thread.run_sync(
            lambda: _trim_segment_to_motion_root(
                owner_id=oid,
                src_video_path=src_path,
                t_start=eff_start,
                t_end=eff_end,
            )
        )
        ds = max(1, int(math.ceil(float(rb.get("effective_duration") or (eff_end - eff_start)))))
        ds_effective = evolink_video_duration_seconds(
            ds,
            variant=normalize_evolink_seedance_variant(str(p.get("seedance_variant") or "standard")),
        )
        _mv_id, vpath_eff, _ = await anyio.to_thread.run_sync(
            lambda: prepare_motion_video_file_for_duration(
                owner_id=oid,
                file_id=seg_file_id,
                source_path=seg_path,
                target_sec=ds_effective,
            )
        )

        mode = "extracted"
        opening_jpeg: bytes | None = None
        use_tail = _truthy(state.get("use_previous_tail_as_opening", True))
        if batch_id > 1 and use_tail:
            prev_path = _prev_approved_video_path(state, batch_id, out_dir)
            if prev_path is not None:
                opening_jpeg = await anyio.to_thread.run_sync(
                    lambda pp=prev_path: _extract_last_frame_jpeg(pp)
                )
                mode = "previous_batch_tail"

        if opening_jpeg is None:
            opening_jpeg = await anyio.to_thread.run_sync(
                lambda vp=vpath_eff: _extract_opening_frame_jpeg(vp, t=0.0)
            )
            mode = "extracted"

        source_mode = mode
        scene = _identity_brief(prompt, batch_id=batch_id)

        display_jpeg = opening_jpeg
        if rb.get("requires_synthetic_opening_frame") or batch_id > 1:
            try:
                synth = await _generate_synthetic_opening_frame(
                    session=session,
                    user=user,
                    owner_id=oid,
                    model_id=mid,
                    scene_brief=scene,
                    output_aspect=output_aspect,
                    segment_video_path=vpath_eff,
                    opening_frame_jpeg=opening_jpeg,
                    lock_model_hairstyle=batch_id > 1,
                    workflow_wave_model=str(p.get("workflow_wave_model") or "").strip() or None,
                    wan_edit_tier=str(p.get("wan_edit_tier") or "standard"),
                    studio_wave_profile=str(p.get("studio_wave_profile") or "").strip() or None,
                )
            except Exception as e:
                log.warning("wizard opening synth failed job=%s batch=%s: %s", job.id, batch_id, e)
                synth = None
            synth_url = str((synth or {}).get("generated_image_url") or "").strip()
            if synth_url:
                opening_url = synth_url
                mode = "synthetic_generated"
                try:
                    display_jpeg = await _download_url_bytes(synth_url)
                except Exception as e:
                    log.warning(
                        "wizard opening synth download failed job=%s batch=%s: %s",
                        job.id,
                        batch_id,
                        e,
                    )
            else:
                opening_url = await evolink_upload_file_bytes(
                    data=opening_jpeg,
                    filename=f"opening_batch_{batch_id}_g{gen}.jpg",
                    content_type="image/jpeg",
                )
        else:
            opening_url = await evolink_upload_file_bytes(
                data=opening_jpeg,
                filename=f"opening_batch_{batch_id}_g{gen}.jpg",
                content_type="image/jpeg",
            )

        local_name = f"opening_batch_{batch_id}_g{gen}.jpg"
        (out_dir / local_name).write_bytes(display_jpeg)

        entry["opening"] = _set_opening_ready(
            opening=opening,
            status="ready",
            generation=gen,
            mode=mode,
            source_mode=source_mode,
            preview_url=_jpeg_data_url(display_jpeg),
            public_url=_public_media_url(
                pub=pub,
                owner_id=oid,
                job_id=int(job.id),
                kind="frame",
                frame_name=local_name,
            ),
            evolink_url=opening_url,
            local_name=local_name,
        )
    finally:
        td.cleanup()

    state["batches"][key] = entry
    state["wizard_phase"] = "openings"
    return await _save_state(session, job, state)


async def wizard_approve_opening(
    session: AsyncSession,
    job: StudioJob,
    *,
    batch_id: int,
) -> dict[str, Any]:
    state = _wizard_state(job)
    key = _batch_key(batch_id)
    entry = (state.get("batches") or {}).get(key)
    if not entry:
        raise RuntimeError(f"unknown batch {batch_id}")
    opening = entry.get("opening") or {}
    if opening.get("status") not in ("ready", "approved"):
        raise RuntimeError("generate opening frame first")
    opening["status"] = "approved"
    entry["opening"] = opening
    state["batches"][key] = entry
    if state.get("identity_anchor_batch_id") is None:
        state["identity_anchor_batch_id"] = batch_id
    state["wizard_phase"] = "openings"
    return await _save_state(session, job, state)


async def wizard_render_batch(
    session: AsyncSession,
    job: StudioJob,
    user: User,
    *,
    batch_id: int,
) -> dict[str, Any]:
    p = job_params(job)
    state = _wizard_state(job)
    key = _batch_key(batch_id)
    entry = (state.get("batches") or {}).get(key)
    if not entry:
        raise RuntimeError(f"unknown batch {batch_id}")

    opening = entry.get("opening") or {}
    if opening.get("status") != "approved":
        raise RuntimeError("approve opening frame before rendering video")

    rb = entry.get("resolved") or {}
    oid = workspace_owner_id(user)
    mid = int(str(p.get("model_id") or "").strip())
    pub = (settings.public_app_url or "").strip().rstrip("/")
    prompt = str(p.get("scene_brief") or p.get("prompt") or "").strip()
    negative_prompt = str(p.get("negative_prompt") or "").strip()
    motion_timeline = str(p.get("motion_timeline") or "").strip()
    output_aspect = str(p.get("output_aspect") or "9:16")
    generate_audio = _truthy(p.get("generate_audio") or "0")
    video_resolution = str(p.get("video_resolution") or settings.evolink_video_default_resolution)
    seedance_variant = normalize_evolink_seedance_variant(str(p.get("seedance_variant") or "standard"))

    wardrobe_from_opening = _opening_locks_wardrobe(opening, batch_id=batch_id)
    # Use full motion-swap identity refs (face+turnaround/body). Face-only was too weak
    # vs @Video1 and Seedance kept the reference actor. Wardrobe still locked to @Image1.
    _sm, model_urls = await _load_model_context(
        session,
        owner_id=oid,
        model_id=mid,
        pub=pub,
        face_only=False,
    )
    _ = evolink_platform_api_key()

    video = dict(entry.get("video") or {})
    gen = int(video.get("generation") or 0) + 1
    video["generation"] = gen
    video["status"] = "generating"

    eff_start = float(rb.get("effective_t_start") or 0.0)
    eff_end = float(rb.get("effective_t_end") or 0.0)
    eff_dur = float(rb.get("effective_duration") or (eff_end - eff_start))
    requested_dur = max(1, int(math.ceil(eff_dur)))
    ds_effective = evolink_video_duration_seconds(requested_dur, variant=seedance_variant)
    video_res = normalize_evolink_resolution(video_resolution, variant=seedance_variant)
    ar_t2v = aspect_ratio_for_seedance_i2v(output_aspect)

    src_path, td = _load_source_video_path(p)
    out_dir = studio_job_dir(int(job.id))
    try:
        # Edge-outline like motion control: @Video1 carries silhouette/motion only,
        # so Seedance cannot keep the reference actor (opening stays @Image1 identity).
        mv_id_eff, _vpath_eff, _raw_color, motion_outlined = await prepare_shot_batch_motion_ref(
            owner_id=oid,
            src_video_path=src_path,
            t_start=eff_start,
            t_end=eff_end,
            target_sec=ds_effective,
        )
        vid_tok = create_motion_video_access_token(user_id=oid, file_id=mv_id_eff)
        motion_vid_url = f"{pub}/api/studio/public-motion-video?t={quote(vid_tok, safe='')}"
        motion_aud_url: str | None = None
        if generate_audio and resolve_motion_audio_file(oid, mv_id_eff) is not None:
            motion_aud_url = f"{pub}/api/studio/public-motion-audio?t={quote(vid_tok, safe='')}"

        opening_url = str(opening.get("evolink_url") or "").strip()
        if not opening_url:
            raise RuntimeError("approved opening has no evolink_url")

        scene = _identity_brief(
            prompt,
            batch_id=batch_id,
            wardrobe_from_opening=wardrobe_from_opening,
        )
        seed_prompt, _prompt_source = await build_seedance_t2v_prompt(
            user_brief=scene,
            n_start_frame=1,
            n_model_images=len(model_urls),
            n_outfit_images=0,
            n_motion_videos=1,
            motion_summary=motion_timeline or None,
            model_profile_text=None,
            negative=negative_prompt,
            output_aspect=ar_t2v or output_aspect,
            duration_seconds=ds_effective,
            force_template=False,
            reference_only=False,
            remove_face_grid=False,
            soft_identity=False,
        )
        seed_prompt = _append_character_swap_lock(seed_prompt)
        if wardrobe_from_opening:
            seed_prompt = _append_wardrobe_from_opening_lock(seed_prompt)
        if motion_aud_url:
            seed_prompt = append_motion_original_audio_prompt(seed_prompt)

        # First image is THIS batch opening / start frame. Do not append previous
        # batch openings — Seedance treats extra stills as competing start frames.
        evolink_images = [opening_url] + list(model_urls)
        evolink_images = evolink_images[:MAX_SEEDANCE_REFERENCE_IMAGES]

        provider_url = await seedance_evolink_video_url(
            prompt=seed_prompt,
            variant=seedance_variant,
            image_urls=evolink_images,
            video_urls=[motion_vid_url],
            audio_urls=[motion_aud_url] if motion_aud_url else None,
            aspect_ratio=ar_t2v,
            resolution=video_res,
            duration=ds_effective,
            generate_audio=generate_audio,
            session=session,
        )

        rendered_raw = await _download_url_bytes(provider_url)
        raw_path = out_dir / f"batch_{batch_id}_g{gen}_provider.mp4"
        raw_path.write_bytes(rendered_raw)
        local_name = f"batch_{batch_id}_g{gen}.mp4"
        trimmed_path = out_dir / local_name
        # Seedance may return duration_min (4s) even when the planned batch is shorter —
        # always cut back to effective source length so stitch does not keep freeze padding.
        trim_target = max(0.2, float(eff_dur))
        probed_trim = await anyio.to_thread.run_sync(
            lambda: _trim_rendered_video_to_duration(
                source_path=raw_path,
                out_path=trimmed_path,
                duration_sec=trim_target,
            )
        )

        video.update(
            {
                "status": "ready",
                "start_frame_mode": opening.get("source_mode") or opening.get("mode"),
                "start_frame_label": opening.get("source_label") or _opening_source_label(opening.get("source_mode")),
                "start_frame_public_url": opening.get("public_url"),
                "provider_url": provider_url,
                "local_name": local_name,
                "provider_duration_sec": ds_effective,
                "target_duration_sec": trim_target,
                "trimmed_duration_sec": probed_trim,
                "motion_outline": bool(motion_outlined),
                "preview_public_url": _public_media_url(
                    pub=pub,
                    owner_id=oid,
                    job_id=int(job.id),
                    kind="batch",
                    batch_id=batch_id,
                    cache_version=gen,
                ),
            }
        )
        canonical = out_dir / f"batch_{batch_id}.mp4"
        canonical.write_bytes(trimmed_path.read_bytes())
    finally:
        td.cleanup()

    entry["video"] = video
    state["batches"][key] = entry
    state["wizard_phase"] = "videos"
    return await _save_state(session, job, state)


async def wizard_approve_video(
    session: AsyncSession,
    job: StudioJob,
    user: User,
    *,
    batch_id: int,
) -> dict[str, Any]:
    state = _wizard_state(job)
    key = _batch_key(batch_id)
    entry = (state.get("batches") or {}).get(key)
    if not entry:
        raise RuntimeError(f"unknown batch {batch_id}")
    video = dict(entry.get("video") or {})
    if video.get("status") not in ("ready", "approved"):
        raise RuntimeError("render batch video first")
    video["status"] = "approved"
    video.pop("prefill_next_error", None)
    entry["video"] = video
    state["batches"][key] = entry
    state["wizard_phase"] = "videos"
    try:
        state = await _prefill_next_batch_opening_from_previous_video(
            session,
            job,
            user,
            approved_batch_id=batch_id,
            state=state,
        )
    except Exception as e:  # noqa: BLE001 - keep approve; user can upload/generate next opening
        entry = (state.get("batches") or {}).get(key) or entry
        video = dict(entry.get("video") or {})
        video["prefill_next_error"] = str(e)
        entry["video"] = video
        state["batches"][key] = entry
    return await _save_state(session, job, state)


async def wizard_stitch(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    state = _wizard_state(job)
    out_dir = studio_job_dir(int(job.id))
    oid = workspace_owner_id(user)
    pub = (settings.public_app_url or "").strip().rstrip("/")

    video_paths: list[str] = []
    with tempfile.TemporaryDirectory() as td_name:
        td = Path(td_name)
        for bid in _sorted_batch_ids(state):
            entry = (state.get("batches") or {}).get(_batch_key(bid)) or {}
            video = entry.get("video") or {}
            if video.get("status") != "approved":
                raise RuntimeError(f"batch {bid} video not approved")
            name = str(video.get("local_name") or "").strip()
            path = out_dir / name
            if not path.is_file():
                raise RuntimeError(f"batch {bid} video file missing")
            rb = entry.get("resolved") or {}
            target = float(
                video.get("target_duration_sec")
                or rb.get("effective_duration")
                or 0.0
            )
            if target > 0.2:
                # Safety net: drop Seedance min-duration pad even if an older render
                # skipped trim or a manual upload kept the padded length.
                stitch_clip = td / f"stitch_batch_{bid}.mp4"
                await anyio.to_thread.run_sync(
                    lambda src=path, dst=stitch_clip, dur=target: _trim_rendered_video_to_duration(
                        source_path=src,
                        out_path=dst,
                        duration_sec=dur,
                    )
                )
                video_paths.append(stitch_clip.as_posix())
            else:
                video_paths.append(path.as_posix())

        if not video_paths:
            raise RuntimeError("no approved batch videos")

        crossfade_ms = int(state.get("crossfade_ms") or 0)
        stitch_gen = int(state.get("stitch_generation") or 0) + 1
        out_path = out_dir / "shot_batch_output.mp4"
        # Hard cut + tiny head trim removes duplicate opening frame from previous-tail continuity.
        seam_trim_sec = 0.08 if crossfade_ms <= 0 and len(video_paths) >= 2 else 0.0
        await anyio.to_thread.run_sync(
            lambda: _stitch_video_urls_to_mp4(
                video_urls=video_paths,
                out_path=out_path,
                crossfade_ms=crossfade_ms,
                seam_trim_sec=seam_trim_sec,
            )
        )

    state["stitched"] = {
        "status": "ready",
        "local_path": out_path.as_posix(),
        "public_url": _public_media_url(
            pub=pub,
            owner_id=oid,
            job_id=int(job.id),
            kind="stitched",
            cache_version=stitch_gen,
        ),
        "endpoint": f"/api/studio/debug/shot-batch-output/{job.id}",
        "crossfade_ms": crossfade_ms,
        "seam_trim_sec": seam_trim_sec,
        "generation": stitch_gen,
    }
    state["stitch_generation"] = stitch_gen
    state["wizard_phase"] = "stitched"
    return await _save_state(session, job, state)


def wizard_state_for_api(job: StudioJob) -> dict[str, Any]:
    state = _wizard_state(job)
    p = job_params(job)
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "params": {
            "seedance_variant": p.get("seedance_variant"),
            "video_resolution": p.get("video_resolution"),
            "workflow_wave_model": p.get("workflow_wave_model"),
            "wan_edit_tier": p.get("wan_edit_tier"),
            "studio_wave_profile": p.get("studio_wave_profile"),
            "output_aspect": p.get("output_aspect"),
        },
        **state,
    }
