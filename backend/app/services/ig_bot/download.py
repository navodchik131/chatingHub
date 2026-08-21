"""Скачивание Instagram видео/фото через API cookies + fallback yt-dlp."""

from __future__ import annotations

import logging
import random
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
import yt_dlp

from app.config import settings
from app.services.ig_bot.urls import suggested_filename, validate_instagram_media_url

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parents[3]
WRITABLE_COOKIES = APP_DIR / "data" / "ig_bot_cookies.active.txt"

_DOWNLOAD_LOCK = threading.Lock()
_MAX_ATTEMPTS = 3
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov"}
_IG_APP_ID = "936619743392459"
_IG_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
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
    "there is no video",
    "status_code=5",
    "connection reset",
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


@dataclass(frozen=True)
class _RemoteMedia:
    url: str
    kind: MediaKind
    ext: str


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


def _extract_media_id(url: str) -> str:
    m = re.search(
        r"/(?:reel|reels|p|tv|share/(?:reel|p|reels)?)/([A-Za-z0-9_-]+)",
        url,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r"/(?:reel|reels|p)/([A-Za-z0-9_-]+)", url, re.I)
    return m.group(1) if m else ""


def shortcode_to_pk(shortcode: str) -> int:
    code = (shortcode or "").strip()
    if len(code) > 28:
        code = code[:-28]
    n = 0
    for ch in code:
        n = n * 64 + _SHORTCODE_ALPHABET.index(ch)
    return n


def _is_retryable_error(exc: BaseException | None) -> bool:
    if exc is None:
        return False
    text = str(exc).lower()
    return any(marker in text for marker in _RETRYABLE_MARKERS)


def _friendly_error(exc: BaseException | None) -> str:
    text = str(exc or "").strip()
    low = text.lower()
    if "there is no video" in low or "no video formats" in low:
        return (
            "Не удалось получить медиа по ссылке. "
            "Если это фото/карусель — cookies могли устареть; "
            "если Reels — попробуйте ещё раз через несколько секунд."
        )
    if "empty media response" in low:
        return (
            "Instagram временно не отдал медиа (пустой ответ). "
            "Это бывает даже на рабочих cookies — попробуйте ещё раз через несколько секунд."
        )
    if "login required" in low or "cookies" in low or "unauthorized" in low:
        return (
            "Instagram требует авторизацию. Cookies на сервере, скорее всего, устарели — "
            "обратитесь к администратору."
        )
    if "rate-limit" in low or "rate limit" in low or "429" in low:
        return "Instagram ограничил частоту скачиваний. Подождите минуту и попробуйте снова."
    return text or "Не удалось скачать — проверьте ссылку и cookies"


def _candidate_urls(url: str) -> list[str]:
    base = url.strip().rstrip("/")
    out: list[str] = [base + "/"]
    alt = base
    if "/reels/" in alt:
        alt = alt.replace("/reels/", "/reel/", 1)
    elif "/reel/" in alt:
        alt = alt.replace("/reel/", "/reels/", 1)
    if alt != base:
        out.append(alt + "/")
    # share → классический /p/|/reel/
    m = re.search(r"/share/(?:reel|reels|p)?/([A-Za-z0-9_-]+)", base, re.I)
    if m:
        code = m.group(1)
        kind = "reel" if "/share/reel" in base.lower() else "p"
        out.append(f"https://www.instagram.com/{kind}/{code}/")
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


def _guess_ext_from_url(url: str, *, kind: MediaKind) -> str:
    path = urlparse(url).path.lower()
    for ext in (".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"):
        if ext in path:
            return ".jpg" if ext == ".jpeg" else ext
    return ".mp4" if kind == "video" else ".jpg"


def _best_candidate_url(candidates: list[dict[str, Any]] | None) -> str | None:
    if not candidates:
        return None
    ranked = sorted(
        (c for c in candidates if isinstance(c, dict) and c.get("url")),
        key=lambda c: int(c.get("width") or 0) * int(c.get("height") or 0),
        reverse=True,
    )
    if not ranked:
        return None
    return str(ranked[0]["url"]).strip() or None


def _remote_from_ig_item(item: dict[str, Any]) -> _RemoteMedia | None:
    video_versions = item.get("video_versions")
    if isinstance(video_versions, list) and video_versions:
        url = _best_candidate_url(video_versions)
        if url:
            return _RemoteMedia(url=url, kind="video", ext=_guess_ext_from_url(url, kind="video"))

    image_versions2 = item.get("image_versions2") or {}
    candidates = image_versions2.get("candidates") if isinstance(image_versions2, dict) else None
    url = _best_candidate_url(candidates if isinstance(candidates, list) else None)
    if not url:
        url = str(item.get("display_uri") or item.get("thumbnail_url") or "").strip() or None
    if url:
        return _RemoteMedia(url=url, kind="image", ext=_guess_ext_from_url(url, kind="image"))
    return None


def _remotes_from_media_payload(payload: dict[str, Any]) -> list[_RemoteMedia]:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise RuntimeError("Instagram API: пустой ответ items")

    root = items[0] if isinstance(items[0], dict) else None
    if root is None:
        raise RuntimeError("Instagram API: некорректный media item")

    carousel = root.get("carousel_media")
    nodes: list[dict[str, Any]]
    if isinstance(carousel, list) and carousel:
        nodes = [n for n in carousel if isinstance(n, dict)]
    else:
        nodes = [root]

    remotes: list[_RemoteMedia] = []
    for node in nodes:
        remote = _remote_from_ig_item(node)
        if remote:
            remotes.append(remote)
    if not remotes:
        raise RuntimeError("Instagram API: в посте нет скачиваемых фото/видео")
    return remotes


def _load_cookie_jar(cookies_src: Path) -> MozillaCookieJar:
    jar = MozillaCookieJar(str(cookies_src))
    jar.load(ignore_discard=True, ignore_expires=True)
    return jar


def _httpx_cookies_from_jar(jar: MozillaCookieJar) -> httpx.Cookies:
    cookies = httpx.Cookies()
    for c in jar:
        domain = (c.domain or "").lstrip(".")
        if "instagram" not in domain and "cdninstagram" not in domain:
            continue
        try:
            cookies.set(c.name, c.value, domain=domain or "instagram.com", path=c.path or "/")
        except Exception:
            continue
    return cookies


def _ig_api_headers(shortcode: str) -> dict[str, str]:
    return {
        "User-Agent": _IG_UA,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-IG-App-ID": _IG_APP_ID,
        "X-ASBD-ID": "129477",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.instagram.com/p/{shortcode}/",
        "Origin": "https://www.instagram.com",
    }


def _fetch_media_info_api(shortcode: str, cookies_src: Path) -> dict[str, Any]:
    pk = shortcode_to_pk(shortcode)
    jar = _load_cookie_jar(cookies_src)
    cookies = _httpx_cookies_from_jar(jar)
    headers = _ig_api_headers(shortcode)
    csrf = None
    for c in jar:
        if c.name == "csrftoken" and c.value:
            csrf = c.value
            break
    if csrf:
        headers["X-CSRFToken"] = csrf

    urls = [
        f"https://www.instagram.com/api/v1/media/{pk}/info/",
        f"https://i.instagram.com/api/v1/media/{pk}/info/",
    ]
    last_err: Exception | None = None
    with httpx.Client(
        cookies=cookies,
        headers=headers,
        follow_redirects=True,
        timeout=60.0,
    ) as client:
        for api_url in urls:
            try:
                resp = client.get(api_url)
                if resp.status_code in (401, 403):
                    raise RuntimeError("login required (Instagram API)")
                if resp.status_code == 429:
                    raise RuntimeError("rate-limit (Instagram API)")
                if resp.status_code >= 500:
                    raise RuntimeError(f"http error {resp.status_code}")
                if resp.status_code != 200:
                    last_err = RuntimeError(f"Instagram API status={resp.status_code}")
                    continue
                data = resp.json()
                if not isinstance(data, dict):
                    last_err = RuntimeError("Instagram API: не JSON")
                    continue
                if data.get("status") == "fail":
                    msg = str(data.get("message") or data.get("error_title") or "fail")
                    last_err = RuntimeError(f"Instagram API fail: {msg}")
                    continue
                return data
            except Exception as exc:
                last_err = exc
                log.warning("ig api media info failed shortcode=%s url=%s: %s", shortcode, api_url, exc)
    raise RuntimeError(_friendly_error(last_err) if last_err else "Instagram API недоступен")


def _download_remote_files(
    remotes: list[_RemoteMedia],
    *,
    cookies_src: Path,
    output_dir: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jar = _load_cookie_jar(cookies_src)
    cookies = _httpx_cookies_from_jar(jar)
    headers = {
        "User-Agent": _IG_UA,
        "Referer": "https://www.instagram.com/",
        "Accept": "*/*",
    }
    out: list[Path] = []
    with httpx.Client(
        cookies=cookies,
        headers=headers,
        follow_redirects=True,
        timeout=120.0,
    ) as client:
        for i, remote in enumerate(remotes, start=1):
            resp = client.get(remote.url)
            resp.raise_for_status()
            path = output_dir / f"{i:03d}_{remote.kind}{remote.ext}"
            path.write_bytes(resp.content)
            if path.stat().st_size < 64:
                raise RuntimeError(f"скачанный файл слишком маленький: {path.name}")
            out.append(path)
    return out


def _download_via_instagram_api(url: str, cookies_src: Path, output_dir: Path) -> list[Path]:
    shortcode = _extract_media_id(url)
    if not shortcode:
        raise RuntimeError("Не удалось извлечь shortcode из ссылки")
    payload = _fetch_media_info_api(shortcode, cookies_src)
    remotes = _remotes_from_media_payload(payload)
    return _download_remote_files(remotes, cookies_src=cookies_src, output_dir=output_dir)


def _build_ydl_opts(cookies: Path | None, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    opts: dict = {
        "outtmpl": str(output_dir / "%(autonumber)03d_%(id)s.%(ext)s"),
        "format": "bestvideo*+bestaudio/best",
        "noplaylist": False,
        "ignore_no_formats_error": True,
        "writethumbnail": True,
        "writeinfojson": False,
        "socket_timeout": 60,
        "retries": 5,
        "fragment_retries": 5,
        "quiet": True,
        "no_warnings": True,
    }
    if cookies:
        opts["cookiefile"] = str(cookies)
    return opts


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

    video_stems = {v.stem for v in videos}
    kept_images: list[Path] = []
    for img in images:
        stem = img.stem
        if stem in video_stems:
            continue
        if any(stem == vs or stem.startswith(f"{vs}.") for vs in video_stems):
            continue
        kept_images.append(img)

    return sorted(videos + kept_images, key=lambda p: p.name)


def _download_once_ytdlp(url: str, cookies_src: Path, output_dir: Path) -> list[Path]:
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
    Сначала Instagram API (фото+видео), затем fallback yt-dlp.
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

    with _DOWNLOAD_LOCK:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            attempt_url = candidates[(attempt - 1) % len(candidates)]
            attempt_dir = tmp_dir / f"try_{attempt}"
            found: list[Path] = []
            try:
                # 1) Нативный API — корректно тянет фото/карусели/видео.
                try:
                    found = _download_via_instagram_api(attempt_url, cookies, attempt_dir / "api")
                except Exception as api_exc:
                    log.warning(
                        "ig bot api attempt=%s failed url=%s: %s",
                        attempt,
                        attempt_url,
                        api_exc,
                    )
                    last_error = api_exc
                    found = []

                # 2) Fallback yt-dlp (в основном для Reels, если API пустой).
                if not found:
                    try:
                        found = _download_once_ytdlp(attempt_url, cookies, attempt_dir / "ytdlp")
                    except Exception as ydl_exc:
                        log.warning(
                            "ig bot ytdlp attempt=%s failed url=%s: %s",
                            attempt,
                            attempt_url,
                            ydl_exc,
                        )
                        last_error = ydl_exc
                        found = []

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

                if last_error is None:
                    last_error = RuntimeError("не удалось скачать медиафайл")
            except Exception as exc:
                last_error = exc
                log.warning(
                    "ig bot download attempt=%s failed url=%s: %s",
                    attempt,
                    attempt_url,
                    exc,
                )

            if attempt < _MAX_ATTEMPTS:
                time.sleep(0.8 + random.random() * 1.4)
                continue
            break

    shutil.rmtree(tmp_dir, ignore_errors=True)
    raise RuntimeError(_friendly_error(last_error))


def download_instagram_video(url: str) -> tuple[Path, Path, str]:
    """Обратная совместимость: первое видео (или ошибка, если только фото)."""
    media = download_instagram_media(url)
    videos = [it for it in media.items if it.kind == "video"]
    if not videos:
        shutil.rmtree(media.temp_dir, ignore_errors=True)
        raise RuntimeError(
            "По ссылке нет видео. Бот пришлёт фото, если отправить ссылку обычным сообщением."
        )
    first = videos[0]
    return first.path, media.temp_dir, first.filename
