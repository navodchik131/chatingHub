"""Подстановка phone-метаданных и снятие C2PA/XMP с видео без перекодирования (exiftool)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

_VIDEO_EXTS = frozenset({".mp4", ".mov", ".m4v", ".qt"})

# Теги провайдеров / C2PA — удаляем без трогания видеопотока.
_AI_METADATA_CLEAR_ARGS: tuple[str, ...] = (
    "-JUMBF:All=",
    "-C2PA:All=",
    "-Item:All=",
    "-XMP:All=",
    "-ICC_Profile:All=",
    "-Producer=",
    "-Encoder=",
    "-Keys:Author=",
    "-Keys:Creator=",
    "-Keys:Artwork=",
    "-QuickTime:Encoder=",
    "-QuickTime:Producer=",
    "-XMPToolkit=",
)


def _normalize_video_ext(ext: str) -> str:
    e = (ext or "").strip().lower()
    if not e.startswith("."):
        e = f".{e}" if e else ".mp4"
    return e


def _exiftool_bin() -> str:
    raw = (settings.exiftool_binary or "").strip() or "exiftool"
    if Path(raw).is_file():
        return raw
    found = shutil.which(raw)
    if found:
        return found
    raise FileNotFoundError(
        f"Не найден exiftool («{raw}»). Установите libimage-exiftool-perl в Docker "
        "или задайте EXIFTOOL_BINARY в backend/.env."
    )


def iso6709_location(lat: float, lon: float) -> str:
    """Apple QuickTime location.ISO6709: +DD.DDDD+DDD.DDDD/"""
    la = max(-90.0, min(90.0, float(lat)))
    lo = max(-180.0, min(180.0, float(lon)))
    lat_s = f"{la:+.4f}"
    lon_s = f"{lo:+.4f}"
    return f"{lat_s}{lon_s}/"


def exif_datetime_string(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y:%m:%d %H:%M:%S")


def apple_quicktime_creation_date(dt: datetime) -> str:
    local = dt.astimezone()
    tz = local.strftime("%z")
    return local.strftime(f"%Y-%m-%dT%H:%M:%S{tz}")


def build_phone_video_exiftool_args(
    preset: dict[str, Any],
    *,
    selfie: bool,
    export_lat: float | None,
    export_lon: float | None,
    captured_at: datetime | None = None,
) -> list[str]:
    make = str(preset.get("make") or "Unknown").strip()
    model = str(preset.get("model") or "Phone").strip()
    if selfie:
        lens = str(preset.get("lens_selfie") or "").strip()
        focal = int(preset.get("focal_35_selfie") or 23)
    else:
        lens = str(preset.get("lens_main") or "").strip()
        focal = int(preset.get("focal_35_main") or 24)

    when = captured_at or datetime.now(timezone.utc)
    dt_exif = exif_datetime_string(when)
    dt_apple = apple_quicktime_creation_date(when)
    software = str(preset.get("software") or "").strip()

    args: list[str] = [
        f"-Make={make}",
        f"-Model={model}",
        f"-Keys:Make={make}",
        f"-Keys:Model={model}",
        f"-UserData:com.apple.quicktime.make={make}",
        f"-UserData:com.apple.quicktime.model={model}",
        f"-CreateDate={dt_exif}",
        f"-ModifyDate={dt_exif}",
        f"-MediaCreateDate={dt_exif}",
        f"-TrackCreateDate={dt_exif}",
        f"-DateTimeOriginal={dt_exif}",
        f"-UserData:com.apple.quicktime.creationdate={dt_apple}",
    ]
    if software:
        args.extend(
            [
                f"-Software={software}",
                f"-Keys:Software={software}",
                f"-UserData:com.apple.quicktime.software={software}",
            ]
        )
    if lens:
        args.append(f"-LensModel={lens}")
    if focal:
        args.append(f"-FocalLengthIn35mmFormat={focal}")

    if export_lat is not None and export_lon is not None:
        if -90 <= export_lat <= 90 and -180 <= export_lon <= 180:
            loc = iso6709_location(export_lat, export_lon)
            lat_ref = "N" if export_lat >= 0 else "S"
            lon_ref = "E" if export_lon >= 0 else "W"
            args.extend(
                [
                    f"-GPSLatitude={abs(export_lat)}",
                    f"-GPSLongitude={abs(export_lon)}",
                    f"-GPSLatitudeRef={lat_ref}",
                    f"-GPSLongitudeRef={lon_ref}",
                    f"-UserData:com.apple.quicktime.location.ISO6709={loc}",
                ]
            )
    return args


def _run_exiftool_in_place(path: Path, tag_args: list[str], *, timeout: float) -> bool:
    cmd = [
        _exiftool_bin(),
        "-api",
        "largefilesupport=1",
        "-m",
        "-P",
        "-overwrite_original",
        *tag_args,
        str(path),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log.warning("video metadata: exiftool timeout (%s s)", timeout)
        return False
    except FileNotFoundError:
        log.warning("video metadata: exiftool not found")
        return False
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:400]
        log.warning("video metadata: exiftool failed rc=%s: %s", proc.returncode, err)
        return False
    backup = Path(f"{path}_original")
    if backup.is_file():
        try:
            backup.unlink()
        except OSError:
            pass
    return True


def process_video_archive_bytes(
    data: bytes,
    *,
    ext: str,
    preset: dict[str, Any] | None = None,
    selfie: bool = False,
    export_lat: float | None = None,
    export_lon: float | None = None,
    captured_at: datetime | None = None,
    strip_ai: bool | None = None,
) -> tuple[bytes, bool]:
    """
    Снимает C2PA/XMP и подставляет phone-метаданные в контейнер mp4/mov без перекодирования.
    Возвращает (байты, changed). При ошибке — исходные байты, changed=False.
    """
    if not data or len(data) < 64:
        return data, False

    norm_ext = _normalize_video_ext(ext)
    if norm_ext not in _VIDEO_EXTS:
        return data, False

    do_strip = (
        settings.studio_strip_ai_metadata_enabled
        if strip_ai is None
        else bool(strip_ai)
    )
    do_phone = bool(preset) and settings.studio_video_phone_export_enabled
    if not do_strip and not do_phone:
        return data, False

    tag_args: list[str] = []
    if do_strip:
        tag_args.extend(_AI_METADATA_CLEAR_ARGS)
    if do_phone and preset:
        tag_args.extend(
            build_phone_video_exiftool_args(
                preset,
                selfie=selfie,
                export_lat=export_lat,
                export_lon=export_lon,
                captured_at=captured_at,
            )
        )
    if not tag_args:
        return data, False

    src_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=norm_ext, delete=False) as tmp:
            tmp.write(data)
            src_path = Path(tmp.name)

        timeout = float(settings.studio_video_metadata_exiftool_timeout_seconds)
        if not _run_exiftool_in_place(src_path, tag_args, timeout=timeout):
            return data, False

        out = src_path.read_bytes()
        if not out:
            return data, False
        log.info(
            "video metadata: processed (%s → %s bytes, strip=%s phone=%s)",
            len(data),
            len(out),
            do_strip,
            do_phone,
        )
        return out, True
    except Exception as e:
        log.warning("video metadata: failed: %s", e)
        return data, False
    finally:
        if src_path is not None:
            try:
                src_path.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                Path(f"{src_path}_original").unlink(missing_ok=True)
            except OSError:
                pass
