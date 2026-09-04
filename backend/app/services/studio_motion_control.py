"""Motion Control wizard: промпты, trim реф-видео, dress/turnaround helpers."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from app.services.studio_model_bootstrap import MODEL_SHEET_ASPECT_KEY

log = logging.getLogger(__name__)

# Video-edit: character-only swap (turnaround @Image1 + trimmed @Video1).
MOTION_CONTROL_VIDEO_EDIT_PROMPT = (
    "Character-only replacement. Use the reference image @image1 as the sole source of "
    "information: face identity from the left face close-up panel, plus hair, body, and clothing "
    "from the full turnaround sheet. Completely discard the original woman's "
    "appearance. Keep all movements, poses, camera trajectory, and timing from the video intact."
)

# На body-панелях развёртки лицо не показываем — identity только в левом close-up (как в workflow sheet).
_MOTION_CONTROL_BODY_NO_FACE_INSTRUCTION = (
    "Face visibility rule (critical): The left face close-up is the ONLY panel where eyes, nose, "
    "mouth, and facial identity must be clearly visible and must exactly match the attached face "
    "reference photo. "
    "In ALL four full-body panels on the right: do NOT show a readable face — no visible eyes, "
    "nose, or mouth. Hide the face using whichever fits each angle best: crop the frame at upper "
    "chest/shoulders so the head is outside the panel; turn the head away so only back of head, "
    "hair, or an featureless profile silhouette shows; or tilt the head so facial features are "
    "not visible. Full-body back view: back of head/hair only, no face. "
    "Keep body proportions, outfit, hairstyle silhouette, and skin tone consistent across panels."
)

def motion_control_turnaround_prompt() -> str:
    """Двухпанельный референс-лист: Image1=лицо, Image2=одежда."""
    from app.services.motion_control_grok import load_motion_control_turnaround_prompt

    return load_motion_control_turnaround_prompt()


# Legacy alias — используйте motion_control_turnaround_prompt().
MOTION_CONTROL_TURNAROUND_PROMPT = ""

# Развёртка Motion Control — горизонтальный лист 16:9.
MOTION_CONTROL_SHEET_ASPECT = "16:9"


def _ffmpeg_bin() -> str:
    from app.services.studio_motion_video import _ffmpeg_bin as motion_ffmpeg_bin

    return motion_ffmpeg_bin()


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
