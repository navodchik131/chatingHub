from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from app.db.models import UserStudioModelImage

STUDIO_MODEL_IMAGE_KINDS = frozenset({"face", "body", "genitals", "turnaround", "other"})

_KIND_ORDER = {"turnaround": 0, "face": 1, "body": 2, "genitals": 3, "other": 4}

_RU_LABEL = {
    "turnaround": "развёртка / character sheet (лицо, ракурсы)",
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
            detail="kind: ожидается одно из: face, body, genitals, turnaround, other",
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


def sort_model_images_for_wan_identity(
    imgs: list[UserStudioModelImage],
) -> list[UserStudioModelImage]:
    """WAN: image 1 = pose; сразу после — body-референсы, затем face (силуэт важнее лица)."""
    _WAN_KIND_ORDER = {"body": 0, "face": 1, "genitals": 2, "other": 3}

    def key(im: UserStudioModelImage) -> tuple[int, int]:
        k = (im.image_kind or "other").lower()
        return _WAN_KIND_ORDER.get(k, 3), im.id

    return sorted(imgs, key=key)


def select_wan_identity_images_with_pose_ref(
    imgs: list[UserStudioModelImage],
    *,
    max_count: int = 3,
    pose_reference_nude: bool = False,
) -> list[UserStudioModelImage]:
    """
    При pose ref = image 1 не отправляем все фото модели (развёртка + face + body…),
    иначе WAN копирует нейтральный character sheet и одежду с листа.
    Если референс nude — только face (без body/turnaround в одежде).
    """
    if max_count <= 0:
        return []
    cap = max(1, min(5, int(max_count)))
    if pose_reference_nude:
        cap = min(cap, 2)
        by_kind: dict[str, list[UserStudioModelImage]] = {}
        for im in imgs:
            k = (im.image_kind or "other").lower()
            by_kind.setdefault(k, []).append(im)
        picked: list[UserStudioModelImage] = []
        for im in by_kind.get("face", []):
            if len(picked) >= cap:
                break
            picked.append(im)
        if not picked:
            for im in imgs[:cap]:
                if (im.image_kind or "").lower() != "genitals":
                    picked.append(im)
        return picked[:cap]

    by_kind: dict[str, list[UserStudioModelImage]] = {}
    for im in imgs:
        k = (im.image_kind or "other").lower()
        by_kind.setdefault(k, []).append(im)

    picked = []

    def take(kind: str) -> None:
        if len(picked) >= cap:
            return
        for im in by_kind.get(kind, []):
            if im not in picked:
                picked.append(im)
                return

    take("face")
    if len(picked) < cap:
        if by_kind.get("body"):
            take("body")
        else:
            take("turnaround")
    if len(picked) < cap and "turnaround" not in {
        (im.image_kind or "").lower() for im in picked
    }:
        take("turnaround")
    if len(picked) < cap:
        for kind in ("body", "other"):
            take(kind)
    return sort_model_images_for_wan_identity(picked)[:cap]


def select_model_scene_wavespeed_identity_images(
    imgs: list[UserStudioModelImage],
    *,
    wave_profile: str,
    max_count: int = 6,
) -> list[UserStudioModelImage]:
    """
    Режим «Модель + промпт»: только снимки модели (развёртка, тело, лицо, анатомия) — без референса сцены.
    """
    if not imgs:
        return []
    wp = (wave_profile or "nsfw").strip().lower()
    cap = max(1, min(8, int(max_count)))
    sorted_imgs = sort_model_images_for_studio(imgs)
    by_kind: dict[str, UserStudioModelImage] = {}
    for im in sorted_imgs:
        k = (im.image_kind or "other").lower()
        if k not in by_kind:
            by_kind[k] = im

    order: list[str] = ["turnaround", "body", "face", "genitals"]
    if wp == "regular":
        order = ["turnaround", "body", "face"]

    picked: list[UserStudioModelImage] = []
    seen: set[int] = set()
    for kind in order:
        if kind == "genitals" and wp != "nsfw":
            continue
        im = by_kind.get(kind)
        if im is None or im.id in seen:
            continue
        picked.append(im)
        seen.add(im.id)
    if not picked:
        for im in sorted_imgs[:cap]:
            if im.id not in seen:
                picked.append(im)
    return sort_model_images_for_wan_identity(picked)[:cap]


_WAVESPEED_KIND_LEGEND: dict[str, str] = {
    "turnaround": "character sheet — face, hair, clothed silhouette",
    "face": "face likeness and skin tone",
    "body": "body proportions and overall build",
    "genitals": "nude anatomy",
    "other": "model reference",
}


def wavespeed_identity_image_legend(imgs: list[UserStudioModelImage]) -> str:
    """Краткая подпись порядка identity-фото для prose-промпта WaveSpeed."""
    if not imgs:
        return ""
    parts: list[str] = []
    for i, im in enumerate(imgs, 1):
        k = (im.image_kind or "other").lower()
        desc = _WAVESPEED_KIND_LEGEND.get(k, "model reference")
        parts.append(f"Image {i}: {desc}")
    return "; ".join(parts)


def select_prompt_only_wavespeed_identity_images(
    imgs: list[UserStudioModelImage],
    *,
    wave_profile: str,
) -> list[UserStudioModelImage]:
    """
    Режим «По промту» (без референса сцены): body → face → genitals (NSFW).
    Без turnaround — студийный лист тянет нейтральный фон/свет вместо сцены из текста.
    """
    if not imgs:
        return []
    wp = (wave_profile or "nsfw").strip().lower()
    by_kind: dict[str, UserStudioModelImage] = {}
    for im in imgs:
        k = (im.image_kind or "other").lower()
        if k in ("body", "face", "genitals") and k not in by_kind:
            by_kind[k] = im

    picked: list[UserStudioModelImage] = []
    for kind in ("body", "face"):
        im = by_kind.get(kind)
        if im is not None:
            picked.append(im)
    if wp == "nsfw":
        gen = by_kind.get("genitals")
        if gen is not None and gen.id not in {x.id for x in picked}:
            picked.append(gen)
    return picked


def select_grok_compose_wavespeed_identity_images(
    imgs: list[UserStudioModelImage],
    *,
    pose_reference_nude: bool = False,
    max_count: int = 4,
) -> list[UserStudioModelImage]:
    """
    Режим «Grok: сцена» — identity URL после pose ref (WAN) или до pose (Nano reorder).

    Nude pose ref: только face + genitals — без body/turnaround (полный body ref + pose bitmap
    дают силуэт донора; face отдельно → «приклеенная голова»).

    Clothed pose ref: body + face, без turnaround (лист тянет студийный outfit/фон).
    """
    if not imgs:
        return []
    cap = max(1, min(5, int(max_count)))

    by_kind: dict[str, list[UserStudioModelImage]] = {}
    for im in imgs:
        k = (im.image_kind or "other").lower()
        by_kind.setdefault(k, []).append(im)

    picked: list[UserStudioModelImage] = []

    def take(kind: str) -> None:
        if len(picked) >= cap:
            return
        for im in by_kind.get(kind, []):
            if im not in picked:
                picked.append(im)
                return

    if pose_reference_nude:
        cap = min(cap, 3)
        take("face")
        take("genitals")
        if not picked:
            for im in imgs[:cap]:
                if (im.image_kind or "").lower() != "body":
                    picked.append(im)
        return picked[:cap]

    take("body")
    take("face")
    if len(picked) < cap:
        for kind in ("body", "face", "other"):
            take(kind)
    if not picked:
        return []
    return sort_model_images_for_wan_identity(picked)[:cap]


def model_images_for_wavespeed_profile(
    imgs_sorted: list[UserStudioModelImage],
    wave_profile: str,
) -> list[UserStudioModelImage]:
    """
    Режим regular (Nano Banana Pro / Google): интимные референсы не передаём в API — иначе часто
    блокировки, таймауты и ошибки политики; NSFW-ветка (WAN) оставляет все кадры.
    """
    p = (wave_profile or "nsfw").strip().lower()
    if p != "regular":
        return imgs_sorted
    return [im for im in imgs_sorted if (im.image_kind or "other").lower() != "genitals"]


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


def normalize_exif_camera(value: str | None) -> str:
    """Режим EXIF при сохранении кадра: selfie (фронталка) или main (основная камера)."""
    v = (value or "main").strip().lower()
    if v in ("selfie", "front", "frontal", "1", "true", "yes"):
        return "selfie"
    return "main"


def exif_camera_is_selfie(exif_camera: str | None) -> bool:
    return normalize_exif_camera(exif_camera) == "selfie"


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
        lines.append(f"- Снимок id={im.id}: **{lab}**.")
    return "\n".join(lines)
