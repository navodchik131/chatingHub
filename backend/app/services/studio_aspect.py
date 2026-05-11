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


def aspect_user_block_english(
    aspect_key: str, *, preserve_reference_framing: bool = False
) -> str:
    """Секция OUTPUT/ASPECT для LLM-рефайнера (шаблон JSON на английском)."""
    k = normalize_aspect_key(aspect_key)
    w, h = ASPECT_PRESETS[k]
    if h > w:
        orient = "portrait/vertical (typical 9:16 story/reel)"
    elif w > h:
        orient = "landscape/horizontal"
    else:
        orient = "square"
    head = (
        "## OUTPUT / ASPECT\n"
        f"Target aspect ratio: {k} (pixel size about {w}×{h}). Output canvas: {orient}. "
        f"Set photography.aspect_ratio to match this target."
    )
    if preserve_reference_framing:
        return head + (
            "\n\n**REFERENCE_IMAGE is present:** The aspect ratio is only the **output canvas**. "
            "You MUST preserve the reference photo's **camera geometry**: implied distance to the subject, camera height "
            "relative to the subject (above eyes / at eyes / chest / low, etc.), horizontal view (straight-on, 3/4, profile), "
            "vertical angle (high / level / low), any dutch tilt, lens/perspective (wide selfie stretch vs normal phone), "
            "and **framing** — what is included vs cropped at frame edges and how large the subject is in the frame. "
            "Do **not** change a close-up into a full-body shot (or the opposite) to fill the canvas; keep the same shot scale. "
            "If the canvas aspect differs from the reference, adjust background margins or minor crop, not the camera relationship. "
            "Fill photography.framing_crop, camera_distance, camera_height_vs_subject, angle, view_direction, lens_perspective, "
            "and shot_type consistently from REFERENCE_IMAGE. MODEL PROFILE supplies identity only."
        )
    return (
        head
        + " Set photography.shot_type, camera_style, angle, framing_crop, and related fields "
        + f"to match this {orient} output."
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


# Соотношения, поддерживаемые Seedance Video-Edit API (4:5 в пресетах студии — не в списке)
_SEEDANCE_VIDEO_EDIT_ASPECTS = frozenset({"16:9", "9:16", "4:3", "3:4", "1:1", "21:9"})


def aspect_ratio_for_seedance_video_edit(output_aspect_key: str | None) -> str | None:
    """Возвращает aspect_ratio для WaveSpeed или None — тогда API подстраивается под входное видео."""
    if output_aspect_key is None or not str(output_aspect_key).strip():
        return None
    raw = str(output_aspect_key).strip()
    if raw in _SEEDANCE_VIDEO_EDIT_ASPECTS:
        return raw
    try:
        k = normalize_aspect_key(raw)
    except ValueError:
        return None
    return k if k in _SEEDANCE_VIDEO_EDIT_ASPECTS else None


def aspect_ratio_for_seedance_i2v(output_aspect_key: str | None) -> str | None:
    """Те же допустимые строки, что у Seedance Image-to-Video (4:5 — пропуск, API адаптирует под кадр)."""
    return aspect_ratio_for_seedance_video_edit(output_aspect_key)
