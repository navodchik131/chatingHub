import json
import sys
from pathlib import Path

from app.services.motion_video_outline import (
    choose_edge_params,
    motion_outline_video_prompt_block,
    output_size_for_source,
    probe_motion_video_stream,
)


def test_output_size_portrait_landscape_square():
    assert output_size_for_source(1080, 1920) == (540, 960)
    assert output_size_for_source(1920, 1080) == (960, 540)
    assert output_size_for_source(720, 720) == (720, 720)


def test_choose_edge_params_by_contrast():
    assert choose_edge_params(30) == (1.6, 0.04, 0.12)
    assert choose_edge_params(80) == (0.8, 0.10, 0.30)
    assert choose_edge_params(50) == (1.0, 0.06, 0.18)


def test_motion_outline_prompt_block():
    text = motion_outline_video_prompt_block(appearance_refs="@Image1, @Image2 and @Image3")
    assert "@Video1" in text
    assert "edge-outline" in text
    assert "@Image1" in text


def test_probe_motion_video_stream_parses_ffprobe_json(monkeypatch):
    sample = json.dumps(
        {
            "streams": [{"width": 1080, "height": 1920}],
            "format": {"duration": "14.52"},
        }
    )

    def fake_run(cmd, *, timeout):
        class R:
            returncode = 0
            stdout = sample
            stderr = ""

        return R()

    monkeypatch.setattr("app.services.motion_video_outline._run_cmd", fake_run)
    monkeypatch.setattr("app.services.motion_video_outline._ffprobe_bin", lambda: "ffprobe")
    w, h, dur = probe_motion_video_stream(Path("/tmp/fake.mp4"))
    assert (w, h) == (1080, 1920)
    assert abs(dur - 14.52) < 0.01


def test_resolve_motion_video_uploaded_finds_source(tmp_path, monkeypatch):
    from app.services import studio_motion_video as smv

    root = tmp_path / "motion_videos"
    owner_dir = root / "42"
    owner_dir.mkdir(parents=True)
    source = owner_dir / "abc123.source.mp4"
    source.write_bytes(b"fake")
    monkeypatch.setattr(smv, "MOTION_VIDEO_ROOT", root)

    assert smv.resolve_motion_video_file(42, "abc123") is None
    assert smv.resolve_motion_video_uploaded(42, "abc123") == source.resolve()

    outline = owner_dir / "abc123.mp4"
    outline.write_bytes(b"outline")
    assert smv.resolve_motion_video_uploaded(42, "abc123") == outline.resolve()


def test_measure_gray_stats_accepts_binary_stdout(monkeypatch):
    from app.services.motion_video_outline import measure_gray_stats

    payload = bytes([50] * 128)

    def fake_run(cmd, *, timeout, binary_stdout=False):
        class R:
            returncode = 0
            stdout = payload if binary_stdout else ""
            stderr = b"" if binary_stdout else ""

        return R()

    monkeypatch.setattr("app.services.motion_video_outline._run_cmd", fake_run)
    monkeypatch.setattr("app.services.motion_video_outline._ffmpeg_bin", lambda: "ffmpeg")
    mean, stddev = measure_gray_stats(Path("/tmp/fake.mp4"))
    assert mean == 50.0
    assert stddev == 0.0


def test_detect_face_in_jpeg_graceful_without_cascade(monkeypatch):
    from app.services.motion_video_outline import _detect_face_in_jpeg

    class FakeCv2:
        IMREAD_GRAYSCALE = 0

        @staticmethod
        def imdecode(arr, flag):
            return [[0]]

    monkeypatch.setitem(sys.modules, "cv2", FakeCv2())
    monkeypatch.setitem(sys.modules, "numpy", __import__("numpy"))
    assert _detect_face_in_jpeg(b"\xff\xd8\xff") is False
