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
from app.services.studio_prompt_bundle import grok_figure_anchor_from_profile
from app.services.studio_openai import (
    StudioOpenAiCredentials,
    _strip_code_fences,
    chat_completion_openai_compatible_text,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.studio_reference_analysis import IdentityVisibility


def _finalize_grok_compose_result(
    result: GrokSceneComposeResult,
    visibility: "IdentityVisibility | None",
) -> GrokSceneComposeResult:
    from app.services.studio_reference_analysis import sanitize_wavespeed_prose_for_visibility

    prompt = sanitize_wavespeed_prose_for_visibility(
        result.wavespeed_scene_prompt, visibility
    )
    if prompt == result.wavespeed_scene_prompt:
        return result
    return GrokSceneComposeResult(
        wavespeed_scene_prompt=prompt,
        reference_scene_lock=result.reference_scene_lock,
        negative_prompt=result.negative_prompt,
    )


def _grok_visibility_user_block(
    *,
    visibility: "IdentityVisibility | None",
    reference_scene_description: str | None,
) -> str:
    from app.services.studio_reference_analysis import build_grok_visibility_context

    ctx = build_grok_visibility_context(
        visibility=visibility,
        reference_scene_description=reference_scene_description,
    )
    return f"\n\n{ctx}" if ctx.strip() else ""


def _model_images_for_grok_compose(
    model_images: list[UserStudioModelImage],
    *,
    wave_profile: str,
    visibility: "IdentityVisibility | None" = None,
) -> list[tuple[str, UserStudioModelImage]]:
    imgs = list(model_images)
    if visibility is not None and imgs:
        from app.services.studio_reference_analysis import filter_model_images_for_visibility

        imgs = filter_model_images_for_visibility(imgs, visibility)
    return collect_model_images_for_grok_compose(imgs, wave_profile=wave_profile)

log = logging.getLogger(__name__)

_GROK_SCENE_LABELS: dict[str, str] = {
    "turnaround": "CHARACTER_SHEET_CLOTHED",
    "face": "FACE_IDENTITY",
    "body": "BODY_REFERENCE",
    "genitals": "ANATOMY_REFERENCE_NUDE",
    "other": "MODEL_REFERENCE_OTHER",
}

_TIMELINE_SYSTEM_EN = (
    "Follow the output format exactly. No markdown fences, no preamble."
)

_MAIN_PROMPT_MARKER = "---PROMPT---"
_MAIN_NEGATIVE_MARKER = "---NEGATIVE---"
_MAIN_VISIBLE_MARKER = "---VISIBLE---"


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


def load_grok_scene_compose_main_system() -> str:
    configured = (settings.grok_scene_compose_main_system_path or "").strip()
    candidates = _grok_prompt_file_candidates(
        configured, "grok_scene_compose_main_system.txt"
    )
    for path in candidates:
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t:
                return t
    inline = (settings.grok_scene_compose_main_system_inline or "").strip()
    if inline:
        return inline
    raise RuntimeError(
        "Промпт Grok main scene compose пуст: добавьте grok_scene_compose_main_system.txt "
        "или GROK_SCENE_COMPOSE_MAIN_SYSTEM_INLINE"
    )


def load_grok_scene_compose_model_scene_system() -> str:
    configured = (settings.grok_scene_compose_model_scene_system_path or "").strip()
    candidates = _grok_prompt_file_candidates(
        configured, "grok_scene_compose_model_scene_system.txt"
    )
    for path in candidates:
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t:
                return t
    inline = (settings.grok_scene_compose_model_scene_system_inline or "").strip()
    if inline:
        return inline
    return load_grok_scene_compose_text_system()


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
    """Grok «По промту»: body + face + genitals (NSFW) для vision при сборке брифа."""
    picked = select_prompt_only_wavespeed_identity_images(imgs, wave_profile=wave_profile)
    out: list[tuple[str, UserStudioModelImage]] = []
    for im in picked:
        k = (im.image_kind or "other").lower()
        label = _GROK_SCENE_LABELS.get(k, "MODEL_REFERENCE")
        out.append((label, im))
    return out


def _parse_grok_main_prose_output(raw: str) -> GrokSceneComposeResult:
    t = _strip_code_fences(raw).strip()
    prompt = ""
    negative = ""
    visible = ""

    p_idx = t.find(_MAIN_PROMPT_MARKER)
    n_idx = t.find(_MAIN_NEGATIVE_MARKER)
    v_idx = t.find(_MAIN_VISIBLE_MARKER)

    if p_idx >= 0:
        p_start = p_idx + len(_MAIN_PROMPT_MARKER)
        ends = [x for x in (n_idx, v_idx) if x >= 0 and x > p_start]
        p_end = min(ends) if ends else len(t)
        prompt = t[p_start:p_end].strip()
    if n_idx >= 0:
        n_start = n_idx + len(_MAIN_NEGATIVE_MARKER)
        n_end = v_idx if v_idx > n_start else len(t)
        negative = t[n_start:n_end].strip()
    if v_idx >= 0:
        visible = t[v_idx + len(_MAIN_VISIBLE_MARKER) :].strip()

    if not prompt:
        prompt = t
    lim = int(settings.grok_scene_compose_output_max_chars)
    if len(prompt) > lim:
        prompt = prompt[: lim - 1].rstrip() + "…"
    if not prompt:
        raise RuntimeError("Grok main compose: пустой промпт")
    return GrokSceneComposeResult(
        wavespeed_scene_prompt=prompt,
        reference_scene_lock=visible[:400] if visible else "",
        negative_prompt=negative,
    )


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


async def grok_compose_studio_main_scene(
    *,
    user_ref_bytes: bytes,
    user_ref_mime: str | None,
    model_images: list[UserStudioModelImage],
    model_profile_text: str | None,
    wave_profile: str,
    user_notes: str,
    lock_hairstyle: bool,
    credentials: StudioOpenAiCredentials | None = None,
    visibility: "IdentityVisibility | None" = None,
    reference_scene_description: str | None = None,
) -> GrokSceneComposeResult:
    """
    Режим «Основная»: Grok → plain prose (без JSON), референс только для анализа сцены.
    WaveSpeed получает prose + фото модели, без реф-кадра пользователя.
    """
    creds = credentials or grok_motion_studio_credentials()
    labeled = _model_images_for_grok_compose(
        model_images, wave_profile=wave_profile, visibility=visibility
    )
    if not labeled:
        raise RuntimeError(
            "Для режима «Основная» у модели нужны снимки: развёртка (turnaround) "
            "и/или лицо/тело. Добавьте их в кабинете модели."
        )

    system = load_grok_scene_compose_main_system()
    wp = (wave_profile or "nsfw").strip().lower()
    profile = (model_profile_text or "").strip() or "{}"
    notes = (user_notes or "").strip()
    hair_rule = (
        "Hairstyle from MODEL photos and profile, not from USER_SCENE_REFERENCE."
        if lock_hairstyle
        else "Hairstyle may follow USER_SCENE_REFERENCE when USER_NOTES request it."
    )
    max_out = int(settings.grok_scene_compose_output_max_chars)
    vis_block = _grok_visibility_user_block(
        visibility=visibility,
        reference_scene_description=reference_scene_description,
    )

    figure_anchor = grok_figure_anchor_from_profile(model_profile_text, visibility=visibility)
    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"WAVE_PROFILE: {wp}\n"
                f"HAIRSTYLE: {hair_rule}\n"
                f"MAX_PROMPT_CHARS: {max_out}\n\n"
                "BODY_FIGURE_RULE: USER_SCENE_REFERENCE supplies pose/camera/light/wardrobe coverage ONLY. "
                "Face, hair color, skin tone, and body proportions in ---PROMPT--- must come from "
                "MODEL_PROFILE_JSON + attached model images — never the sitter on USER_SCENE_REFERENCE.\n\n"
                f"FIGURE_LOCK_ANCHOR (mandatory — weave into ---PROMPT---, do not paste as a label block):\n"
                f"{figure_anchor}\n\n"
                f"MODEL_PROFILE_JSON:\n{profile}\n\n"
                f"USER_NOTES:\n{notes or '(none)'}\n\n"
                "Attached model images are labeled. USER_SCENE_REFERENCE is last."
                f"{vis_block}"
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
                "[USER_SCENE_REFERENCE] Scene donor — pose, camera, light, environment, "
                "wardrobe coverage only. Do NOT copy sitter identity."
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
    return _finalize_grok_compose_result(_parse_grok_main_prose_output(raw_out), visibility)


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
    standalone_scene_prompt: bool = False,
    visibility: "IdentityVisibility | None" = None,
    reference_scene_description: str | None = None,
) -> GrokSceneComposeResult:
    creds = credentials or grok_motion_studio_credentials()
    labeled = _model_images_for_grok_compose(
        model_images, wave_profile=wave_profile, visibility=visibility
    )
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

    figure_anchor = grok_figure_anchor_from_profile(model_profile_text, visibility=visibility)
    output_rule = ""
    if standalone_scene_prompt:
        output_rule = (
            "\n\nPROMPT_OUTPUT_RULE (MODEL_SCENE / Основная): wavespeed_scene_prompt must be fully "
            "self-contained English prose. The image API will also receive USER_SCENE_REFERENCE as a "
            "pose/framing bitmap — your text must **agree** with it on geometry, crop, light, and wardrobe zones. "
            "Never write 'reference image', 'user photo', 'as in the reference', 'image 1', or similar meta phrases. "
            "Describe pose with **maximal geometric precision**: limb angles, hand/finger placement, weight on each leg, "
            "head yaw/pitch, gaze vs lens, camera height, distance, crop edges, background layout, light direction, "
            "wardrobe/nudity coverage, expression — distilled from USER_SCENE_REFERENCE + USER_NOTES. "
            "FIGURE_LOCK (bust/waist/hips/build) stays from MODEL only — never the sitter's body mass.\n"
        )
    vis_block = _grok_visibility_user_block(
        visibility=visibility,
        reference_scene_description=reference_scene_description,
    )
    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"WAVE_PROFILE: {wp}\n"
                f"HAIRSTYLE_RULE: {hair_rule}\n\n"
                "BODY_FIGURE_RULE: USER_SCENE_REFERENCE supplies pose/camera/light/wardrobe coverage ONLY. "
                "Apply MODEL proportions and skin tone ONLY on PROMPT_MENTION regions from REFERENCE_ANALYSIS — "
                "never on anatomy listed under PROMPT_OMIT. "
                "Open wavespeed_scene_prompt using the FIGURE_LOCK anchor below.\n\n"
                f"FIGURE_LOCK_ANCHOR (mandatory in prose):\n{figure_anchor}\n\n"
                f"MODEL_PROFILE_JSON:\n{profile}\n\n"
                f"USER_NOTES:\n{notes or '(none)'}"
                f"{output_rule}\n\n"
                "Attached images follow. Labels in captions are authoritative."
                f"{vis_block}"
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
        return _finalize_grok_compose_result(_parse_grok_compose_json(raw_out), visibility)
    except RuntimeError:
        log.warning("grok scene compose: JSON parse failed, using raw prose fallback")
        prose = _strip_code_fences(raw_out).strip()
        if len(prose) < 80:
            raise RuntimeError("Grok вернул слишком короткий ответ без JSON")
        return _finalize_grok_compose_result(
            GrokSceneComposeResult(
                wavespeed_scene_prompt=prose,
                reference_scene_lock="",
                negative_prompt="",
            ),
            visibility,
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


async def grok_compose_studio_model_scene(
    *,
    model_images: list[UserStudioModelImage],
    model_profile_text: str | None,
    wave_profile: str,
    user_notes: str,
    credentials: StudioOpenAiCredentials | None = None,
) -> GrokSceneComposeResult:
    """
    Режим «Модель + промпт»: сцена только из USER_NOTES, identity из листов модели (включая развёртку),
    без референса пользователя в Grok и WaveSpeed.
    """
    creds = credentials or grok_motion_studio_credentials()
    labeled = collect_model_images_for_grok_compose(model_images, wave_profile=wave_profile)
    if not labeled:
        raise RuntimeError(
            "Для режима «Модель + промпт» у модели нужны снимки: развёртка (turnaround) "
            "и/или лицо/тело. Добавьте их в кабинете модели."
        )

    system = load_grok_scene_compose_model_scene_system()
    wp = (wave_profile or "nsfw").strip().lower()
    profile = (model_profile_text or "").strip() or "{}"
    notes = (user_notes or "").strip()
    if not notes:
        raise RuntimeError(
            "Опишите сцену в промпте: место, поза, одежда, свет — референс-фото в этом режиме не используется."
        )

    figure_anchor = grok_figure_anchor_from_profile(model_profile_text)
    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"WAVE_PROFILE: {wp}\n"
                "MODE: MODEL_SCENE_ONLY — no user pose/scene reference image. "
                "Compose pose, camera, framing, lighting, background, and wardrobe/nudity from USER_NOTES only.\n\n"
                "BODY_FIGURE_RULE: Bust, waist, hip width, glute volume, torso/leg proportions MUST come from "
                "MODEL_PROFILE_JSON + CHARACTER_SHEET_CLOTHED + BODY_REFERENCE / ANATOMY_REFERENCE_NUDE. "
                "State figure proportions and distinctive traits explicitly in wavespeed_scene_prompt.\n\n"
                f"FIGURE_LOCK_ANCHOR (mandatory in prose):\n{figure_anchor}\n\n"
                f"MODEL_PROFILE_JSON:\n{profile}\n\n"
                f"USER_NOTES:\n{notes}\n\n"
                "Attached images are model identity references only (not a scene donor). "
                "Labels in captions are authoritative."
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
        log.warning("grok model_scene compose: JSON parse failed, using raw prose fallback")
        prose = _strip_code_fences(raw_out).strip()
        if len(prose) < 80:
            raise RuntimeError("Grok вернул слишком короткий ответ без JSON")
        return GrokSceneComposeResult(
            wavespeed_scene_prompt=prose,
            reference_scene_lock="",
            negative_prompt="",
        )


_WORKFLOW_MULTI_REF_SYSTEM_ADDON = """
WORKFLOW MULTI-REFERENCE MODE:
The user attached one or more labeled USER_WORKFLOW_REFERENCE images (after any MODEL studio photos).
Each reference has a Role in USER_NOTES → REFERENCE_CONTEXT — treat Roles as authoritative.

Common roles (honor strictly):
- photo base / model / subject — the photo to edit: keep this person's identity, pose, camera, crop, background, light; apply changes only where SCENE_DIRECTION and other roles allow.
- pose / scene — geometry, camera, framing, light, background only — not identity.
- clothes / outfit / wardrobe — garment donor only: copy outfit style, colors, coverage zones onto the base person; never copy the outfit model's face, body, or scene.
- face — face likeness donor when SCENE_DIRECTION requests it.

Rules:
- Merge SCENE_DIRECTION with REFERENCE_CONTEXT; on conflict, Role instructions win for that reference's domain.
- Never paste an outfit-donor person's identity onto the base photo person.
- When MODEL studio photos are present, identity (face, hair, skin, body volumes) comes from MODEL photos + profile — workflow refs supply pose/scene/outfit unless Role says otherwise.
- Output format: ---PROMPT--- / ---NEGATIVE--- / ---VISIBLE--- blocks (plain descriptive English in PROMPT).
"""


@dataclass(frozen=True)
class WorkflowGrokUserRef:
    data: bytes
    mime: str
    role: str
    description: str
    file_name: str


def _workflow_ref_caption(ref: WorkflowGrokUserRef, index: int) -> str:
    role = (ref.role or "").strip() or "reference"
    parts = [f"[USER_WORKFLOW_REFERENCE_{index}] Role: {role}"]
    if (ref.description or "").strip():
        parts.append(f"Notes: {ref.description.strip()}")
    if (ref.file_name or "").strip():
        parts.append(f"File: {ref.file_name.strip()}")
    parts.append(
        "Follow the Role — do not copy identity from outfit/clothes donors onto the base subject."
    )
    return " — ".join(parts)


async def grok_compose_studio_workflow_multi_ref(
    *,
    user_refs: list[WorkflowGrokUserRef],
    model_images: list[UserStudioModelImage],
    model_profile_text: str | None,
    wave_profile: str,
    user_notes: str,
    lock_hairstyle: bool,
    credentials: StudioOpenAiCredentials | None = None,
    visibility: "IdentityVisibility | None" = None,
    reference_scene_description: str | None = None,
) -> GrokSceneComposeResult:
    """Workflow: несколько референсов с ролями + опционально фото модели из кабинета."""
    if not user_refs:
        raise RuntimeError("Workflow: нужен хотя бы один референс")
    creds = credentials or grok_motion_studio_credentials()
    wp = (wave_profile or "nsfw").strip().lower()
    profile = (model_profile_text or "").strip() or "{}"
    notes = (user_notes or "").strip()
    hair_rule = (
        "Hairstyle from MODEL photos and profile when present; otherwise from photo-base workflow ref."
        if lock_hairstyle
        else "Hairstyle may follow workflow references when USER_NOTES request it."
    )
    max_out = int(settings.grok_scene_compose_output_max_chars)

    labeled: list[tuple[str, UserStudioModelImage]] = []
    if model_images:
        labeled = _model_images_for_grok_compose(
            model_images, wave_profile=wave_profile, visibility=visibility
        )

    system = load_grok_scene_compose_main_system() + _WORKFLOW_MULTI_REF_SYSTEM_ADDON
    vis_block = _grok_visibility_user_block(
        visibility=visibility,
        reference_scene_description=reference_scene_description,
    )

    model_rule = ""
    if labeled:
        model_rule = (
            "Attached MODEL studio photos define WHO when present. "
            "USER_WORKFLOW_REFERENCE images follow their Role labels.\n\n"
        )
    else:
        model_rule = (
            "No MODEL studio photos — identity and base scene come from the workflow reference "
            "whose Role is photo base / model / subject; other refs are donors only.\n\n"
        )

    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"WAVE_PROFILE: {wp}\n"
                f"HAIRSTYLE: {hair_rule}\n"
                f"MAX_PROMPT_CHARS: {max_out}\n\n"
                f"{model_rule}"
                f"MODEL_PROFILE_JSON:\n{profile}\n\n"
                f"USER_NOTES:\n{notes or '(none)'}\n\n"
                "Attached images: MODEL studio photos first (if any), then USER_WORKFLOW_REFERENCE images in order."
                f"{vis_block}"
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

    for i, ref in enumerate(user_refs, 1):
        ref_mime = (ref.mime or "image/jpeg").split(";")[0].strip()
        if ref_mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            ref_mime = "image/jpeg"
        ref_b64 = base64.standard_b64encode(ref.data).decode("ascii")
        user_parts.append({"type": "text", "text": _workflow_ref_caption(ref, i)})
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
    return _finalize_grok_compose_result(_parse_grok_main_prose_output(raw_out), visibility)
