"""Convert arbitrary video bytes to Telegram video note (square MP4)."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

import anyio

from app.services.studio_motion_video import _ffmpeg_bin

log = logging.getLogger(__name__)

TELEGRAM_VIDEO_NOTE_MAX_SECONDS = 60
TELEGRAM_VIDEO_NOTE_SIZE = 640


def _run_ffmpeg(input_path: Path, output_path: Path, *, max_seconds: int) -> None:
    vf = (
        f"scale={TELEGRAM_VIDEO_NOTE_SIZE}:{TELEGRAM_VIDEO_NOTE_SIZE}:"
        "force_original_aspect_ratio=increase,"
        f"crop={TELEGRAM_VIDEO_NOTE_SIZE}:{TELEGRAM_VIDEO_NOTE_SIZE}"
    )
    cmd = [
        _ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-t",
        str(max(1, int(max_seconds))),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode(errors="replace")[-900:]
        raise RuntimeError(f"ffmpeg video note failed: {err or proc.returncode}")


def convert_video_bytes_to_telegram_note(raw: bytes, *, max_seconds: int = TELEGRAM_VIDEO_NOTE_MAX_SECONDS) -> bytes:
    if not raw:
        raise ValueError("empty video")
    with tempfile.TemporaryDirectory(prefix="mm-vnote-") as tmp:
        tmp_dir = Path(tmp)
        src = tmp_dir / "in.bin"
        dst = tmp_dir / "note.mp4"
        src.write_bytes(raw)
        _run_ffmpeg(src, dst, max_seconds=max_seconds)
        if not dst.is_file() or dst.stat().st_size <= 0:
            raise RuntimeError("ffmpeg produced empty video note")
        return dst.read_bytes()


async def convert_video_bytes_to_telegram_note_async(
    raw: bytes,
    *,
    max_seconds: int = TELEGRAM_VIDEO_NOTE_MAX_SECONDS,
) -> bytes:
    return await anyio.to_thread.run_sync(
        convert_video_bytes_to_telegram_note,
        raw,
        max_seconds=max_seconds,
    )
