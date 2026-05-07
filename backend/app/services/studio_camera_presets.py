from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR

log = logging.getLogger(__name__)

_PRESETS_REL = Path("data") / "studio_camera_presets.json"


@lru_cache
def _raw_presets() -> dict[str, Any]:
    path = (BACKEND_DIR / _PRESETS_REL).resolve()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log.warning("camera presets file missing: %s", path)
        return {"presets": []}
    except json.JSONDecodeError as e:
        log.warning("camera presets JSON invalid: %s", e)
        return {"presets": []}


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
