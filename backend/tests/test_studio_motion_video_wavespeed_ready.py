from pathlib import Path
from unittest.mock import patch

from app.services.studio_motion_video import ensure_motion_video_wavespeed_ready


def test_wavespeed_ready_skips_valid_mp4(tmp_path: Path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"x" * 2048)
    with patch(
        "app.services.motion_video_outline._moov_valid",
        return_value=True,
    ), patch(
        "app.services.motion_video_outline.probe_motion_video_stream",
        return_value=(720, 1280, 7.9),
    ):
        out, is_temp, dur = ensure_motion_video_wavespeed_ready(src)
    assert out == src
    assert is_temp is False
    assert dur == 7.9


def test_wavespeed_ready_reencodes_non_mp4(tmp_path: Path):
    src = tmp_path / "clip.webm"
    src.write_bytes(b"x" * 2048)
    norm = tmp_path / "norm.mp4"
    norm.write_bytes(b"y" * 4096)
    with patch(
        "app.services.studio_motion_video._ffmpeg_bin",
        return_value="ffmpeg",
    ), patch(
        "app.services.studio_motion_video.probe_video_has_audio",
        return_value=False,
    ), patch(
        "app.services.studio_motion_video.subprocess.run",
        return_value=type("R", (), {"returncode": 0, "stderr": b""})(),
    ), patch(
        "app.services.studio_motion_video.tempfile.mkstemp",
        return_value=(0, str(norm)),
    ), patch(
        "app.services.motion_video_outline.probe_motion_video_stream",
        return_value=(720, 1280, 8.0),
    ):
        out, is_temp, dur = ensure_motion_video_wavespeed_ready(src)
    assert out == norm
    assert is_temp is True
    assert dur == 8.0
