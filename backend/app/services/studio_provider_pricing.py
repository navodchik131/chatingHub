"""USD-прайс провайдеров студии: JSON + env, обновление раз в сутки."""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.config import BACKEND_DIR, settings

log = logging.getLogger(__name__)

MSK = ZoneInfo("Europe/Moscow")
_DAILY_REFRESH = time(6, 0)
_PRICES_PATH = BACKEND_DIR / "data" / "studio_usd_prices.json"

_cache: dict[str, Any] = {
    "data": {},
    "updated_at": None,
    "source": "defaults",
}


def _default_catalog() -> dict[str, Any]:
    return {
        "updated_at": None,
        "source": "config",
        "images": {
            "nano-banana-2": float(settings.studio_image_usd_nano_banana_2),
            "nano-banana-pro": float(settings.studio_image_usd_nano_banana_pro),
            "gpt-image-2": float(settings.studio_image_usd_gpt_image_2),
            "wan-2.7": float(settings.studio_image_usd_wan_2_7),
            "wan-2.7-pro": float(settings.studio_image_usd_wan_2_7_pro),
            "seedream-v5.0-pro": float(settings.studio_image_usd_seedream_v5_pro),
        },
        "grok_pipeline_usd": {
            "none": 0.0,
            "light": float(settings.studio_grok_pipeline_usd_light),
            "standard": float(settings.studio_grok_pipeline_usd_standard),
            "heavy": float(settings.studio_grok_pipeline_usd_heavy),
            "workflow": float(settings.studio_grok_pipeline_usd_workflow),
        },
        "operations_usd": {
            "prompt_refine": float(settings.studio_prompt_refine_usd),
            "model_profile_generate": float(settings.studio_model_profile_generate_usd),
            "carousel_shot": float(settings.studio_carousel_shot_usd),
            "upscale": float(settings.studio_upscale_usd),
            "inpaint": float(settings.studio_inpaint_usd),
        },
        "video": {
            "wavespeed": {
                "standard_with_ref_720p": float(settings.studio_motion_usd_per_sec_with_ref),
                "standard_no_ref_720p": float(settings.studio_motion_usd_per_sec_no_ref),
                "mini_with_ref_720p": float(settings.studio_motion_mini_usd_per_sec_with_ref),
                "mini_no_ref_720p": float(settings.studio_motion_mini_usd_per_sec_no_ref),
                "seedance_25_with_ref_720p": float(settings.studio_motion_seedance_25_usd_per_sec_with_ref),
                "seedance_25_no_ref_720p": float(settings.studio_motion_seedance_25_usd_per_sec_no_ref),
            },
            "evolink": {
                "standard_output_720p": float(settings.studio_evolink_20_usd_per_sec_output_720p),
                "standard_output_480p": float(settings.studio_evolink_20_usd_per_sec_output_480p),
                "standard_video_ref_720p": float(settings.studio_evolink_20_usd_per_sec_video_ref_720p),
                "standard_video_ref_480p": float(settings.studio_evolink_20_usd_per_sec_video_ref_480p),
                "seedance_25_output_720p": float(settings.studio_evolink_25_usd_per_sec_output_720p),
                "seedance_25_output_480p": float(settings.studio_evolink_25_usd_per_sec_output_480p),
                "seedance_25_video_ref_720p": float(settings.studio_evolink_25_usd_per_sec_video_ref_720p),
                "seedance_25_video_ref_480p": float(settings.studio_evolink_25_usd_per_sec_video_ref_480p),
                "standard_with_ref_720p": float(settings.studio_evolink_20_usd_per_sec_video_ref_720p),
                "standard_no_ref_720p": float(settings.studio_evolink_20_usd_per_sec_output_720p),
                "seedance_25_with_ref_720p": float(settings.studio_evolink_25_usd_per_sec_video_ref_720p),
                "seedance_25_no_ref_720p": float(settings.studio_evolink_25_usd_per_sec_output_720p),
            },
            "grok_imagine_i2v": {
                "usd_per_sec_480p": float(settings.studio_grok_imagine_i2v_usd_per_sec_480p),
                "usd_per_sec_720p": float(settings.studio_grok_imagine_i2v_usd_per_sec_720p),
                "usd_per_image": float(settings.studio_grok_imagine_i2v_usd_per_image),
            },
            "video_upscale_per_5s": {
                "720p": float(settings.studio_video_upscale_usd_per_5s_720p),
                "1080p": float(settings.studio_video_upscale_usd_per_5s_1080p),
                "2k": float(settings.studio_video_upscale_usd_per_5s_2k),
                "4k": float(settings.studio_video_upscale_usd_per_5s_4k),
            },
        },
    }


def _merge_dict(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_dict(out[k], v)
        else:
            out[k] = v
    return out


def _load_json_catalog() -> dict[str, Any] | None:
    if not _PRICES_PATH.is_file():
        return None
    try:
        raw = json.loads(_PRICES_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception as e:
        log.warning("studio_usd_prices.json read failed: %s", e)
    return None


def _latest_daily_slot(now: datetime) -> datetime:
    now_msk = now.astimezone(MSK)
    today = now_msk.date()
    yesterday = today - timedelta(days=1)
    candidates = [
        datetime.combine(today, _DAILY_REFRESH, tzinfo=MSK),
        datetime.combine(yesterday, _DAILY_REFRESH, tzinfo=MSK),
    ]
    past = [c for c in candidates if c <= now_msk]
    return max(past)


def _needs_daily_refresh(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    updated = _cache.get("updated_at")
    if updated is None or not isinstance(updated, datetime):
        return True
    return updated.astimezone(MSK) < _latest_daily_slot(now)


def refresh_provider_pricing(*, force: bool = False) -> dict[str, Any]:
    """Перечитать JSON и слить с дефолтами из config (раз в сутки или force)."""
    now = datetime.now(timezone.utc)
    if not force and not _needs_daily_refresh(now):
        data = _cache.get("data")
        return data if isinstance(data, dict) else _default_catalog()

    catalog = _default_catalog()
    file_data = _load_json_catalog()
    if file_data:
        catalog = _merge_dict(catalog, file_data)
        catalog["source"] = str(file_data.get("source") or "json")
        catalog["updated_at"] = file_data.get("updated_at")
    _cache["data"] = catalog
    _cache["updated_at"] = now
    _cache["source"] = catalog.get("source") or "config"
    return catalog


def provider_pricing_catalog() -> dict[str, Any]:
    data = _cache.get("data")
    if isinstance(data, dict) and data:
        return data
    refreshed = refresh_provider_pricing(force=True)
    if isinstance(refreshed, dict) and refreshed:
        return refreshed
    return _default_catalog()


def image_model_usd(model_id: str) -> float:
    cat = provider_pricing_catalog()
    images = cat.get("images") if isinstance(cat.get("images"), dict) else {}
    key = (model_id or "wan-2.7").strip().lower()
    val = images.get(key)
    if isinstance(val, (int, float)) and float(val) >= 0:
        return float(val)
    return float(settings.studio_image_usd_wan_2_7)


def grok_pipeline_usd(kind: str) -> float:
    cat = provider_pricing_catalog()
    block = cat.get("grok_pipeline_usd") if isinstance(cat.get("grok_pipeline_usd"), dict) else {}
    k = (kind or "standard").strip().lower()
    val = block.get(k, block.get("standard", 0))
    return max(0.0, float(val or 0))


def operation_usd(name: str) -> float:
    cat = provider_pricing_catalog()
    block = cat.get("operations_usd") if isinstance(cat.get("operations_usd"), dict) else {}
    val = block.get(name, 0)
    return max(0.0, float(val or 0))


def video_wavespeed_usd_per_sec_720p(*, variant: str, has_ref: bool) -> float:
    cat = provider_pricing_catalog()
    ws = (cat.get("video") or {}).get("wavespeed") if isinstance(cat.get("video"), dict) else {}
    ws = ws if isinstance(ws, dict) else {}
    v = (variant or "standard").strip().lower().replace("-", "_")
    if v in ("seedance_25", "seedance25", "2_5", "25"):
        key = "seedance_25_with_ref_720p" if has_ref else "seedance_25_no_ref_720p"
    elif v == "mini":
        key = "mini_with_ref_720p" if has_ref else "mini_no_ref_720p"
    else:
        key = "standard_with_ref_720p" if has_ref else "standard_no_ref_720p"
    val = ws.get(key)
    if isinstance(val, (int, float)) and float(val) >= 0:
        return float(val)
    return float(settings.studio_motion_usd_per_sec_with_ref if has_ref else settings.studio_motion_usd_per_sec_no_ref)


def video_evolink_usd_per_sec(
    *,
    variant: str,
    billing_kind: str = "output_seconds",
    resolution: str = "720p",
    has_ref: bool | None = None,
) -> float:
    """USD/s для EvoLink Seedance (официальный прайс evolink.ai/seedance-2-0)."""
    if has_ref is not None:
        billing_kind = "video_reference_seconds" if has_ref else "output_seconds"
    cat = provider_pricing_catalog()
    ev = (cat.get("video") or {}).get("evolink") if isinstance(cat.get("video"), dict) else {}
    ev = ev if isinstance(ev, dict) else {}
    v = (variant or "standard").strip().lower().replace("-", "_")
    is_25 = v in ("seedance_25", "seedance25", "2_5", "25")
    prefix = "seedance_25" if is_25 else "standard"
    res = (resolution or "720p").strip().lower()
    res_key = "480p" if res in ("480p", "480") else "720p"
    kind = "video_ref" if billing_kind == "video_reference_seconds" else "output"
    key = f"{prefix}_{kind}_{res_key}"
    val = ev.get(key)
    if isinstance(val, (int, float)) and float(val) >= 0:
        return float(val)
    if is_25:
        if billing_kind == "video_reference_seconds":
            return float(
                settings.studio_evolink_25_usd_per_sec_video_ref_480p
                if res_key == "480p"
                else settings.studio_evolink_25_usd_per_sec_video_ref_720p
            )
        return float(
            settings.studio_evolink_25_usd_per_sec_output_480p
            if res_key == "480p"
            else settings.studio_evolink_25_usd_per_sec_output_720p
        )
    if billing_kind == "video_reference_seconds":
        return float(
            settings.studio_evolink_20_usd_per_sec_video_ref_480p
            if res_key == "480p"
            else settings.studio_evolink_20_usd_per_sec_video_ref_720p
        )
    return float(
        settings.studio_evolink_20_usd_per_sec_output_480p
        if res_key == "480p"
        else settings.studio_evolink_20_usd_per_sec_output_720p
    )


def video_evolink_usd_per_sec_720p(*, variant: str, has_ref: bool) -> float:
    """Legacy: has_ref=True → video-reference tier."""
    return video_evolink_usd_per_sec(
        variant=variant,
        billing_kind="video_reference_seconds" if has_ref else "output_seconds",
        resolution="720p",
    )


def provider_pricing_public() -> dict[str, Any]:
    cat = provider_pricing_catalog()
    updated = _cache.get("updated_at")
    return {
        **cat,
        "cache_updated_at": updated.isoformat() if isinstance(updated, datetime) else None,
        "cache_source": _cache.get("source"),
        "prices_file": str(_PRICES_PATH),
    }
