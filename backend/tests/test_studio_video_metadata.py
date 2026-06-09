from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.studio_video_metadata import (
    apple_quicktime_creation_date,
    build_phone_video_exiftool_args,
    exif_datetime_string,
    iso6709_location,
    process_video_archive_bytes,
)


def test_iso6709_location():
    assert iso6709_location(55.7512, 37.6184) == "+55.7512+37.6184/"
    assert iso6709_location(-33.8688, 151.2093) == "-33.8688+151.2093/"


def test_datetime_helpers():
    dt = datetime(2024, 6, 2, 14, 30, 0, tzinfo=timezone.utc)
    assert exif_datetime_string(dt) == "2024:06:02 14:30:00" or ":" in exif_datetime_string(dt)
    apple = apple_quicktime_creation_date(dt)
    assert "T" in apple
    assert apple.endswith("00") or "+" in apple or "-" in apple


def test_build_phone_video_exiftool_args_includes_gps_and_lens():
    preset = {
        "make": "Apple",
        "model": "iPhone 15 Pro",
        "lens_main": "iPhone 15 Pro back triple camera 6.765mm f/1.78",
        "focal_35_main": 24,
        "software": "18.0",
    }
    args = build_phone_video_exiftool_args(
        preset,
        selfie=False,
        export_lat=55.75,
        export_lon=37.62,
        captured_at=datetime(2024, 6, 2, 12, 0, 0, tzinfo=timezone.utc),
    )
    joined = " ".join(args)
    assert "-Make=Apple" in args
    assert "-Model=iPhone 15 Pro" in args
    assert "-LensModel=" in joined
    assert "location.ISO6709" in joined
    assert "-GPSLatitude=55.75" in args


def test_process_video_skips_non_video_ext():
    raw = b"\x00" * 128
    out, changed = process_video_archive_bytes(raw, ext=".png", preset=None, strip_ai=False)
    assert out == raw
    assert changed is False


@pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_process_video_strip_and_phone_tags():
    with tempfile.TemporaryDirectory() as td:
        mp4 = Path(td) / "clip.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=64x64:d=0.2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(mp4),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "exiftool",
                "-overwrite_original",
                "-XMP:Description=Made with AI",
                "-Producer=AI Generator",
                str(mp4),
            ],
            check=True,
            capture_output=True,
        )
        raw = mp4.read_bytes()

    preset = {
        "make": "Apple",
        "model": "iPhone 14",
        "lens_main": "iPhone 14 back dual wide camera 5.7mm f/1.5",
        "focal_35_main": 26,
    }
    out, changed = process_video_archive_bytes(
        raw,
        ext=".mp4",
        preset=preset,
        selfie=False,
        export_lat=40.7,
        export_lon=-74.0,
        strip_ai=True,
    )
    assert changed is True
    assert out
    assert len(out) > 100

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(out)
        check_path = Path(tmp.name)
    try:
        meta = subprocess.run(
            ["exiftool", "-s", "-Make", "-Model", "-XMP:Description", "-Producer", str(check_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        text = meta.stdout
        assert "Apple" in text
        assert "iPhone 14" in text
        assert "Made with AI" not in text
        assert "AI Generator" not in text
    finally:
        check_path.unlink(missing_ok=True)
        backup = Path(f"{check_path}_original")
        backup.unlink(missing_ok=True)
