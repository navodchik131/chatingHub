"""Тесты multi-ref карусели и outfit anchor."""

from __future__ import annotations


def test_build_carousel_multi_ref_wave_prompt_includes_bindings():
    from app.services.studio_carousel import build_carousel_multi_ref_wave_prompt

    p = build_carousel_multi_ref_wave_prompt(
        master_scene_context="beach sunset",
        shot_variation="STORY_BEAT: lift hem slightly; camera closer",
        ref_binding_block="@Image2 — FACE\n@Image3 — OUTFIT",
        story_nsfw=True,
    )
    assert "@Image2" in p
    assert "NSFW_STORY" in p
    assert "lift hem" in p


def test_carousel_ref_bundle_prompt_binding():
    from app.services.studio_carousel_refs import CarouselRefSlot, CarouselReferenceBundle

    bundle = CarouselReferenceBundle(
        slots=[
            CarouselRefSlot(1, "https://x/master.jpg", "master", "MASTER FRAME"),
            CarouselRefSlot(2, "https://x/face.jpg", "face", "FACE"),
            CarouselRefSlot(3, "https://x/outfit.jpg", "outfit", "OUTFIT"),
            CarouselRefSlot(4, "https://x/intim.jpg", "genitals", "INTIMATE"),
        ],
        use_multi_ref=True,
        carousel_mode="story_nsfw",
    )
    assert len(bundle.image_urls) == 4
    block = bundle.prompt_binding_block()
    assert "@Image4" in block
    assert "INTIMATE" in block


def test_generation_is_outfit_anchor():
    from types import SimpleNamespace

    from app.services.studio_outfit_anchor import (
        generation_is_hidden_outfit_anchor,
        generation_is_outfit_anchor,
    )

    assert generation_is_outfit_anchor(
        SimpleNamespace(prompt_excerpt="[Outfit anchor]", refined_prompt="")
    )
    assert generation_is_outfit_anchor(
        SimpleNamespace(prompt_excerpt="", refined_prompt="Motion Control dress")
    )
    assert not generation_is_outfit_anchor(
        SimpleNamespace(prompt_excerpt="random shot", refined_prompt="")
    )
    assert generation_is_hidden_outfit_anchor(
        SimpleNamespace(prompt_excerpt="[Outfit anchor] anchor mode A", refined_prompt="")
    )
    assert not generation_is_hidden_outfit_anchor(
        SimpleNamespace(prompt_excerpt="", refined_prompt="Motion Control dress")
    )


def test_find_studio_generation_by_job_id_skips_hidden_outfit_anchor():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from app.services.studio_generation_placeholders import find_studio_generation_by_job_id

    outfit = SimpleNamespace(id=102, prompt_excerpt="[Outfit anchor]", refined_prompt="")
    main = SimpleNamespace(id=101, prompt_excerpt="beach scene", refined_prompt="")

    session = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [outfit, main]
    session.execute = AsyncMock(return_value=result)

    import asyncio

    row = asyncio.run(find_studio_generation_by_job_id(session, 55))
    assert row is main
