"""Стоимость Seedance через EvoLink (Seedance Sale) в кредитах."""

from __future__ import annotations

import math

from app.config import settings
from app.services.studio_motion_pricing import (
    SeedanceT2vResolution,
    SeedanceT2vVariant,
    normalize_seedance_t2v_resolution,
    normalize_seedance_t2v_variant,
)

_EVOLINK_RES_MULT: dict[str, float] = {
    "480p": 0.75,
    "720p": 1.0,
    "1080p": 1.5,
}


def apply_seedance_sale_credit_cost(_plan: str, base_cost: int) -> int:
    """Seedance Sale — всегда списываем кредиты (включая Pro)."""
    return max(0, int(base_cost))


def evolink_video_duration_seconds(
    raw: str | int | None,
    *,
    variant: SeedanceT2vVariant | str = "standard",
    default: int | None = None,
) -> int:
    v = normalize_seedance_t2v_variant(variant if isinstance(variant, str) else "standard")
    lim_min = int(settings.evolink_video_duration_min)
    lim_max = (
        int(settings.evolink_video_duration_max_25)
        if v == "seedance_25"
        else int(settings.evolink_video_duration_max_20)
    )
    fallback = default if default is not None else int(settings.evolink_video_duration_default)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return max(lim_min, min(lim_max, int(fallback)))
    try:
        ds = int(str(raw).strip())
    except (TypeError, ValueError):
        return max(lim_min, min(lim_max, int(fallback)))
    return max(lim_min, min(lim_max, ds))


def normalize_evolink_resolution(raw: str | None, *, variant: str) -> SeedanceT2vResolution:
    v = normalize_seedance_t2v_variant(variant)
    r = normalize_seedance_t2v_resolution(raw or settings.evolink_video_default_resolution)
    if v == "seedance_25" and r == "1080p":
        return "720p"
    if r not in ("480p", "720p", "1080p"):
        return "720p"
    return r  # type: ignore[return-value]


def _usd_per_sec_at_720p(
    *,
    variant: SeedanceT2vVariant,
    has_motion_reference_video: bool,
) -> float:
    if variant == "seedance_25":
        if has_motion_reference_video:
            return float(settings.studio_evolink_25_usd_per_sec_with_ref)
        return float(settings.studio_evolink_25_usd_per_sec_no_ref)
    if variant == "mini":
        if has_motion_reference_video:
            return float(settings.studio_evolink_mini_usd_per_sec_with_ref)
        return float(settings.studio_evolink_mini_usd_per_sec_no_ref)
    if has_motion_reference_video:
        return float(settings.studio_evolink_20_usd_per_sec_with_ref)
    return float(settings.studio_evolink_20_usd_per_sec_no_ref)


def evolink_video_usd_per_sec(
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
) -> float:
    v = normalize_seedance_t2v_variant(variant if isinstance(variant, str) else "standard")
    res = normalize_evolink_resolution(
        resolution if isinstance(resolution, str) else "720p",
        variant=v,
    )
    base = _usd_per_sec_at_720p(variant=v, has_motion_reference_video=has_motion_reference_video)
    mult = _EVOLINK_RES_MULT.get(res, 1.0)
    return max(0.0, base * mult)


def evolink_video_billed_seconds(
    output_duration: int,
    *,
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
) -> int:
    out = max(1, int(output_duration))
    if not has_motion_reference_video:
        return out
    if reference_video_duration is None:
        ref = out
    else:
        try:
            ref = int(math.ceil(float(reference_video_duration)))
        except (TypeError, ValueError):
            ref = out
    ref = max(2, min(30, ref))
    return ref + out


def evolink_video_usd_total(
    duration_seconds: int,
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
) -> float:
    rate = evolink_video_usd_per_sec(
        variant=variant,
        resolution=resolution,
        has_motion_reference_video=has_motion_reference_video,
    )
    billed = evolink_video_billed_seconds(
        duration_seconds,
        has_motion_reference_video=has_motion_reference_video,
        reference_video_duration=reference_video_duration,
    )
    return max(0.0, rate * billed)


def _credit_cost_raw(
    duration_seconds: float,
    *,
    variant: SeedanceT2vVariant = "standard",
    resolution: SeedanceT2vResolution = "720p",
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
) -> int:
    dur = max(1, int(math.ceil(float(duration_seconds))))
    usd = evolink_video_usd_total(
        dur,
        variant=variant,
        resolution=resolution,
        has_motion_reference_video=has_motion_reference_video,
        reference_video_duration=reference_video_duration,
    )
    rub_total = usd * float(settings.studio_motion_rub_per_usd)
    per_credit = float(settings.studio_motion_rub_per_credit)
    if per_credit <= 0:
        return max(1, dur)
    return max(1, int(math.ceil(rub_total / per_credit)))


def evolink_video_credit_cost(
    duration_seconds: int,
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
) -> int:
    v = normalize_seedance_t2v_variant(variant if isinstance(variant, str) else "standard")
    res = normalize_evolink_resolution(
        resolution if isinstance(resolution, str) else "720p",
        variant=v,
    )
    dur = evolink_video_duration_seconds(duration_seconds, variant=v)
    return _credit_cost_raw(
        dur,
        variant=v,
        resolution=res,
        has_motion_reference_video=has_motion_reference_video,
        reference_video_duration=reference_video_duration,
    )


def _variant_block(variant: SeedanceT2vVariant) -> dict[str, float | int]:
    return {
        "usd_per_sec_720p_with_reference_video": evolink_video_usd_per_sec(
            variant=variant,
            resolution="720p",
            has_motion_reference_video=True,
        ),
        "usd_per_sec_720p_without_reference_video": evolink_video_usd_per_sec(
            variant=variant,
            resolution="720p",
            has_motion_reference_video=False,
        ),
        "credits_per_sec_720p_with_reference_video": _credit_cost_raw(
            1,
            variant=variant,
            resolution="720p",
            has_motion_reference_video=True,
        ),
        "credits_per_sec_720p_without_reference_video": _credit_cost_raw(
            1,
            variant=variant,
            resolution="720p",
            has_motion_reference_video=False,
        ),
    }


def evolink_video_pricing_public() -> dict:
    v25 = "seedance_25"
    dur_default = int(settings.evolink_video_duration_default)
    default_res = normalize_evolink_resolution(None, variant="standard")
    return {
        "backend": "evolink",
        "rub_per_usd": float(settings.studio_motion_rub_per_usd),
        "rub_per_credit": float(settings.studio_motion_rub_per_credit),
        "duration_min": int(settings.evolink_video_duration_min),
        "duration_max_20": int(settings.evolink_video_duration_max_20),
        "duration_max_25": int(settings.evolink_video_duration_max_25),
        "duration_default": dur_default,
        "default_resolution": default_res,
        "resolutions": ["480p", "720p"] if True else ["480p", "720p", "1080p"],
        "resolutions_by_variant": {
            "standard": ["480p", "720p", "1080p"],
            "mini": ["480p", "720p", "1080p"],
            "seedance_25": ["480p", "720p"],
        },
        "default_variant": "standard",
        "variants": {
            "standard": _variant_block("standard"),
            "mini": _variant_block("mini"),
            "seedance_25": _variant_block("seedance_25"),
        },
        "credits_example_default_duration_with_ref": evolink_video_credit_cost(
            dur_default,
            variant="standard",
            resolution=default_res,
            has_motion_reference_video=True,
        ),
        "always_charges_credits": True,
        "nsfw_supported": False,
    }
