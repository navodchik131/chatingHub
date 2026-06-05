"""Seedance 2.0 Text-to-Video: reference_images + @ImageN в промпте."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import quote

from app.config import settings
from app.db.models import UserStudioModel, UserStudioModelImage

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

MAX_SEEDANCE_REFERENCE_IMAGES = 9
MAX_SEEDANCE_REFERENCE_VIDEOS = 3
SEEDANCE_T2V_PROMPT_MAX_CHARS = 3000

_T2V_KIND_ORDER = {"turnaround": 0, "face": 1, "body": 2, "other": 3, "genitals": 99}

_RU_LABEL = {
    "turnaround": "развёртка / character sheet",
    "face": "лицо и идентичность",
    "body": "телосложение",
    "other": "общий референс",
    "genitals": "интимная анатомия",
}


def sort_model_images_for_seedance_t2v(
    imgs: list[UserStudioModelImage],
    *,
    include_genitals: bool = False,
) -> list[UserStudioModelImage]:
    """Приоритет: turnaround → face → body → other (до 9 шт.)."""
    filtered: list[UserStudioModelImage] = []
    for im in imgs:
        k = (im.image_kind or "other").lower()
        if k == "genitals" and not include_genitals:
            continue
        filtered.append(im)
    filtered.sort(
        key=lambda im: (
            _T2V_KIND_ORDER.get((im.image_kind or "other").lower(), 50),
            im.id,
        )
    )
    return filtered[:MAX_SEEDANCE_REFERENCE_IMAGES]


def model_reference_public_urls(
    *,
    owner_id: int,
    images: list[UserStudioModelImage],
    public_app_base: str,
    token_factory,
) -> list[str]:
    """Публичные HTTPS URL фото модели для reference_images."""
    base = (public_app_base or "").strip().rstrip("/")
    if not base:
        return []
    out: list[str] = []
    for im in images:
        tok = token_factory(user_id=owner_id, image_id=im.id)
        out.append(f"{base}/api/studio/public-model-image?t={quote(tok, safe='')}")
    return out


def generation_still_public_url(
    *,
    owner_id: int,
    generation_id: int,
    public_app_base: str,
    token_factory,
) -> str | None:
    base = (public_app_base or "").strip().rstrip("/")
    if not base:
        return None
    tok = token_factory(user_id=owner_id, generation_id=generation_id)
    return f"{base}/api/studio/public-generation-image?t={quote(tok, safe='')}"


def assemble_seedance_t2v_prompt(
    user_prompt: str,
    *,
    n_start_frame: int = 0,
    n_model_images: int,
    n_outfit_images: int = 0,
    n_motion_videos: int = 0,
    motion_summary: str | None = None,
    negative: str | None = None,
) -> str:
    """
    Собирает промпт с метками @ImageN / @VideoN (порядок = порядок в reference_* массивах).
    При n_start_frame=1: @Image1 — opening still; @Image2+ — identity модели.
    """
    parts: list[str] = []
    if n_start_frame > 0:
        parts.append(
            "@Image1 is the approved opening still at t=0: starting pose, wardrobe, garments, lighting, "
            "camera framing, and environment. @Image1 is the wardrobe authority at t=0. "
            "Do not treat @Image1 as the sole face/body identity reference."
        )
    if n_model_images > 0:
        start_idx = 1 + n_start_frame
        end_idx = start_idx + n_model_images - 1
        if n_model_images == 1:
            tags = f"@Image{start_idx}"
        else:
            tags = f"@Image{start_idx}–@Image{end_idx}"
        parts.append(
            f"Same person throughout — identity via {tags} (face/body/hair bound through reference images; "
            "do not restate facial identity or skin details in this text). "
            f"IGNORE all clothing, garments, and wardrobe visible on {tags} — those sheets are identity-only "
            "and may show neutral base outfits. "
            "Never adopt the reference video actor's face or identity."
        )
        if n_start_frame > 0 and n_outfit_images == 0:
            parts.append(
                "Dress the character in the exact wardrobe shown in @Image1 and USER_BRIEF for the full clip."
            )
    if n_outfit_images > 0:
        start = 1 + n_start_frame + n_model_images
        for j in range(n_outfit_images):
            idx = start + j
            parts.append(
                f"Wardrobe and garment details for the entire clip: match @Image{idx} exactly "
                "(override any clothing visible on model identity references or @Image1 if they differ)."
            )
    if n_motion_videos > 0:
        vtags = ", ".join(f"@Video{i}" for i in range(1, n_motion_videos + 1))
        parts.append(
            f"Motion, pacing, and body dynamics: follow {vtags} for choreography and timing ONLY."
        )
    if motion_summary and motion_summary.strip():
        parts.append(f"Additional motion notes:\n{motion_summary.strip()}")
    up = (user_prompt or "").strip()
    if up:
        parts.append(up)
    neg = (negative or "").strip()
    if neg:
        parts.append(f"Avoid: {neg}")
    if not parts:
        parts.append(
            "Natural cinematic motion; smooth camera; expressive performance; preserve character identity."
        )
    return "\n\n".join(parts)


def truncate_seedance_t2v_prompt(text: str, *, max_chars: int | None = None) -> str:
    lim = max_chars if max_chars is not None else settings.studio_seedance_t2v_prompt_max_chars
    s = (text or "").strip()
    if len(s) <= lim:
        return s
    cut = s[: lim - 1].rstrip()
    return f"{cut}…"


async def build_seedance_t2v_prompt(
    *,
    user_brief: str,
    n_start_frame: int = 0,
    n_model_images: int,
    n_outfit_images: int = 0,
    n_motion_videos: int = 0,
    motion_summary: str | None = None,
    model_profile_text: str | None = None,
    negative: str | None = None,
    output_aspect: str | None = None,
    duration_seconds: int = 5,
) -> tuple[str, str]:
    """
    Grok (если настроен) → иначе шаблон. Возвращает (prompt, source: grok|template).
    """
    from app.services.studio_grok_motion import (
        grok_expand_seedance_t2v_prompt,
        grok_motion_api_configured,
    )

    lim = settings.studio_seedance_t2v_prompt_max_chars
    if grok_motion_api_configured():
        try:
            p = await grok_expand_seedance_t2v_prompt(
                user_brief=user_brief,
                n_start_frame=n_start_frame,
                n_model_images=n_model_images,
                n_outfit_images=n_outfit_images,
                n_motion_videos=n_motion_videos,
                motion_notes=motion_summary,
                model_profile_text=model_profile_text,
                negative=negative,
                output_aspect=output_aspect,
                duration_seconds=duration_seconds,
                max_chars=lim,
            )
            return p, "grok"
        except Exception as e:
            log.warning("grok seedance t2v prompt failed, template fallback: %s", e)

    p = assemble_seedance_t2v_prompt(
        user_brief,
        n_start_frame=n_start_frame,
        n_model_images=n_model_images,
        n_outfit_images=n_outfit_images,
        n_motion_videos=n_motion_videos,
        motion_summary=motion_summary,
        negative=negative,
    )
    return truncate_seedance_t2v_prompt(p, max_chars=lim), "template"


def model_has_turnaround_sheet(model: UserStudioModel | None) -> bool:
    if model is None:
        return False
    return any((im.image_kind or "").lower() == "turnaround" for im in model.images)
