"""Сериализация одного или нескольких файлов в stars_business_orders.media_relative_path."""

from __future__ import annotations

import json

_JSON_PREFIX = "json:"


def encode_media_paths(paths: list[str]) -> str:
    """Один путь — как раньше; альбом — json: [...]."""
    clean = [p.strip() for p in paths if (p or "").strip()]
    if not clean:
        raise ValueError("empty media paths")
    if len(clean) == 1:
        return clean[0]
    return _JSON_PREFIX + json.dumps(clean, ensure_ascii=False)


def decode_media_paths(stored: str) -> list[str]:
    raw = (stored or "").strip()
    if raw.startswith(_JSON_PREFIX):
        parsed = json.loads(raw[len(_JSON_PREFIX) :])
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("invalid album json")
        return [str(x) for x in parsed]
    return [raw]
