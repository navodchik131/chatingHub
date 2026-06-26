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
    filter_model_images_for_seedance_video,
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
) -> BoardStoryReferenceLayout:
    idx = n_model + 1
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

    identity = seedance_model_identity_tag_expr(0, n_model)
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
    """BoardStory: только одна развёртка (turnaround) из кабинета модели."""
    return filter_model_images_for_seedance_video(
        imgs,
        minimal=True,
        max_identity=1,
    )


def boardstory_tag_rules_text(
    layout: BoardStoryReferenceLayout,
    *,
    has_motion: bool,
    clothing_from_video: bool = False,
    environment_from_video: bool = False,
) -> str:
    lines: list[str] = []
    if layout.identity_tag_expr:
        lines.append(
            f"{layout.identity_tag_expr} = model identity ONLY (face, body, hair from model turnaround sheet — "
            "NOT clothing, NOT room)"
        )
    if layout.clothing_tag:
        lines.append(f"{layout.clothing_tag} = clothing / wardrobe reference (garments only)")
    elif clothing_from_video:
        lines.append(
            "Wardrobe and outfit: take EXCLUSIVELY from @Video1 motion reference — "
            "match glittery top, pants, fabric, and colors seen in the video. "
            "Do NOT describe wardrobe on @Image identity refs."
        )
    else:
        lines.append("Wardrobe: derive from @Video1 motion reference when no clothing image attached")
    if layout.environment_tag:
        lines.append(f"{layout.environment_tag} = environment / room / lighting reference (scene plate only)")
    elif environment_from_video:
        lines.append(
            "Room, background, lighting, and ambient glow: take EXCLUSIVELY from @Video1 — "
            "same intimate interior, plush textures, soft illumination as in the video. "
            "Do NOT invent a different location."
        )
    else:
        lines.append(
            "Environment and lighting: derive from @Video1 motion reference when no environment image attached"
        )
    for i, img_idx in enumerate(layout.other_image_indices, 1):
        lines.append(f"@Image{img_idx} = additional reference {i}")
    if has_motion:
        id_expr = layout.identity_tag_expr or ""
        lines.append(
            "@Video1 = motion, choreography, timing, gestures, emotions, camera movement ONLY "
            f"(character appearance from {id_expr or 'model @Image'}; "
            "wardrobe/room from rules above — never copy reference video actor face)"
        )
    return "\n".join(lines)


def append_boardstory_video_fallback_lines(prompt: str, *, clothing_from_video: bool, environment_from_video: bool) -> str:
    """Добавляет явные строки про @Video1, если Grok их пропустил."""
    body = (prompt or "").strip()
    extra: list[str] = []
    if clothing_from_video and "wardrobe" not in body.lower() and "@video1" in body.lower():
        extra.append("Wardrobe and outfit match @Video1.")
    if environment_from_video and "environment" not in body.lower() and "room" not in body.lower():
        extra.append("Room, lighting, and background match @Video1.")
    if not extra:
        return body
    return f"{body}\n\n{' '.join(extra)}".strip()


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
) -> tuple[list[str], BoardStoryReferenceLayout]:
    """
    Порядок reference_images для Seedance BoardStory:
    model identity → clothing → environment → other refs.
    """
    urls: list[str] = list(model_image_urls)
    n_model = len(urls)

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

    if len(urls) > MAX_SEEDANCE_REFERENCE_IMAGES:
        urls = urls[:MAX_SEEDANCE_REFERENCE_IMAGES]

    layout = compute_boardstory_layout(
        n_model,
        has_clothing=clothing_url is not None,
        has_environment=environment_url is not None,
        n_other=other_count,
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
