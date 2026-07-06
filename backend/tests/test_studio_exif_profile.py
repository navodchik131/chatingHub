import piexif
from PIL import Image
from io import BytesIO

from app.services.studio_model_images import exif_camera_is_selfie, normalize_exif_camera
from app.services.studio_exif_profile import (
    _extract_via_exiftool,
    extract_phone_exif_profile,
    phone_exif_profile_from_json,
    phone_exif_profile_summary,
    phone_exif_profile_to_json,
    profile_for_phone_export,
)


def _jpeg_with_exif(*, make: str, model: str, lens: str) -> bytes:
    im = Image.new("RGB", (64, 64), color=(120, 80, 90))
    buf = BytesIO()
    zeroth = {
        piexif.ImageIFD.Make: make.encode("utf-8"),
        piexif.ImageIFD.Model: model.encode("utf-8"),
    }
    exif_ifd = {
        piexif.ExifIFD.LensModel: lens.encode("utf-8"),
        piexif.ExifIFD.FocalLengthIn35mmFilm: 24,
        piexif.ExifIFD.ISOSpeedRatings: 100,
    }
    exif_bytes = piexif.dump({"0th": zeroth, "Exif": exif_ifd, "GPS": {}, "1st": {}, "thumbnail": None})
    im.save(buf, format="JPEG", exif=exif_bytes, quality=90)
    return buf.getvalue()


def test_extract_phone_exif_profile():
    raw = _jpeg_with_exif(
        make="Apple",
        model="iPhone 15 Pro",
        lens="iPhone 15 Pro back triple camera 6.765mm f/1.78",
    )
    profile = extract_phone_exif_profile(raw)
    assert profile["make"] == "Apple"
    assert profile["model"] == "iPhone 15 Pro"
    assert "back triple" in profile["lens_model"]
    assert profile["focal_35mm"] == 24
    assert profile["iso"] == 100


def test_profile_roundtrip_and_export_preset():
    profile = {"make": "samsung", "model": "SM-S928B", "lens_model": "Main Rear", "focal_35mm": 26}
    blob = phone_exif_profile_to_json(profile)
    loaded = phone_exif_profile_from_json(blob)
    assert loaded is not None
    assert phone_exif_profile_summary(loaded) is not None
    preset = profile_for_phone_export(loaded, selfie=False)
    assert preset["lens_main"] == "Main Rear"
    assert preset["focal_35_main"] == 26


def test_normalize_exif_camera():
    assert normalize_exif_camera("main") == "main"
    assert normalize_exif_camera("selfie") == "selfie"
    assert normalize_exif_camera("front") == "selfie"
    assert normalize_exif_camera(None) == "main"
    assert exif_camera_is_selfie("selfie") is True
    assert exif_camera_is_selfie("main") is False


def test_extract_rejects_empty_exif():
    im = Image.new("RGB", (8, 8), color=(0, 0, 0))
    buf = BytesIO()
    im.save(buf, format="PNG")
    try:
        extract_phone_exif_profile(buf.getvalue(), filename="screenshot.png")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "PNG" in str(e) or "EXIF" in str(e)


def test_extract_rejects_instagram_filename():
    im = Image.new("RGB", (8, 8), color=(0, 0, 0))
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=90)
    try:
        extract_phone_exif_profile(buf.getvalue(), filename="instagram_1783070233663.jpg")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "Instagram" in str(e) or "камер" in str(e).lower()


def test_extract_via_exiftool_same_as_piexif():
    import shutil

    if shutil.which("exiftool") is None:
        return
    raw = _jpeg_with_exif(
        make="Apple",
        model="iPhone 15 Pro",
        lens="iPhone 15 Pro back triple camera 6.765mm f/1.78",
    )
    profile = _extract_via_exiftool(raw, suffix=".jpg")
    assert profile is not None
    assert profile["make"] == "Apple"
    assert profile["model"] == "iPhone 15 Pro"
