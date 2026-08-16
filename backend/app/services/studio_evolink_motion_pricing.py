"""Стоимость Seedance через EvoLink (Seedance Sale) в кредитах.

Seedance 2.0 Sale вызывает ``seedance-2.0-fast-reference-to-video`` — биллинг EvoLink Fast tier
(≈ −25% к Standard; тарифы в ``studio_evolink_20_*``). Seedance 2.5 — Standard tier.
"""

from __future__ import annotations

import math
from typing import Literal

from app.config import settings
from app.services.credit_units import credit_units_public, usd_to_credits
from app.services.fx_rate import cached_cbr_rub_per_usd_sync
from app.services.studio_motion_pricing import (
    SeedanceT2vResolution,
    SeedanceT2vVariant,
    normalize_seedance_t2v_resolution,
    normalize_seedance_t2v_variant,
)
from app.services.studio_provider_pricing import video_evolink_usd_per_sec
from app.services.studio_seedance_t2v import (
    filter_model_images_for_seedance_motion_swap,
    filter_model_images_for_seedance_video,
)

EvolinkBillingKind = Literal["output_seconds", "video_reference_seconds"]

_EVOLINK_RES_MULT: dict[str, float] = {
    "480p": 1.0,
    "720p": 1.0,
}


def apply_seedance_sale_credit_cost(_plan: str, base_cost: int) -> int:
    """Seedance Sale тАФ ╨▓╤Б╨╡╨│╨┤╨░ ╤Б╨┐╨╕╤Б╤Л╨▓╨░╨╡╨╝ ╨║╤А╨╡╨┤╨╕╤В╤Л (╨▓╨║╨╗╤О╤З╨░╤П Pro)."""
    return max(0, int(base_cost))


def normalize_evolink_seedance_variant(raw: str | None) -> SeedanceT2vVariant:
    """Seedance Sale: ╤В╨╛╨╗╤М╨║╨╛ 2.0 (standard) ╨╕ 2.5."""
    v = normalize_seedance_t2v_variant(raw if isinstance(raw, str) else "standard")
    if v == "mini":
        return "standard"
    if v != "seedance_25":
        return "standard"
    return v


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
    _ = normalize_seedance_t2v_variant(variant)
    r = normalize_seedance_t2v_resolution(raw or settings.evolink_video_default_resolution)
    if r == "480p":
        return "480p"
    return "720p"


def evolink_billing_kind(
    *,
    has_motion_reference_video: bool,
) -> EvolinkBillingKind:
    """EvoLink: motion-video ref billed input+output at video-ref rate; ╨╕╨╜╨░╤З╨╡ тАФ output-only."""
    if has_motion_reference_video:
        return "video_reference_seconds"
    return "output_seconds"


def evolink_quote_reference_image_count(
    *,
    prompt_only_mode: bool,
    has_first_frame: bool,
    has_motion_video: bool,
    model_images: list,
) -> int:
    """Сколько image_urls уйдёт в EvoLink (для UI и логов)."""
    if has_motion_video:
        n_model = len(filter_model_images_for_seedance_motion_swap(model_images))
        return (1 if has_first_frame else 0) + n_model
    if prompt_only_mode and has_first_frame:
        return 1
    if has_first_frame:
        n_model = len(
            filter_model_images_for_seedance_video(model_images, minimal=False, include_body=False)
        )
        return 1 + n_model
    return len(filter_model_images_for_seedance_video(model_images, minimal=False, include_body=False))


def evolink_video_usd_per_sec(
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    billing_kind: EvolinkBillingKind,
) -> float:
    v = normalize_seedance_t2v_variant(variant if isinstance(variant, str) else "standard")
    res = normalize_evolink_resolution(
        resolution if isinstance(resolution, str) else "720p",
        variant=v,
    )
    base = video_evolink_usd_per_sec(variant=v, billing_kind=billing_kind, resolution=res)
    mult = _EVOLINK_RES_MULT.get(res, 1.0)
    return max(0.0, base * mult)


def evolink_video_billed_seconds(
    output_duration: int,
    *,
    billing_kind: EvolinkBillingKind,
    reference_video_duration: int | None = None,
) -> int:
    out = max(1, int(output_duration))
    if billing_kind != "video_reference_seconds":
        return out
    if reference_video_duration is None:
        return out
    try:
        ref = int(math.ceil(float(reference_video_duration)))
    except (TypeError, ValueError):
        return out
    ref = max(2, min(30, min(ref, out)))
    return ref + out


def evolink_video_usd_total(
    duration_seconds: int,
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
) -> float:
    billing_kind = evolink_billing_kind(has_motion_reference_video=has_motion_reference_video)
    rate = evolink_video_usd_per_sec(
        variant=variant,
        resolution=resolution,
        billing_kind=billing_kind,
    )
    billed = evolink_video_billed_seconds(
        duration_seconds,
        billing_kind=billing_kind,
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
    return usd_to_credits(usd, markup_usd=0.0)


def evolink_video_credit_cost(
    duration_seconds: int,
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
    reference_image_count: int = 0,
) -> int:
    _ = reference_image_count  # same output rate for 1 vs N image refs on EvoLink
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
        "usd_per_sec_720p_output": evolink_video_usd_per_sec(
            variant=variant,
            resolution="720p",
            billing_kind="output_seconds",
        ),
        "usd_per_sec_720p_video_reference": evolink_video_usd_per_sec(
            variant=variant,
            resolution="720p",
            billing_kind="video_reference_seconds",
        ),
        "usd_per_sec_480p_output": evolink_video_usd_per_sec(
            variant=variant,
            resolution="480p",
            billing_kind="output_seconds",
        ),
        "usd_per_sec_480p_video_reference": evolink_video_usd_per_sec(
            variant=variant,
            resolution="480p",
            billing_kind="video_reference_seconds",
        ),
        "credits_per_sec_720p_output": _credit_cost_raw(
            1,
            variant=variant,
            resolution="720p",
            has_motion_reference_video=False,
        ),
        "credits_per_sec_720p_video_reference": _credit_cost_raw(
            1,
            variant=variant,
            resolution="720p",
            has_motion_reference_video=True,
            reference_video_duration=1,
        ),
        # Legacy keys for older frontend bundles
        "usd_per_sec_720p_with_reference_video": evolink_video_usd_per_sec(
            variant=variant,
            resolution="720p",
            billing_kind="video_reference_seconds",
        ),
        "usd_per_sec_720p_without_reference_video": evolink_video_usd_per_sec(
            variant=variant,
            resolution="720p",
            billing_kind="output_seconds",
        ),
    }


def evolink_video_pricing_public() -> dict:
    dur_default = int(settings.evolink_video_duration_default)
    default_res = normalize_evolink_resolution(None, variant="standard")
    units = credit_units_public()
    return {
        **units,
        "backend": "evolink",
        "rub_per_usd": cached_cbr_rub_per_usd_sync(),
        "rub_per_usd_cbr": cached_cbr_rub_per_usd_sync(),
        "rub_per_credit": units.get("rub_per_credit", 0),
        "duration_min": int(settings.evolink_video_duration_min),
        "duration_max_20": int(settings.evolink_video_duration_max_20),
        "duration_max_25": int(settings.evolink_video_duration_max_25),
        "duration_default": dur_default,
        "default_resolution": default_res,
        "resolutions": ["480p", "720p"],
        "resolutions_by_variant": {
            "standard": ["480p", "720p"],
            "seedance_25": ["480p", "720p"],
        },
        "default_variant": "standard",
        "variants": {
            "standard": _variant_block("standard"),
            "seedance_25": _variant_block("seedance_25"),
        },
        "credits_example_default_duration_output": evolink_video_credit_cost(
            dur_default,
            variant="standard",
            resolution=default_res,
            has_motion_reference_video=False,
        ),
        "credits_example_default_duration_with_ref": evolink_video_credit_cost(
            dur_default,
            variant="standard",
            resolution=default_res,
            has_motion_reference_video=True,
            reference_video_duration=dur_default,
        ),
        "always_charges_credits": True,
        "nsfw_supported": False,
        "pricing_tier_20": "fast",
        "billing_notes": {
            "output_seconds": "T2V / I2V / reference images тАФ billed by output duration",
            "video_reference_seconds": "Motion video ref тАФ billed input + output at lower $/s",
        },
    }
