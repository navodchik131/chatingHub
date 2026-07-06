"""Извлечение и применение EXIF-профиля с эталонного снимка телефона."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import piexif
from PIL import Image

from app.config import settings

log = logging.getLogger(__name__)

DEFAULT_GRAIN_SIGMA = 3.6


def _decode_exif_value(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        try:
            return raw.decode("utf-8", errors="ignore").strip().strip("\x00")
        except Exception:
            return ""
    return str(raw).strip()


def _rational_to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        if isinstance(val, tuple) and len(val) == 2:
            num, den = int(val[0]), int(val[1])
            if den == 0:
                return None
            return num / den
        return float(val)
    except (TypeError, ValueError):
        return None


def _suffix_from_filename(filename: str | None) -> str:
    if not filename:
        return ".jpg"
    lower = filename.lower()
    for ext in (".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
        if lower.endswith(ext):
            return ext
    return ".jpg"


def _exiftool_bin() -> str | None:
    raw = (settings.exiftool_binary or "").strip() or "exiftool"
    if Path(raw).is_file():
        return raw
    return shutil.which(raw)


def _build_profile(
    *,
    make: str,
    model: str,
    lens: str,
    software: str = "",
    focal_35_int: int | None = None,
    focal_len: float | None = None,
    f_number: float | None = None,
    iso_int: int | None = None,
) -> dict[str, Any] | None:
    if not make and not model and not lens:
        return None
    return {
        "make": make or "Unknown",
        "model": model or "Phone",
        "lens_model": lens,
        "focal_35mm": focal_35_int,
        "focal_length": focal_len,
        "f_number": f_number,
        "iso": iso_int,
        "software": software,
        "grain_sigma": DEFAULT_GRAIN_SIGMA,
    }


def _profile_from_piexif_dict(exif_raw: dict) -> dict[str, Any] | None:
    zeroth = exif_raw.get("0th") or {}
    exif_ifd = exif_raw.get("Exif") or {}

    make = _decode_exif_value(zeroth.get(piexif.ImageIFD.Make))
    model = _decode_exif_value(zeroth.get(piexif.ImageIFD.Model))
    lens = _decode_exif_value(exif_ifd.get(piexif.ExifIFD.LensModel))
    software = _decode_exif_value(zeroth.get(piexif.ImageIFD.Software))

    focal_35 = exif_ifd.get(piexif.ExifIFD.FocalLengthIn35mmFilm)
    focal_35_int: int | None = None
    if focal_35 is not None:
        try:
            focal_35_int = int(focal_35)
        except (TypeError, ValueError):
            focal_35_int = None

    focal_len = _rational_to_float(exif_ifd.get(piexif.ExifIFD.FocalLength))
    f_number = _rational_to_float(exif_ifd.get(piexif.ExifIFD.FNumber))
    iso = exif_ifd.get(piexif.ExifIFD.ISOSpeedRatings)
    iso_int: int | None = None
    if iso is not None:
        try:
            iso_int = int(iso)
        except (TypeError, ValueError):
            iso_int = None

    return _build_profile(
        make=make,
        model=model,
        lens=lens,
        software=software,
        focal_35_int=focal_35_int,
        focal_len=focal_len,
        f_number=f_number,
        iso_int=iso_int,
    )


def _extract_via_piexif(image_bytes: bytes) -> dict[str, Any] | None:
    try:
        exif_raw = piexif.load(image_bytes)
    except Exception:
        return None
    return _profile_from_piexif_dict(exif_raw)


def _register_heif_if_available() -> None:
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except ImportError:
        pass


def _extract_via_pillow(image_bytes: bytes) -> dict[str, Any] | None:
    try:
        _register_heif_if_available()
        im = Image.open(BytesIO(image_bytes))
        exif = im.getexif()
        if not exif:
            return None
        make = _decode_exif_value(exif.get(piexif.ImageIFD.Make))
        model = _decode_exif_value(exif.get(piexif.ImageIFD.Model))
        software = _decode_exif_value(exif.get(piexif.ImageIFD.Software))
        exif_ifd = exif.get_ifd(piexif.ImageIFD.ExifTag) if hasattr(exif, "get_ifd") else {}
        lens = _decode_exif_value(exif_ifd.get(piexif.ExifIFD.LensModel))
        focal_35 = exif_ifd.get(piexif.ExifIFD.FocalLengthIn35mmFilm)
        focal_35_int: int | None = None
        if focal_35 is not None:
            try:
                focal_35_int = int(focal_35)
            except (TypeError, ValueError):
                focal_35_int = None
        focal_len = _rational_to_float(exif_ifd.get(piexif.ExifIFD.FocalLength))
        f_number = _rational_to_float(exif_ifd.get(piexif.ExifIFD.FNumber))
        iso = exif_ifd.get(piexif.ExifIFD.ISOSpeedRatings)
        iso_int: int | None = None
        if iso is not None:
            try:
                iso_int = int(iso)
            except (TypeError, ValueError):
                iso_int = None
        return _build_profile(
            make=make,
            model=model,
            lens=lens,
            software=software,
            focal_35_int=focal_35_int,
            focal_len=focal_len,
            f_number=f_number,
            iso_int=iso_int,
        )
    except Exception:
        return None


def _profile_from_exiftool_tags(tags: dict[str, Any]) -> dict[str, Any] | None:
    make = str(tags.get("Make") or "").strip()
    model = str(tags.get("Model") or "").strip()
    lens = str(tags.get("LensModel") or "").strip()
    software = str(tags.get("Software") or "").strip()

    focal_35_int: int | None = None
    focal_raw = tags.get("FocalLengthIn35mmFormat")
    if focal_raw is not None:
        try:
            focal_35_int = int(float(focal_raw))
        except (TypeError, ValueError):
            focal_35_int = None

    focal_len = _rational_to_float(tags.get("FocalLength"))
    f_number = _rational_to_float(tags.get("FNumber"))
    iso_int: int | None = None
    iso_raw = tags.get("ISO")
    if iso_raw is not None:
        try:
            iso_int = int(float(iso_raw))
        except (TypeError, ValueError):
            iso_int = None

    return _build_profile(
        make=make,
        model=model,
        lens=lens,
        software=software,
        focal_35_int=focal_35_int,
        focal_len=focal_len,
        f_number=f_number,
        iso_int=iso_int,
    )


def _extract_via_exiftool(image_bytes: bytes, *, suffix: str) -> dict[str, Any] | None:
    bin_path = _exiftool_bin()
    if not bin_path:
        return None

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        proc = subprocess.run(
            [
                bin_path,
                "-j",
                "-n",
                "-Make",
                "-Model",
                "-LensModel",
                "-FocalLengthIn35mmFormat",
                "-FocalLength",
                "-FNumber",
                "-ISO",
                "-Software",
                tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            return None
        rows = json.loads(proc.stdout or "[]")
        if not rows or not isinstance(rows[0], dict):
            return None
        return _profile_from_exiftool_tags(rows[0])
    except Exception:
        log.debug("exiftool image exif read failed", exc_info=True)
        return None
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def _format_missing_camera_error(filename: str | None) -> str:
    lower = (filename or "").lower()
    if "instagram" in lower:
        return (
            "В файле почти нет данных камеры — похоже на сохранёнку из Instagram или другого мессенджера. "
            "Там EXIF уже удалён. Отправьте **оригинал из «Фото»** на телефоне (файлом 📎)."
        )
    if lower.endswith((".jpg", ".jpeg")):
        return (
            "В файле почти нет данных камеры (Make/Model/Lens). "
            "Скорее всего это не оригинал с камеры, а сохранённое/пересланное фото. "
            "Откройте снимок в галереи телефона и отправьте **файлом** (📎), не пересылкой из чата."
        )
    return (
        "В файле почти нет данных камеры (Make/Model/Lens). "
        "Сохраните снимок из галереи телефона, не из чата."
    )


def _format_extract_error(filename: str | None) -> str:
    lower = (filename or "").lower()
    if lower.endswith((".heic", ".heif")):
        return (
            "Не удалось прочитать EXIF из HEIC. "
            "Отправьте тот же снимок как JPEG: Настройки → Камера → Форматы → «Наиболее совместимые», "
            "или «Поделиться» → «Сохранить в Файлы» и отправьте .jpg файлом."
        )
    if "instagram" in lower:
        return (
            "Не удалось прочитать EXIF — файл похож на сохранёнку из Instagram (метаданные камеры уже сняты). "
            "Нужен оригинал из галереи телефона, файлом 📎."
        )
    if lower.endswith(".png"):
        return (
            "PNG не содержит EXIF камеры (часто это скриншот или экспорт). "
            "Сделайте снимок **камерой телефона** и отправьте JPEG/HEIC **файлом** из галереи."
        )
    return (
        "Не удалось прочитать EXIF. Загрузите оригинал JPEG или HEIC с телефона "
        "(не скриншот и не пересланное из мессенджера), **файлом** 📎."
    )


def extract_phone_exif_profile(image_bytes: bytes, *, filename: str | None = None) -> dict[str, Any]:
    """
    Парсит EXIF из оригинала с телефона. Возвращает нормализованный профиль для подстановки при экспорте.
    Поддерживает JPEG (piexif), HEIC/PNG/WebP (Pillow, exiftool).
    """
    if not image_bytes:
        raise ValueError("Пустой файл.")

    suffix = _suffix_from_filename(filename)
    profile = _extract_via_piexif(image_bytes)
    if profile is None:
        profile = _extract_via_pillow(image_bytes)
    if profile is None:
        profile = _extract_via_exiftool(image_bytes, suffix=suffix)

    if profile is None:
        raise ValueError(_format_extract_error(filename))

    make = str(profile.get("make") or "").strip()
    model = str(profile.get("model") or "").strip()
    lens = str(profile.get("lens_model") or "").strip()
    if (make in ("", "Unknown") and model in ("", "Phone") and not lens) or (
        not make and not model and not lens
    ):
        raise ValueError(_format_missing_camera_error(filename))

    return profile


def phone_exif_profile_to_json(profile: dict[str, Any]) -> str:
    return json.dumps(profile, ensure_ascii=False)


def phone_exif_profile_from_json(raw: str | None) -> dict[str, Any] | None:
    if not (raw or "").strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("phone exif profile: invalid json")
        return None
    return data if isinstance(data, dict) else None


def phone_exif_profile_summary(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None
    make = str(profile.get("make") or "").strip()
    model = str(profile.get("model") or "").strip()
    lens = str(profile.get("lens_model") or "").strip()
    parts = [p for p in (f"{make} {model}".strip(), lens) if p]
    if not parts:
        return None
    return " · ".join(parts)[:240]


def profile_for_phone_export(
    profile: dict[str, Any],
    *,
    selfie: bool,
) -> dict[str, Any]:
    """Приводит сохранённый профиль к полям, ожидаемым apply_phone_export_to_jpeg."""
    lens = str(profile.get("lens_model") or "").strip()
    focal = profile.get("focal_35mm")
    try:
        focal_i = int(focal) if focal is not None else (23 if selfie else 24)
    except (TypeError, ValueError):
        focal_i = 23 if selfie else 24
    return {
        "make": str(profile.get("make") or "Unknown").strip(),
        "model": str(profile.get("model") or "Phone").strip(),
        "lens_selfie": lens if selfie else "",
        "lens_main": lens if not selfie else "",
        "focal_35_selfie": focal_i if selfie else 23,
        "focal_35_main": focal_i if not selfie else 24,
        "grain_sigma": float(profile.get("grain_sigma") or DEFAULT_GRAIN_SIGMA),
        "iso": profile.get("iso"),
        "f_number": profile.get("f_number"),
        "software": str(profile.get("software") or "").strip(),
    }
