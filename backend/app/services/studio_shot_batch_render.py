from __future__ import annotations

import base64
import logging
import math
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import anyio
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import StudioJob, User, UserStudioModel
from app.services.evolink_client import evolink_upload_file_bytes, seedance_evolink_video_url
from app.services.evolink_client import evolink_platform_api_key
from app.services.motion_video_outline import append_motion_original_audio_prompt
from app.services.studio_evolink_motion_pricing import (
    evolink_video_duration_seconds,
    normalize_evolink_resolution,
    normalize_evolink_seedance_variant,
)
from app.services.studio_image_token import create_model_image_access_token
from app.services.studio_image_token import create_motion_video_access_token
from app.services.studio_jobs import job_params, studio_job_dir
from app.services.studio_motion_video import (
    MOTION_VIDEO_ROOT,
    _ffmpeg_bin,
    prepare_motion_video_file_for_duration,
    probe_video_has_audio,
    resolve_motion_audio_file,
)
from app.services.studio_seedance_t2v import (
    MAX_SEEDANCE_REFERENCE_IMAGES,
    build_seedance_t2v_prompt,
    filter_model_images_for_seedance_motion_swap,
    model_reference_public_urls,
)
from app.services.studio_aspect import aspect_ratio_for_seedance_i2v
from app.services.workspace import workspace_owner_id
from app.services.studio_shot_batch_plan import plan_shot_batches

log = logging.getLogger(__name__)


def _truthy(raw: Any) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


def _owner_motion_dir(owner_id: int) -> Path:
    owner_dir = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    root = MOTION_VIDEO_ROOT.resolve()
    if not str(owner_dir).startswith(str(root)):
        raise RuntimeError("invalid motion video dir")
    owner_dir.mkdir(parents=True, exist_ok=True)
    return owner_dir


def _run_ffmpeg(cmd: list[str], *, timeout: float) -> None:
    subprocess.run(
        cmd,
        check=True,
        timeout=timeout,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _jpeg_data_url(jpeg: bytes) -> str:
    enc = base64.b64encode(jpeg).decode("ascii")
    return f"data:image/jpeg;base64,{enc}"


def _extract_opening_frame_jpeg(video_path: Path, *, t: float, jpeg_quality: int = 5) -> bytes:
    t2 = max(0.0, float(t))
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "opening.jpg"
        cmd = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{t2:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            str(jpeg_quality),
            str(out),
        ]
        _run_ffmpeg(cmd, timeout=120)
        if not out.is_file() or out.stat().st_size < 64:
            raise RuntimeError("ffmpeg did not extract opening frame")
        return out.read_bytes()


def _trim_segment_to_motion_root(
    *,
    owner_id: int,
    src_video_path: Path,
    t_start: float,
    t_end: float,
) -> tuple[str, Path]:
    # Re-encode to keep concat stable.
    dur = float(t_end) - float(t_start)
    if dur <= 0.05:
        dur = 0.05
    has_audio = probe_video_has_audio(src_video_path)

    owner_dir = _owner_motion_dir(owner_id)
    fid = uuid.uuid4().hex
    out_path = owner_dir / f"{fid}.mp4"

    cmd: list[str] = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{max(0.0, float(t_start)):.3f}",
        "-i",
        str(src_video_path),
        "-t",
        f"{dur:.3f}",
        "-movflags",
        "+faststart",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
    ]
    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])
    else:
        cmd.append("-an")
    cmd.append(str(out_path))

    _run_ffmpeg(cmd, timeout=600)
    if not out_path.is_file() or out_path.stat().st_size < 1024:
        raise RuntimeError("trimmed segment video is empty")
    return fid, out_path


def _stitch_video_urls_to_mp4(*, video_urls: list[str], out_path: Path) -> None:
    if len(video_urls) == 1:
        # Still run ffmpeg to normalize container.
        cmd = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            video_urls[0],
            "-map",
            "0:v:0",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        _run_ffmpeg(cmd, timeout=600)
        return

    # Video-only concat (audio stream differences often break stream-copy).
    n = len(video_urls)
    inputs: list[str] = []
    for u in video_urls:
        inputs.extend(["-i", u])
    refs = "".join(f"[{i}:v:0]" for i in range(n))
    cmd = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        f"{refs}concat=n={n}:v=1:a=0[v]",
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out_path),
    ]
    _run_ffmpeg(cmd, timeout=1200)
    if not out_path.is_file() or out_path.stat().st_size < 1024:
        raise RuntimeError("stitched output is empty")


def _trim_rendered_video_to_duration(
    *,
    source_path: Path,
    out_path: Path,
    duration_sec: float,
) -> None:
    dur = max(0.2, float(duration_sec))
    cmd = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-t",
        f"{dur:.3f}",
        "-movflags",
        "+faststart",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(out_path),
    ]
    _run_ffmpeg(cmd, timeout=600)
    if not out_path.is_file() or out_path.stat().st_size < 1024:
        raise RuntimeError("trimmed rendered batch is empty")


async def _download_url_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.content or b""
        if len(data) < 64:
            raise RuntimeError("downloaded media is empty")
        return data


async def _generate_synthetic_opening_frame(
    *,
    session: AsyncSession,
    user: User,
    owner_id: int,
    model_id: int,
    scene_brief: str,
    output_aspect: str,
    segment_video_path: Path,
    opening_frame_jpeg: bytes,
) -> dict[str, Any] | None:
    # Reuse the existing motion_first_frame pipeline so the opening anchor is
    # actually synthesized from the target model + local segment context.
    from app.api import studio_routes as sr
    from app.services import studio_jobs

    params: dict[str, Any] = {
        "existing_generation_id": "",
        "model_id": str(model_id),
        "description": scene_brief,
        "output_aspect": output_aspect,
        "wan_edit_tier": "standard",
        "studio_wave_profile": "regular",
        "workflow_wave_model": None,
        "auto_motion_prompt": "1",
        "lock_model_hairstyle": "1",
        "use_still_as_final": "0",
        "exif_camera": "main",
    }
    job = await studio_jobs.create_studio_job(
        session,
        owner_id=owner_id,
        actor_user_id=user.id,
        job_type="motion_first_frame",
        params=params,
    )
    params["video_path"] = studio_jobs.save_studio_job_file(
        job.id,
        "video.bin",
        segment_video_path.read_bytes(),
    )
    params["video_filename"] = "shot_batch_segment.mp4"
    params["first_frame_path"] = studio_jobs.save_studio_job_file(
        job.id,
        "first_frame.bin",
        opening_frame_jpeg,
    )
    params["first_frame_mime"] = "image/jpeg"
    await studio_jobs.update_studio_job_params(session, job, params)
    result = await sr._studio_job_execute_motion_first_frame(session, job, user)
    return result if isinstance(result, dict) else None


async def execute_shot_batch_render(session: AsyncSession, job: StudioJob, user: User) -> dict[str, Any]:
    """
    Debug/Prototype shot-batch renderer:
    1) plan_shot_batches()
    2) render each resolved batch via EvoLink
    3) stitch resulting URLs into one mp4 via ffmpeg
    """

    p = job_params(job)
    if not (p.get("motion_video_path") or "").strip():
        raise RuntimeError("shot-batch-render: motion_video_path missing")

    oid = workspace_owner_id(user)
    mid = int(str(p.get("model_id") or "").strip())
    prompt = str(p.get("scene_brief") or p.get("prompt") or "").strip()
    negative_prompt = str(p.get("negative_prompt") or "").strip()
    motion_timeline = str(p.get("motion_timeline") or "").strip()
    output_aspect = str(p.get("output_aspect") or "9:16")
    generate_audio = _truthy(p.get("generate_audio") or "0")
    video_resolution = str(p.get("video_resolution") or settings.evolink_video_default_resolution)
    seedance_variant = normalize_evolink_seedance_variant(str(p.get("seedance_variant") or "standard"))

    scene_threshold = float(p.get("scene_threshold") or 0.35)
    max_shots_per_batch = int(p.get("max_shots_per_batch") or 4)
    max_batch_duration_sec = float(p.get("max_batch_duration_sec") or 12)
    min_shot_duration_sec = float(p.get("min_shot_duration_sec") or 0.4)
    face_samples = int(p.get("face_samples") or 6)

    # Load uploaded video bytes from job dir.
    from app.services.studio_jobs import load_studio_job_file

    raw = load_studio_job_file(str(p["motion_video_path"]))
    if len(raw) < 64:
        raise RuntimeError("shot-batch-render: empty motion video file")

    suffix = str(p.get("motion_video_suffix") or ".mp4").strip() or ".mp4"
    if not suffix.startswith("."):
        suffix = "." + suffix

    with tempfile.TemporaryDirectory() as td:
        src_path = Path(td) / f"shot_batch_src{suffix}"
        src_path.write_bytes(raw)

        # Plan (sync ffprobe/cv2/ffmpeg) in thread.
        plan: dict[str, Any] = await anyio.to_thread.run_sync(
            lambda: plan_shot_batches(
                src_path,
                scene_threshold=scene_threshold,
                max_shots_per_batch=max_shots_per_batch,
                max_batch_duration_sec=max_batch_duration_sec,
                min_shot_duration_sec=min_shot_duration_sec,
                face_samples=face_samples,
            )
        )

        resolved_batches = plan.get("resolved_batches") or []
        if not isinstance(resolved_batches, list) or not resolved_batches:
            raise RuntimeError("shot-batch-render: no resolved_batches")

        # Load studio model images.
        stmt = (
            select(UserStudioModel)
            .where(UserStudioModel.id == mid, UserStudioModel.user_id == oid)
            .options(selectinload(UserStudioModel.images))
        )
        sm = (await session.execute(stmt)).scalar_one_or_none()
        if not sm:
            raise RuntimeError("shot-batch-render: studio model not found")

        model_imgs = filter_model_images_for_seedance_motion_swap(list(sm.images))
        if not model_imgs:
            raise RuntimeError("shot-batch-render: model has no face refs for motion")

        pub = (settings.public_app_url or "").strip().rstrip("/")
        if not pub.lower().startswith("https://"):
            raise RuntimeError("shot-batch-render: PUBLIC_APP_URL must be https://")

        motion_summary = motion_timeline or None
        n_model = len(model_imgs)

        token_factory = create_model_image_access_token
        model_urls = model_reference_public_urls(
            owner_id=oid,
            images=model_imgs,
            public_app_base=pub,
            token_factory=token_factory,
        )
        if not model_urls:
            raise RuntimeError("shot-batch-render: no model reference urls")

        # Pre-check EvoLink key existence (fast fail).
        _ = evolink_platform_api_key()

        output_aspect_key = output_aspect
        ar_t2v = aspect_ratio_for_seedance_i2v(output_aspect_key)

        out_dir = studio_job_dir(int(job.id))
        out_dir.mkdir(parents=True, exist_ok=True)

        batch_outputs: list[dict[str, Any]] = []
        video_urls: list[str] = []

        for rb in resolved_batches:
            rb_id = rb.get("id")
            eff_start = float(rb.get("effective_t_start") or 0.0)
            eff_end = float(rb.get("effective_t_end") or 0.0)
            eff_dur = float(rb.get("effective_duration") or (eff_end - eff_start))

            # EvoLink duration normalization uses int seconds.
            requested_dur = max(1, int(math.ceil(eff_dur)))
            ds_effective = evolink_video_duration_seconds(
                requested_dur,
                variant=seedance_variant,
            )
            video_res = normalize_evolink_resolution(video_resolution, variant=seedance_variant)

            # Trim segment for motion reference (so each batch starts at its own t=0).
            seg_file_id, seg_path = await anyio.to_thread.run_sync(
                lambda: _trim_segment_to_motion_root(
                    owner_id=oid,
                    src_video_path=src_path,
                    t_start=eff_start,
                    t_end=eff_end,
                )
            )

            # Fit reference to exact provider duration.
            mv_id_eff, vpath_eff, _ref_video_duration = await anyio.to_thread.run_sync(
                lambda: prepare_motion_video_file_for_duration(
                    owner_id=oid,
                    file_id=seg_file_id,
                    source_path=seg_path,
                    target_sec=ds_effective,
                )
            )

            vid_tok = create_motion_video_access_token(user_id=oid, file_id=mv_id_eff)
            motion_vid_url = f"{pub}/api/studio/public-motion-video?t={quote(vid_tok, safe='')}"

            motion_aud_url: str | None = None
            if generate_audio and resolve_motion_audio_file(oid, mv_id_eff) is not None:
                motion_aud_url = f"{pub}/api/studio/public-motion-audio?t={quote(vid_tok, safe='')}"

            # Opening frame at batch start.
            opening_jpeg = await anyio.to_thread.run_sync(
                lambda vp=vpath_eff: _extract_opening_frame_jpeg(vp, t=0.0)
            )
            opening_mode = "extracted"
            opening_url: str | None = None
            if rb.get("requires_synthetic_opening_frame"):
                try:
                    synth = await _generate_synthetic_opening_frame(
                        session=session,
                        user=user,
                        owner_id=oid,
                        model_id=mid,
                        scene_brief=prompt,
                        output_aspect=output_aspect_key,
                        segment_video_path=vpath_eff,
                        opening_frame_jpeg=opening_jpeg,
                    )
                except Exception as e:
                    log.warning(
                        "shot-batch synthetic opening failed job=%s batch=%s: %s",
                        job.id,
                        rb_id,
                        e,
                    )
                    synth = None
                synth_url = str((synth or {}).get("generated_image_url") or "").strip()
                if synth_url:
                    opening_url = synth_url
                    opening_mode = "synthetic_generated"
            if not opening_url:
                opening_url = await evolink_upload_file_bytes(
                    data=opening_jpeg,
                    filename=f"opening_batch_{rb_id or len(batch_outputs) + 1}.jpg",
                    content_type="image/jpeg",
                )
            opening_local_name = f"opening_batch_{int(rb_id or len(batch_outputs) + 1)}.jpg"
            (out_dir / opening_local_name).write_bytes(opening_jpeg)

            # Seedance prompt.
            seed_prompt, prompt_source = await build_seedance_t2v_prompt(
                user_brief=prompt,
                n_start_frame=1,
                n_model_images=n_model,
                n_outfit_images=0,
                n_motion_videos=1,
                motion_summary=motion_summary,
                model_profile_text=None,
                negative=negative_prompt,
                output_aspect=ar_t2v or output_aspect_key,
                duration_seconds=ds_effective,
                force_template=False,
                reference_only=False,
                remove_face_grid=False,
                soft_identity=False,
            )
            if motion_aud_url:
                seed_prompt = append_motion_original_audio_prompt(seed_prompt)

            evolink_images = [opening_url] + (model_urls or [])
            evolink_images = evolink_images[:MAX_SEEDANCE_REFERENCE_IMAGES]

            # Render batch.
            video_url = await seedance_evolink_video_url(
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
            rendered_raw = await _download_url_bytes(video_url)
            raw_path = out_dir / f"batch_{int(rb_id or len(batch_outputs) + 1)}_provider.mp4"
            raw_path.write_bytes(rendered_raw)
            trimmed_path = out_dir / f"batch_{int(rb_id or len(batch_outputs) + 1)}.mp4"
            await anyio.to_thread.run_sync(
                lambda sp=raw_path, op=trimmed_path, dur=eff_dur: _trim_rendered_video_to_duration(
                    source_path=sp,
                    out_path=op,
                    duration_sec=dur,
                )
            )

            batch_outputs.append(
                {
                    "batch_id": rb_id,
                    "effective_t_start": eff_start,
                    "effective_t_end": eff_end,
                    "effective_duration": eff_dur,
                    "object_risk_level": rb.get("object_risk_level"),
                    "resolution_action": rb.get("resolution_action"),
                    "video_url": video_url,
                    "rendered_batch_endpoint": f"/api/studio/debug/shot-batch-output/{job.id}/batches/{int(rb_id or len(batch_outputs) + 1)}",
                    "opening_frame_url": opening_url,
                    "opening_frame_endpoint": f"/api/studio/debug/shot-batch-output/{job.id}/frames/{opening_local_name}",
                    "opening_frame_preview_url": _jpeg_data_url(opening_jpeg),
                    "opening_frame_mode": opening_mode,
                    "prompt_source": prompt_source,
                }
            )
            video_urls.append(trimmed_path.as_posix())

        # Stitch into local mp4 in job dir (debug endpoint serves it).
        out_path = out_dir / "shot_batch_output.mp4"

        await anyio.to_thread.run_sync(
            lambda: _stitch_video_urls_to_mp4(video_urls=video_urls, out_path=out_path),
        )

        return {
            "ok": True,
            "plan": plan,
            "batch_outputs": batch_outputs,
            "stitched_job_output_path": out_path.as_posix(),
            "stitched_output_endpoint": f"/api/studio/debug/shot-batch-output/{job.id}",
        }

