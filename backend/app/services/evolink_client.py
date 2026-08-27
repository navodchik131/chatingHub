"""EvoLink API — Seedance 2.0 / 2.5 video (async task + poll)."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import re
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlparse

import httpx

from app.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
        # EvoLink API: точка в версии (2.0), не дефис (2-0).
        return "seedance-2.0-fast-image-to-video"
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


_EVOLINK_DIRECT_MEDIA_SUFFIXES = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".mp4",
    ".webm",
    ".mov",
)


def evolink_files_api_base() -> str:
    return (getattr(settings, "evolink_files_api_base", None) or "https://files-api.evolink.ai").rstrip(
        "/"
    )


def _url_has_direct_media_suffix(url: str) -> bool:
    path = urlparse((url or "").strip()).path.lower()
    return any(path.endswith(ext) for ext in _EVOLINK_DIRECT_MEDIA_SUFFIXES)


def _url_is_evolink_hosted(url: str) -> bool:
    host = urlparse((url or "").strip()).netloc.lower()
    return host.endswith("evolink.ai") or host.endswith("files.evolink.ai")


def _url_is_studio_public_media(url: str) -> bool:
    from app.services.studio_public_media import _studio_public_url_paths

    return _studio_public_url_paths(url) is not None


def _needs_evolink_file_mirror(url: str) -> bool:
    u = (url or "").strip()
    if not u:
        return False
    if _url_is_studio_public_media(u):
        return True
    if _url_is_evolink_hosted(u) and _url_has_direct_media_suffix(u):
        return False
    if _url_has_direct_media_suffix(u):
        return False
    return True


def _sniff_media_ext(data: bytes) -> str | None:
    """Определяет расширение по magic bytes (важно для JWT URL без .mp4 в path)."""
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return ".mp4"
    if len(data) >= 4 and data[:4] == b"\x1aE\xdf\xa3":
        return ".webm"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return ".wav"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if len(data) >= 3 and data[:3] == b"ID3":
        return ".mp3"
    if len(data) >= 2 and data[0] == 0xFF and data[1] in (0xFB, 0xF3, 0xF2):
        return ".mp3"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return None


def _upload_filename_for_bytes(
    url: str,
    data: bytes,
    *,
    default_stem: str,
    media_kind: str | None = None,
) -> tuple[str, str]:
    parsed = urlparse((url or "").strip())
    path = (parsed.path or "").lower()
    name = parsed.path.rsplit("/", 1)[-1] if parsed.path else ""
    sniffed = _sniff_media_ext(data)
    kind = (media_kind or "").strip().lower()

    if name and "." in name:
        ext = "." + name.rsplit(".", 1)[-1].lower()
        stem = name.rsplit(".", 1)[0][:48] or default_stem
    elif path.endswith("/studio/public-motion-video") or kind == "video":
        ext = sniffed or ".mp4"
        stem = default_stem
    elif path.endswith("/studio/public-motion-audio") or kind == "audio":
        ext = sniffed or ".mp3"
        stem = default_stem
    elif sniffed:
        ext = sniffed
        stem = default_stem
    else:
        ext = ".jpg"
        stem = default_stem

    if ext.lower() in (".bin", ".dat", ""):
        ext = sniffed or (".mp4" if kind == "video" else ".jpg")
    if kind == "video" and ext in (".jpg", ".jpeg", ".png", ".webp") and sniffed in (
        ".mp4",
        ".webm",
        ".mov",
    ):
        ext = sniffed

    mime = mimetypes.guess_type(f"{stem}{ext}")[0] or "application/octet-stream"
    if ext in (".mp4", ".webm", ".mov") and not mime.startswith("video/"):
        mime = "video/mp4" if ext == ".mp4" else mime
    if ext in (".mp3", ".wav", ".m4a") and not mime.startswith("audio/"):
        mime = "audio/mpeg" if ext == ".mp3" else ("audio/wav" if ext == ".wav" else "audio/mp4")
    if ext in (".jpg", ".jpeg", ".png", ".webp") and not mime.startswith("image/"):
        mime = "image/jpeg"
    return f"{stem}{ext}", mime


def _parse_evolink_file_upload_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError(format_evolink_user_error("неожиданный ответ загрузки файла"))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        raise RuntimeError(format_evolink_user_error("неожиданный ответ загрузки файла"))
    for key in ("file_url", "download_url", "url"):
        u = str(data.get(key) or "").strip()
        if u.startswith("http"):
            return u
    raise RuntimeError(format_evolink_user_error("EvoLink не вернул URL загруженного файла"))


async def evolink_upload_file_bytes(
    *,
    data: bytes,
    filename: str,
    content_type: str,
) -> str:
    if len(data) < 64:
        raise RuntimeError(format_evolink_user_error("файл для EvoLink пустой"))
    api_key = evolink_platform_api_key()
    upload_url = f"{evolink_files_api_base()}/api/v1/files/upload/stream"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            upload_url,
            headers=headers,
            files={"file": (filename, data, content_type or "application/octet-stream")},
        )
    if r.status_code >= 400:
        detail = (r.text or "")[:1000]
        log.warning("evolink file upload %s: %s", r.status_code, detail[:300])
        raise RuntimeError(
            format_evolink_user_error(detail or f"HTTP {r.status_code} при загрузке файла")
        )
    try:
        payload = r.json()
    except Exception as e:
        raise RuntimeError(format_evolink_user_error("невалидный JSON при загрузке файла")) from e
    file_url = _parse_evolink_file_upload_payload(payload)
    log.info("evolink file upload ok name=%s bytes=%s url=%s", filename, len(data), file_url[:120])
    return file_url


async def _load_media_bytes_for_evolink_mirror(
    url: str,
    *,
    session: "AsyncSession | None",
    label: str = "медиа",
) -> bytes:
    if session is not None:
        from app.services.studio_public_media import read_studio_public_media_bytes

        local = await read_studio_public_media_bytes(session, url)
        if local is not None:
            return local
    if "/studio/public-motion-video" in url:
        raise RuntimeError(
            format_evolink_user_error(
                f"Референс-видео не найдено на сервере при чтении {label} для EvoLink. "
                "Загрузите видео заново на шаге 1 wizard."
            )
        )
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(url)
        if r.status_code >= 400:
            raise RuntimeError(
                format_evolink_user_error(
                    f"HTTP {r.status_code} при чтении {label} для EvoLink. "
                    "Перезагрузите файл или сгенерируйте кадр заново."
                )
            )
        data = r.content or b""
        if len(data) < 64:
            raise RuntimeError(format_evolink_user_error("пустой файл медиа для EvoLink"))
        return data


async def evolink_mirror_media_urls(
    urls: list[str],
    *,
    session: "AsyncSession | None" = None,
    label: str = "Reference",
) -> list[str]:
    """EvoLink fetcher принимает прямые .jpg/.png URL — studio JWT URL зеркалим в files-api."""
    out: list[str] = []
    for i, raw in enumerate(urls, start=1):
        url = (raw or "").strip()
        if not url:
            continue
        if not _needs_evolink_file_mirror(url):
            out.append(url)
            continue
        data = await _load_media_bytes_for_evolink_mirror(url, session=session, label=label)
        default_stem = f"{label.lower()}_{i}"
        if label.lower().startswith("video"):
            media_kind = "video"
        elif label.lower().startswith("audio"):
            media_kind = "audio"
        else:
            media_kind = "image"
        filename, mime = _upload_filename_for_bytes(
            url,
            data,
            default_stem=default_stem,
            media_kind=media_kind,
        )
        mirrored = await evolink_upload_file_bytes(
            data=data,
            filename=filename,
            content_type=mime,
        )
        out.append(mirrored)
    return out


async def assert_evolink_media_urls_reachable(
    urls: list[str],
    *,
    label: str = "Reference",
    session: "AsyncSession | None" = None,
) -> None:
    """Проверка, что ref URL отдаёт картинку/видео (как fetcher EvoLink, не браузер)."""
    cleaned = [u.strip() for u in urls if (u or "").strip()]
    if not cleaned:
        return
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        for i, url in enumerate(cleaned, start=1):
            payload: bytes | None = None
            if session is not None:
                from app.services.studio_public_media import read_studio_public_media_bytes

                payload = await read_studio_public_media_bytes(session, url)
            if payload is not None:
                if len(payload) < 64:
                    raise RuntimeError(
                        format_evolink_user_error(
                            f"{label} {i}: файл на сервере пустой. Загрузите кадр заново."
                        )
                    )
                continue
            try:
                r = await client.get(url)
            except httpx.HTTPError as e:
                raise RuntimeError(
                    format_evolink_user_error(
                        f"{label} {i}: URL could not be fetched ({e}). "
                        "Загрузите кадр заново или проверьте PUBLIC_APP_URL."
                    )
                ) from e
            if r.status_code >= 400:
                hint = (
                    "Файл не найден на сервере — загрузите кадр заново."
                    if "/studio/public-" in url
                    else "Ссылка провайдера недоступна — перегенерируйте кадр или загрузите новый файл."
                )
                raise RuntimeError(
                    format_evolink_user_error(
                        f"{label} {i}: HTTP {r.status_code}. {hint}"
                    )
                )
            if len(r.content or b"") < 64:
                raise RuntimeError(
                    format_evolink_user_error(
                        f"{label} {i}: пустой ответ. Загрузите кадр заново и повторите."
                    )
                )


async def seedance_evolink_video_url(
    *,
    prompt: str,
    variant: EvolinkSeedanceVariant | str = "standard",
    image_urls: list[str] | None = None,
    video_urls: list[str] | None = None,
    audio_urls: list[str] | None = None,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    duration: int | None = None,
    generate_audio: bool = True,
    session: "AsyncSession | None" = None,
) -> str:
    """
    Создать задачу POST /v1/videos/generations и дождаться results[0].
    """
    api_key = evolink_platform_api_key()
    imgs = [u.strip() for u in (image_urls or []) if (u or "").strip()]
    vids = [u.strip() for u in (video_urls or []) if (u or "").strip()]
    auds = [u.strip() for u in (audio_urls or []) if (u or "").strip()]
    imgs = await evolink_mirror_media_urls(imgs, session=session, label="Image")
    vids = await evolink_mirror_media_urls(vids, session=session, label="Video")
    auds = await evolink_mirror_media_urls(auds, session=session, label="Audio")
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
    if auds:
        body["audio_urls"] = auds[:3]

    await assert_evolink_media_urls_reachable(imgs, label="Image", session=session)
    await assert_evolink_media_urls_reachable(vids, label="Video", session=session)
    await assert_evolink_media_urls_reachable(auds, label="Audio", session=session)

    log.info(
        "evolink submit prepare model=%s dur=%s quality=%s imgs=%s vids=%s auds=%s i2v=%s",
        model,
        body.get("duration"),
        quality,
        len(imgs),
        len(vids),
        len(auds),
        image_to_video,
    )

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
            raise RuntimeError(
                format_evolink_user_error(
                    detail or f"HTTP {r.status_code} (задача в EvoLink не создана)"
                )
            )
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
