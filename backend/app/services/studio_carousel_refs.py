"""Multi-ref bundle для карусели: master + face + outfit + genitals (NSFW)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudioGeneration, UserStudioModel, UserStudioModelImage
from app.services.studio_image_token import (
    create_generation_image_access_token,
    create_model_image_access_token,
)
from app.services.studio_model_images import (
    profile_gen_image_kind_caption,
    select_prompt_only_wavespeed_identity_images,
)
from app.services.studio_outfit_anchor import find_outfit_generation_for_master
from app.services.studio_seedance_t2v import generation_still_public_url

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CarouselRefSlot:
    """Один ref-слот с индексом @ImageN для WaveSpeed prompt."""
    index: int
    url: str
    role: str
    label: str


@dataclass
class CarouselReferenceBundle:
    """Набор URL и подписей для multi-ref карусели."""
    slots: list[CarouselRefSlot] = field(default_factory=list)
    outfit_generation_id: int | None = None
    use_multi_ref: bool = False
    carousel_mode: str = "standard"

    @property
    def image_urls(self) -> list[str]:
        return [s.url for s in self.slots if s.url]

    def prompt_binding_block(self) -> str:
        if not self.slots:
            return ""
        lines = [
            "[REFERENCE IMAGES — bind strictly by @ImageN; do not swap roles]",
        ]
        for slot in self.slots:
            lines.append(f"@Image{slot.index} — {slot.label}")
        return "\n".join(lines)


async def resolve_carousel_reference_bundle(
    session: AsyncSession,
    *,
    owner_id: int,
    public_app_base: str,
    master_row: StudioGeneration | None,
    master_url: str,
    studio_model: UserStudioModel | None,
    wave_profile: str,
    carousel_mode: str,
) -> CarouselReferenceBundle:
    """
    Собирает refs для карусели.
    Порядок: master → face → outfit → genitals (NSFW story).
    Без модели — только master (legacy).
    """
    mode = (carousel_mode or "standard").strip().lower()
    wp = (wave_profile or "nsfw").strip().lower()
    is_nsfw_story = mode in ("story_nsfw", "nsfw_story") or (
        mode == "auto" and wp == "nsfw"
    )

    bundle = CarouselReferenceBundle(carousel_mode="story_nsfw" if is_nsfw_story else "standard")
    slots: list[CarouselRefSlot] = []

    # Image 1 — master: pose/composition/camera base для этого кадра.
    slots.append(
        CarouselRefSlot(
            index=1,
            url=master_url,
            role="master",
            label=(
                "MASTER FRAME: pose, camera angle, crop, scene composition, lighting "
                "for this carousel shot. Apply SHOT_VARIATION to this base."
            ),
        )
    )

    if studio_model is None or not studio_model.images:
        bundle.slots = slots
        return bundle

    imgs: list[UserStudioModelImage] = list(studio_model.images or [])
    identity = select_prompt_only_wavespeed_identity_images(imgs, wave_profile=wp)
    by_kind: dict[str, UserStudioModelImage] = {}
    for im in identity:
        k = (im.image_kind or "other").lower()
        if k not in by_kind:
            by_kind[k] = im

    def _model_url(im: UserStudioModelImage) -> str | None:
        tok = create_model_image_access_token(user_id=owner_id, image_id=int(im.id))
        pub = (public_app_base or "").strip().rstrip("/")
        if not pub.lower().startswith("https://"):
            return None
        return f"{pub}/api/studio/public-model-image?t={quote(tok, safe='')}"

    next_idx = 2

    face_im = by_kind.get("face")
    if face_im is not None:
        url = _model_url(face_im)
        if url:
            cap = profile_gen_image_kind_caption("face")
            slots.append(
                CarouselRefSlot(
                    index=next_idx,
                    url=url,
                    role="face",
                    label=f"FACE IDENTITY: {cap}. Keep exact face, hair, skin — no drift.",
                )
            )
            next_idx += 1

    outfit_url: str | None = None
    outfit_gid: int | None = None
    if master_row is not None:
        outfit_gid = await find_outfit_generation_for_master(session, master_row)
    if outfit_gid is not None:
        outfit_url = generation_still_public_url(
            owner_id=owner_id,
            generation_id=outfit_gid,
            public_app_base=public_app_base,
            token_factory=create_generation_image_access_token,
        )
    if outfit_url:
        slots.append(
            CarouselRefSlot(
                index=next_idx,
                url=outfit_url,
                role="outfit",
                label=(
                    "OUTFIT & BODY: exact clothing, fit, body proportions and silhouette "
                    "from this dressed reference. Wardrobe locked unless SHOT_VARIATION "
                    "explicitly describes a story wardrobe beat."
                ),
            )
        )
        next_idx += 1
        bundle.outfit_generation_id = outfit_gid
    else:
        body_im = by_kind.get("body")
        if body_im is not None:
            url = _model_url(body_im)
            if url:
                slots.append(
                    CarouselRefSlot(
                        index=next_idx,
                        url=url,
                        role="body",
                        label=(
                            "BODY REFERENCE: silhouette, proportions, body mass. "
                            "Combine with face and master outfit cues."
                        ),
                    )
                )
                next_idx += 1

    if is_nsfw_story or wp == "nsfw":
        gen_im = by_kind.get("genitals")
        if gen_im is not None:
            url = _model_url(gen_im)
            if url:
                cap = profile_gen_image_kind_caption("genitals")
                slots.append(
                    CarouselRefSlot(
                        index=next_idx,
                        url=url,
                        role="genitals",
                        label=(
                            f"INTIMATE ANATOMY (NSFW): {cap}. Use for correct anatomy when "
                            "clothing reveals or story beat requires; do not copy pose from this image."
                        ),
                    )
                )
                next_idx += 1

    bundle.slots = slots
    bundle.use_multi_ref = len(slots) > 1
    log.info(
        "carousel refs owner=%s slots=%s outfit_gid=%s mode=%s",
        owner_id,
        [(s.role, s.index) for s in slots],
        outfit_gid,
        bundle.carousel_mode,
    )
    return bundle
