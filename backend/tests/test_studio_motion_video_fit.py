from pathlib import Path
from unittest.mock import patch

from app.services.studio_motion_video import fit_motion_video_to_duration


def test_fit_skips_when_already_close(tmp_path: Path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"x")
    with patch(
        "app.services.studio_motion_video.probe_video_duration_seconds",
        return_value=8.1,
    ):
        out, is_temp = fit_motion_video_to_duration(src, 8)
    assert out == src
    assert is_temp is False
