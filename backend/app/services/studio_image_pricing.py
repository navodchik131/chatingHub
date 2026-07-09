"""Стоимость генерации картинок в кредитах: модель WaveSpeed + пайплайн (внутренний расчёт)."""

from __future__ import annotations

from typing import Literal

from app.config import settings

WaveModelId = Literal[
    "nano-banana-2",
    "nano-banana-pro",
    "gpt-image-2",
    "wan-2.7",
    "seedream-v5.0-pro",
]
WanEditTier = Literal["standard", "pro"]
GrokPipelineKind = Literal["none", "light", "standard", "heavy", "workflow"]

# База WaveSpeed (кредиты), ориентиры по прайсу провайдера + маржа
_WS_BASE_CREDITS: dict[str, int] = {
    "nano-banana-2": 2,
    "nano-banana-pro": 3,
    "gpt-image-2": 3,
    "wan-2.7": 2,
    "seedream-v5.0-pro": 3,
}

# Внутренние надбавки (промпт/vision на сервере) — не показываем пользователю отдельно
_GROK_SURCHARGE: dict[GrokPipelineKind, int] = {
    "none": 0,
    "light": 1,
    "standard": 2,
    "heavy": 3,
    "workflow": 3,
}

_WAN_PRO_EXTRA = 2


def normalize_wave_model_id(raw: str | None) -> str:
    m = (raw or "wan-2.7").strip().lower()
    if m in _WS_BASE_CREDITS:
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
    if m in ("model",) and not workflow:
        return "standard"
    return "light"


def quote_studio_image_credits(
    *,
    wave_model_id: str | None = None,
    wan_edit_tier: str | None = None,
    grok_pipeline: GrokPipelineKind = "standard",
    extra_reference_count: int = 0,
) -> int:
    """Итоговая цена операции в кредитах (одна цифра для UI)."""
    model = normalize_wave_model_id(wave_model_id)
    tier = normalize_wan_edit_tier(wan_edit_tier)
    base = _WS_BASE_CREDITS.get(model, 2)
    if model == "wan-2.7" and tier == "pro":
        base += _WAN_PRO_EXTRA
    grok = _GROK_SURCHARGE.get(grok_pipeline, 2)
    refs = max(0, int(extra_reference_count))
    ref_extra = min(2, refs // 2)
    total = base + grok + ref_extra
    return max(1, total)


DEMO_WAN_WAVE_MODEL = "wan-2.7"


def normalize_studio_wave_profile(raw: str | None) -> str:
    """regular = Nano Banana; nsfw = WAN / Seedream."""
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
    """Модель для биллинга/демо: явный workflow_wave_model или дефолт по профилю."""
    explicit = (wave_model_id or "").strip().lower()
    if explicit in _WS_BASE_CREDITS:
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
    """
    Бесплатная демо-генерация: любая модель профиля (regular / NSFW), кроме Wan Pro tier.
    """
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
    """Таблица «от N кр.» для health / UI."""
    models = []
    for mid in _WS_BASE_CREDITS:
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
                "credits_standard_tier": std,
                "credits_pro_tier": pro,
            }
        )
    return {
        "models": models,
        "demo_generations_grant": max(0, int(settings.demo_generations_grant)),
        "demo_credits_per_generation": quote_demo_image_credits(),
        "demo_wave_models": sorted(demo_allowed_wave_model_ids()),
    }
