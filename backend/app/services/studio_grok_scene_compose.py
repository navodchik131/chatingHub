"""
Grok vision: собрать сцену с пользовательского рефа + листов модели + JSON профиля
в один текстовый промпт для WaveSpeed (без пачки identity-URL в API).
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.config import BACKEND_DIR, settings
from app.db.models import UserStudioModelImage
from app.services.studio_grok_motion import (
    _grok_fps_stills_model,
    grok_motion_api_configured,
    grok_motion_studio_credentials,
)
from app.services.studio_model_images import (
    select_prompt_only_wavespeed_identity_images,
    sort_model_images_for_studio,
)
from app.services.studio_openai import (
    StudioOpenAiCredentials,
    _strip_code_fences,
    chat_completion_openai_compatible_text,
)

log = logging.getLogger(__name__)

_GROK_SCENE_LABELS: dict[str, str] = {
    "turnaround": "CHARACTER_SHEET_CLOTHED",
    "face": "FACE_IDENTITY",
    "body": "BODY_REFERENCE",
    "genitals": "ANATOMY_REFERENCE_NUDE",
    "other": "MODEL_REFERENCE_OTHER",
}

_TIMELINE_SYSTEM_EN = (
    "You follow instructions precisely. Reply only in the requested JSON schema. "
    "No preamble, no markdown code fences."
)


@dataclass(frozen=True)
class GrokSceneComposeResult:
    wavespeed_scene_prompt: str
    reference_scene_lock: str
    negative_prompt: str


def grok_scene_compose_configured() -> bool:
    return grok_motion_api_configured()


def _grok_prompt_file_candidates(configured_rel: str, default_filename: str) -> list[Path]:
    """Том Docker часто перекрывает data/prompts — всегда пробуем _bundled_prompts из образа."""
    rel = (configured_rel or "").strip()
    name = default_filename
    if rel:
        p = (BACKEND_DIR / rel).resolve()
        name = p.name
    ordered = [
        (BACKEND_DIR / rel).resolve() if rel else None,
        (BACKEND_DIR / "data" / "prompts" / name).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / name).resolve(),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for item in ordered:
        if item is None:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def load_grok_scene_compose_text_system() -> str:
    configured = (settings.grok_scene_compose_text_system_path or "").strip()
    candidates = _grok_prompt_file_candidates(
        configured, "grok_scene_compose_text_system.txt"
    )
    for path in candidates:
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t:
                return t
    inline = (settings.grok_scene_compose_text_system_inline or "").strip()
    if inline:
        return inline
    raise RuntimeError(
        "Промпт Grok text-only compose пуст: добавьте grok_scene_compose_text_system.txt "
        "или GROK_SCENE_COMPOSE_TEXT_SYSTEM_INLINE"
    )


def load_grok_scene_compose_system() -> str:
    """data/prompts (том Docker) → _bundled_prompts (в образе) → GROK_SCENE_COMPOSE_SYSTEM_INLINE."""
    configured = (settings.grok_scene_compose_system_path or "").strip()
    candidates = _grok_prompt_file_candidates(
        configured, "grok_scene_compose_system.txt"
    )
    for path in candidates:
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t:
                return t
    inline = (settings.grok_scene_compose_system_inline or "").strip()
    if inline:
        return inline
    raise RuntimeError(
        "Промпт Grok scene compose пуст: добавьте grok_scene_compose_system.txt в образ "
        "(пересборка api), скопируйте в /app/backend/data/prompts на томе или задайте "
        "GROK_SCENE_COMPOSE_SYSTEM_INLINE"
    )


def _read_model_image_file(im: UserStudioModelImage) -> tuple[bytes, str]:
    path = (BACKEND_DIR / im.relative_path).resolve()
    if not path.is_file():
        raise RuntimeError(f"Файл снимка модели не найден: {im.relative_path}")
    raw = path.read_bytes()
    if not raw:
        raise RuntimeError(f"Пустой файл снимка модели id={im.id}")
    ext = path.suffix.lower()
    mime = "image/jpeg"
    if ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    elif ext == ".gif":
        mime = "image/gif"
    return raw, mime


def collect_model_images_for_grok_compose(
    imgs: list[UserStudioModelImage],
    *,
    wave_profile: str,
) -> list[tuple[str, UserStudioModelImage]]:
    """
    Порядок для Grok: clothed sheet → nude anatomy (NSFW) → face → body.
    Без дубликатов по id.
    """
    wp = (wave_profile or "nsfw").strip().lower()
    sorted_imgs = sort_model_images_for_studio(imgs)
    by_kind: dict[str, UserStudioModelImage] = {}
    for im in sorted_imgs:
        k = (im.image_kind or "other").lower()
        if k not in by_kind:
            by_kind[k] = im

    order: list[str] = ["turnaround", "genitals", "face", "body"]
    if wp == "regular":
        order = ["turnaround", "face", "body"]

    out: list[tuple[str, UserStudioModelImage]] = []
    seen: set[int] = set()
    for kind in order:
        if kind == "genitals" and wp != "nsfw":
            continue
        im = by_kind.get(kind)
        if im is None or im.id in seen:
            continue
        label = _GROK_SCENE_LABELS.get(kind, "MODEL_REFERENCE")
        out.append((label, im))
        seen.add(im.id)
    return out


def collect_model_images_for_grok_text_compose(
    imgs: list[UserStudioModelImage],
    *,
    wave_profile: str,
) -> list[tuple[str, UserStudioModelImage]]:
    """Grok «По промту»: только body + genitals (NSFW) для vision при сборке брифа."""
    picked = select_prompt_only_wavespeed_identity_images(imgs, wave_profile=wave_profile)
    out: list[tuple[str, UserStudioModelImage]] = []
    for im in picked:
        k = (im.image_kind or "other").lower()
        label = _GROK_SCENE_LABELS.get(k, "MODEL_REFERENCE")
        out.append((label, im))
    return out


def _parse_grok_compose_json(raw: str) -> GrokSceneComposeResult:
    t = _strip_code_fences(raw)
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Grok вернул не JSON: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError("Ответ Grok должен быть JSON-объектом")
    prompt = str(data.get("wavespeed_scene_prompt") or data.get("scene_prompt") or "").strip()
    if not prompt:
        prompt = str(data.get("prompt") or "").strip()
    lock = str(data.get("reference_scene_lock") or data.get("scene_lock") or "").strip()
    neg = str(data.get("negative_prompt") or data.get("negative") or "").strip()
    if not prompt:
        raise RuntimeError("Grok JSON без wavespeed_scene_prompt")
    return GrokSceneComposeResult(
        wavespeed_scene_prompt=prompt,
        reference_scene_lock=lock,
        negative_prompt=neg,
    )


def _grok_scene_compose_model() -> str:
    m = (settings.grok_scene_compose_model or "").strip()
    return m if m else _grok_fps_stills_model()


async def grok_compose_studio_scene(
    *,
    user_ref_bytes: bytes,
    user_ref_mime: str | None,
    model_images: list[UserStudioModelImage],
    model_profile_text: str | None,
    wave_profile: str,
    user_notes: str,
    lock_hairstyle: bool,
    credentials: StudioOpenAiCredentials | None = None,
) -> GrokSceneComposeResult:
    creds = credentials or grok_motion_studio_credentials()
    labeled = collect_model_images_for_grok_compose(model_images, wave_profile=wave_profile)
    if not labeled:
        raise RuntimeError(
            "Для режима «Grok: сцена» у модели нужны снимки: развёртка (turnaround) "
            "или лицо/тело. Добавьте их в кабинете модели."
        )

    system = load_grok_scene_compose_system()
    wp = (wave_profile or "nsfw").strip().lower()
    profile = (model_profile_text or "").strip() or "{}"
    notes = (user_notes or "").strip()
    hair_rule = (
        "Hairstyle follows MODEL_PROFILE_JSON, not USER_SCENE_REFERENCE."
        if lock_hairstyle
        else "Hairstyle may follow USER_SCENE_REFERENCE when USER_NOTES request it."
    )

    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"WAVE_PROFILE: {wp}\n"
                f"HAIRSTYLE_RULE: {hair_rule}\n\n"
                "BODY_FIGURE_RULE: USER_SCENE_REFERENCE supplies pose/camera/light/wardrobe coverage ONLY. "
                "Bust, waist, hip width, glute volume, torso/leg proportions MUST come from MODEL_PROFILE_JSON "
                "+ BODY_REFERENCE / ANATOMY_REFERENCE_NUDE / CHARACTER_SHEET — never from the pose-reference sitter. "
                "State figure proportions explicitly in wavespeed_scene_prompt.\n\n"
                f"MODEL_PROFILE_JSON:\n{profile}\n\n"
                f"USER_NOTES:\n{notes or '(none)'}\n\n"
                "Attached images follow. Labels in captions are authoritative."
            ),
        },
    ]

    for label, im in labeled:
        raw, mime = _read_model_image_file(im)
        b64 = base64.standard_b64encode(raw).decode("ascii")
        user_parts.append(
            {"type": "text", "text": f"[{label}] studio_model_image id={im.id}"}
        )
        user_parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        )

    ref_mime = (user_ref_mime or "image/jpeg").split(";")[0].strip()
    if ref_mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        ref_mime = "image/jpeg"
    ref_b64 = base64.standard_b64encode(user_ref_bytes).decode("ascii")
    user_parts.append(
        {
            "type": "text",
            "text": (
                "[USER_SCENE_REFERENCE] Pose, camera, framing, lighting, background, "
                "wardrobe coverage — NOT identity."
            ),
        }
    )
    user_parts.append(
        {
            "type": "image_url",
            "image_url": {"url": f"data:{ref_mime};base64,{ref_b64}"},
        }
    )

    model = _grok_scene_compose_model()
    raw_out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": system + "\n\n" + _TIMELINE_SYSTEM_EN},
            {"role": "user", "content": user_parts},
        ],
        max_tokens=int(settings.grok_scene_compose_max_tokens),
        temperature=float(settings.grok_scene_compose_temperature),
        credentials=creds,
        timeout_seconds=float(settings.grok_scene_compose_timeout_seconds),
    )
    try:
        return _parse_grok_compose_json(raw_out)
    except RuntimeError:
        log.warning("grok scene compose: JSON parse failed, using raw prose fallback")
        prose = _strip_code_fences(raw_out).strip()
        if len(prose) < 80:
            raise RuntimeError("Grok вернул слишком короткий ответ без JSON")
        return GrokSceneComposeResult(
            wavespeed_scene_prompt=prose,
            reference_scene_lock="",
            negative_prompt="",
        )


async def grok_compose_studio_text_scene(
    *,
    model_images: list[UserStudioModelImage],
    model_profile_text: str | None,
    wave_profile: str,
    user_notes: str,
    credentials: StudioOpenAiCredentials | None = None,
) -> GrokSceneComposeResult:
    """«По промту»: сцена из USER_NOTES + профиль + body/genitals refs, без фото сцены пользователя."""
    creds = credentials or grok_motion_studio_credentials()
    labeled = collect_model_images_for_grok_text_compose(model_images, wave_profile=wave_profile)
    if not labeled:
        raise RuntimeError(
            "Для режима «По промту» у модели нужен снимок «Тело целиком» (body). "
            "Для NSFW добавьте «Интимная анатомия» (genitals) при необходимости."
        )

    system = load_grok_scene_compose_text_system()
    wp = (wave_profile or "nsfw").strip().lower()
    profile = (model_profile_text or "").strip() or "{}"
    notes = (user_notes or "").strip()
    if not notes:
        raise RuntimeError("Для режима «По промту» заполните промпт — опишите сцену.")

    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"WAVE_PROFILE: {wp}\n"
                "MODE: TEXT_SCENE_ONLY — no user pose reference image. "
                "Compose pose, camera, framing, lighting, background, and wardrobe/nudity from USER_NOTES.\n\n"
                "BODY_FIGURE_RULE: Bust, waist, hip width, glute volume, torso/leg proportions MUST come from "
                "MODEL_PROFILE_JSON + BODY_REFERENCE / ANATOMY_REFERENCE_NUDE. "
                "State figure proportions explicitly in wavespeed_scene_prompt.\n\n"
                f"MODEL_PROFILE_JSON:\n{profile}\n\n"
                f"USER_NOTES:\n{notes}\n\n"
                "Attached images are identity references only (not scene). Labels in captions are authoritative."
            ),
        },
    ]

    for label, im in labeled:
        raw, mime = _read_model_image_file(im)
        b64 = base64.standard_b64encode(raw).decode("ascii")
        user_parts.append(
            {"type": "text", "text": f"[{label}] studio_model_image id={im.id}"}
        )
        user_parts.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        )

    model = _grok_scene_compose_model()
    raw_out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {"role": "system", "content": system + "\n\n" + _TIMELINE_SYSTEM_EN},
            {"role": "user", "content": user_parts},
        ],
        max_tokens=int(settings.grok_scene_compose_max_tokens),
        temperature=float(settings.grok_scene_compose_temperature),
        credentials=creds,
        timeout_seconds=float(settings.grok_scene_compose_timeout_seconds),
    )
    try:
        return _parse_grok_compose_json(raw_out)
    except RuntimeError:
        log.warning("grok text scene compose: JSON parse failed, using raw prose fallback")
        prose = _strip_code_fences(raw_out).strip()
        if len(prose) < 80:
            raise RuntimeError("Grok вернул слишком короткий ответ без JSON")
        return GrokSceneComposeResult(
            wavespeed_scene_prompt=prose,
            reference_scene_lock="",
            negative_prompt="",
        )
