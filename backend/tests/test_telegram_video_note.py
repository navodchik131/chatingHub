from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.services.telegram_video_note import (
    TELEGRAM_VIDEO_NOTE_SIZE,
    convert_video_bytes_to_telegram_note,
)


def _ffmpeg_available() -> bool:
    if not shutil.which("ffmpeg"):
        return False
    try:
        proc = subprocess.run(["ffmpeg", "-version"], capture_output=True, check=False)
        return proc.returncode == 0
    except OSError:
        return False


def _make_test_mp4(path: Path, *, size: int = 320, seconds: int = 1) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=red:s={size}x{size}:d={seconds}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        pytest.skip(f"ffmpeg test source failed: {(proc.stderr or b'').decode(errors='replace')[-200:]}")


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not available")
def test_convert_video_bytes_to_telegram_note_square_mp4():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src.mp4"
        _make_test_mp4(src, size=1280, seconds=2)
        raw = src.read_bytes()
        note = convert_video_bytes_to_telegram_note(raw, max_seconds=5)
        assert note
        assert note[:4] == b"\x00\x00\x00\x18" or note[4:8] == b"ftyp"
        out = Path(tmp) / "note.mp4"
        out.write_bytes(note)
        probe = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(out),
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            check=False,
        )
        stderr = (probe.stderr or b"").decode(errors="replace")
        assert f"{TELEGRAM_VIDEO_NOTE_SIZE}x{TELEGRAM_VIDEO_NOTE_SIZE}" in stderr


def test_convert_video_bytes_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        convert_video_bytes_to_telegram_note(b"")
