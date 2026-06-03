"""Промпты и константы для вкладки «База модели» (face merge + развёртка)."""

from __future__ import annotations

DEFAULT_FACE_MERGE_PROMPT = (
    "Integrate a face into an existing scene. Substitute the face in the reference image "
    "with the face from the donor image. The objective is a seamless merge: the new face must "
    "inherit the exact expression, pose, and lighting interaction from the reference, while its "
    "color attributes (hair and eyes) are adapted from the donor for a perfectly harmonious and "
    "natural result."
)

DEFAULT_MODEL_SHEET_PROMPT = (
    "Сделай на нейтральном сером фоне раскладку персонажа с картинки, треть раскладки слева — "
    "крупный план лица, остальное — крупные планы вид справа, вид слева, вид сзади. "
    "В полный рост спереди и в полный рост сзади. "
    "Одежда - черный топ с глубоким декольте черные спортивные шорты из облегающего материала"
)

MODEL_SHEET_ASPECT_KEY = "16:9"


def resolve_face_merge_prompt(user_prompt: str | None) -> str:
    p = (user_prompt or "").strip()
    return p if p else DEFAULT_FACE_MERGE_PROMPT
