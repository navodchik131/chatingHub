"""Стоимость Seedance T2V в кредитах: USD/сек × курс × длительность ÷ цена кредита."""

from __future__ import annotations

import math
from typing import Literal

from app.config import settings

SeedanceT2vVariant = Literal["standard", "mini"]
SeedanceT2vResolution = Literal["480p", "720p", "1080p"]

_RESOLUTION_MULT_FROM_720P: dict[str, float] = {
    "480p": 0.5,
    "720p": 1.0,
    "1080p": 2.5,
}
_VALID_VARIANTS = frozenset({"standard", "mini"})
_VALID_RESOLUTIONS = frozenset(_RESOLUTION_MULT_FROM_720P.keys())


def normalize_seedance_t2v_variant(raw: str | None) -> SeedanceT2vVariant:
    v = (raw or "standard").strip().lower()
    return "mini" if v == "mini" else "standard"


def normalize_seedance_t2v_resolution(raw: str | None) -> SeedanceT2vResolution:
    r = (raw or settings.wavespeed_seedance_20_t2v_resolution or "720p").strip().lower()
    if r in _VALID_RESOLUTIONS:
        return r  # type: ignore[return-value]
    return "720p"


def motion_video_duration_seconds(raw: str | int | None, *, default: int | None = None) -> int:
    """4–15 с (лимит WaveSpeed Seedance T2V); пустое значение → default из настроек."""
    lim_min = int(settings.studio_motion_video_duration_min)
    lim_max = int(settings.studio_motion_video_duration_max)
    fallback = default if default is not None else settings.wavespeed_seedance_20_t2v_duration
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return max(lim_min, min(lim_max, int(fallback)))
    try:
        ds = int(str(raw).strip())
    except (TypeError, ValueError):
        return max(lim_min, min(lim_max, int(fallback)))
    return max(lim_min, min(lim_max, ds))


def _usd_per_sec_at_720p(
    *,
    variant: SeedanceT2vVariant,
    has_motion_reference_video: bool,
) -> float:
    """Базовая ставка USD/с при 720p (масштабируется по resolution)."""
    if variant == "mini":
        if has_motion_reference_video:
            return float(settings.studio_motion_mini_usd_per_sec_with_ref)
        return float(settings.studio_motion_mini_usd_per_sec_no_ref)
    if has_motion_reference_video:
        return float(settings.studio_motion_usd_per_sec_with_ref)
    return float(settings.studio_motion_usd_per_sec_no_ref)


def motion_video_usd_per_sec(
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
) -> float:
    """USD/с с учётом варианта модели и разрешения (WaveSpeed: 720p=2×480p, 1080p=5×480p)."""
    v = normalize_seedance_t2v_variant(variant if isinstance(variant, str) else "standard")
    res = normalize_seedance_t2v_resolution(resolution if isinstance(resolution, str) else "720p")
    base_720p = _usd_per_sec_at_720p(variant=v, has_motion_reference_video=has_motion_reference_video)
    mult = _RESOLUTION_MULT_FROM_720P.get(res, 1.0)
    return max(0.0, base_720p * mult)


def _motion_video_credit_cost_raw(
    duration_seconds: float,
    *,
    variant: SeedanceT2vVariant = "standard",
    resolution: SeedanceT2vResolution = "720p",
    has_motion_reference_video: bool,
) -> int:
    """Кредиты за duration секунд без clamp min–max (для отображения «кр./с»)."""
    duration = max(1.0, float(duration_seconds))
    usd_per_sec = motion_video_usd_per_sec(
        variant=variant,
        resolution=resolution,
        has_motion_reference_video=has_motion_reference_video,
    )
    rub_total = usd_per_sec * duration * float(settings.studio_motion_rub_per_usd)
    per_credit = float(settings.studio_motion_rub_per_credit)
    if per_credit <= 0:
        return max(1, int(math.ceil(duration)))
    return max(1, int(math.ceil(rub_total / per_credit)))


def motion_video_credit_cost(
    duration_seconds: int,
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
) -> int:
    """
    Кредиты за ролик: ceil(duration × USD/s × RUB/USD / RUB за кредит).
    USD/s зависит от варианта (standard/mini), разрешения и наличия реф-видео.
    """
    duration = motion_video_duration_seconds(duration_seconds)
    return _motion_video_credit_cost_raw(
        duration,
        variant=normalize_seedance_t2v_variant(variant if isinstance(variant, str) else "standard"),
        resolution=normalize_seedance_t2v_resolution(
            resolution if isinstance(resolution, str) else "720p"
        ),
        has_motion_reference_video=has_motion_reference_video,
    )


def _variant_pricing_block(variant: SeedanceT2vVariant) -> dict[str, float | int]:
    return {
        "usd_per_sec_720p_with_reference_video": motion_video_usd_per_sec(
            variant=variant,
            resolution="720p",
            has_motion_reference_video=True,
        ),
        "usd_per_sec_720p_without_reference_video": motion_video_usd_per_sec(
            variant=variant,
            resolution="720p",
            has_motion_reference_video=False,
        ),
        "credits_per_sec_720p_with_reference_video": _motion_video_credit_cost_raw(
            1,
            variant=variant,
            resolution="720p",
            has_motion_reference_video=True,
        ),
        "credits_per_sec_720p_without_reference_video": _motion_video_credit_cost_raw(
            1,
            variant=variant,
            resolution="720p",
            has_motion_reference_video=False,
        ),
    }


def motion_video_pricing_public() -> dict[str, float | int | dict | list]:
    """Поля для /api/health — фронт считает стоимость по длительности, варианту и качеству."""
    dur_default = settings.wavespeed_seedance_20_t2v_duration
    default_res = normalize_seedance_t2v_resolution(None)
    return {
        # Обратная совместимость (720p, standard)
        "usd_per_sec_with_reference_video": motion_video_usd_per_sec(
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
        ),
        "usd_per_sec_without_reference_video": motion_video_usd_per_sec(
            variant="standard",
            resolution="720p",
            has_motion_reference_video=False,
        ),
        "rub_per_usd": float(settings.studio_motion_rub_per_usd),
        "rub_per_credit": float(settings.studio_motion_rub_per_credit),
        "duration_min": int(settings.studio_motion_video_duration_min),
        "duration_max": int(settings.studio_motion_video_duration_max),
        "duration_default": dur_default,
        "credits_per_sec_with_reference_video": _motion_video_credit_cost_raw(
            1,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=True,
        ),
        "credits_per_sec_without_reference_video": _motion_video_credit_cost_raw(
            1,
            variant="standard",
            resolution="720p",
            has_motion_reference_video=False,
        ),
        "credits_example_default_duration_with_ref": motion_video_credit_cost(
            dur_default,
            variant="standard",
            resolution=default_res,
            has_motion_reference_video=True,
        ),
        "credits_example_default_duration_without_ref": motion_video_credit_cost(
            dur_default,
            variant="standard",
            resolution=default_res,
            has_motion_reference_video=False,
        ),
        "default_resolution": default_res,
        "resolutions": ["480p", "720p", "1080p"],
        "resolution_multipliers_from_720p": dict(_RESOLUTION_MULT_FROM_720P),
        "default_variant": "standard",
        "variants": {
            "standard": _variant_pricing_block("standard"),
            "mini": _variant_pricing_block("mini"),
        },
        "mini_t2v_path": (settings.wavespeed_seedance_20_mini_t2v_path or "").strip(),
    }
