"""Скачивание Instagram видео/фото через yt-dlp и cookies администратора."""

from __future__ import annotations

import logging
import random
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yt_dlp

from app.config import settings
from app.services.ig_bot.urls import suggested_filename, validate_instagram_media_url

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parents[3]
WRITABLE_COOKIES = APP_DIR / "data" / "ig_bot_cookies.active.txt"

# Instagram часто отдаёт empty media на один запрос и нормальный ответ на следующий.
# Сериализуем скачивания: один cookie-файл + параллельные yt-dlp портят сессию.
_DOWNLOAD_LOCK = threading.Lock()
_MAX_ATTEMPTS = 3
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov"}
_RETRYABLE_MARKERS = (
    "empty media response",
    "login required",
    "rate-limit",
    "rate limit",
    "please wait",
    "challenge_required",
    "checkpoint_required",
    "http error 429",
    "http error 5",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "unable to extract",
    "no video formats found",
)


MediaKind = Literal["video", "image"]


@dataclass(frozen=True)
class IgMediaItem:
    path: Path
    kind: MediaKind
    filename: str


@dataclass(frozen=True)
class IgDownloadedMedia:
    items: list[IgMediaItem]
    temp_dir: Path

    @property
    def path(self) -> Path:
        return self.items[0].path

    @property
    def kind(self) -> MediaKind:
        return self.items[0].kind

    @property
    def filename(self) -> str:
        return self.items[0].filename


def resolve_cookies_path() -> Path | None:
    raw = (settings.ig_bot_cookies_path or "").strip()
    if not raw:
        return None
    src = Path(raw)
    if not src.is_absolute():
        src = APP_DIR / src
    if not src.is_file():
        log.warning("IG bot cookies file not found: %s", src)
        return None
    src_str = str(src).replace("\\", "/")
    if "/data/ig_bot/" in src_str or src_str.endswith("ig_bot_cookies.active.txt"):
        return src
    WRITABLE_COOKIES.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, WRITABLE_COOKIES)
    return WRITABLE_COOKIES


def _build_ydl_opts(cookies: Path | None, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    # Карусель = playlist. Для фото-слайдов yt-dlp часто пишет thumbnail
    # (ignore_no_formats_error), для видео — обычный download.
    opts: dict = {
        "outtmpl": str(output_dir / "%(autonumber)03d_%(id)s.%(ext)s"),
        "format": "bestvideo*+bestaudio/best",
        "noplaylist": False,
        "ignore_no_formats_error": True,
        "writethumbnail": True,
        "socket_timeout": 60,
        "retries": 5,
        "fragment_retries": 5,
        "quiet": True,
        "no_warnings": True,
    }
    if cookies:
        opts["cookiefile"] = str(cookies)
    return opts


def _extract_media_id(url: str) -> str:
    m = re.search(r"/(?:reel|reels|p)/([A-Za-z0-9_-]+)", url, re.I)
    return m.group(1) if m else ""


def _is_retryable_error(exc: BaseException | None) -> bool:
    if exc is None:
        return False
    text = str(exc).lower()
    return any(marker in text for marker in _RETRYABLE_MARKERS)


def _friendly_error(exc: BaseException | None) -> str:
    text = str(exc or "").strip()
    low = text.lower()
    if "empty media response" in low:
        return (
            "Instagram временно не отдал медиа (пустой ответ). "
            "Это бывает даже на рабочих cookies — попробуйте ещё раз через несколько секунд."
        )
    if "login required" in low or "cookies" in low:
        return (
            "Instagram требует авторизацию. Cookies на сервере, скорее всего, устарели — "
            "обратитесь к администратору."
        )
    if "rate-limit" in low or "rate limit" in low or "429" in low:
        return "Instagram ограничил частоту скачиваний. Подождите минуту и попробуйте снова."
    return text or "Не удалось скачать — проверьте ссылку и cookies"


def _candidate_urls(url: str) -> list[str]:
    """Небольшие варианты URL — IG иногда отвечает пусто на один формат и ок на другой."""
    base = url.strip().rstrip("/")
    out: list[str] = [base + "/"]
    alt = base
    if "/reels/" in alt:
        alt = alt.replace("/reels/", "/reel/", 1)
    elif "/reel/" in alt:
        alt = alt.replace("/reel/", "/reels/", 1)
    if alt != base:
        out.append(alt + "/")
    seen: set[str] = set()
    uniq: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def _media_kind(path: Path) -> MediaKind | None:
    ext = path.suffix.lower()
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _IMAGE_EXTS:
        return "image"
    return None


def _collect_downloaded_media(output_dir: Path) -> list[Path]:
    videos: list[Path] = []
    images: list[Path] = []
    for p in sorted(output_dir.iterdir(), key=lambda x: x.name):
        if not p.is_file() or p.name == "cookies.txt":
            continue
        kind = _media_kind(p)
        if kind == "video":
            videos.append(p)
        elif kind == "image":
            images.append(p)

    # Не тащим превью видео как отдельную «фотку карусели».
    video_stems = {v.stem for v in videos}
    kept_images: list[Path] = []
    for img in images:
        stem = img.stem
        if stem in video_stems:
            continue
        # yt-dlp иногда пишет thumb как id.webp рядом с id.mp4
        if any(stem == vs or stem.startswith(f"{vs}.") for vs in video_stems):
            continue
        kept_images.append(img)

    return sorted(videos + kept_images, key=lambda p: p.name)


def _download_once(url: str, cookies_src: Path, output_dir: Path) -> list[Path]:
    """
    Одна попытка yt-dlp. Cookies копируются во временный файл, чтобы параллельные
    (или повторные) запуски не дрались за один Netscape-файл.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cookie_copy = output_dir / "cookies.txt"
    shutil.copy2(cookies_src, cookie_copy)
    opts = _build_ydl_opts(cookie_copy, output_dir)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return _collect_downloaded_media(output_dir)


def download_instagram_media(url: str) -> IgDownloadedMedia:
    """
    Скачивает видео/фото/карусель во временную папку.
    temp_dir нужно удалить после отправки.
    """
    target = url.strip()
    validate_instagram_media_url(target)

    cookies = resolve_cookies_path()
    if cookies is None:
        raise RuntimeError(
            "Cookies Instagram не настроены на сервере — обратитесь к администратору."
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="ig-bot-"))
    last_error: Exception | None = None
    candidates = _candidate_urls(target)
    code = _extract_media_id(target) or "media"

    with _DOWNLOAD_LOCK:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            attempt_url = candidates[(attempt - 1) % len(candidates)]
            attempt_dir = tmp_dir / f"try_{attempt}"
            try:
                found = _download_once(attempt_url, cookies, attempt_dir)
                items: list[IgMediaItem] = []
                for idx, path in enumerate(found, start=1):
                    kind = _media_kind(path)
                    if kind is None:
                        continue
                    fname = suggested_filename(
                        target,
                        kind=kind,
                        ext=path.suffix,
                    )
                    if len(found) > 1:
                        stem = Path(fname).stem
                        fname = f"{stem}_{idx}{path.suffix.lower()}"
                    items.append(IgMediaItem(path=path, kind=kind, filename=fname))
                if items:
                    if attempt > 1:
                        log.info(
                            "ig bot download ok on retry attempt=%s count=%s url=%s",
                            attempt,
                            len(items),
                            attempt_url,
                        )
                    return IgDownloadedMedia(items=items, temp_dir=tmp_dir)
                last_error = RuntimeError("yt-dlp завершился без медиафайла")
            except Exception as exc:
                last_error = exc
                log.warning(
                    "ig bot download attempt=%s failed url=%s: %s",
                    attempt,
                    attempt_url,
                    exc,
                )
                if attempt < _MAX_ATTEMPTS and _is_retryable_error(exc):
                    time.sleep(0.8 + random.random() * 1.4)
                    continue
                if attempt < _MAX_ATTEMPTS and not _is_retryable_error(exc):
                    time.sleep(0.5)
                    continue
                break

    shutil.rmtree(tmp_dir, ignore_errors=True)
    _ = code
    raise RuntimeError(_friendly_error(last_error))


def download_instagram_video(url: str) -> tuple[Path, Path, str]:
    """Обратная совместимость: первое видео (или ошибка, если только фото)."""
    media = download_instagram_media(url)
    videos = [it for it in media.items if it.kind == "video"]
    if not videos:
        shutil.rmtree(media.temp_dir, ignore_errors=True)
        raise RuntimeError("По ссылке нет видео. Бот пришлёт фото, если отправить ссылку обычным сообщением.")
    first = videos[0]
    return first.path, media.temp_dir, first.filename
