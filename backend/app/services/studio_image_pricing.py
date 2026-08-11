"""Стоимость генерации картинок: USD провайдера → cent-credits."""

from __future__ import annotations

from typing import Literal

from app.config import settings
from app.services.credit_units import usd_to_credits
from app.services.studio_provider_pricing import grok_pipeline_usd, image_model_usd

WaveModelId = Literal[
    "nano-banana-2",
    "nano-banana-pro",
    "gpt-image-2",
    "wan-2.7",
    "seedream-v5.0-pro",
]
WanEditTier = Literal["standard", "pro"]
GrokPipelineKind = Literal["none", "light", "standard", "heavy", "workflow"]

_WAVE_MODELS = frozenset(
    {"nano-banana-2", "nano-banana-pro", "gpt-image-2", "wan-2.7", "seedream-v5.0-pro"}
)


def normalize_wave_model_id(raw: str | None) -> str:
    m = (raw or "wan-2.7").strip().lower()
    if m in _WAVE_MODELS:
        return m
    return "wan-2.7"


def normalize_wan_edit_tier(raw: str | None) -> WanEditTier:
    t = (raw or "standard").strip().lower()
    return "pro" if t == "pro" else "standard"


def grok_pipeline_for_studio_mode(mode: str, *, workflow: bool = False) -> GrokPipelineKind:
    if workflow:
        return "workflow"
    m = (mode or "").strip().lower()
    if m in ("model", "model_scene", "grok_compose"):
        return "standard"
    return "light"


def _image_model_usd(
    *,
    wave_model_id: str,
    wan_edit_tier: WanEditTier,
) -> float:
    model = normalize_wave_model_id(wave_model_id)
    if model == "wan-2.7" and wan_edit_tier == "pro":
        return image_model_usd("wan-2.7-pro")
    return image_model_usd(model)


def quote_studio_image_credits(
    *,
    wave_model_id: str | None = None,
    wan_edit_tier: str | None = None,
    grok_pipeline: GrokPipelineKind = "standard",
    extra_reference_count: int = 0,
) -> int:
    """Итоговая цена операции в cent-credits."""
    tier = normalize_wan_edit_tier(wan_edit_tier)
    base_usd = _image_model_usd(
        wave_model_id=normalize_wave_model_id(wave_model_id),
        wan_edit_tier=tier,
    )
    grok_usd = grok_pipeline_usd(grok_pipeline)
    refs = max(0, int(extra_reference_count))
    ref_usd = min(0.04, refs * 0.005)
    return usd_to_credits(base_usd + grok_usd + ref_usd, markup_usd=0.0)


DEMO_WAN_WAVE_MODEL = "wan-2.7"


def normalize_studio_wave_profile(raw: str | None) -> str:
    p = (raw or "nsfw").strip().lower()
    return "regular" if p == "regular" else "nsfw"


def demo_allowed_wave_model_id() -> str:
    return (settings.demo_studio_wave_model or "nano-banana-2").strip().lower()


def demo_allowed_wave_model_ids() -> frozenset[str]:
    return frozenset({demo_allowed_wave_model_id(), DEMO_WAN_WAVE_MODEL})


def effective_wave_model_for_billing(
    wave_model_id: str | None,
    *,
    wave_profile: str | None = None,
) -> str:
    explicit = (wave_model_id or "").strip().lower()
    if explicit in _WAVE_MODELS:
        return explicit
    if normalize_studio_wave_profile(wave_profile) == "regular":
        return "nano-banana-pro"
    return DEMO_WAN_WAVE_MODEL


def demo_request_eligible_for_free_slot(
    *,
    wave_model_id: str | None,
    grok_pipeline: str,
    wave_profile: str | None = "nsfw",
    wan_edit_tier: str | None = "standard",
) -> bool:
    profile = normalize_studio_wave_profile(wave_profile)
    model = effective_wave_model_for_billing(wave_model_id, wave_profile=profile)
    tier = normalize_wan_edit_tier(wan_edit_tier)
    gp = grok_pipeline

    if tier == "pro":
        return False

    regular_models = frozenset({"nano-banana-2", "nano-banana-pro", "gpt-image-2", "seedream-v5.0-pro"})
    nsfw_models = frozenset({"wan-2.7", "seedream-v5.0-pro"})

    if profile == "regular" and model in regular_models:
        return gp in ("light", "none", "workflow", "standard")
    if profile == "nsfw" and model in nsfw_models:
        return gp in ("light", "standard", "none", "workflow")
    return False


def demo_allowed_models_label() -> str:
    return "любая модель выбранного профиля (Обычные или NSFW), кроме Wan 2.7 Pro"


def quote_demo_image_credits() -> int:
    return quote_studio_image_credits(
        wave_model_id=demo_allowed_wave_model_id(),
        wan_edit_tier="standard",
        grok_pipeline="light",
    )


def image_pricing_public_dict() -> dict:
    from app.services.credit_units import credit_units_public

    models = []
    for mid in sorted(_WAVE_MODELS):
        std = quote_studio_image_credits(
            wave_model_id=mid, wan_edit_tier="standard", grok_pipeline="standard"
        )
        pro = (
            quote_studio_image_credits(
                wave_model_id=mid, wan_edit_tier="pro", grok_pipeline="standard"
            )
            if mid == "wan-2.7"
            else None
        )
        models.append(
            {
                "wave_model_id": mid,
                "usd_standard_tier": round(
                    _image_model_usd(wave_model_id=mid, wan_edit_tier="standard"), 4
                ),
                "credits_standard_tier": std,
                "credits_pro_tier": pro,
            }
        )
    return {
        **credit_units_public(),
        "models": models,
        "demo_generations_grant": max(0, int(settings.demo_generations_grant)),
        "demo_credits_per_generation": quote_demo_image_credits(),
        "demo_wave_models": sorted(demo_allowed_wave_model_ids()),
    }
