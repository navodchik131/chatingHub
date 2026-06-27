"""BoardStory: Seedance без первого кадра — identity из кабинета + отдельные refs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

from app.services.studio_seedance_t2v import (
    MAX_SEEDANCE_REFERENCE_IMAGES,
    generation_still_public_url,
    model_reference_public_urls,
    seedance_model_identity_tag_expr,
    sort_model_images_for_seedance_t2v,
)

_CLOTHING_HINTS = (
    "cloth",
    "outfit",
    "wardrobe",
    "garment",
    "одежд",
    "наряд",
    "dress",
)
_ENVIRONMENT_HINTS = (
    "environment",
    "room",
    "scene",
    "location",
    "interior",
    "background",
    "lighting",
    "окруж",
    "комнат",
    "интерьер",
    "свет",
    "декор",
    "ambient",
)


def classify_boardstory_ref_role(role: str) -> str:
    """clothing | environment | other"""
    r = (role or "").strip().lower()
    if any(h in r for h in _CLOTHING_HINTS):
        return "clothing"
    if any(h in r for h in _ENVIRONMENT_HINTS):
        return "environment"
    return "other"


@dataclass(frozen=True)
class BoardStoryImageSlot:
    kind: str
    generation_id: int | None = None
    ref_id: str | None = None
    role: str = ""
    description: str = ""


class _ExtraRef(Protocol):
    ref_id: str


@dataclass(frozen=True)
class BoardStoryReferenceLayout:
    n_model_images: int
    n_clothing_images: int
    n_environment_images: int
    n_other_images: int
    clothing_image_index: int | None
    environment_image_index: int | None
    identity_tag_expr: str | None
    clothing_tag: str | None
    environment_tag: str | None
    other_image_indices: tuple[int, ...]


def compute_boardstory_layout(
    n_model: int,
    *,
    has_clothing: bool,
    has_environment: bool,
    n_other: int = 0,
    n_start_frame: int = 0,
) -> BoardStoryReferenceLayout:
    idx = n_start_frame + n_model + 1
    clothing_idx: int | None = None
    environment_idx: int | None = None
    if has_clothing:
        clothing_idx = idx
        idx += 1
    if has_environment:
        environment_idx = idx
        idx += 1
    other_indices: list[int] = []
    for _ in range(n_other):
        other_indices.append(idx)
        idx += 1

    identity = seedance_model_identity_tag_expr(n_start_frame, n_model)
    return BoardStoryReferenceLayout(
        n_model_images=n_model,
        n_clothing_images=1 if has_clothing else 0,
        n_environment_images=1 if has_environment else 0,
        n_other_images=n_other,
        clothing_image_index=clothing_idx,
        environment_image_index=environment_idx,
        identity_tag_expr=identity,
        clothing_tag=f"@Image{clothing_idx}" if clothing_idx else None,
        environment_tag=f"@Image{environment_idx}" if environment_idx else None,
        other_image_indices=tuple(other_indices),
    )


def filter_model_images_for_boardstory(
    imgs: list,
) -> list:
    """BoardStory: face + turnaround + body (до 3 refs); @Image1 = лицо."""
    from app.services.studio_seedance_t2v import filter_model_images_for_seedance_video

    kind_order = {"face": 0, "turnaround": 1, "body": 2, "other": 3, "genitals": 99}
    picked = filter_model_images_for_seedance_video(imgs, include_body=True)
    if picked:
        return sorted(
            picked,
            key=lambda im: kind_order.get((im.image_kind or "other").lower(), 3),
        )
    sorted_all = sort_model_images_for_seedance_t2v(imgs)
    for im in sorted_all:
        if (im.image_kind or "other").lower() == "body":
            return [im]
    return sorted_all[:1] if sorted_all else []


def filter_model_images_for_boardstory_video_edit(
    imgs: list,
) -> list:
    """Video-Edit swap: одно фото лица (как в playground WaveSpeed)."""
    for im in filter_model_images_for_boardstory(imgs):
        if (im.image_kind or "other").lower() == "face":
            return [im]
    picked = filter_model_images_for_boardstory(imgs)
    return picked[:1] if picked else []


def build_boardstory_video_edit_swap_prompt(
    *,
    n_identity_refs: int = 1,
    has_clothing: bool = False,
    has_environment: bool = False,
    user_notes: str = "",
    negative: str | None = None,
    max_chars: int | None = None,
) -> str:
    """
    Промпт для Seedance Video-Edit Turbo — как в playground WaveSpeed.
    Без @Video1/@ImageN: video = input clip, reference_images = модель.
    https://wavespeed.ai/models/bytedance/seedance-2.0/video-edit-turbo
    """
    from app.services.studio_seedance_t2v import truncate_seedance_t2v_prompt

    parts = [
        "Replace the person in the video with the person from reference image 1, "
        "keeping the same actions, expressions, and camera movement.",
        "Face, body, and hair must match reference image 1 in every frame — "
        "never keep the original video actor.",
    ]
    idx = 1 + max(0, n_identity_refs)
    if has_clothing:
        parts.append(
            f"Dress the person in the exact clothing and accessories from reference image {idx}."
        )
        idx += 1
    if has_environment:
        parts.append(
            f"Match room, background, lighting, and atmosphere from reference image {idx}."
        )
    notes = (user_notes or "").strip()
    if notes:
        parts.append(notes)
    neg = (negative or "").strip()
    if neg:
        parts.append(f"Avoid: {neg}")
    return truncate_seedance_t2v_prompt("\n\n".join(parts), max_chars=max_chars)


def build_boardstory_video_edit_reference_urls(
    *,
    identity_image_urls: list[str],
    clothing_slot: BoardStoryImageSlot | None,
    environment_slot: BoardStoryImageSlot | None,
    generation_url_factory,
    workflow_ref_url_factory,
) -> tuple[list[str], bool, bool]:
    """reference_images для Video-Edit: face → clothing → environment."""
    refs: list[str] = [u for u in identity_image_urls if (u or "").strip()][:1]
    if not refs:
        return [], False, False

    clothing_url: str | None = None
    if clothing_slot is not None:
        if clothing_slot.generation_id is not None:
            clothing_url = generation_url_factory(clothing_slot.generation_id)
        elif clothing_slot.ref_id:
            clothing_url = workflow_ref_url_factory(clothing_slot.ref_id)
        if clothing_url:
            refs.append(clothing_url)

    environment_url: str | None = None
    if environment_slot is not None:
        if environment_slot.generation_id is not None:
            environment_url = generation_url_factory(environment_slot.generation_id)
        elif environment_slot.ref_id:
            environment_url = workflow_ref_url_factory(environment_slot.ref_id)
        if environment_url:
            refs.append(environment_url)

    if len(refs) > MAX_SEEDANCE_REFERENCE_IMAGES:
        refs = refs[:MAX_SEEDANCE_REFERENCE_IMAGES]
    return refs, clothing_url is not None, environment_url is not None


def boardstory_identity_role_lines(n_model_images: int) -> str:
    """Явные роли @Image1..N — без диапазонов @Image1–@Image3 (Seedance путает с clothing/env)."""
    if n_model_images <= 0:
        return "@Image1 = approved model identity for every frame."
    if n_model_images == 1:
        return (
            "@Image1 = primary face and identity anchor — the on-screen person in every frame."
        )
    lines = [
        "@Image1 = primary face and identity anchor — the on-screen person in every frame.",
    ]
    if n_model_images >= 2:
        lines.append("@Image2 = character sheet / turnaround for stable proportions.")
    if n_model_images >= 3:
        lines.append("@Image3 = body silhouette and proportions reference.")
    return "\n".join(lines)


def boardstory_video_only_swap_mode(
    *,
    clothing_ref: BoardStoryImageSlot | None,
    environment_ref: BoardStoryImageSlot | None,
    generate_clothing_from_video: bool,
    generate_environment_from_video: bool,
    send_video_reference: bool,
) -> bool:
    """Нет рефов одежды/комнаты и нет галочек extract — всё кроме identity из @Video1."""
    return (
        send_video_reference
        and clothing_ref is None
        and environment_ref is None
        and not generate_clothing_from_video
        and not generate_environment_from_video
    )


_BOARDSTORY_VIDEO_ONLY_SWAP_TEMPLATE = """\
MODEL REPLACEMENT — PRIMARY TASK
Replace the reference performer in {video_tag} with the lead character from @Image1.
The visible person in every frame must be @Image1 — never the original {video_tag} actor.

IDENTITY
{identity_role_lines}

MOTION ONLY ({video_tag})
From {video_tag} copy ONLY: choreography, timing, pacing, gestures, head movement, gaze shifts, hand and body movement, posture transitions, camera movement, and framing changes.
Do NOT take from {video_tag}: face, skin, hair, body shape, or any biometric trait of the reference performer.

WARDROBE AND SCENE ({video_tag} → on @Image1)
Dress @Image1 in the same outfit style, accessories, and styling seen in {video_tag} — worn by the NEW person, not the original actor.
Match lighting mood, background layout, camera angle, and atmosphere from {video_tag} while keeping @Image1's identity unchanged.

QUALITY
Ultra realistic natural phone video. Stable @Image1 identity in every frame. Smooth motion. No temporal flicker.

NEGATIVE
Do not copy the {video_tag} performer identity. No reference-actor face. No face morphing. No identity drift. No extra people."""


def build_boardstory_video_only_swap_prompt(
    *,
    user_notes: str = "",
    n_model_images: int = 1,
    video_tag: str = "@Video1",
    max_chars: int | None = None,
) -> str:
    """
    Фиксированный Seedance-промпт: identity из @Image1 (+ @Image2/@Image3), motion из @Video1.
    """
    from app.services.studio_seedance_t2v import truncate_seedance_t2v_prompt

    template = _BOARDSTORY_VIDEO_ONLY_SWAP_TEMPLATE.format(
        video_tag=video_tag,
        identity_role_lines=boardstory_identity_role_lines(n_model_images),
    )

    parts = [template.strip()]
    notes = (user_notes or "").strip()
    if notes:
        parts.append(f"USER_DIRECTION:\n{notes}")

    return truncate_seedance_t2v_prompt("\n\n".join(parts), max_chars=max_chars)


def boardstory_clothing_env_swap_mode(
    *,
    clothing_ref: BoardStoryImageSlot | None,
    environment_ref: BoardStoryImageSlot | None,
    send_video_reference: bool,
) -> bool:
    """Одежда и помещение подключены — фиксированный промпт с @Image2 clothing и сценой из @Video1."""
    return (
        send_video_reference
        and clothing_ref is not None
        and environment_ref is not None
    )


_BOARDSTORY_CLOTHING_ENV_SWAP_TEMPLATE = """\
MODEL REPLACEMENT — PRIMARY TASK
Replace the reference performer in {video_tag} with the lead character from @Image1.
The visible person in every frame must be @Image1 — never the original {video_tag} actor.

IDENTITY
{identity_role_lines}

CLOTHING ({clothing_tag})
Dress @Image1 in the exact clothing, accessories, and styling from {clothing_tag}.
Stable outfit consistency throughout the video.

MOTION ONLY ({video_tag})
From {video_tag} copy ONLY: choreography, timing, pacing, gestures, head movement, gaze shifts, hand and body movement, posture transitions, camera movement, and framing changes.
Do NOT take from {video_tag}: face, skin, hair, body shape, or any biometric trait of the reference performer.

SCENE
Room, background, lighting, and atmosphere: match {environment_tag}.
Follow motion and camera work from {video_tag} without cloning the reference actor.

QUALITY
Ultra realistic natural phone video. Stable @Image1 identity. Stable {clothing_tag} wardrobe. Smooth motion.

NEGATIVE
Do not copy the {video_tag} performer identity. No reference-actor face. No face morphing. No identity drift. No clothing drift from {clothing_tag}."""


def build_boardstory_clothing_env_swap_prompt(
    *,
    user_notes: str = "",
    n_model_images: int = 1,
    clothing_tag: str = "@Image2",
    environment_tag: str = "@Image3",
    video_tag: str = "@Video1",
    max_chars: int | None = None,
) -> str:
    """Фиксированный промпт: @Image1 identity, отдельные clothing/env теги, motion из @Video1."""
    from app.services.studio_seedance_t2v import truncate_seedance_t2v_prompt

    template = _BOARDSTORY_CLOTHING_ENV_SWAP_TEMPLATE.format(
        video_tag=video_tag,
        clothing_tag=clothing_tag,
        environment_tag=environment_tag,
        identity_role_lines=boardstory_identity_role_lines(n_model_images),
    )

    parts = [template.strip()]
    notes = (user_notes or "").strip()
    if notes:
        parts.append(f"USER_DIRECTION:\n{notes}")

    return truncate_seedance_t2v_prompt("\n\n".join(parts), max_chars=max_chars)


def boardstory_tag_rules_text(
    layout: BoardStoryReferenceLayout,
    *,
    has_motion: bool,
    clothing_from_video: bool = False,
    environment_from_video: bool = False,
    send_video_reference: bool = True,
) -> str:
    lines: list[str] = []
    id_expr = layout.identity_tag_expr or "@Image1"

    if send_video_reference and has_motion:
        lines.append(
            "MODEL REPLACEMENT (critical): @Video1 contains a reference performer — "
            "DO NOT copy their face, body, skin, or hair. "
            "Replace them entirely with @Image1 (primary face anchor)."
        )
        if layout.n_model_images >= 2:
            lines.append("@Image2 = character sheet / turnaround proportions.")
        if layout.n_model_images >= 3:
            lines.append("@Image3 = body silhouette reference.")
    else:
        lines.append(
            f"{id_expr} = the lead character (face, body, hair, age, ethnicity from model body reference)."
        )

    if layout.identity_tag_expr:
        suffix = (
            "NOT clothing, NOT room, NOT the @Video1 actor)"
            if send_video_reference and has_motion
            else "NOT clothing, NOT room)"
        )
        lines.append(
            f"{layout.identity_tag_expr} = model identity ONLY (face, body, hair from model body photo — "
            + suffix
        )
    if layout.clothing_tag:
        lines.append(
            f"{layout.clothing_tag} = clothing / wardrobe ONLY — dress the {id_expr} character "
            "in these exact garments."
        )
    elif clothing_from_video:
        if send_video_reference and has_motion:
            lines.append(
                "Wardrobe and outfit: take EXCLUSIVELY from @Video1 motion reference — "
                "match garments seen in the video but on the NEW character from "
                f"{id_expr}, not on the reference actor."
            )
        else:
            lines.append(
                "Wardrobe: describe outfit in exhaustive visual detail in prose "
                "(colors, fabric, cut, accessories) — derived from motion analysis, no video tag."
            )
    else:
        src = (
            "derive from @Video1 motion reference when no clothing image attached"
            if send_video_reference and has_motion
            else "describe in full visual detail in prose when no clothing image attached"
        )
        lines.append(f"Wardrobe: {src}; apply to {id_expr} character only.")
    if layout.environment_tag:
        lines.append(
            f"{layout.environment_tag} = environment / room / lighting ONLY (scene plate) — "
            "same camera angle and illumination as the story."
        )
    elif environment_from_video:
        if send_video_reference and has_motion:
            lines.append(
                "Room, background, lighting, and ambient glow: take EXCLUSIVELY from @Video1 — "
                "same intimate interior and soft illumination as in the video."
            )
        else:
            lines.append(
                "Room, background, lighting: describe in exhaustive visual detail in prose "
                "(derived from motion analysis, no video tag)."
            )
    else:
        env_src = (
            "derive from @Video1 motion reference when no environment image attached"
            if send_video_reference and has_motion
            else "describe in full visual detail in prose when no environment image attached"
        )
        lines.append(f"Environment and lighting: {env_src}")
    for i, img_idx in enumerate(layout.other_image_indices, 1):
        lines.append(f"@Image{img_idx} = additional reference {i}")
    if has_motion and send_video_reference:
        lines.append(
            "@Video1 = motion, choreography, timing, gestures, emotions, camera angle and movement ONLY. "
            f"NEVER the reference actor's face, body, or hair — only movement data for {id_expr}."
        )
    elif not send_video_reference:
        lines.append(
            "NO @Video tags: motion timeline is embedded as plain cinematic prose with `[t s]` markers — "
            "never mention reference video, source clip, or any video tag."
        )
    return "\n".join(lines)


def append_boardstory_prompt_enforcement(
    prompt: str,
    *,
    layout: BoardStoryReferenceLayout,
    clothing_from_video: bool,
    environment_from_video: bool,
    send_video_reference: bool = True,
) -> str:
    """Добавляет явные строки, если Grok пропустил ключевые правила."""
    import re

    body = (prompt or "").strip()
    extra: list[str] = []
    id_expr = layout.identity_tag_expr or "@Image1"

    if send_video_reference:
        low = body.lower()
        if "replace" not in low and "replacement" not in low:
            extra.append(
                "Replace the performer in @Video1 with @Image1 (primary face anchor) — "
                "same choreography, different person."
            )
        if layout.clothing_tag and layout.clothing_tag.lower() not in low:
            extra.append(f"Wardrobe from {layout.clothing_tag}.")
        elif clothing_from_video and "wardrobe" not in low:
            extra.append(f"Wardrobe on {id_expr} matches garments seen in @Video1.")
        if layout.environment_tag and "room" not in low and "environment" not in low:
            extra.append(f"Room and lighting from {layout.environment_tag}.")
        elif environment_from_video and "room" not in low:
            extra.append("Room, lighting, and background match @Video1.")
        if "@video1" in low and "never" not in low and "not copy" not in low:
            extra.append(
                f"From @Video1 take ONLY motion, timing, gestures, and camera — "
                f"never the reference actor's face or body."
            )
    else:
        body = re.sub(r"@Video\d+\b", "", body)
        body = re.sub(r"\s{2,}", " ", body).strip()
        low = body.lower()
        if id_expr.lower() not in low:
            extra.append(f"Lead character from {id_expr}.")
        if layout.clothing_tag and layout.clothing_tag.lower() not in low:
            extra.append(f"Wardrobe from {layout.clothing_tag}.")
        elif clothing_from_video and "wardrobe" not in low:
            extra.append("Wardrobe described in full visual detail.")
        if layout.environment_tag and "room" not in low and "environment" not in low:
            extra.append(f"Room and lighting from {layout.environment_tag}.")
        elif environment_from_video and "room" not in low:
            extra.append("Room and lighting described in full visual detail.")
        if "@video" in low or "reference video" in low or "motion reference" in low:
            body = re.sub(r"\breference video\b", "scene", body, flags=re.I)
            body = re.sub(r"\bmotion reference\b", "choreography", body, flags=re.I)

    if not extra:
        return body
    return f"{body}\n\n{' '.join(extra)}".strip()


def boardstory_model_swap_lock_text(
    layout: BoardStoryReferenceLayout,
) -> str:
    """Жёсткая строка swap для Seedance T2V (prepend к grok/ручным промптам)."""
    parts: list[str] = [
        "MODEL REPLACEMENT: Replace the person in @Video1 with @Image1 "
        "(primary face anchor from model photos — NOT the video actor).",
    ]
    if layout.n_model_images >= 2:
        parts.append("@Image2 supports character-sheet proportions.")
    if layout.n_model_images >= 3:
        parts.append("@Image3 supports body silhouette.")
    if layout.clothing_tag:
        parts.append(f"Outfit from {layout.clothing_tag}.")
    if layout.environment_tag:
        parts.append(f"Scene from {layout.environment_tag}.")
    parts.append(
        "@Video1 supplies motion, timing, gestures, emotions, and camera ONLY — "
        "never the reference actor's face or body."
    )
    return " ".join(parts)


def finalize_boardstory_t2v_prompt(
    prompt: str,
    *,
    layout: BoardStoryReferenceLayout | None = None,
    n_motion_videos: int = 0,
    max_chars: int | None = None,
) -> str:
    """Финализация BoardStory-промпта перед Seedance T2V: swap-lead + motion lock."""
    from app.services.studio_seedance_t2v import truncate_seedance_t2v_prompt

    body = (prompt or "").strip()
    if not body:
        return ""

    if layout is not None and n_motion_videos > 0:
        body = append_boardstory_prompt_enforcement(
            body,
            layout=layout,
            clothing_from_video=layout.n_clothing_images == 0,
            environment_from_video=layout.n_environment_images == 0,
            send_video_reference=True,
        )

    low = body.lower()
    parts: list[str] = []
    if n_motion_videos > 0 and "model replacement" not in low:
        if layout is not None:
            parts.append(boardstory_model_swap_lock_text(layout))
        else:
            parts.append(
                "MODEL REPLACEMENT: Replace the person in @Video1 with @Image1 "
                "(face, body, hair from model photos — NOT the video actor). "
                "@Video1 supplies motion, timing, gestures, and camera ONLY."
            )

    parts.append(body)

    if n_motion_videos > 0 and "motion only" not in low and "only motion" not in low:
        parts.append(
            "MOTION LOCK: @Video1 — choreography and camera ONLY; "
            "on-screen person is @Image1 in every frame."
        )

    lim = max_chars if max_chars is not None else None
    return truncate_seedance_t2v_prompt("\n\n".join(parts).strip(), max_chars=lim)


def append_boardstory_video_fallback_lines(
    prompt: str, *, clothing_from_video: bool, environment_from_video: bool
) -> str:
    """Deprecated alias — use append_boardstory_prompt_enforcement."""
    layout = compute_boardstory_layout(1, has_clothing=False, has_environment=False)
    return append_boardstory_prompt_enforcement(
        prompt,
        layout=layout,
        clothing_from_video=clothing_from_video,
        environment_from_video=environment_from_video,
        send_video_reference=True,
    )


def workflow_reference_public_url(
    *,
    owner_id: int,
    ref_id: str,
    public_app_base: str,
    token_factory,
) -> str | None:
    base = (public_app_base or "").strip().rstrip("/")
    rid = (ref_id or "").strip()
    if not base or not rid:
        return None
    tok = token_factory(user_id=owner_id, ref_id=rid)
    return f"{base}/api/studio/public-workflow-ref?t={quote(tok, safe='')}"


def build_boardstory_opening_frame_t2v_prompt(
    *,
    layout: BoardStoryReferenceLayout,
    n_motion_videos: int = 1,
    user_notes: str = "",
    negative: str | None = None,
    max_chars: int | None = None,
) -> str:
    """Seedance T2V с @Image1 = swapped opening still, @Image2+ = model refs, @Video1 = motion."""
    from app.services.studio_seedance_t2v import (
        _IDENTITY_NEGATIVE_DEFAULTS,
        truncate_seedance_t2v_prompt,
    )

    identity_tags = layout.identity_tag_expr or "@Image2"
    parts: list[str] = [
        "MODEL REPLACEMENT: Replace the performer in @Video1 with the model character. "
        "The on-screen person in every frame must match the model — never the original @Video1 actor.",
        (
            "@Image1 — opening still at t=0: exact pose, framing, lighting, and wardrobe from the "
            "motion reference, with the MODEL's face and body (not the video actor)."
        ),
        f"Reinforce character identity from {identity_tags}.",
    ]
    if layout.clothing_tag:
        parts.append(f"Wardrobe from {layout.clothing_tag}.")
    if layout.environment_tag:
        parts.append(f"Room, background, and lighting from {layout.environment_tag}.")
    if n_motion_videos > 0:
        parts.append(
            "@Video1 — motion, timing, gestures, emotions, and camera movement ONLY. "
            "Never copy the reference actor's face, skin, hair, or body from @Video1."
        )
    notes = (user_notes or "").strip()
    if notes:
        parts.append(f"USER_DIRECTION:\n{notes}")
    neg_parts = [_IDENTITY_NEGATIVE_DEFAULTS]
    if (negative or "").strip():
        neg_parts.append(negative.strip())
    parts.append(f"Avoid: {'; '.join(neg_parts)}")
    return truncate_seedance_t2v_prompt("\n\n".join(parts), max_chars=max_chars)


def build_boardstory_reference_urls(
    *,
    owner_id: int,
    public_app_base: str,
    model_image_urls: list[str],
    clothing_slot: BoardStoryImageSlot | None,
    environment_slot: BoardStoryImageSlot | None,
    extra_refs: tuple[_ExtraRef, ...],
    generation_url_factory,
    workflow_ref_url_factory,
    opening_still_url: str | None = None,
) -> tuple[list[str], BoardStoryReferenceLayout]:
    """
    Порядок reference_images для Seedance BoardStory:
    [opening still] → model identity → clothing → environment → other refs.
    """
    urls: list[str] = list(model_image_urls)
    n_model = len(urls)
    n_start = 0

    clothing_url: str | None = None
    if clothing_slot is not None:
        if clothing_slot.generation_id is not None:
            clothing_url = generation_url_factory(clothing_slot.generation_id)
        elif clothing_slot.ref_id:
            clothing_url = workflow_ref_url_factory(clothing_slot.ref_id)
        if clothing_url:
            urls.append(clothing_url)

    environment_url: str | None = None
    if environment_slot is not None:
        if environment_slot.generation_id is not None:
            environment_url = generation_url_factory(environment_slot.generation_id)
        elif environment_slot.ref_id:
            environment_url = workflow_ref_url_factory(environment_slot.ref_id)
        if environment_url:
            urls.append(environment_url)

    other_count = 0
    for ref in extra_refs:
        if not (ref.ref_id or "").strip():
            continue
        u = workflow_ref_url_factory(ref.ref_id)
        if u:
            urls.append(u)
            other_count += 1

    if opening_still_url:
        urls.insert(0, opening_still_url.strip())
        n_start = 1

    if len(urls) > MAX_SEEDANCE_REFERENCE_IMAGES:
        urls = urls[:MAX_SEEDANCE_REFERENCE_IMAGES]

    layout = compute_boardstory_layout(
        n_model,
        has_clothing=clothing_url is not None,
        has_environment=environment_url is not None,
        n_other=other_count,
        n_start_frame=n_start,
    )
    return urls, layout


def boardstory_slot_from_json(raw: dict[str, Any] | None) -> BoardStoryImageSlot | None:
    if not isinstance(raw, dict):
        return None
    gen_raw = raw.get("generation_id")
    generation_id: int | None = None
    if gen_raw is not None and str(gen_raw).strip():
        try:
            generation_id = int(gen_raw)
        except (TypeError, ValueError):
            generation_id = None
    ref_id = str(raw.get("ref_id") or "").strip() or None
    if generation_id is None and ref_id is None:
        return None
    return BoardStoryImageSlot(
        kind=str(raw.get("kind") or "other"),
        generation_id=generation_id,
        ref_id=ref_id,
        role=str(raw.get("role") or ""),
        description=str(raw.get("description") or ""),
    )


def boardstory_slot_to_json(slot: BoardStoryImageSlot | None) -> dict[str, str]:
    if slot is None:
        return {}
    out: dict[str, str] = {"kind": slot.kind}
    if slot.generation_id is not None:
        out["generation_id"] = str(slot.generation_id)
    if slot.ref_id:
        out["ref_id"] = slot.ref_id
    if slot.role:
        out["role"] = slot.role
    if slot.description:
        out["description"] = slot.description
    return out
