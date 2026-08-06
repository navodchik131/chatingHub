"""Бюджет символов для Grok-prose и финального prompt WaveSpeed."""

from __future__ import annotations

from app.config import settings


# Оценка резерва под префиксы/суффиксы assemble_wavespeed_image_edit_prompt (без текста сцены).
_NANO_ASSEMBLY_RESERVE = 4200
_WAN_ASSEMBLY_RESERVE = 5200


def wavespeed_prompt_char_limit(*, wave_profile: str) -> int:
    wp = (wave_profile or "nsfw").strip().lower()
    if wp == "regular":
        return int(settings.wavespeed_nano_prompt_max_chars)
    # WAN / Seedream: жёсткого лимита в API нет — большой запас под полный prompt.
    return 32000


def grok_scene_prose_char_budget(
    *,
    wave_profile: str,
    include_realism_coda: bool = True,
) -> int:
    """
    Сколько символов Grok может занять в ---PROMPT--- / wavespeed_scene_prompt,
    чтобы после сборки (префиксы + identity + coda) уложиться в лимит WaveSpeed.
    """
    from app.services.studio_prompt_bundle import PHONE_CANDID_PHOTO_CODA

    total = wavespeed_prompt_char_limit(wave_profile=wave_profile)
    reserve = _NANO_ASSEMBLY_RESERVE if (wave_profile or "").strip().lower() == "regular" else _WAN_ASSEMBLY_RESERVE
    coda = (len(PHONE_CANDID_PHOTO_CODA) + 2) if include_realism_coda else 0
    configured = int(settings.grok_scene_compose_output_max_chars)
    available = total - reserve - coda
    return max(1200, min(configured, available))
