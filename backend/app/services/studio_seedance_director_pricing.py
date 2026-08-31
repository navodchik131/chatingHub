"""Стоимость Seedance Director: Grok compose + генерация WaveSpeed / EvoLink."""

from __future__ import annotations

from app.services.credit_units import credit_units_public, usd_to_credits
from app.services.studio_evolink_motion_pricing import (
    evolink_video_credit_cost,
    normalize_evolink_resolution,
    normalize_evolink_seedance_variant,
)
from app.services.studio_motion_pricing import (
    motion_video_credit_cost,
    normalize_seedance_t2v_resolution,
    normalize_seedance_t2v_variant,
    seedance_fast_t2v_output_credit_cost,
)
from app.services.studio_provider_pricing import grok_pipeline_usd, operation_usd


def seedance_director_compose_usd(*, image_count: int) -> float:
    """
    Grok compose: тяжёлый vision-запрос с инструкцией + N фото.
    База = heavy pipeline, каждое фото ≈ light pipeline (оценка vision-токенов).
    """
    n = max(1, int(image_count or 1))
    op = operation_usd("seedance_director_compose")
    if op > 0:
        return op + grok_pipeline_usd("light") * max(0, n - 1)
    return grok_pipeline_usd("heavy") + grok_pipeline_usd("light") * max(0, n - 1)


def seedance_director_compose_credit_cost(*, image_count: int) -> int:
    return usd_to_credits(seedance_director_compose_usd(image_count=image_count), markup_usd=0.0)


def seedance_director_piece_credit_cost(
    *,
    version: str,
    duration_seconds: int,
    resolution: str,
    video_backend: str,
) -> int:
    """Кредиты за один кусок Seedance 2.0 / 2.5."""
    variant = normalize_seedance_t2v_variant("seedance_25" if str(version).strip() == "2.5" else "standard")
    backend = (video_backend or "wavespeed").strip().lower()
    dur = max(1, int(duration_seconds or 1))

    if backend == "evolink":
        res = normalize_evolink_resolution(resolution, variant=variant)
        return evolink_video_credit_cost(
            dur,
            variant=variant,
            resolution=res,
            has_motion_reference_video=False,
        )

    res = normalize_seedance_t2v_resolution(resolution)
    # Fast T2V + reference_images (без reference_videos): output-only $0.20/с @720p, не motion ref $0.13/с.
    return seedance_fast_t2v_output_credit_cost(
        dur,
        variant=variant,
        resolution=res,
    )


def seedance_director_pricing_public() -> dict:
    """Публичный снимок для /api/health."""
    units = credit_units_public()
    sample_compose = seedance_director_compose_credit_cost(image_count=3)
    sample_piece_20 = seedance_director_piece_credit_cost(
        version="2.0",
        duration_seconds=10,
        resolution="720p",
        video_backend="wavespeed",
    )
    sample_piece_25 = seedance_director_piece_credit_cost(
        version="2.5",
        duration_seconds=15,
        resolution="720p",
        video_backend="wavespeed",
    )
    from app.services.studio_motion_pricing import seedance_fast_t2v_output_usd_per_sec

    return {
        "compose_usd_base": grok_pipeline_usd("heavy"),
        "compose_usd_per_extra_image": grok_pipeline_usd("light"),
        "compose_credits_sample_3_images": sample_compose,
        "piece_credits_sample_20_10s_wavespeed": sample_piece_20,
        "piece_credits_sample_25_15s_wavespeed": sample_piece_25,
        "fast_t2v_output_usd_per_sec_720p": seedance_fast_t2v_output_usd_per_sec(
            variant="standard", resolution="720p"
        ),
        "credits_per_usd": units.get("credits_per_usd"),
    }
