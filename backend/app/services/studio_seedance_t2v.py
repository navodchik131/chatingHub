"""Seedance 2.0 Text-to-Video: reference_images + @ImageN в промпте."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from urllib.parse import quote

from app.config import settings
from app.db.models import UserStudioModel, UserStudioModelImage

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

MAX_SEEDANCE_REFERENCE_IMAGES = 9
MAX_SEEDANCE_REFERENCE_VIDEOS = 3
MAX_SEEDANCE_VIDEO_MODEL_IDENTITY_IMAGES = 2
MAX_SEEDANCE_VIDEO_MODEL_IDENTITY_WITH_BODY = 3
SEEDANCE_T2V_PROMPT_MAX_CHARS = 3000

_T2V_KIND_ORDER = {"turnaround": 0, "face": 1, "body": 2, "other": 3, "genitals": 99}
_VIDEO_IDENTITY_KINDS = frozenset({"turnaround", "face"})
_VIDEO_IDENTITY_KINDS_WITH_BODY = frozenset({"turnaround", "face", "body"})

_MOTION_NOTE_BANNED_SUBSTRINGS = (
    "skin tone",
    "skin texture",
    "eye color",
    "cheekbone",
    "ethnicity",
    "makeup",
    "facial identity",
    "face shape",
    "beauty adjective",
    "biometric",
    "identity catalog",
)

_PROVIDER_PROMPT_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bface/body/hair\b", re.I), "character"),
    (re.compile(r"\bfacial identity\b", re.I), "appearance"),
    (re.compile(r"\b(?:skin tone|skin texture|skin details)\b", re.I), ""),
    (re.compile(r"\bbody proportions\b", re.I), "figure"),
    (re.compile(r"\bidentity via\b", re.I), "character via"),
    (re.compile(r"\bidentity only from\b", re.I), "character from"),
    (re.compile(r"\bmodel identity\b", re.I), "model reference"),
    (re.compile(r"\bNever adopt the reference video actor['']s face or identity\.?\s*", re.I), ""),
    (re.compile(r"\bdo not restate facial identity[^.]*\.?\s*", re.I), ""),
    (re.compile(r"\bIGNORE all clothing[^.]*\.?\s*", re.I), ""),
    (re.compile(r"\bwardrobe authority\b", re.I), "wardrobe"),
    (re.compile(r"\bCONTENT_SAFETY[^.]*\.?\s*", re.I), ""),
]

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


def filter_model_images_for_seedance_video(
    imgs: list[UserStudioModelImage],
    *,
    minimal: bool = False,
    include_body: bool = False,
    max_identity: int | None = None,
) -> list[UserStudioModelImage]:
    """
    Для render-video: turnaround (+ face, опционально body), без other/genitals.
    Полные ню-листы модели чаще всего триггерят sensitive у Seedance.
    """
    if minimal:
        kinds = frozenset({"turnaround"})
        default_cap = 1
    elif include_body:
        kinds = _VIDEO_IDENTITY_KINDS_WITH_BODY
        default_cap = MAX_SEEDANCE_VIDEO_MODEL_IDENTITY_WITH_BODY
    else:
        kinds = _VIDEO_IDENTITY_KINDS
        default_cap = MAX_SEEDANCE_VIDEO_MODEL_IDENTITY_IMAGES
    cap = max_identity if max_identity is not None else default_cap
    cap = max(1, min(cap, MAX_SEEDANCE_REFERENCE_IMAGES))
    sorted_all = sort_model_images_for_seedance_t2v(imgs)
    picked: list[UserStudioModelImage] = []
    for im in sorted_all:
        k = (im.image_kind or "other").lower()
        if k in kinds:
            picked.append(im)
        if len(picked) >= cap:
            break
    if not picked:
        picked = sorted_all[:cap]
    return picked


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


def prepare_motion_notes_for_seedance(
    notes: str | None,
    *,
    max_chars: int = 1800,
) -> str | None:
    """Убирает из Grok-таймлайна строки с biometric/identity — их флагает Seedance."""
    raw = (notes or "").strip()
    if not raw:
        return None
    kept: list[str] = []
    for line in raw.splitlines():
        low = line.lower()
        if any(b in low for b in _MOTION_NOTE_BANNED_SUBSTRINGS):
            continue
        kept.append(line)
    out = "\n".join(kept).strip()
    if not out:
        return None
    if len(out) > max_chars:
        out = out[: max_chars - 1].rstrip() + "…"
    return out


def seedance_model_identity_tag_expr(
    n_start_frame: int,
    n_model_images: int,
) -> str | None:
    if n_model_images <= 0:
        return None
    start_idx = 1 + n_start_frame
    end_idx = start_idx + n_model_images - 1
    if n_model_images == 1:
        return f"@Image{start_idx}"
    return f"@Image{start_idx}–@Image{end_idx}"


_IDENTITY_NEGATIVE_DEFAULTS = (
    "different person, face change mid-clip, identity drift, morphing face, "
    "reference video actor face, character swap, inconsistent appearance, "
    "wrong face, actor from reference video"
)

_WORKFLOW_FACE_GRID_REMOVAL_EN = (
    "Remove the white guide grid overlay from the face in every frame; "
    "keep natural skin texture and the same character identity from the reference images."
)

_WORKFLOW_FACE_GRID_REMOVAL_ZH = "每一帧都要去掉脸上的白色参考网格线，保留自然肤色和参考图里的同一角色外观。"


def append_workflow_face_grid_removal(prompt: str, *, language: str = "en") -> str:
    line = _WORKFLOW_FACE_GRID_REMOVAL_ZH if language == "zh" else _WORKFLOW_FACE_GRID_REMOVAL_EN
    body = (prompt or "").strip()
    if not body:
        return line
    if line.lower() in body.lower():
        return body
    return f"{body}\n\n{line}".strip()


def _seedance_identity_lock_block(
    *,
    tags: str,
    n_start_frame: int,
    n_motion_videos: int,
    language: str = "en",
) -> str:
    if language == "zh":
        lines = [
            f"整段视频保持同一角色——外观参照 {tags}。",
        ]
        if n_start_frame > 0:
            lines.append(
                f"@Image1 — t=0 开场画面（姿势、场景、光线、服装）；"
                f"角色外形来自 {tags}，而非 @Image1。"
            )
        if n_motion_videos > 0:
            vtags = ", ".join(f"@Video{i}" for i in range(1, n_motion_videos + 1))
            lines.append(
                f"{vtags} — 动作、节奏与镜头参考；"
                f"角色外观保持 {tags}。"
            )
        return " ".join(lines)

    lines = [
        f"Same character for the whole clip — appearance from {tags}.",
    ]
    if n_start_frame > 0:
        lines.append(
            "@Image1 — opening frame at t=0 (pose, scene, lighting, wardrobe); "
            f"character likeness from {tags}, not from @Image1."
        )
    if n_motion_videos > 0:
        vtags = ", ".join(f"@Video{i}" for i in range(1, n_motion_videos + 1))
        lines.append(
            f"{vtags} — motion, timing, and camera reference; "
            f"character appearance stays on {tags}."
        )
    return " ".join(lines)


def append_seedance_identity_lock(
    prompt: str,
    *,
    n_start_frame: int,
    n_model_images: int,
    n_motion_videos: int,
    max_chars: int | None = None,
    language: str = "en",
) -> str:
    """
    Жёсткий lock до и после тела промпта: Seedance привязывает identity только к явным @ImageN.
    """
    lim = max_chars if max_chars is not None else settings.studio_seedance_t2v_prompt_max_chars
    tags = seedance_model_identity_tag_expr(n_start_frame, n_model_images)
    if not tags:
        return truncate_seedance_t2v_prompt(prompt, max_chars=lim)
    lock = _seedance_identity_lock_block(
        tags=tags,
        n_start_frame=n_start_frame,
        n_motion_videos=n_motion_videos,
        language=language,
    )
    body = (prompt or "").strip()
    combined = f"{lock}\n\n{body}\n\n{lock}".strip()
    return truncate_seedance_t2v_prompt(combined, max_chars=lim)


def soften_seedance_provider_prompt(text: str) -> str:
    """Финальная чистка промпта перед WaveSpeed/Seedance (anti-sensitive)."""
    s = (text or "").strip()
    for pat, repl in _PROVIDER_PROMPT_REPLACEMENTS:
        s = pat.sub(repl, s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


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
    identity_tags = seedance_model_identity_tag_expr(n_start_frame, n_model_images)
    if identity_tags:
        parts.append(
            f"One consistent character — appearance from {identity_tags}."
        )
    if n_start_frame > 0:
        if identity_tags:
            parts.append(
                "@Image1 — opening frame at t=0 (pose, scene, lighting, camera, wardrobe). "
                f"Character look from {identity_tags}."
            )
        else:
            parts.append(
                "@Image1 — opening frame at t=0 (pose, scene, lighting, camera, wardrobe)."
            )
        if n_outfit_images == 0:
            parts.append("Wardrobe at t=0: match @Image1 and USER_BRIEF.")
    if n_outfit_images > 0:
        start = 1 + n_start_frame + n_model_images
        for j in range(n_outfit_images):
            idx = start + j
            parts.append(f"Wardrobe: match @Image{idx}.")
    if n_motion_videos > 0:
        vtags = ", ".join(f"@Video{i}" for i in range(1, n_motion_videos + 1))
        if identity_tags:
            parts.append(
                f"Motion and pacing from {vtags}; "
                f"character appearance from {identity_tags}."
            )
        else:
            parts.append(f"Motion and pacing from {vtags} only (timing, gestures, camera).")
    if motion_summary and motion_summary.strip():
        parts.append(f"Motion notes:\n{motion_summary.strip()}")
    up = (user_prompt or "").strip()
    if up:
        parts.append(up)
    neg_parts: list[str] = []
    if identity_tags:
        neg_parts.append(_IDENTITY_NEGATIVE_DEFAULTS)
    neg = (negative or "").strip()
    if neg:
        neg_parts.append(neg)
    if neg_parts:
        parts.append(f"Avoid: {'; '.join(neg_parts)}")
    if not parts:
        parts.append(
            "Natural cinematic motion; smooth camera; expressive performance; same character throughout."
        )
    body = soften_seedance_provider_prompt("\n\n".join(parts))
    return append_seedance_identity_lock(
        body,
        n_start_frame=n_start_frame,
        n_model_images=n_model_images,
        n_motion_videos=n_motion_videos,
    )


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
    force_template: bool = False,
    remove_face_grid: bool = False,
) -> tuple[str, str]:
    """
    Grok (если настроен) → иначе шаблон. Возвращает (prompt, source: grok|template).
    """
    from app.services.studio_grok_motion import (
        grok_expand_seedance_t2v_prompt,
        grok_motion_api_configured,
    )

    lim = settings.studio_seedance_t2v_prompt_max_chars
    safe_motion = prepare_motion_notes_for_seedance(motion_summary)
    if not force_template and grok_motion_api_configured():
        try:
            p = await grok_expand_seedance_t2v_prompt(
                user_brief=user_brief,
                n_start_frame=n_start_frame,
                n_model_images=n_model_images,
                n_outfit_images=n_outfit_images,
                n_motion_videos=n_motion_videos,
                motion_notes=safe_motion,
                model_profile_text=None,
                negative=negative,
                output_aspect=output_aspect,
                duration_seconds=duration_seconds,
                max_chars=lim,
            )
            lock_lang = "zh" if settings.studio_seedance_grok_prompt_zh else "en"
            locked = append_seedance_identity_lock(
                soften_seedance_provider_prompt(p),
                n_start_frame=n_start_frame,
                n_model_images=n_model_images,
                n_motion_videos=n_motion_videos,
                max_chars=lim,
                language=lock_lang,
            )
            if remove_face_grid:
                locked = append_workflow_face_grid_removal(locked, language=lock_lang)
            return (locked, "grok")
        except Exception as e:
            log.warning("grok seedance t2v prompt failed, template fallback: %s", e)

    p = assemble_seedance_t2v_prompt(
        user_brief,
        n_start_frame=n_start_frame,
        n_model_images=n_model_images,
        n_outfit_images=n_outfit_images,
        n_motion_videos=n_motion_videos,
        motion_summary=safe_motion,
        negative=negative,
    )
    if remove_face_grid:
        p = append_workflow_face_grid_removal(p, language="en")
    return (p, "template")


def assemble_seedance_video_edit_prompt(
    user_brief: str,
    *,
    n_ref_images: int,
    motion_summary: str | None = None,
    negative: str | None = None,
) -> str:
    """
    Промпт для Seedance Video-Edit: исходное видео = motion, reference_images = модель.
    Префикс «Edit the input video.» WaveSpeed добавляет сам.
    """
    parts = [
        "Replace the performer with the character from the reference images.",
        "Keep exact motion, choreography, camera movement, pacing, background, and lighting from the input video.",
        "Face, body, and hair must match the reference images in every frame — never keep the original video actor.",
    ]
    if n_ref_images > 0:
        if n_ref_images == 1:
            parts.append("Identity: reference image 1 is the approved model look.")
        else:
            parts.append(
                f"Identity: reference images 1–{n_ref_images}; image 1 is the approved opening still with the target model."
            )
    safe_motion = prepare_motion_notes_for_seedance(motion_summary)
    if safe_motion:
        parts.append(f"Motion notes:\n{safe_motion}")
    up = (user_brief or "").strip()
    if up:
        parts.append(up)
    neg = (negative or "").strip()
    if neg:
        parts.append(f"Avoid: {neg}")
    return "\n\n".join(parts)


def model_has_turnaround_sheet(model: UserStudioModel | None) -> bool:
    if model is None:
        return False
    return any((im.image_kind or "").lower() == "turnaround" for im in model.images)
