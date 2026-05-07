from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from app.db.models import UserStudioModelImage

STUDIO_MODEL_IMAGE_KINDS = frozenset({"face", "body", "genitals", "other"})

_KIND_ORDER = {"face": 0, "body": 1, "genitals": 2, "other": 3}

_RU_LABEL = {
    "face": "лицо и идентичность",
    "body": "телосложение и тело целиком",
    "genitals": "интимная анатомия (референс для соответствующих зон)",
    "other": "общий референс модели",
}


def normalize_studio_image_kind(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if s not in STUDIO_MODEL_IMAGE_KINDS:
        return "other"
    return s


def assert_studio_image_kind(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if s not in STUDIO_MODEL_IMAGE_KINDS:
        raise HTTPException(
            status_code=400,
            detail="kind: ожидается одно из: face, body, genitals, other",
        )
    return s


def parse_image_kinds_json(form_value: str | None, n_files: int) -> list[str]:
    if n_files <= 0:
        return []
    if not form_value or not str(form_value).strip():
        return ["other"] * n_files
    try:
        arr = json.loads(str(form_value).strip())
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"image_kinds: невалидный JSON ({e})",
        ) from e
    if not isinstance(arr, list):
        raise HTTPException(status_code=400, detail="image_kinds: нужен JSON-массив")
    out: list[str] = []
    for i in range(n_files):
        if i < len(arr):
            out.append(normalize_studio_image_kind(arr[i]))
        else:
            out.append("other")
    return out


def sort_model_images_for_studio(imgs: list[UserStudioModelImage]) -> list[UserStudioModelImage]:
    def key(im: UserStudioModelImage) -> tuple[int, int]:
        k = (im.image_kind or "other").lower()
        ord_ = _KIND_ORDER.get(k, 3)
        return ord_, im.id

    return sorted(imgs, key=key)


def parse_image_export_selfies_json(
    form_value: str | None, n_files: int, kinds_list: list[str]
) -> list[bool]:
    """Параллель массиву файлов: селфи для EXIF по каждому кадру; по умолчанию True только для kind=face."""

    def default_selfie(i: int) -> bool:
        k = (kinds_list[i] if i < len(kinds_list) else "other").lower()
        return k == "face"

    if n_files <= 0:
        return []
    if not form_value or not str(form_value).strip():
        return [default_selfie(i) for i in range(n_files)]
    try:
        arr = json.loads(str(form_value).strip())
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"image_export_selfies: невалидный JSON ({e})",
        ) from e
    if not isinstance(arr, list):
        raise HTTPException(status_code=400, detail="image_export_selfies: нужен JSON-массив")
    out: list[bool] = []
    for i in range(n_files):
        if i < len(arr):
            out.append(bool(arr[i]))
        else:
            out.append(default_selfie(i))
    return out


def export_selfie_flag_for_phone_exif(imgs: list[UserStudioModelImage]) -> bool:
    """Какой флаг «передняя камера» подставить в итоговый JPEG: сначала кадр с kind=face, иначе первый в студийном порядке."""
    ordered = sort_model_images_for_studio(imgs)
    for im in ordered:
        if (im.image_kind or "").lower() == "face":
            return bool(getattr(im, "export_selfie", False))
    if ordered:
        return bool(getattr(ordered[0], "export_selfie", False))
    return False


def model_reference_photos_block(imgs_sorted: list[UserStudioModelImage]) -> str:
    if not imgs_sorted:
        return ""
    lines: list[str] = [
        "## MODEL_REFERENCE_PHOTOS (сохранённые снимки модели — порядок: лицо → тело → интимные референсы → прочие)",
        "Эти кадры передаются в image-edit в **этом порядке**. Референс пользователя (если есть) задаёт позу, ракурс, окружение и одежду; **лицо, фигура и зоны, отмеченные ниже,** согласуй с этими снимками и MODEL_PROFILE, а не с телом/лицом человека на пользовательском рефе.",
    ]
    for im in imgs_sorted:
        k = (im.image_kind or "other").lower()
        lab = _RU_LABEL.get(k, _RU_LABEL["other"])
        cam = "селфи" if bool(getattr(im, "export_selfie", False)) else "основная камера"
        lines.append(f"- Снимок id={im.id}: **{lab}** (для EXIF-экспорта: {cam}).")
    return "\n".join(lines)
