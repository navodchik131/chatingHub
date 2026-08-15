"""Стоимость вспомогательных операций студии (USD → cent-credits)."""

from __future__ import annotations

from app.config import settings
from app.services.credit_units import usd_to_credits
from app.services.studio_provider_pricing import operation_usd


def studio_prompt_refine_credit_cost() -> int:
    """Фиксированная надбавка за LLM-промпт, включается в цену генерации."""
    return max(1, int(settings.credit_cost_studio_prompt_refine))


def studio_model_profile_generate_credit_cost() -> int:
    return usd_to_credits(operation_usd("model_profile_generate"))


def studio_carousel_shot_credit_cost() -> int:
    return usd_to_credits(operation_usd("carousel_shot"))


def studio_upscale_credit_cost() -> int:
    return usd_to_credits(operation_usd("upscale"))


def studio_inpaint_credit_cost() -> int:
    return usd_to_credits(operation_usd("inpaint"))


def studio_operations_pricing_public() -> dict[str, int]:
    return {
        "prompt_refine": studio_prompt_refine_credit_cost(),
        "model_profile_generate": studio_model_profile_generate_credit_cost(),
        "carousel_shot": studio_carousel_shot_credit_cost(),
        "upscale": studio_upscale_credit_cost(),
        "inpaint": studio_inpaint_credit_cost(),
    }
