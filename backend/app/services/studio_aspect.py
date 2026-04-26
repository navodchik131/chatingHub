from __future__ import annotations

# Ключ → (width, height) в пределах 512–8192 (WaveSpeed Seedream).
ASPECT_PRESETS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1024, 1024),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
    "4:5": (1024, 1280),
    "21:9": (2560, 1097),
}

DEFAULT_ASPECT_KEY = "9:16"

# Порядок в выпадающем списке UI
_ASPECT_ORDER: tuple[str, ...] = (
    "9:16",
    "16:9",
    "1:1",
    "4:3",
    "3:4",
    "4:5",
    "21:9",
)


def normalize_aspect_key(raw: str | None) -> str:
    if raw is None or not str(raw).strip():
        return DEFAULT_ASPECT_KEY
    key = str(raw).strip()
    if key in ASPECT_PRESETS:
        return key
    allowed = ", ".join(sorted(ASPECT_PRESETS.keys()))
    raise ValueError(f"Недопустимый формат кадра «{key}». Доступно: {allowed}")


def wavespeed_size_string(aspect_key: str) -> str:
    """Строка размера для API WaveSpeed (ширина x высота)."""
    k = normalize_aspect_key(aspect_key)
    w, h = ASPECT_PRESETS[k]
    return f"{w}x{h}"


def aspect_instruction_for_prompt(aspect_key: str) -> str:
    """Блок в пользовательское сообщение OpenAI (шаг 2)."""
    k = normalize_aspect_key(aspect_key)
    w, h = ASPECT_PRESETS[k]
    orient = "вертикальный портрет" if h > w else "горизонтальный" if w > h else "квадрат"
    return (
        f"Целевой формат итогового изображения: соотношение сторон {k} ({w}×{h} px), кадр {orient}. "
        f"В JSON обязательно согласуй photography.aspect_ratio, shot_type, camera_style и связанные поля "
        f"с этим форматом (вертикаль / горизонталь / квадрат)."
    )


def aspect_presets_public() -> list[dict[str, str]]:
    """Для GET /api/studio/output-aspects — одна точка правды для UI."""
    labels = {
        "9:16": "9:16 — вертикаль (сторис, Reels)",
        "16:9": "16:9 — горизонталь (YouTube, широкий)",
        "1:1": "1:1 — квадрат",
        "4:3": "4:3 — классический горизонталь",
        "3:4": "3:4 — вертикальный портрет",
        "4:5": "4:5 — портрет (лента)",
        "21:9": "21:9 — киноширокий",
    }
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for key in _ASPECT_ORDER:
        if key not in ASPECT_PRESETS:
            continue
        seen.add(key)
        w, h = ASPECT_PRESETS[key]
        out.append({"key": key, "label": labels.get(key, key), "size": f"{w}x{h}"})
    for key in sorted(ASPECT_PRESETS.keys()):
        if key in seen:
            continue
        w, h = ASPECT_PRESETS[key]
        out.append({"key": key, "label": labels.get(key, key), "size": f"{w}x{h}"})
    return out
