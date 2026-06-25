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

_CINEMATIC_FRAMING_EN = (
    "Professional cinematic film still, 35mm film grain, anamorphic lens, "
    "cinematic lighting, movie storyboard frame, director's vision, "
    "high production value, dramatic atmosphere, tasteful fashion editorial."
)

# Слова, которые чаще триггерят Seedance/WaveSpeed moderation (intent filter).
_BRIEF_TRIGGER_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bbody curves\b", re.I), "graceful silhouette"),
    (re.compile(r"\bcurves\b", re.I), "silhouette"),
    (re.compile(r"\bsexy\b", re.I), "elegant"),
    (re.compile(r"\bseductive\b", re.I), "confident"),
    (re.compile(r"\bsensual\b", re.I), "expressive"),
    (re.compile(r"\bprovocative\b", re.I), "bold"),
    (re.compile(r"\bbarely clothed\b", re.I), "in flowing garments"),
    (re.compile(r"\bexposed\b", re.I), "revealing light"),
    (re.compile(r"\bnude\b", re.I), "artistic figure study"),
    (re.compile(r"\bnaked\b", re.I), "artistic figure study"),
    (re.compile(r"\btopless\b", re.I), "shoulders visible"),
    (re.compile(r"\bnsfw\b", re.I), ""),
    (re.compile(r"\byoung girl\b", re.I), "adult woman"),
    (re.compile(r"\bteen\b", re.I), "adult"),
    (re.compile(r"\bminor\b", re.I), "adult"),
    (re.compile(r"\blingerie\b", re.I), "elegant dress"),
    (re.compile(r"\bbikini\b", re.I), "swimwear"),
    (re.compile(r"\bcleavage\b", re.I), "neckline"),
    (re.compile(r"\bbreast\b", re.I), "torso"),
    (re.compile(r"\bbreasts\b", re.I), "torso"),
    (re.compile(r"\bbutt\b", re.I), "hips"),
    (re.compile(r"\bass\b", re.I), "posture"),
]

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
    (re.compile(r"\bidentity lock\b", re.I), "character continuity"),
    (re.compile(r"\bnever change or morph\b", re.I), "keep consistent"),
]

_RU_LABEL = {
    "turnaround": "развёртка / character sheet",
    "face": "лицо и идентичность",
    "body": "телосложение",
    "other": "общий референс",
    "genitals": "интимная анатомия",
}


def sanitize_seedance_user_brief(text: str) -> str:
    """Смягчает USER_BRIEF перед Seedance (anti-sensitive intent)."""
    s = (text or "").strip()
    if not s:
        return s
    for pat, repl in _BRIEF_TRIGGER_REPLACEMENTS:
        s = pat.sub(repl, s)
    return re.sub(r"\s{2,}", " ", s).strip()


def wrap_seedance_cinematic_framing(text: str) -> str:
    body = sanitize_seedance_user_brief(text)
    if not body:
        return _CINEMATIC_FRAMING_EN
    return f"{_CINEMATIC_FRAMING_EN}\n\n{body}"


def translate_seedance_brief_to_zh(text: str) -> str:
    """Опциональный fallback: китайский промпт иногда проходит moderation."""
    raw = sanitize_seedance_user_brief(text)
    if not raw:
        return raw
    try:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="auto", target="zh-CN").translate(raw[:2000])
    except Exception as e:
        log.warning("seedance brief zh translate failed: %s", e)
        return raw


def prepare_seedance_user_brief(
    text: str,
    *,
    sanitize: bool = False,
    cinematic: bool = False,
    translate_zh: bool = False,
) -> str:
    if translate_zh:
        return translate_seedance_brief_to_zh(text)
    if cinematic:
        return wrap_seedance_cinematic_framing(text)
    if sanitize:
        return sanitize_seedance_user_brief(text)
    return (text or "").strip()


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


def _seedance_identity_lock_block(
    *,
    tags: str,
    n_start_frame: int,
    n_motion_videos: int,
) -> str:
    lines = [
        f"CHARACTER LOCK (all frames, entire clip): face, body, hair ONLY from {tags}. "
        "Never change or morph the character.",
    ]
    if n_start_frame > 0:
        lines.append(
            "@Image1 = pose, scene, lighting, wardrobe at t=0 ONLY — "
            "never take face, body, or hair from @Image1."
        )
    if n_motion_videos > 0:
        vtags = ", ".join(f"@Video{i}" for i in range(1, n_motion_videos + 1))
        lines.append(
            f"{vtags} = choreography and camera motion ONLY — "
            f"ignore the performer's face, body, and hair in {vtags}; "
            f"character look stays {tags} in every frame."
        )
    return " ".join(lines)


def append_seedance_identity_lock(
    prompt: str,
    *,
    n_start_frame: int,
    n_model_images: int,
    n_motion_videos: int,
    max_chars: int | None = None,
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
            f"One consistent character for the full clip — face, body, hair from {identity_tags} only."
        )
    if n_start_frame > 0:
        parts.append(
            "@Image1: opening frame — pose, scene, lighting, camera, wardrobe at t=0. "
            "Do NOT use face, body, or hair from @Image1."
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
                f"Motion timing, gestures, and camera from {vtags} only — "
                f"not the performer's face or body. Character look locked to {identity_tags}."
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
    sanitize_brief: bool = False,
    cinematic_framing: bool = False,
    translate_zh: bool = False,
) -> tuple[str, str]:
    """
    Grok (если настроен) → иначе шаблон. Возвращает (prompt, source: grok|template).
    """
    from app.services.studio_grok_motion import (
        grok_expand_seedance_t2v_prompt,
        grok_motion_api_configured,
    )

    lim = settings.studio_seedance_t2v_prompt_max_chars
    brief = prepare_seedance_user_brief(
        user_brief,
        sanitize=sanitize_brief or cinematic_framing or translate_zh,
        cinematic=cinematic_framing and not translate_zh,
        translate_zh=translate_zh,
    )
    safe_motion = prepare_motion_notes_for_seedance(motion_summary)
    if not force_template and grok_motion_api_configured():
        try:
            p = await grok_expand_seedance_t2v_prompt(
                user_brief=brief,
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
            return (
                append_seedance_identity_lock(
                    soften_seedance_provider_prompt(p),
                    n_start_frame=n_start_frame,
                    n_model_images=n_model_images,
                    n_motion_videos=n_motion_videos,
                    max_chars=lim,
                ),
                "grok",
            )
        except Exception as e:
            log.warning("grok seedance t2v prompt failed, template fallback: %s", e)

    p = assemble_seedance_t2v_prompt(
        brief,
        n_start_frame=n_start_frame,
        n_model_images=n_model_images,
        n_outfit_images=n_outfit_images,
        n_motion_videos=n_motion_videos,
        motion_summary=safe_motion,
        negative=negative,
    )
    return (
        append_seedance_identity_lock(
            p,
            n_start_frame=n_start_frame,
            n_model_images=n_model_images,
            n_motion_videos=n_motion_videos,
            max_chars=lim,
        ),
        "template",
    )


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
