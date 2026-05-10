"""Временные driving-video для Kling Motion Control (файл на диске + публичный JWT URL)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from app.config import BACKEND_DIR

MOTION_VIDEO_ROOT = (BACKEND_DIR / "data" / "studio_motion_videos").resolve()

_VIDEO_SUFFIX = {".mp4", ".webm", ".mov", ".m4v"}


def _ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError(
            "На сервере не найден ffmpeg (PATH). Установите ffmpeg для извлечения кадров из видео."
        )
    return exe


def _ext_for_filename(name: str | None) -> str:
    if not name:
        return ".mp4"
    suf = Path(name).suffix.lower()
    return suf if suf in _VIDEO_SUFFIX else ".mp4"


def save_motion_video_bytes(*, owner_id: int, raw: bytes, filename: str | None) -> str:
    """Сохраняет видео, возвращает file_id (stem) для JWT."""
    file_id = uuid.uuid4().hex
    ext = _ext_for_filename(filename)
    owner_dir = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    if not str(owner_dir).startswith(str(MOTION_VIDEO_ROOT)):
        raise RuntimeError("invalid motion video path")
    owner_dir.mkdir(parents=True, exist_ok=True)
    path = owner_dir / f"{file_id}{ext}"
    path.write_bytes(raw)
    return file_id


def resolve_motion_video_file(owner_id: int, file_id: str) -> Path | None:
    root = MOTION_VIDEO_ROOT.resolve()
    base = (MOTION_VIDEO_ROOT / str(int(owner_id))).resolve()
    if not str(base).startswith(str(root)) or not base.is_dir():
        return None
    fid = str(file_id).strip()[:128]
    if not fid:
        return None
    for p in base.glob(f"{fid}.*"):
        if not p.is_file():
            continue
        rp = p.resolve()
        if not str(rp).startswith(str(base)):
            continue
        if p.suffix.lower() in _VIDEO_SUFFIX:
            return rp
    return None


def extract_first_frame_jpeg(video_path: Path) -> bytes:
    """Первый кадр ролика — для референса позы (Nano Banana) и опционально vision."""
    out: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            out = Path(tmp.name)
        subprocess.run(
            [
                _ffmpeg_bin(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video_path),
                "-vf",
                "select=eq(n\\,0)",
                "-vframes",
                "1",
                "-q:v",
                "3",
                str(out),
            ],
            check=True,
            timeout=120,
            capture_output=True,
        )
        return out.read_bytes()
    finally:
        if out is not None:
            out.unlink(missing_ok=True)


def extract_video_sample_frames_jpeg(video_path: Path, *, max_frames: int = 4) -> list[bytes]:
    """Несколько кадров (равномерно по времени) — для LLM-описания движения."""
    capped = max(1, min(8, max_frames))
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        pattern = str(tdir / "f%03d.jpg")
        subprocess.run(
            [
                _ffmpeg_bin(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(video_path),
                "-vf",
                "fps=1/2",
                "-frames:v",
                str(capped),
                pattern,
            ],
            check=True,
            timeout=180,
            capture_output=True,
        )
        paths = sorted(tdir.glob("f*.jpg"))
        return [p.read_bytes() for p in paths if p.is_file()]
