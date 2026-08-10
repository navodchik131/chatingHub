"""Стоимость Seedance T2V в кредитах: USD/сек × курс × длительность ÷ цена кредита."""

from __future__ import annotations

import math
from typing import Literal

from app.config import settings
from app.services.fx_rate import cached_cbr_rub_per_usd_sync, studio_motion_rub_per_usd_effective

SeedanceT2vVariant = Literal["standard", "mini", "seedance_25"]
SeedanceT2vResolution = Literal["480p", "720p", "1080p"]
GrokImagineI2vResolution = Literal["480p", "720p"]
WorkflowVideoProvider = Literal["seedance_t2v", "grok_imagine_i2v"]

_RESOLUTION_MULT_FROM_720P: dict[str, float] = {
    "480p": 0.5,
    "720p": 1.0,
    "1080p": 2.5,
}
_VALID_VARIANTS = frozenset({"standard", "mini", "seedance_25"})
_VALID_RESOLUTIONS = frozenset(_RESOLUTION_MULT_FROM_720P.keys())


def normalize_seedance_t2v_variant(raw: str | None) -> SeedanceT2vVariant:
    v = (raw or "standard").strip().lower().replace("-", "_")
    if v in ("seedance_25", "seedance25", "v25", "2_5"):
        return "seedance_25"
    if v == "mini":
        return "mini"
    return "standard"


def normalize_seedance_t2v_resolution(raw: str | None) -> SeedanceT2vResolution:
    r = (raw or settings.wavespeed_seedance_20_t2v_resolution or "720p").strip().lower()
    if r in _VALID_RESOLUTIONS:
        return r  # type: ignore[return-value]
    return "720p"


def normalize_workflow_video_provider(raw: str | None) -> WorkflowVideoProvider:
    v = (raw or "seedance_t2v").strip().lower()
    return "grok_imagine_i2v" if v == "grok_imagine_i2v" else "seedance_t2v"


def normalize_grok_imagine_i2v_resolution(raw: str | None) -> GrokImagineI2vResolution:
    r = (raw or "720p").strip().lower()
    return "480p" if r == "480p" else "720p"


def grok_imagine_i2v_duration_seconds(raw: str | int | None, *, default: int | None = None) -> int:
    """1–15 с (лимит WaveSpeed Grok Imagine Video I2V)."""
    lim_min = int(settings.studio_grok_imagine_i2v_duration_min)
    lim_max = 15
    fallback = default if default is not None else 6
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return max(lim_min, min(lim_max, int(fallback)))
    try:
        ds = int(str(raw).strip())
    except (TypeError, ValueError):
        return max(lim_min, min(lim_max, int(fallback)))
    return max(lim_min, min(lim_max, ds))


def grok_imagine_i2v_usd_total(
    duration_seconds: int,
    *,
    resolution: GrokImagineI2vResolution | str = "720p",
) -> float:
    dur = grok_imagine_i2v_duration_seconds(duration_seconds)
    res = normalize_grok_imagine_i2v_resolution(
        resolution if isinstance(resolution, str) else "720p"
    )
    rate = (
        float(settings.studio_grok_imagine_i2v_usd_per_sec_480p)
        if res == "480p"
        else float(settings.studio_grok_imagine_i2v_usd_per_sec_720p)
    )
    return max(0.0, rate * dur + float(settings.studio_grok_imagine_i2v_usd_per_image))


def grok_imagine_i2v_credit_cost(
    duration_seconds: int,
    *,
    resolution: GrokImagineI2vResolution | str = "720p",
) -> int:
    usd = grok_imagine_i2v_usd_total(duration_seconds, resolution=resolution)
    rub_total = usd * studio_motion_rub_per_usd_effective()
    per_credit = float(settings.studio_motion_rub_per_credit)
    if per_credit <= 0:
        return max(1, grok_imagine_i2v_duration_seconds(duration_seconds))
    return max(1, int(math.ceil(rub_total / per_credit)))


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
    if variant == "seedance_25":
        if has_motion_reference_video:
            return float(settings.studio_motion_seedance_25_usd_per_sec_with_ref)
        return float(settings.studio_motion_seedance_25_usd_per_sec_no_ref)
    if variant == "mini":
        if has_motion_reference_video:
            return float(settings.studio_motion_mini_usd_per_sec_with_ref)
        return float(settings.studio_motion_mini_usd_per_sec_no_ref)
    if has_motion_reference_video:
        return float(settings.studio_motion_usd_per_sec_with_ref)
    return float(settings.studio_motion_usd_per_sec_no_ref)


def _clamp_reference_video_seconds(raw: float | int | None, *, fallback: int) -> int:
    """WaveSpeed: ref video 2–15 с при биллинге ref+output."""
    if raw is None:
        ref = fallback
    else:
        try:
            ref = int(math.ceil(float(raw)))
        except (TypeError, ValueError):
            ref = fallback
    return max(2, min(15, ref))


def motion_video_billed_seconds(
    output_duration: int,
    *,
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
) -> int:
    """Секунды для биллинга WaveSpeed (с ref: input ref + output)."""
    out = motion_video_duration_seconds(output_duration)
    if not has_motion_reference_video:
        return out
    ref = _clamp_reference_video_seconds(reference_video_duration, fallback=out)
    return ref + out


def motion_video_usd_total(
    duration_seconds: int,
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
) -> float:
    """Полная стоимость ролика в USD по прайсу WaveSpeed."""
    out = motion_video_duration_seconds(duration_seconds)
    rate = motion_video_usd_per_sec(
        variant=variant,
        resolution=resolution,
        has_motion_reference_video=has_motion_reference_video,
    )
    if has_motion_reference_video:
        billed = motion_video_billed_seconds(
            out,
            has_motion_reference_video=True,
            reference_video_duration=reference_video_duration,
        )
        return max(0.0, rate * billed)
    return max(0.0, rate * out)


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
    reference_video_duration: int | None = None,
) -> int:
    """Кредиты за ролик (без clamp duration min–max для «кр./с»-подсказок)."""
    dur = max(1, int(math.ceil(float(duration_seconds))))
    usd = motion_video_usd_total(
        dur,
        variant=variant,
        resolution=resolution,
        has_motion_reference_video=has_motion_reference_video,
        reference_video_duration=reference_video_duration,
    )
    rub_total = usd * studio_motion_rub_per_usd_effective()
    per_credit = float(settings.studio_motion_rub_per_credit)
    if per_credit <= 0:
        return max(1, dur)
    return max(1, int(math.ceil(rub_total / per_credit)))


def motion_video_credit_cost(
    duration_seconds: int,
    *,
    variant: SeedanceT2vVariant | str = "standard",
    resolution: SeedanceT2vResolution | str = "720p",
    has_motion_reference_video: bool,
    reference_video_duration: int | None = None,
) -> int:
    """
    Кредиты за ролик: USD total × RUB/USD / RUB за кредит.
    С ref-видео WaveSpeed считает ref duration + output duration.
    """
    duration = motion_video_duration_seconds(duration_seconds)
    return _motion_video_credit_cost_raw(
        duration,
        variant=normalize_seedance_t2v_variant(variant if isinstance(variant, str) else "standard"),
        resolution=normalize_seedance_t2v_resolution(
            resolution if isinstance(resolution, str) else "720p"
        ),
        has_motion_reference_video=has_motion_reference_video,
        reference_video_duration=reference_video_duration,
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


VideoUpscaleResolution = Literal["720p", "1080p", "2k", "4k"]
_VALID_VIDEO_UPSCALE_RESOLUTIONS = frozenset({"720p", "1080p", "2k", "4k"})


def normalize_video_upscale_resolution(raw: str | None) -> VideoUpscaleResolution:
    r = (raw or "1080p").strip().lower()
    if r in _VALID_VIDEO_UPSCALE_RESOLUTIONS:
        return r  # type: ignore[return-value]
    return "1080p"


def _video_upscale_usd_per_5s(resolution: VideoUpscaleResolution | str) -> float:
    res = normalize_video_upscale_resolution(resolution if isinstance(resolution, str) else "1080p")
    mapping = {
        "720p": float(settings.studio_video_upscale_usd_per_5s_720p),
        "1080p": float(settings.studio_video_upscale_usd_per_5s_1080p),
        "2k": float(settings.studio_video_upscale_usd_per_5s_2k),
        "4k": float(settings.studio_video_upscale_usd_per_5s_4k),
    }
    return max(0.0, mapping.get(res, mapping["1080p"]))


def video_upscale_credit_cost(
    target_resolution: VideoUpscaleResolution | str = "1080p",
    *,
    duration_seconds: int | None = None,
) -> int:
    """Кредиты за апскейл (минимум 5 с биллинга WaveSpeed, см. docs)."""
    min_sec = max(1, int(settings.studio_video_upscale_min_billed_seconds))
    dur = max(min_sec, int(duration_seconds or min_sec))
    usd = _video_upscale_usd_per_5s(target_resolution) * (dur / 5.0)
    rub_total = usd * studio_motion_rub_per_usd_effective()
    per_credit = float(settings.studio_motion_rub_per_credit)
    if per_credit <= 0:
        return max(1, int(math.ceil(dur / 5.0)))
    return max(1, int(math.ceil(rub_total / per_credit)))


def video_upscale_pricing_public() -> dict[str, float | int | list[str] | dict[str, int]]:
    res_list: list[VideoUpscaleResolution] = ["720p", "1080p", "2k", "4k"]
    credits_by_resolution = {r: video_upscale_credit_cost(r) for r in res_list}
    return {
        "resolutions": list(res_list),
        "default_resolution": "1080p",
        "min_billed_seconds": int(settings.studio_video_upscale_min_billed_seconds),
        "usd_per_5s_720p": _video_upscale_usd_per_5s("720p"),
        "usd_per_5s_1080p": _video_upscale_usd_per_5s("1080p"),
        "usd_per_5s_2k": _video_upscale_usd_per_5s("2k"),
        "usd_per_5s_4k": _video_upscale_usd_per_5s("4k"),
        "credits_by_resolution": credits_by_resolution,
        "credits_example_1080p": credits_by_resolution["1080p"],
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
        "rub_per_usd": studio_motion_rub_per_usd_effective(),
        "rub_per_usd_cbr": cached_cbr_rub_per_usd_sync(),
        "rub_per_usd_margin": float(settings.studio_motion_rub_per_usd_margin),
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
            "seedance_25": _variant_pricing_block("seedance_25"),
        },
        "mini_t2v_path": (settings.wavespeed_seedance_20_mini_t2v_path or "").strip(),
        "seedance_25_t2v_path": (settings.wavespeed_seedance_25_t2v_path or "").strip(),
        "grok_imagine_i2v": {
            "usd_per_sec_480p": float(settings.studio_grok_imagine_i2v_usd_per_sec_480p),
            "usd_per_sec_720p": float(settings.studio_grok_imagine_i2v_usd_per_sec_720p),
            "usd_per_image": float(settings.studio_grok_imagine_i2v_usd_per_image),
            "duration_min": int(settings.studio_grok_imagine_i2v_duration_min),
            "duration_max": 15,
            "duration_default": 6,
            "resolutions": ["480p", "720p"],
            "default_resolution": "720p",
            "credits_example_6s_720p": grok_imagine_i2v_credit_cost(6, resolution="720p"),
        },
        "video_upscale": video_upscale_pricing_public(),
    }
