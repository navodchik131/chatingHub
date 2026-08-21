"""Разбор и нормализация ссылок Instagram (одиночное видеo/reel)."""

from __future__ import annotations

import re

INSTAGRAM_HOST = re.compile(r"^https?://(www\.)?instagram\.com/", re.I)
_URL_IN_TEXT = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels)/[A-Za-z0-9_-]+/?",
    re.I,
)
_SINGLE_MEDIA = re.compile(r"/(p|reel|reels)/[A-Za-z0-9_-]+", re.I)


def extract_instagram_url(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("http") and INSTAGRAM_HOST.match(raw.split()[0]):
        candidate = normalize_single_url(raw.split()[0])
        return candidate if is_single_media_url(candidate) else None
    m = _URL_IN_TEXT.search(raw)
    if m:
        return normalize_single_url(m.group(0))
    return None


def normalize_single_url(raw: str) -> str:
    url = raw.strip()
    if not url.startswith("http"):
        url = f"https://{url.lstrip('/')}"
    url = url.split("?")[0].rstrip("/") + "/"
    return url


def is_single_media_url(url: str) -> bool:
    return bool(_SINGLE_MEDIA.search(url or ""))


def validate_instagram_media_url(url: str) -> None:
    if not INSTAGRAM_HOST.match(url):
        raise ValueError("Нужна ссылка на instagram.com")
    if not is_single_media_url(url):
        raise ValueError(
            "Поддерживаются только ссылки на пост, фото или Reels: "
            "/p/…, /reel/… или /reels/…"
        )


def suggested_filename(
    url: str,
    *,
    kind: str = "video",
    ext: str | None = None,
) -> str:
    m = re.search(r"/(?:reel|reels|p)/([A-Za-z0-9_-]+)", url, re.I)
    code = m.group(1) if m else ("photo" if kind == "image" else "video")
    if ext:
        suffix = ext if ext.startswith(".") else f".{ext}"
    else:
        suffix = ".jpg" if kind == "image" else ".mp4"
    return f"instagram_{code}{suffix}"
