"""Motion Control wizard: промпты, trim реф-видео, dress/turnaround helpers."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from app.config import settings
from app.services.studio_model_bootstrap import MODEL_SHEET_ASPECT_KEY

log = logging.getLogger(__name__)

# Video-edit: character-only swap (turnaround @Image1 + trimmed @Video1).
MOTION_CONTROL_VIDEO_EDIT_PROMPT = (
    "Character-only replacement. Use the reference image @image1 as the sole source of "
    "information: face, hair, body, and clothing. Completely discard the original woman's "
    "appearance. Keep all movements, poses, camera trajectory, and timing from the video intact."
)

# Turnaround sheet для Motion Control (16:9, face + outfit из шага «Образ»).
MOTION_CONTROL_TURNAROUND_PROMPT = (
    "Create a character turnaround reference sheet based on the attached face photo, "
    "in a 16:9 horizontal layout with the following arrangement:\n\n"
    "Left third:\n"
    "One large close-up of the face, front view only (facing camera)\n"
    "Tight crop on head/face, same lighting and skin tone as the reference photo\n\n"
    "Right two-thirds:\n"
    "Full body, front view (facing camera)\n"
    "Full body, 3/4 view (turned ~45°)\n"
    "Full body, side/profile view (90°)\n"
    "Full body, back view (180°)\n"
    "All four body views shown at the same scale/zoom, standing neutrally "
    "(relaxed A-pose, arms slightly away from body)\n"
    "Identical clothing, hairstyle and body proportions across all four body views\n\n"
    "General requirements:\n"
    "Flat, even studio lighting — no dramatic shadows — consistent across the whole sheet\n"
    "Plain neutral background (light grey or white)\n"
    "Photorealistic style, consistent skin tone and texture throughout\n"
    "Face identity, hairstyle and features must exactly match the attached reference photo\n"
    "No text, no watermarks, no borders/dividers between sections\n"
    "Layout should fit naturally into a 16:9 canvas: face close-up occupies the left third, "
    "the four full-body views share the right two-thirds evenly, arranged so each view is "
    "clearly separated and fully visible"
)

# Развёртка Motion Control — горизонтальный лист 16:9.
MOTION_CONTROL_SHEET_ASPECT = "16:9"


def _ffmpeg_bin() -> str:
    return (settings.ffmpeg_path or "ffmpeg").strip() or "ffmpeg"


def trim_motion_video_segment(
    source: Path,
    *,
    start_sec: float,
    end_sec: float,
) -> tuple[Path, bool]:
    """
    Вырезает [start_sec, end_sec] из исходника. Возвращает (path, is_temp).
    """
    start = max(0.0, float(start_sec))
    end = max(start + 0.25, float(end_sec))
    duration = end - start
    fd, tmp_path_str = tempfile.mkstemp(prefix="motion_trim_", suffix=".mp4")
    os.close(fd)
    out_path = Path(tmp_path_str)
    try:
        cmd = [
            _ffmpeg_bin(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-movflags",
            "+faststart",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
        ]
        from app.services.studio_motion_video import probe_video_has_audio

        if probe_video_has_audio(source):
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.append("-an")
        cmd.append(str(out_path))
        subprocess.run(cmd, check=True, timeout=600, capture_output=True)
        return out_path, True
    except Exception:
        out_path.unlink(missing_ok=True)
        log.warning("motion trim failed start=%s end=%s", start, end, exc_info=True)
        raise


def motion_control_trim_duration_seconds(
    *,
    full_duration: float | None,
    trim_start: float | None,
    trim_end: float | None,
    use_full: bool,
) -> float:
    """Длина клипа для биллинга и Seedance duration."""
    if full_duration is None or full_duration <= 0:
        full_duration = 5.0
    if use_full or trim_start is None or trim_end is None:
        return min(30.0, max(1.0, float(full_duration)))
    start = max(0.0, float(trim_start))
    end = min(float(full_duration), max(start + 0.25, float(trim_end)))
    return min(30.0, max(0.5, end - start))
