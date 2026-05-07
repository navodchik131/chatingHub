from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import piexif
from PIL import Image, ImageFilter

log = logging.getLogger(__name__)


def _b(s: str) -> bytes:
    return (s or "").strip().encode("utf-8")


def _dt_exif(dt: datetime) -> bytes:
    # EXIF: local time wall clock without TZ
    return dt.strftime("%Y:%m:%d %H:%M:%S").encode("utf-8")


def _dms_rationals(deg_abs: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    d = int(deg_abs)
    m_float = (deg_abs - d) * 60.0
    m = int(m_float)
    s = (m_float - m) * 60.0
    sec = round(s * 1_000_000)
    return (d, 1), (m, 1), (sec, 1_000_000)


def _build_gps_ifd(lat: float, lon: float) -> dict[int, Any]:
    lat_ref = b"N" if lat >= 0 else b"S"
    lon_ref = b"E" if lon >= 0 else b"W"
    la, lo = abs(lat), abs(lon)
    return {
        piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: _dms_rationals(la),
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: _dms_rationals(lo),
    }


def _add_grain_sharpen(rgb: Image.Image, sigma: float) -> Image.Image:
    import numpy as np

    arr = np.asarray(rgb, dtype=np.float32)
    noise = np.random.default_rng().standard_normal(arr.shape, dtype=np.float64) * float(sigma)
    arr = np.clip(arr + noise.astype(np.float32), 0.0, 255.0).astype(np.uint8)
    im = Image.fromarray(arr, "RGB")
    return im.filter(ImageFilter.UnsharpMask(radius=0.75, percent=108, threshold=2))


def apply_phone_export_to_jpeg(
    image_bytes: bytes,
    *,
    preset: dict[str, Any],
    selfie: bool,
    export_lat: float | None,
    export_lon: float | None,
    captured_at: datetime | None = None,
) -> bytes | None:
    """Перекодирует в JPEG с лёгким шумом/резкостью и EXIF «как у телефона». При ошибке — None."""
    try:
        src = Image.open(BytesIO(image_bytes))
        if getattr(src, "n_frames", 1) > 1:
            src.seek(0)
        im = src.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3] if im.mode == "RGBA" else None)
        rgb = bg
    except Exception as e:
        log.warning("phone export: decode failed: %s", e)
        return None

    sigma = float(preset.get("grain_sigma") or 3.6)
    try:
        processed = _add_grain_sharpen(rgb, sigma)
        out_io = BytesIO()
        processed.save(
            out_io,
            format="JPEG",
            quality=92,
            subsampling=2,
            optimize=True,
        )
        jpeg_bytes = out_io.getvalue()
    except Exception as e:
        log.warning("phone export: encode failed: %s", e)
        return None

    make = str(preset.get("make") or "Unknown").strip()
    model = str(preset.get("model") or "Phone").strip()
    if selfie:
        lens = str(preset.get("lens_selfie") or "")
        focal = int(preset.get("focal_35_selfie") or 23)
    else:
        lens = str(preset.get("lens_main") or "")
        focal = int(preset.get("focal_35_main") or 24)

    when = captured_at or datetime.now(timezone.utc)
    when = when.astimezone()  # локальное время сервера для «обычной» даты в EXIF

    zeroth: dict[int, Any] = {
        piexif.ImageIFD.Make: _b(make),
        piexif.ImageIFD.Model: _b(model),
    }
    exif_ifd: dict[int, Any] = {
        piexif.ExifIFD.DateTimeOriginal: _dt_exif(when),
        piexif.ExifIFD.DateTimeDigitized: _dt_exif(when),
        piexif.ExifIFD.LensModel: _b(lens),
        piexif.ExifIFD.FocalLengthIn35mmFilm: focal,
    }

    gps_ifd: dict[int, Any] = {}
    if export_lat is not None and export_lon is not None:
        if -90 <= export_lat <= 90 and -180 <= export_lon <= 180:
            gps_ifd = _build_gps_ifd(export_lat, export_lon)

    exif_dict: dict[str, Any] = {
        "0th": zeroth,
        "Exif": exif_ifd,
        "GPS": gps_ifd,
        "1st": {},
        "thumbnail": None,
    }

    try:
        exif_bytes = piexif.dump(exif_dict)
        merged = BytesIO()
        piexif.insert(exif_bytes, jpeg_bytes, merged)
        return merged.getvalue()
    except Exception as e:
        log.warning("phone export: exif failed: %s", e)
        return jpeg_bytes
