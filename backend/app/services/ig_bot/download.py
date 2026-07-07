"""Скачивание Instagram-видео через yt-dlp и cookies администратора."""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path

import yt_dlp

from app.config import settings
from app.services.ig_bot.urls import suggested_filename, validate_instagram_media_url

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parents[3]
WRITABLE_COOKIES = APP_DIR / "data" / "ig_bot_cookies.active.txt"


def resolve_cookies_path() -> Path | None:
    raw = (settings.ig_bot_cookies_path or "").strip()
    if not raw:
        return None
    src = Path(raw)
    if not src.is_file():
        return None
    src_str = str(src).replace("\\", "/")
    if "/data/ig_bot/" in src_str or src_str.endswith("ig_bot_cookies.active.txt"):
        return src
    WRITABLE_COOKIES.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, WRITABLE_COOKIES)
    return WRITABLE_COOKIES


def _build_ydl_opts(cookies: Path | None, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    opts: dict = {
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
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


def download_instagram_video(url: str) -> tuple[Path, Path, str]:
    """
    Скачивает одно видеo во временную папку.
    Returns (mp4_path, temp_dir, filename) — temp_dir нужно удалить после отправки.
    """
    target = url.strip()
    validate_instagram_media_url(target)

    cookies = resolve_cookies_path()
    if cookies is None:
        raise RuntimeError(
            "Cookies Instagram не настроены на сервере — обратитесь к администратору."
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="ig-bot-"))
    opts = _build_ydl_opts(cookies, tmp_dir)
    error: Exception | None = None
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([target])
    except Exception as exc:
        error = exc

    media_id = _extract_media_id(target)
    expected = tmp_dir / f"{media_id}.mp4" if media_id else None
    if expected and expected.is_file() and expected.stat().st_size > 0:
        return expected, tmp_dir, suggested_filename(target)

    mp4_files = sorted(tmp_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if mp4_files and mp4_files[0].stat().st_size > 0:
        return mp4_files[0], tmp_dir, suggested_filename(target)

    shutil.rmtree(tmp_dir, ignore_errors=True)
    raise RuntimeError(str(error or "Не удалось скачать видео — проверьте ссылку и cookies"))
