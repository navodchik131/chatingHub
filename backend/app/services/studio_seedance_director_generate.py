"""Фоновая генерация видео Seedance Director (WaveSpeed / EvoLink)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import StudioGeneration, StudioJob, User
from app.services.credits import ensure_can_consume_credits, record_usage
from app.services.studio_image_token import create_pose_reference_access_token
from app.services.studio_keys import (
    load_owner_studio_billing,
    studio_wavespeed_api_key,
)
from app.services.studio_jobs import job_params, studio_job_dir
from app.services.studio_pose_reference import save_pose_reference_bytes
from app.services.studio_seedance_director import duration_from_span, variant_for_piece_version
from app.services.studio_seedance_director_pricing import seedance_director_piece_credit_cost
from app.services.studio_evolink_motion_pricing import normalize_evolink_resolution
from app.services.studio_generation_placeholders import find_studio_generation_by_job_id
from app.services.studio_generation_storage import (
    mark_studio_generation_failed,
    studio_finish_video_generation,
)
from app.services.workspace import workspace_owner_id

log = logging.getLogger(__name__)


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _image_paths_from_params(params: dict[str, Any]) -> list[str]:
    out: list[str] = []
    n = int(params.get("image_count") or 0)
    for i in range(n):
        rel = str(params.get(f"image_{i}_path") or "").strip()
        if rel:
            out.append(rel)
    return out


def _build_reference_urls(*, owner_id: int, image_paths: list[str], public_base: str) -> list[str]:
    urls: list[str] = []
    for rel in image_paths:
        path = Path(rel)
        if not path.is_file():
            full = settings.BACKEND_DIR / rel if not path.is_absolute() else path
            if not full.is_file():
                continue
            path = full
        raw = path.read_bytes()
        if len(raw) < 64:
            continue
        mime = "image/jpeg"
        if path.suffix.lower() == ".png":
            mime = "image/png"
        fid = save_pose_reference_bytes(owner_id=owner_id, raw=raw, content_type=mime)
        tok = create_pose_reference_access_token(user_id=owner_id, file_id=fid)
        urls.append(f"{public_base}/api/studio/public-pose-reference?t={quote(tok, safe='')}")
    return urls


async def execute_seedance_director_generate_job(
    session: AsyncSession,
    job: StudioJob,
    user: User,
) -> dict[str, Any]:
    """Долгая генерация — в фоне, без 504 на nginx."""
    params = job_params(job)
    oid = workspace_owner_id(user)
    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise RuntimeError("Нужен публичный HTTPS (PUBLIC_APP_URL).")

    prompt_text = str(params.get("prompt") or "").strip()
    if not prompt_text:
        raise RuntimeError("Пустой промпт")

    vb = str(params.get("video_backend") or "wavespeed").strip().lower()
    is_evolink = vb == "evolink"
    ver = str(params.get("version") or "2.0").strip()
    if ver not in ("2.0", "2.5"):
        ver = "2.0"
    variant = variant_for_piece_version(ver)
    dur = duration_from_span(
        "",
        fallback=int(params.get("duration_seconds") or 10),
        version=ver,
    )
    dur = duration_from_span(f"0-{dur}s", fallback=dur, version=ver)
    res_norm = str(params.get("resolution") or "720p").strip() or "720p"
    aspect = str(params.get("aspect_ratio") or "9:16").strip() or "9:16"
    generate_audio = _truthy(str(params.get("generate_audio") or "1"))

    roles: list[str] = []
    try:
        parsed = json.loads(str(params.get("image_roles") or "[]"))
        if isinstance(parsed, list):
            roles = [str(x) for x in parsed]
    except json.JSONDecodeError:
        roles = []

    image_paths = _image_paths_from_params(params)
    if not image_paths:
        # fallback: все image_*.bin в папке задачи
        jd = studio_job_dir(job.id)
        image_paths = sorted(str(p.relative_to(settings.BACKEND_DIR)).replace("\\", "/") for p in jd.glob("image_*.bin"))

    image_urls = _build_reference_urls(owner_id=oid, image_paths=image_paths, public_base=pub)
    if not image_urls:
        raise RuntimeError("Не удалось подготовить reference_images")

    sub_b, _llm, ws_row, plan, _credits, demo = await load_owner_studio_billing(session, oid)
    gen_cost_raw = int(params.get("gen_cost_raw") or seedance_director_piece_credit_cost(
        version=ver,
        duration_seconds=dur,
        resolution=res_norm,
        video_backend=vb,
    ))
    gen_cost = int(params.get("gen_cost") or gen_cost_raw)
    billing = await ensure_can_consume_credits(session, user, gen_cost)

    video_url: str | None = None
    provider = "seedance_t2v"
    try:
        if is_evolink:
            from app.services.evolink_client import seedance_evolink_video_url

            i2v_idx = 0
            for i, role in enumerate(roles):
                rl = role.strip().lower()
                if rl in ("first frame", "first_frame", "first") or "first frame" in rl:
                    i2v_idx = min(i, len(image_urls) - 1)
                    break
            video_url = await seedance_evolink_video_url(
                prompt=prompt_text,
                variant=variant,
                image_urls=[image_urls[i2v_idx]],
                aspect_ratio=aspect,
                resolution=normalize_evolink_resolution(res_norm, variant=variant),
                duration=dur,
                generate_audio=generate_audio,
                session=session,
            )
            provider = "evolink_i2v"
        else:
            from app.services.wavespeed_client import seedance_20_text_to_video_url

            ws_key = studio_wavespeed_api_key(
                plan=plan,
                ws_row=ws_row,
                owner_subscription=sub_b,
                demo_generations_remaining=demo,
            )
            video_url = await seedance_20_text_to_video_url(
                api_key=ws_key,
                prompt=prompt_text,
                reference_images=image_urls,
                aspect_ratio=aspect,
                resolution=res_norm,
                duration=dur,
                generate_audio=generate_audio,
                variant=variant,
            )
            provider = "seedance_t2v"
    except RuntimeError:
        raise
    except Exception as e:
        log.exception("seedance director generate job=%s failed", job.id)
        raise RuntimeError(str(e) or "generate failed") from e

    gen_placeholder = await find_studio_generation_by_job_id(session, job.id)
    ph_id = params.get("placeholder_generation_id")
    if gen_placeholder is None and ph_id is not None:
        try:
            gen_placeholder = await session.get(StudioGeneration, int(ph_id))
        except (TypeError, ValueError):
            gen_placeholder = None

    if gen_placeholder is not None and is_evolink:
        gen_placeholder.video_backend = "evolink"

    if video_url:
        vu = video_url.strip()
        if gen_placeholder is not None:
            await studio_finish_video_generation(
                session,
                gen_placeholder,
                video_url=vu,
                prompt_excerpt=prompt_text[:2000] or None,
            )
    elif gen_placeholder is not None:
        await mark_studio_generation_failed(
            session,
            gen_placeholder,
            message="Провайдер не вернул видео",
            step=provider,
        )
        raise RuntimeError("Провайдер не вернул видео")

    if video_url and gen_cost > 0:
        await record_usage(
            session,
            user,
            billing,
            "studio_seedance_director_generate",
            gen_cost,
            {
                "version": ver,
                "duration_seconds": dur,
                "resolution": res_norm,
                "video_backend": vb,
                "provider": provider,
                "image_count": len(image_urls),
                "job_id": job.id,
                "piece_id": params.get("piece_id"),
            },
        )
    await session.commit()

    out: dict[str, Any] = {
        "video_url": video_url,
        "variant": variant,
        "version": ver,
        "duration_seconds": dur,
        "aspect_ratio": aspect,
        "resolution": res_norm,
        "video_backend": vb,
        "provider": provider,
        "generate_credit_cost": gen_cost,
    }
    if gen_placeholder is not None:
        out["generation_id"] = gen_placeholder.id
    return out
