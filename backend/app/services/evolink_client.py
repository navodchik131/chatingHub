"""EvoLink API — Seedance 2.0 / 2.5 video (async task + poll)."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Literal

import httpx

from app.config import settings

log = logging.getLogger(__name__)

EvolinkSeedanceVariant = Literal["standard", "mini", "seedance_25"]

_EVOLINK_ADAPTIVE_ASPECT_SUFFIXES = ("-image-to-video", "-video-edit")
_EVOLINK_VIDEO_EDIT_MODELS = frozenset({"seedance-2.5-video-edit"})


def evolink_base() -> str:
    return (settings.evolink_api_base or "https://api.evolink.ai").rstrip("/")


def evolink_platform_api_key() -> str:
    key = (settings.evolink_platform_api_key or "").strip()
    if not key:
        raise RuntimeError(
            "Seedance Sale временно недоступен. Обратитесь в поддержку."
        )
    return key


def wavespeed_tags_to_evolink(prompt: str) -> str:
    """@Image1 / @Video1 (WaveSpeed) → @image1 / @video1 (EvoLink)."""

    def _repl(m: re.Match[str]) -> str:
        return f"@{m.group(1).lower()}{m.group(2)}"

    return re.sub(r"@(Image|Video|Audio)(\d+)", _repl, prompt or "", flags=re.I)


def _normalize_evolink_quality(resolution: str | None, *, variant: str) -> str:
    r = (resolution or "720p").strip().lower()
    v = (variant or "standard").strip().lower()
    if v in ("seedance_25", "seedance25", "2_5", "25"):
        return "480p" if r == "480p" else "720p"
    if r in ("480p", "480"):
        return "480p"
    if r in ("1080p", "1080", "4k"):
        return "1080p"
    return "720p"


def evolink_model_requires_adaptive_aspect(model: str) -> bool:
    m = (model or "").strip().lower()
    if m in _EVOLINK_VIDEO_EDIT_MODELS:
        return True
    return any(m.endswith(sfx) for sfx in _EVOLINK_ADAPTIVE_ASPECT_SUFFIXES)


def normalize_evolink_aspect_ratio(model: str, aspect_ratio: str | None) -> str | None:
    """EvoLink i2v/video-edit принимают только adaptive; t2v/ref — фиксированные ratio."""
    if evolink_model_requires_adaptive_aspect(model):
        return "adaptive"
    ar = (aspect_ratio or "").strip()
    return ar or None


def normalize_evolink_duration(model: str, duration: int | None) -> int:
    """Video-edit: только -1 (длина = входное видео)."""
    m = (model or "").strip().lower()
    if m in _EVOLINK_VIDEO_EDIT_MODELS or m.endswith("-video-edit"):
        return -1
    return int(duration or settings.evolink_video_duration_default)


def format_evolink_video_edit_prompt(prompt: str) -> str:
    """EvoLink video-edit требует явного editing intent в промпте."""
    text = wavespeed_tags_to_evolink((prompt or "").strip())
    if not text:
        return "Edit the video."
    low = text.lower()
    if low.startswith("edit the video"):
        return text
    return f"Edit the video: {text}"


def resolve_evolink_model(
    *,
    variant: EvolinkSeedanceVariant | str,
    has_reference_video: bool,
    has_reference_images: bool,
    image_to_video: bool,
) -> str:
    v = (variant or "standard").strip().lower().replace("-", "_")
    if v in ("seedance_25", "seedance25", "v25", "2_5"):
        if has_reference_video:
            return "seedance-2.5-video-edit"
        if has_reference_images and not image_to_video:
            return "seedance-2.5-reference-to-video"
        if image_to_video:
            return "seedance-2.5-image-to-video"
        return "seedance-2.5-text-to-video"
    if v == "mini":
        if has_reference_video or (has_reference_images and not image_to_video):
            return "seedance-2.0-mini-reference-to-video"
        if image_to_video:
            return "seedance-2.0-mini-image-to-video"
        return "seedance-2.0-mini-text-to-video"
    if has_reference_video or (has_reference_images and not image_to_video):
        return "seedance-2.0-fast-reference-to-video"
    if image_to_video:
        return "seedance-2.0-image-to-video"
    return "seedance-2.0-text-to-video"


def format_evolink_user_error(message: str) -> str:
    raw = (message or "").strip()
    if not raw:
        return "Не удалось создать видео. Попробуйте позже."
    if raw.lower().startswith("evolink:"):
        raw = raw.split(":", 1)[1].strip()
    if not raw:
        return "Не удалось создать видео. Попробуйте позже."
    return raw


async def _poll_evolink_task(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    task_id: str,
    poll_interval: float,
    max_polls: int,
) -> str:
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    url = f"{evolink_base()}/v1/tasks/{task_id}"
    for _ in range(max_polls):
        await asyncio.sleep(poll_interval)
        pr = await client.get(url, headers=headers)
        if pr.status_code >= 400:
            log.warning("evolink poll %s: %s", pr.status_code, (pr.text or "")[:800])
            continue
        try:
            data = pr.json()
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        st = (data.get("status") or "").lower()
        if st == "failed":
            err = data.get("error")
            if isinstance(err, dict):
                msg = str(err.get("message") or err.get("code") or "task failed")
            else:
                msg = str(err or "task failed")
            raise RuntimeError(format_evolink_user_error(msg))
        if st == "completed":
            results = data.get("results")
            if isinstance(results, list) and results:
                u = str(results[0] or "").strip()
                if u.startswith("http"):
                    return u
            raise RuntimeError(format_evolink_user_error("задача completed, но URL видео пуст"))
    raise RuntimeError(format_evolink_user_error("timeout waiting for video"))


async def assert_evolink_media_urls_reachable(
    urls: list[str],
    *,
    label: str = "Reference",
) -> None:
    """Проверка, что ref URL отдаёт картинку/видео (как fetcher EvoLink, не браузер)."""
    cleaned = [u.strip() for u in urls if (u or "").strip()]
    if not cleaned:
        return
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        for i, url in enumerate(cleaned, start=1):
            try:
                r = await client.get(url)
            except httpx.HTTPError as e:
                raise RuntimeError(
                    format_evolink_user_error(
                        f"{label} {i}: URL could not be fetched ({e}). "
                        "Перегенерируйте кадр или выберите другой из архива."
                    )
                ) from e
            if r.status_code >= 400:
                raise RuntimeError(
                    format_evolink_user_error(
                        f"{label} {i}: HTTP {r.status_code}. "
                        "Файл мог протухнуть — выберите свежий кадр из архива."
                    )
                )
            if len(r.content or b"") < 64:
                raise RuntimeError(
                    format_evolink_user_error(
                        f"{label} {i}: пустой ответ. Перегенерируйте кадр и повторите."
                    )
                )


async def seedance_evolink_video_url(
    *,
    prompt: str,
    variant: EvolinkSeedanceVariant | str = "standard",
    image_urls: list[str] | None = None,
    video_urls: list[str] | None = None,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    duration: int | None = None,
    generate_audio: bool = True,
) -> str:
    """
    Создать задачу POST /v1/videos/generations и дождаться results[0].
    """
    api_key = evolink_platform_api_key()
    imgs = [u.strip() for u in (image_urls or []) if (u or "").strip()]
    vids = [u.strip() for u in (video_urls or []) if (u or "").strip()]
    has_vids = bool(vids)
    has_imgs = bool(imgs)
    image_to_video = has_imgs and not has_vids and len(imgs) == 1
    model = resolve_evolink_model(
        variant=variant,
        has_reference_video=has_vids,
        has_reference_images=has_imgs,
        image_to_video=image_to_video,
    )
    quality = _normalize_evolink_quality(resolution, variant=variant)
    prompt_text = wavespeed_tags_to_evolink(prompt)
    if has_vids and model.endswith("-video-edit"):
        prompt_text = format_evolink_video_edit_prompt(prompt_text)
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt_text,
        "duration": normalize_evolink_duration(model, duration),
        "quality": quality,
        "generate_audio": bool(generate_audio),
        "content_filter": True,
    }
    ar = normalize_evolink_aspect_ratio(model, aspect_ratio)
    if has_vids:
        body["aspect_ratio"] = "adaptive"
    elif ar:
        body["aspect_ratio"] = ar
    if has_imgs:
        body["image_urls"] = imgs[:30]
    if has_vids:
        body["video_urls"] = vids[:10]

    await assert_evolink_media_urls_reachable(imgs, label="Image")
    await assert_evolink_media_urls_reachable(vids, label="Video")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    post_url = f"{evolink_base()}/v1/videos/generations"
    poll_interval = float(settings.evolink_video_poll_interval_seconds)
    max_polls = int(settings.evolink_video_max_polls)

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(post_url, headers=headers, json=body)
        if r.status_code >= 400:
            detail = (r.text or "")[:2000]
            try:
                ej = r.json()
                if isinstance(ej, dict):
                    err = ej.get("error")
                    if isinstance(err, dict):
                        detail = str(err.get("message") or err.get("code") or detail)
            except Exception:
                pass
            log.warning("evolink submit %s: %s", r.status_code, detail[:500])
            raise RuntimeError(format_evolink_user_error(detail or f"HTTP {r.status_code}"))
        try:
            resp = r.json()
        except Exception as e:
            raise RuntimeError(format_evolink_user_error("невалидный JSON в ответе")) from e
        if not isinstance(resp, dict):
            raise RuntimeError(format_evolink_user_error("неожиданный формат ответа"))
        st = (resp.get("status") or "").lower()
        if st == "completed":
            results = resp.get("results")
            if isinstance(results, list) and results:
                u = str(results[0] or "").strip()
                if u.startswith("http"):
                    return u
        task_id = str(resp.get("id") or "").strip()
        if not task_id:
            raise RuntimeError(format_evolink_user_error("нет task id в ответе"))
        log.info(
            "evolink task created id=%s model=%s dur=%s quality=%s imgs=%s vids=%s",
            task_id,
            model,
            body.get("duration"),
            quality,
            len(imgs),
            len(vids),
        )
        return await _poll_evolink_task(
            client,
            api_key=api_key,
            task_id=task_id,
            poll_interval=poll_interval,
            max_polls=max_polls,
        )
