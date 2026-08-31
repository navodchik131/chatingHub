"""Run Anchor Studio wardrobe-prep + Mode A/B prompt assembly for cabinet swap/ref."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.config import settings
from app.services.studio_anchor_pipeline import (
    DRESS_BODY_PROMPT,
    SCENE_ANALYSIS_PROMPT,
    AnchorVisibility,
    anchor_mode_a_scene_first,
    build_mode_a_face_closeup_prompt,
    build_mode_a_prompt,
    build_mode_b_prompt,
    detect_face_closeup_from_bytes,
    detect_face_closeup_scene,
    dressed_body_cache_key,
    filter_anchor_by_visibility,
    load_cached_dressed_body,
    order_mode_a_face_closeup_urls,
    order_mode_a_image_urls,
    parse_visibility_from_scene_text,
    pick_face_and_body_images,
    profile_text_to_identity_anchor,
    save_cached_dressed_body,
    should_use_anchor_pipeline,
    visibility_from_identity_visibility,
)
from app.services.studio_prompt_bundle import extract_creative_notes_from_workflow_description
from app.services.studio_image_token import (
    create_model_image_access_token,
    create_pose_reference_access_token,
)
from app.services.studio_pose_reference import save_pose_reference_bytes

log = logging.getLogger(__name__)


@dataclass
class AnchorPipelineResult:
    refined_prompt: str
    image_urls: list[str]
    """WaveSpeed URL order (scene-first for WAN, identity-first for Nano)."""
    mode: str  # "A" | "B"
    dressed_from_cache: bool
    scene_description: str
    visibility: AnchorVisibility
    cache_key: str
    dressed_body_bytes: bytes | None = None
    outfit_generation_id: int | None = None
    scene_first: bool = False
    face_closeup: bool = False


async def _analyze_scene_text(
    *,
    scene_bytes: bytes,
    scene_mime: str,
    credentials: Any,
) -> str:
    import base64

    from app.config import settings
    from app.services.studio_grok_motion import _grok_fps_stills_model
    from app.services.studio_grok_scene_compose import grok_scene_compose_configured
    from app.services.studio_openai import chat_completion_openai_compatible_text

    if grok_scene_compose_configured():
        model = (settings.grok_scene_compose_model or "").strip() or _grok_fps_stills_model()
    else:
        model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model

    mime = (scene_mime or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"
    b64 = base64.standard_b64encode(scene_bytes).decode("ascii")
    text = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SCENE_ANALYSIS_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            },
        ],
        max_tokens=4096,
        temperature=0.2,
        credentials=credentials,
        timeout_seconds=120.0,
    )
    return (text or "").strip()


async def _dress_body_via_wavespeed(
    *,
    api_key: str,
    body_url: str,
    scene_url: str,
    wave_profile: str,
    wan_edit_tier: str,
    wave_model_id: str,
    aspect_ratio: str = "9:16",
) -> bytes:
    from app.services.studio_shot_batch_render import _download_url_bytes
    from app.services.wavespeed_client import workflow_edit_image_url

    model = (wave_model_id or "").strip() or (
        "wan-2.7" if (wave_profile or "").lower() == "nsfw" else "nano-banana-pro"
    )
    result = await workflow_edit_image_url(
        api_key=api_key,
        wave_model_id=model,
        image_urls=[body_url, scene_url],
        prompt=DRESS_BODY_PROMPT,
        aspect_ratio=aspect_ratio or "9:16",
        wan_edit_tier=wan_edit_tier or "standard",
        wave_profile=wave_profile,
    )
    url = str(getattr(result, "url", "") or "").strip()
    if not url:
        raise RuntimeError("wardrobe prep: empty WaveSpeed result URL")
    raw = await _download_url_bytes(url)
    if not raw or len(raw) < 64:
        raise RuntimeError("wardrobe prep: empty downloaded image")
    return raw


async def run_anchor_pipeline(
    *,
    studio_mode: str,
    owner_id: int,
    model_id: int,
    model_images: list[Any],
    model_profile_text: str | None,
    scene_bytes: bytes,
    scene_mime: str,
    user_notes: str = "",
    identity_visibility: Any = None,
    existing_scene_description: str | None = None,
    llm_credentials: Any = None,
    wavespeed_api_key: str,
    wave_profile: str = "nsfw",
    wan_edit_tier: str = "standard",
    wave_model_id: str = "",
    aspect_ratio: str = "9:16",
    force_redress: bool = False,
    lock_hairstyle_style: bool = True,
) -> AnchorPipelineResult | None:
    """
    Returns None if mode shouldn't use anchor pipeline.
    Mode A (face_swap): final URLs = face, dressed, scene; prompt Mode A.
    Mode B (model_scene): final URLs = face, dressed; prompt Mode B with scene text.
    """
    mode_n = (studio_mode or "").strip().lower()
    if not should_use_anchor_pipeline(
        studio_mode=mode_n,
        has_scene_bytes=bool(scene_bytes),
        has_model=model_id > 0 and bool(model_images),
    ):
        return None

    face_im, body_im = pick_face_and_body_images(model_images)
    if face_im is None or body_im is None:
        log.warning("anchor pipeline: missing face/body for model_id=%s", model_id)
        return None

    pub = (settings.public_app_url or "").strip().rstrip("/")
    if not pub.lower().startswith("https://"):
        raise RuntimeError("PUBLIC_APP_URL must be https:// for anchor pipeline")

    scene_description = (existing_scene_description or "").strip()
    # Для face_swap всегда анализируем сцену — нужны VISIBILITY и close-up для выбора режима.
    looks_like_html_scene = bool(
        scene_description
        and re.search(r"(?im)^ENVIRONMENT\s*:", scene_description)
        and re.search(r"(?im)^VISIBILITY\s*:", scene_description)
    )
    if llm_credentials is not None and (mode_n == "face_swap" or not looks_like_html_scene):
        try:
            scene_description = await _analyze_scene_text(
                scene_bytes=scene_bytes,
                scene_mime=scene_mime,
                credentials=llm_credentials,
            )
        except Exception as e:
            log.warning("anchor scene analysis failed: %s", e)
            if not scene_description:
                scene_description = ""

    if scene_description and re.search(r"(?im)^VISIBILITY\s*:", scene_description):
        vis = parse_visibility_from_scene_text(scene_description)
    else:
        vis = visibility_from_identity_visibility(identity_visibility)

    face_closeup = mode_n == "face_swap" and detect_face_closeup_scene(
        vis, scene_description
    )
    if mode_n == "face_swap" and not face_closeup:
        face_closeup = detect_face_closeup_from_bytes(scene_bytes)

    anchor = profile_text_to_identity_anchor(model_profile_text)
    filtered = filter_anchor_by_visibility(anchor, vis) if anchor else ""
    # Только SCENE_DIRECTION / пользовательские заметки — без REFERENCE_CONTEXT из workflow.
    notes = extract_creative_notes_from_workflow_description(user_notes)

    cache_key = dressed_body_cache_key(
        model_id=model_id,
        face_image_id=getattr(face_im, "id", None),
        body_image_id=getattr(body_im, "id", None),
        scene_bytes=scene_bytes,
        vis=vis,
    )

    dressed_bytes: bytes | None = None
    from_cache = False
    if not force_redress:
        dressed_bytes = load_cached_dressed_body(cache_key)
        from_cache = dressed_bytes is not None

    face_tok = create_model_image_access_token(user_id=owner_id, image_id=int(face_im.id))
    body_tok = create_model_image_access_token(user_id=owner_id, image_id=int(body_im.id))
    face_url = f"{pub}/api/studio/public-model-image?t={quote(face_tok, safe='')}"
    body_url = f"{pub}/api/studio/public-model-image?t={quote(body_tok, safe='')}"

    scene_fid = save_pose_reference_bytes(
        owner_id=owner_id,
        raw=scene_bytes,
        content_type=scene_mime or "image/jpeg",
    )
    scene_tok = create_pose_reference_access_token(user_id=owner_id, file_id=scene_fid)
    scene_url = f"{pub}/api/studio/public-pose-reference?t={quote(scene_tok, safe='')}"

    dressed_url = ""
    if not face_closeup:
        if dressed_bytes is None:
            log.info(
                "anchor wardrobe prep model=%s key=%s…",
                model_id,
                cache_key[:12],
            )
            dressed_bytes = await _dress_body_via_wavespeed(
                api_key=wavespeed_api_key,
                body_url=body_url,
                scene_url=scene_url,
                wave_profile=wave_profile,
                wan_edit_tier=wan_edit_tier,
                wave_model_id=wave_model_id,
                aspect_ratio=aspect_ratio,
            )
            save_cached_dressed_body(
                cache_key,
                dressed_bytes,
                meta={"model_id": model_id, "mode": mode_n},
            )

        dressed_fid = save_pose_reference_bytes(
            owner_id=owner_id,
            raw=dressed_bytes,
            content_type="image/jpeg",
        )
        dressed_tok = create_pose_reference_access_token(user_id=owner_id, file_id=dressed_fid)
        dressed_url = f"{pub}/api/studio/public-pose-reference?t={quote(dressed_tok, safe='')}"
    else:
        log.info("anchor face close-up: skip wardrobe prep model=%s", model_id)
        dressed_bytes = None
        from_cache = False

    scene_first = False
    if mode_n == "face_swap":
        scene_first = anchor_mode_a_scene_first(wave_profile=wave_profile)
        if face_closeup:
            prompt = build_mode_a_face_closeup_prompt(
                filtered_anchor=filtered or anchor,
                vis=vis,
                notes=notes,
                lock_hairstyle_style=lock_hairstyle_style,
                scene_first=scene_first,
            )
            urls = order_mode_a_face_closeup_urls(
                face_url=face_url,
                scene_url=scene_url,
                scene_first=scene_first,
                duplicate_face=scene_first,
            )
        else:
            prompt = build_mode_a_prompt(
                filtered_anchor=filtered or anchor,
                vis=vis,
                notes=notes,
                lock_hairstyle_style=lock_hairstyle_style,
                scene_first=scene_first,
            )
            urls = order_mode_a_image_urls(
                face_url=face_url,
                dressed_url=dressed_url,
                scene_url=scene_url,
                scene_first=scene_first,
            )
        out_mode = "A"
    else:
        # Mode B — scene as text only
        if not scene_description:
            scene_description = (
                "Recreate the uploaded reference photo's pose, camera, framing, lighting, "
                "and environment exactly — without copying the original person's identity."
            )
        prompt = build_mode_b_prompt(
            filtered_anchor=filtered or anchor,
            scene_description=scene_description,
            vis=vis,
            notes=notes,
            lock_hairstyle_style=lock_hairstyle_style,
        )
        urls = [face_url, dressed_url]
        out_mode = "B"

    return AnchorPipelineResult(
        refined_prompt=prompt,
        image_urls=urls,
        mode=out_mode,
        dressed_from_cache=from_cache,
        scene_description=scene_description,
        visibility=vis,
        cache_key=cache_key,
        dressed_body_bytes=dressed_bytes,
        scene_first=scene_first if mode_n == "face_swap" else False,
        face_closeup=face_closeup if mode_n == "face_swap" else False,
    )
