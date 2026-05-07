from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR

log = logging.getLogger(__name__)

_PRESETS_REL = Path("data") / "studio_camera_presets.json"

# Запасной каталог (если JSON на диске недоступен —(volume, первый запуск до копирования и т.д.))
_BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "id": "iphone_16_pro",
        "label": "Apple iPhone 16 Pro",
        "make": "Apple",
        "model": "iPhone 16 Pro",
        "lens_selfie": "iPhone 16 Pro front camera 4.23mm f/1.9",
        "lens_main": "iPhone 16 Pro back triple camera 6.765mm f/1.78",
        "focal_35_selfie": 23,
        "focal_35_main": 24,
        "grain_sigma": 3.8,
    },
    {
        "id": "iphone_15_pro",
        "label": "Apple iPhone 15 Pro",
        "make": "Apple",
        "model": "iPhone 15 Pro",
        "lens_selfie": "iPhone 15 Pro front camera 3.99mm f/1.9",
        "lens_main": "iPhone 15 Pro back triple camera 6.765mm f/1.78",
        "focal_35_selfie": 23,
        "focal_35_main": 24,
        "grain_sigma": 3.8,
    },
    {
        "id": "iphone_14",
        "label": "Apple iPhone 14",
        "make": "Apple",
        "model": "iPhone 14",
        "lens_selfie": "iPhone 14 front camera 3.99mm f/1.9",
        "lens_main": "iPhone 14 back dual wide camera 5.7mm f/1.5",
        "focal_35_selfie": 23,
        "focal_35_main": 26,
        "grain_sigma": 3.6,
    },
    {
        "id": "samsung_s24_ultra",
        "label": "Samsung Galaxy S24 Ultra",
        "make": "samsung",
        "model": "SM-S928B",
        "lens_selfie": "Samsung Galaxy S24 Ultra Selfie Camera",
        "lens_main": "Samsung Galaxy S24 Ultra Main Rear Camera",
        "focal_35_selfie": 25,
        "focal_35_main": 24,
        "grain_sigma": 3.5,
    },
    {
        "id": "samsung_a55",
        "label": "Samsung Galaxy A55",
        "make": "samsung",
        "model": "SM-A556B",
        "lens_selfie": "Samsung Galaxy A55 Front Camera",
        "lens_main": "Samsung Galaxy A55 Wide Camera",
        "focal_35_selfie": 24,
        "focal_35_main": 25,
        "grain_sigma": 3.9,
    },
    {
        "id": "pixel_9_pro",
        "label": "Google Pixel 9 Pro",
        "make": "Google",
        "model": "Pixel 9 Pro",
        "lens_selfie": "Pixel 9 Pro front camera 3.59mm f/2.2",
        "lens_main": "Pixel 9 Pro rear wide 6.9mm f/1.68",
        "focal_35_selfie": 21,
        "focal_35_main": 24,
        "grain_sigma": 3.4,
    },
    {
        "id": "pixel_8_pro",
        "label": "Google Pixel 8 Pro",
        "make": "Google",
        "model": "Pixel 8 Pro",
        "lens_selfie": "Pixel 8 Pro front camera 2.74mm f/2.2",
        "lens_main": "Pixel 8 Pro rear camera 6.81mm f/1.68",
        "focal_35_selfie": 20,
        "focal_35_main": 24,
        "grain_sigma": 3.4,
    },
    {
        "id": "xiaomi_14",
        "label": "Xiaomi 14",
        "make": "Xiaomi",
        "model": "23043RP34G",
        "lens_selfie": "Xiaomi 14 Front Camera",
        "lens_main": "Xiaomi 14 Main Camera",
        "focal_35_selfie": 24,
        "focal_35_main": 23,
        "grain_sigma": 3.7,
    },
    {
        "id": "oneplus_12",
        "label": "OnePlus 12",
        "make": "OnePlus",
        "model": "CPH2573",
        "lens_selfie": "OnePlus 12 Front Camera",
        "lens_main": "OnePlus 12 Main Camera",
        "focal_35_selfie": 22,
        "focal_35_main": 23,
        "grain_sigma": 3.6,
    },
    {
        "id": "nothing_phone_2",
        "label": "Nothing Phone (2)",
        "make": "Nothing",
        "model": "A065",
        "lens_selfie": "Nothing Phone 2 Front Camera",
        "lens_main": "Nothing Phone 2 Main Camera",
        "focal_35_selfie": 21,
        "focal_35_main": 24,
        "grain_sigma": 3.9,
    },
    {
        "id": "honor_magic6_pro",
        "label": "HONOR Magic6 Pro",
        "make": "HONOR",
        "model": "BVL-AN16",
        "lens_selfie": "HONOR Magic6 Pro Front Camera",
        "lens_main": "HONOR Magic6 Pro Rear Main",
        "focal_35_selfie": 23,
        "focal_35_main": 24,
        "grain_sigma": 3.5,
    },
    {
        "id": "redmi_note_13_pro",
        "label": "Redmi Note 13 Pro",
        "make": "Redmi",
        "model": "2312DRA50G",
        "lens_selfie": "Redmi Note 13 Pro Front Camera",
        "lens_main": "Redmi Note 13 Pro Main Camera",
        "focal_35_selfie": 21,
        "focal_35_main": 24,
        "grain_sigma": 4.0,
    },
    {
        "id": "huawei_p60_pro",
        "label": "HUAWEI P60 Pro",
        "make": "HUAWEI",
        "model": "MNA-LX9",
        "lens_selfie": "HUAWEI P60 Pro Front Camera",
        "lens_main": "HUAWEI P60 Pro Ultra Lighting Camera",
        "focal_35_selfie": 23,
        "focal_35_main": 24,
        "grain_sigma": 3.5,
    },
    {
        "id": "motorola_edge_50_pro",
        "label": "Motorola Edge 50 Pro",
        "make": "motorola",
        "model": "XT2403-1",
        "lens_selfie": "Motorola Edge 50 Pro Front Camera",
        "lens_main": "Motorola Edge 50 Pro Main Camera",
        "focal_35_selfie": 22,
        "focal_35_main": 24,
        "grain_sigma": 3.7,
    },
]


def _preset_paths() -> list[Path]:
    """Возможные расположения JSON (корень backend + относительно этого модуля)."""
    backend_via_config = (BACKEND_DIR / _PRESETS_REL).resolve()
    # app/services -> parents[2] == backend
    backend_via_file = (Path(__file__).resolve().parents[2] / _PRESETS_REL).resolve()
    out: list[Path] = []
    for p in (backend_via_config, backend_via_file):
        if p not in out:
            out.append(p)
    return out


def _raw_presets() -> dict[str, Any]:
    """Без lru_cache: не кэшируем пустой ответ, если файл позже появился."""
    for path in _preset_paths():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except json.JSONDecodeError as e:
            log.warning("camera presets JSON invalid (%s): %s", path, e)
            continue
        presets = raw.get("presets") if isinstance(raw, dict) else None
        if isinstance(presets, list) and len(presets) > 0:
            return raw
    log.warning(
        "camera presets file missing or empty; using built-in list (paths tried: %s)",
        ", ".join(str(p) for p in _preset_paths()),
    )
    return {"presets": list(_BUILTIN_PRESETS)}


def list_camera_presets() -> list[dict[str, Any]]:
    items = _raw_presets().get("presets") or []
    out: list[dict[str, Any]] = []
    for p in items:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "").strip()
        label = str(p.get("label") or pid or "").strip()
        if pid:
            out.append({"id": pid, "label": label})
    return out


def get_camera_preset_by_id(preset_id: str) -> dict[str, Any] | None:
    key = (preset_id or "").strip()
    if not key:
        return None
    for p in _raw_presets().get("presets") or []:
        if isinstance(p, dict) and str(p.get("id") or "").strip() == key:
            return p
    return None
