"""Извлечение и применение EXIF-профиля с эталонного снимка телефона."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import piexif

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


def extract_phone_exif_profile(image_bytes: bytes) -> dict[str, Any]:
    """
    Парсит EXIF из оригинала с телефона. Возвращает нормализованный профиль для подстановки при экспорте.
    """
    if not image_bytes:
        raise ValueError("Пустой файл.")
    try:
        exif_raw = piexif.load(image_bytes)
    except Exception as e:
        raise ValueError(
            "Не удалось прочитать EXIF. Загрузите оригинал JPEG с телефона (не скриншот и не пересланное из мессенджера)."
        ) from e

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

    if not make and not model and not lens:
        raise ValueError(
            "В файле почти нет данных камеры (Make/Model/Lens). "
            "Сохраните снимок из галереи телефона, не из чата."
        )

    profile: dict[str, Any] = {
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
