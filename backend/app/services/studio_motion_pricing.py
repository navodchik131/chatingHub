"""Стоимость Seedance T2V в кредитах: USD/сек × курс × длительность ÷ цена кредита."""

from __future__ import annotations

import math

from app.config import settings


def motion_video_duration_seconds(raw: str | int | None, *, default: int | None = None) -> int:
    """4–15 с (лимит Seedance T2V); пустое значение → default из настроек."""
    lim_min = 4
    lim_max = 15
    fallback = default if default is not None else settings.wavespeed_seedance_20_t2v_duration
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return max(lim_min, min(lim_max, int(fallback)))
    try:
        ds = int(str(raw).strip())
    except (TypeError, ValueError):
        return max(lim_min, min(lim_max, int(fallback)))
    return max(lim_min, min(lim_max, ds))


def _motion_video_credit_cost_raw(
    duration_seconds: float,
    *,
    has_motion_reference_video: bool,
) -> int:
    """Кредиты за duration секунд без clamp 4–15 (для отображения «кр./с»)."""
    duration = max(1.0, float(duration_seconds))
    usd_per_sec = (
        float(settings.studio_motion_usd_per_sec_with_ref)
        if has_motion_reference_video
        else float(settings.studio_motion_usd_per_sec_no_ref)
    )
    rub_total = usd_per_sec * duration * float(settings.studio_motion_rub_per_usd)
    per_credit = float(settings.studio_motion_rub_per_credit)
    if per_credit <= 0:
        return max(1, int(math.ceil(duration)))
    return max(1, int(math.ceil(rub_total / per_credit)))


def motion_video_credit_cost(
    duration_seconds: int,
    *,
    has_motion_reference_video: bool,
) -> int:
    """
    Кредиты за ролик: ceil(duration × USD/s × RUB/USD / RUB за кредит).
    С реф-видео: $0.50/с; без: $0.25/с (по умолчанию в settings).
    """
    duration = motion_video_duration_seconds(duration_seconds)
    return _motion_video_credit_cost_raw(
        duration,
        has_motion_reference_video=has_motion_reference_video,
    )


def motion_video_pricing_public() -> dict[str, float | int]:
    """Поля для /api/health — фронт считает стоимость по длительности и реф-видео."""
    dur_default = settings.wavespeed_seedance_20_t2v_duration
    return {
        "usd_per_sec_with_reference_video": float(settings.studio_motion_usd_per_sec_with_ref),
        "usd_per_sec_without_reference_video": float(settings.studio_motion_usd_per_sec_no_ref),
        "rub_per_usd": float(settings.studio_motion_rub_per_usd),
        "rub_per_credit": float(settings.studio_motion_rub_per_credit),
        "duration_min": 4,
        "duration_max": 15,
        "duration_default": dur_default,
        "credits_per_sec_with_reference_video": _motion_video_credit_cost_raw(
            1, has_motion_reference_video=True
        ),
        "credits_per_sec_without_reference_video": _motion_video_credit_cost_raw(
            1, has_motion_reference_video=False
        ),
        "credits_example_default_duration_with_ref": motion_video_credit_cost(
            dur_default, has_motion_reference_video=True
        ),
        "credits_example_default_duration_without_ref": motion_video_credit_cost(
            dur_default, has_motion_reference_video=False
        ),
    }
