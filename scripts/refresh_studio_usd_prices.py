#!/usr/bin/env python3
"""Обновить backend/data/studio_usd_prices.json (для cron раз в сутки).

Пример cron (06:05 MSK):
  5 6 * * * cd /opt/chatinghub/backend && python ../scripts/refresh_studio_usd_prices.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.studio_provider_pricing import _default_catalog, _PRICES_PATH  # noqa: E402


def main() -> int:
    catalog = _default_catalog()
    catalog["updated_at"] = datetime.now(timezone.utc).isoformat()
    catalog["source"] = "refresh_script"
    _PRICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PRICES_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {_PRICES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
