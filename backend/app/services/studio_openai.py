from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import BACKEND_DIR, settings
from app.services.studio_aspect import aspect_user_block_english

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class StudioOpenAiCredentials:
    api_key: str
    base_url: str
    organization: str = ""


def _wavespeed_pose_ref_prefix(*, lock_model_hairstyle: bool) -> str:
    hair_clause = (
        "**Hairstyle (braids, loose, bun, etc.) follows the JSON brief / model identity — not this image.** "
        if lock_model_hairstyle
        else "hair styling as in that shot, "
    )
    return (
        "[REFERENCE_IMAGE_ORDER] The first image is the user's uploaded pose/scene reference. "
        "Take from it: **full spatial geometry** — pose articulation (hands, limbs, torso), **head tilt/yaw/chin pitch and gaze vs lens when visible**, "
        "camera angle/height/distance, framing, lens feel, **and the shading pattern how light wraps the figure** (same highlight/shadow layout on neck, shoulders, "
        "torso and face when both appear — scene light only), "
        f"{hair_clause}"
        "background and environmental lighting quality. "
        "Garments and body coverage must match only this first image — do not dress the subject from the "
        "other images. If the first image shows no clothing or partial nudity, keep the same coverage (nude/topless/etc.). "
        "**Do not do a face-swap:** synthesize **one cohesive person** in this scene. Silhouette, proportions, and **all visible skin** "
        "(face, neck, chest, arms, torso, legs) must match the identity reference images (following URLs) continuously — same MODEL tone, "
        "same grain, **same light falloff** on face and body (reference **direction**, not donor complexion). "
        "Following image(s): the saved model only for **who** this person is (face + body identity); "
        "**never** copy pose, camera, framing, shading layout, or outfit from those images — those come only from the first image.\n\n"
    )


def _wavespeed_pose_ref_prefix_no_face(*, lock_model_hairstyle: bool) -> str:
    hair_clause = (
        "**Hairstyle follows the JSON brief / model — not this crop image** (often hair is out of frame). "
        if lock_model_hairstyle
        else "hair styling as in that shot when hair is visible in frame, "
    )
    return (
        "[REFERENCE_IMAGE_ORDER — NO_FACE / CROP_LOCKED] The **first** image is the user's uploaded **framing** reference (pose slice, "
        "legs/feet/hands/torso crop, etc.). **Match its edges and scale:** do **not** zoom out, reframe wider, or **add a head/face** "
        "if this image omits them — model reference photos must **not** be used to paste or reconstruct a face into empty headroom. "
        "Take from the first image only: **visible** limb articulation **and joint angles**, camera angle/height/distance, **exact crop**, lens feel, **light wrap on visible volumes**, "
        f"{hair_clause}"
        "background and lighting quality. Garments/coverage only from the first image. "
        "**Later** image(s): **body identity for visible skin only** — continuous skin tone/texture on legs, feet, arms, hands, "
        "visible torso slices **as one person**; **not** a face-swap and **not** inventing facial features where the crop has none. "
        "**Never** copy pose, framing, shading, or outfit from model references.\n\n"
    )


def wavespeed_prompt_with_face_swap_first(
    refined_prompt: str,
    *,
    lock_model_hairstyle: bool = True,
) -> str:
    """WAN: первое фото — сцена/донор; следующие URL — студийная модель (целевая личность)."""
    hair_clause = (
        "**Hairstyle** (cut/color/texture) берётся из JSON-брифа и thumbnails модели — не как у незнакомого человека на Image 1. "
        if lock_model_hairstyle
        else "Причёска может оставаться ближе к исходному кадру, если это явно нужно пользователю; "
    )
    prefix = (
        "[FACE_SWAP — WAN] **Image 1** is the **SOURCE snapshot** (scene + incidental sitter framing). "
        "Following URL(s): **studio portraits of OUR target MODEL** — **WHO only**. "
        "**Replace** recognizable face and every visible epidermis region of the Image‑1 performer with MODEL identity continuously — "
        "same underlying undertone and highlight texture **as one person** chin→neck→upper chest/decollete→arms/legs in **this** lighting. "
        "**Harmonize** white balance and subsurface dispersion so cheeks / shoulders / torso **do not** read like mismatched halves. "
        "Preserve strictly from Image 1: **camera geometry** (FoV crop, viewpoint, body/head yaw, gaze vs lens), limb articulation, garment seams, shadows on fabric/plastic — "
        "**not** micro-skin pigmentation from the incidental sitter — MODEL thumbnails supply complexion/identity. "
        f"{hair_clause}"
        "**No** residual stranger facial microtexture; thumbnails win for likeness; Image 1 defines room + illumination topology.\n\n"
    )
    p = (refined_prompt or "").strip()
    if not p:
        return prefix.strip()
    return prefix + p


def wavespeed_prompt_with_user_pose_reference_first(
    refined_prompt: str,
    *,
    lock_model_hairstyle: bool = True,
    no_face_framing: bool = False,
) -> str:
    """Префикс к финальному промпту WaveSpeed, когда первый URL — загруженный пользователем референс."""
    if no_face_framing:
        prefix = _wavespeed_pose_ref_prefix_no_face(lock_model_hairstyle=lock_model_hairstyle)
    else:
        prefix = _wavespeed_pose_ref_prefix(lock_model_hairstyle=lock_model_hairstyle)
    p = (refined_prompt or "").strip()
    if not p:
        return prefix.strip()
    return prefix + p


_WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX = (
    "[EDIT_BASE — single image only] Exactly **one** input image: the user's **existing photograph**. "
    "**No** supplementary identity-reference photos are supplied — synthesize edits from **this bitmap alone**. "
    "Apply **only** the scene changes described by the structured JSON brief and USER edits (colors, garments, backdrop, "
    "minor lighting, clean-up, removals, small pose tweaks **if explicitly requested**) while keeping the **same person** "
    "— continuous skin grain, plausible anatomy — **avoid** swapping in a different face or body donor. "
    "Do **not** zoom/reframe drastically unless USER_TEXT asks; preserve shot scale when unspecified.\n\n"
)

_WAVESPEED_NO_FACE_SUFFIX = (
    "\n\n[FRAMING] Do not show the subject's face or head unless the reference crop / JSON brief clearly includes them. "
    "Prefer crops on legs, feet, lower body, hands, or torso without head. "
    "Do **not** widen the shot, zoom out, or add headroom to introduce a face. "
    "Do not add, restore, reconstruct, or composite a face from model reference images into a headless crop."
)


_WAN_COMPACT_POSE_PREFIX = (
    "[POSE_REF=image 1 — PRIMARY] Match pose geometry (head yaw, gaze, limb angles, hands), crop, camera, "
    "background, lighting, and wardrobe/body coverage EXACTLY from image 1 and JSON wardrobe_coverage. "
    "Do NOT copy donor body mass from image 1 — use MODEL proportions for silhouette. "
    "[IDENTITY=images 2+ and JSON] Face, skin tone, hair, body proportions only — "
    "NEVER copy clothing, sportswear, lingerie, or neutral studio outfit from images 2+ or profile default_style. "
    "If image 1 is nude/topless, output the same bare coverage; do not dress the subject.\n\n"
)

_GROK_COMPOSED_WAN_PREFIX = (
    "[GROK_SCENE_COMPOSE — NOT face-swap] **Image 1** = pose/scene bitmap: pose geometry, camera, framing, "
    "background, environmental light, and wardrobe/nudity zones ONLY. "
    "Do **not** copy donor face, skin tone, bust/waist/hip mass, muscle definition, or limb thickness from image 1. "
    "**Images 2+** = MODEL identity (face likeness, nude anatomy when present, clothed body ref when present). "
    "Rebuild **one continuous person**: unified skin undertone and grain from face through neck, chest, and limbs; "
    "**no** pasted head, **no** composite collage. "
    "Figure volumes (bust, waist, hips) = JSON FIGURE_LOCK / scene_brief + identity images — not image 1.\n\n"
)

_GROK_MODEL_SCENE_WAN_PREFIX = (
    "[MODEL_SCENE — identity-first compose] **Image 1** = POSE_LOCK bitmap only: match pose articulation, head yaw/gaze, "
    "camera angle/height/distance, crop edges, background, environmental light topology, and wardrobe/nudity **coverage** "
    "from image 1 with **minimal deviation** (target: indistinguishable framing vs source). "
    "**Images 2+** = OUR saved MODEL (character sheet turnaround, body reference, face, anatomy when NSFW): "
    "**WHO** — face likeness, skin undertone/grain, bust/waist/hip width, glute volume, limb build, shoulder width. "
    "**Never** keep donor face, skin tone, or body mass from image 1 — reshape silhouette to MODEL + JSON FIGURE_LOCK. "
    "One cohesive person: seamless neck, unified complexion head→torso→limbs under **image 1's** light direction; "
    "**no** floating head, **no** face-swap paste, **no** composite collage.\n\n"
)

_GROK_COMPOSED_NANO_PREFIX = (
    "[GROK_SCENE_COMPOSE — NOT face-swap] **Earlier image(s)** = MODEL identity (face, optional anatomy/body ref). "
    "Apply **one** skin/light model on all visible skin — seamless neck and shoulders, no pasted face. "
    "**Last** image = pose/framing/light/wardrobe only — never donor body volumes or identity from last image. "
    "JSON brief (scene_brief + realism_engine) defines bust/waist/hip wording — overrides silhouette on last image.\n\n"
)

_GROK_COMPOSED_POSE_LAST_SUFFIX = (
    "\n\n[LAST_INPUT_IMAGE — POSE_REF] The **last** image locks pose geometry, crop, gaze, garments/nudity zones, "
    "and how light falls on the scene — **not** donor face or body proportions. "
    "Reshape visible body mass to match identity images + JSON FIGURE_LOCK; "
    "illuminate MODEL face/skin with the same light direction as this last image (no floating head)."
)

_GROK_TEXT_SCENE_WAN_PREFIX = (
    "[TEXT_SCENE — identity refs only] Attached images are ONE model: **body** (silhouette), **face** (likeness), "
    "optional **anatomy** (NSFW). Scene, pose, camera, background, and light come **only** from the JSON brief below "
    "(scene_brief + photography + realism_engine). "
    "Do **not** copy studio-sheet backdrop, catalog lighting, or portrait-mode bokeh from reference photos. "
    "Background must stay **natural-phone sharp/readable** unless the brief says otherwise. "
    "Face and body proportions must match references and MODEL_PROFILE — not a generic glamour model.\n\n"
)

_GROK_TEXT_SCENE_NANO_PREFIX = (
    "[TEXT_SCENE — identity refs] Earlier images = same model (**body**, **face**, optional anatomy). "
    "JSON brief below defines pose, room, camera, and light — **not** the reference photos. "
    "No heavy fake bokeh; mundane smartphone snapshot; preserve identity on all visible skin.\n\n"
)

_GROK_MAIN_PROSE_WAN_PREFIX = (
    "[MODEL_SCENE] One person — identity from attached model reference photos only. "
    "Recreate the scene exactly as described below (pose, crop, light, wardrobe). "
    "Plain phone snapshot look; natural skin texture.\n\n"
)

_GROK_MAIN_PROSE_NANO_PREFIX = (
    "[MODEL_SCENE] Attached images = one saved model (identity). "
    "Generate the scene described below — same pose, framing, and lighting. "
    "Mundane smartphone photo; no studio glamour.\n\n"
)

_WAN_COMPACT_NO_FACE_PREFIX = (
    "[POSE_REF=image 1 — crop locked] Visible limbs, framing, outfit, light: image 1 only. "
    "Identity skin on visible body from model refs + JSON; never add a face outside the crop.\n\n"
)

_NANO_COMPACT_IDENTITY_PREFIX = (
    "[IDENTITY images first, POSE_REF last] JSON `identity_reference` = WHO (face, hair, body_proportions). "
    "Last image = pose/outfit/scene/light only — ignore donor identity on last image.\n\n"
)

_NANO_TEXT_SCENE_PREFIX = (
    "[IDENTITY images only — no pose bitmap] Scene composition comes **only** from JSON "
    "(REFERENCE-derived scene fields / scene_brief). Preserve model identity on all visible skin.\n\n"
)

_NANO_COMPACT_POSE_LAST_SUFFIX = (
    "\n\n[POSE_REF last] Pose, framing, wardrobe, background, lighting: last image only."
)

_NANO_COMPACT_NO_FACE_LAST_SUFFIX = (
    "\n\n[POSE_REF last — crop locked] Match last image crop and visible-body geometry only."
)


def finalize_wavespeed_studio_prompt(
    refined_prompt: str,
    *,
    studio_mode: str,
    user_image_first: bool,
    lock_model_hairstyle: bool = True,
    prompt_brief_mode: str = "full",
) -> str:
    """Сборка финального текстового промпта для WaveSpeed в зависимости от режима студии."""
    mode = (studio_mode or "model").strip().lower()
    brief = (prompt_brief_mode or "full").strip().lower()
    p = (refined_prompt or "").strip()
    if user_image_first:
        if mode == "photo_edit":
            out = (
                _WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX.strip()
                if not p
                else _WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX + p
            )
        elif mode == "face_swap":
            out = wavespeed_prompt_with_face_swap_first(
                p,
                lock_model_hairstyle=lock_model_hairstyle,
            )
        elif brief == "grok_composed":
            prefix = (
                _GROK_MODEL_SCENE_WAN_PREFIX
                if mode == "model_scene"
                else _GROK_COMPOSED_WAN_PREFIX
            )
            out = prefix.strip() if not p else prefix + p
        elif brief == "compact_pose_image":
            prefix = (
                _WAN_COMPACT_NO_FACE_PREFIX
                if mode == "no_face"
                else _WAN_COMPACT_POSE_PREFIX
            )
            out = prefix.strip() if not p else prefix + p
        else:
            out = wavespeed_prompt_with_user_pose_reference_first(
                p,
                lock_model_hairstyle=lock_model_hairstyle,
                no_face_framing=(mode == "no_face"),
            )
    elif brief == "text_scene":
        out = (_NANO_TEXT_SCENE_PREFIX.strip() if not p else _NANO_TEXT_SCENE_PREFIX + p)
    elif brief == "grok_composed_text":
        out = _GROK_TEXT_SCENE_WAN_PREFIX.strip() if not p else _GROK_TEXT_SCENE_WAN_PREFIX + p
    elif brief == "grok_main_prose":
        out = _GROK_MAIN_PROSE_WAN_PREFIX.strip() if not p else _GROK_MAIN_PROSE_WAN_PREFIX + p
    else:
        out = p
    if mode == "no_face" and brief != "compact_pose_image":
        out = (out or "").rstrip() + _WAVESPEED_NO_FACE_SUFFIX
    return out


_NANO_BANANA_IDENTITY_LOCK_PREFIX = (
    "[MULTI_IMAGE_EDIT — same person] The first input image(s) are reference photos of ONE real person "
    "for **identity only**: face, facial structure, eyes, nose, mouth, skin tone, hairline, hair, and body "
    "proportions/shape. Do **not** use those images as the source of **pose, camera angle, focal length, "
    "framing/crop, background layout, outfit, or scene lighting** — the JSON brief (and the **last** input "
    "image when present) define composition and wardrobe. "
    "The output MUST preserve identity from these references — do not invent a different person or a generic model face. "
    "The block below is a structured scene brief (JSON); identity always wins over any vague text.\n\n"
)

_NANO_BANANA_NO_FACE_IDENTITY_PREFIX = (
    "[MULTI_IMAGE_EDIT — body identity, crop-locked] Earlier input image(s) are reference photos of ONE person for "
    "**visible-body identity** on the final canvas: skin tone, texture, limb proportions, hands/feet shape — "
    "applied **only where human body appears in the output**. "
    "Do **not** use them for pose, camera, **framing edges**, outfit, or scene light — the JSON brief plus the **last** "
    "input image (when present) define those. "
    "**If the last image crops out the head/face, the output must stay headless** — do **not** zoom out, add headroom, "
    "or synthesize a face/head from these identity references to «complete» the figure. "
    "This is **not** face-swap: do not paste the model's face into regions where the pose image shows **no face**. "
    "The block below is structured JSON; **framing from the last image** overrides any urge to show a portrait face.\n\n"
)

_NANO_BANANA_FACE_SWAP_IDENTITY_PREFIX = (
    "[MULTI_IMAGE_EDIT — intentional FACE SWAP] Earlier input image(s): **studio portraits of ONE saved MODEL — identity WHO only** "
    "(face anatomy, hairline/palette, plausible limb proportion bias, skin micro-texture family). "
    "**LAST** input image: **RGB scene photograph** you must **replace** the incidental sitter with MODEL **while keeping** LAST's "
    "**camera geometry**, **framing**, **scene lighting topology** (direction/hard highlights wrap), limbs articulation, garment/coverage. "
    "**Do not** synthesize blended «half-stranger» composites — epidermis on face/neck/visible torso/arms must read as MODEL color science illuminated by LAST ambience; "
    "match white balance/skin undertone gradients head→body so cheeks / sternum / forearms remain **chromatically cohesive**. "
    "Structured JSON + USER_TEXT below constrain mood; thumbnails win likeness over vague wording.\n\n"
)


def _nano_banana_pose_last_suffix(*, lock_model_hairstyle: bool) -> str:
    hair = (
        "**Hairstyle must follow the JSON brief (model identity), not the hair layout on this last image.** "
        if lock_model_hairstyle
        else "**Hairstyle may match the last (pose) image when the JSON says POSE_REFERENCE.** "
    )
    return (
        "\n\n[LAST_INPUT_IMAGE] The **last** input image is the **only** source for **pose geometry, framing, camera geometry, "
        "outfit/body coverage, background, and environmental lighting** in this edit — **including head tilt/yaw and gaze vs lens** when the face is in frame. "
        + hair
        + "Ignore **identity** (face shape, donor skin) on that last image — the subject must match only the earlier identity reference image(s). "
        "Do not blend the pose, shot type, or **light-on-body pattern** from the identity images above; **one continuous light model** on MODEL identity skin."
    )


def _nano_banana_pose_last_suffix_no_face(*, lock_model_hairstyle: bool) -> str:
    hair = (
        "**Hairstyle:** follow MODEL / JSON — reference crop often has **no visible hair**. "
        if lock_model_hairstyle
        else "**Hairstyle** only if hair appears in this last crop; else omit. "
    )
    return (
        "\n\n[LAST_INPUT_IMAGE — NO_FACE] The **last** image locks **crop boundaries**, **scale**, **joint geometry** of **visible** body, "
        "garments/coverage, background, and **how light falls on visible limbs/torso**. "
        + hair
        + "**Never** transplant a face from earlier identity URLs into zones where this last image shows **no face** "
        "(e.g. legs-only, feet macro). Match **MODEL_PROFILE skin/body continuity** only on **pixels that correspond to visible body** "
        "in this crop. Do not widen framing to include a head."
    )


def finalize_nano_banana_studio_prompt(
    refined_prompt: str,
    *,
    studio_mode: str,
    user_photo_edit_first: bool,
    user_pose_reference_is_last: bool,
    lock_model_hairstyle: bool = True,
    prompt_brief_mode: str = "full",
) -> str:
    """
    Nano Banana Pro: порядок URL другой, чем у WAN (сначала лицо модели, поза пользователя — в конце).
    user_photo_edit_first: «Доработать фото» — первое фото = база для правок (порядок не меняли).
    user_pose_reference_is_last: после reorder загруженный референс позы — последний кадр в списке.
    """
    mode = (studio_mode or "model").strip().lower()
    brief = (prompt_brief_mode or "full").strip().lower()
    p = (refined_prompt or "").strip()

    if user_photo_edit_first and mode == "photo_edit":
        out = (
            _WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX.strip()
            if not p
            else _WAVESPEED_PHOTO_EDIT_USER_FIRST_PREFIX + p
        )
    elif brief == "text_scene":
        out = _NANO_TEXT_SCENE_PREFIX.strip() if not p else _NANO_TEXT_SCENE_PREFIX + p
    elif brief == "grok_composed":
        if mode == "model_scene":
            head = (
                "[MODEL_SCENE — identity refs first] **Earlier images** = MODEL (turnaround, body, face, anatomy): "
                "face, skin, hair, bust/waist/hip proportions — FIGURE_LOCK from JSON. "
                "**Last image** = POSE_LOCK: match pose geometry, crop, camera, background, light, wardrobe zones "
                "with **minimal deviation** from source. Never donor identity from last image.\n\n"
            )
            out = head.strip() if not p else head + p
        else:
            out = _GROK_COMPOSED_NANO_PREFIX.strip() if not p else _GROK_COMPOSED_NANO_PREFIX + p
        if user_pose_reference_is_last:
            out = out.rstrip() + _GROK_COMPOSED_POSE_LAST_SUFFIX
    elif brief == "grok_composed_text":
        out = _GROK_TEXT_SCENE_NANO_PREFIX.strip() if not p else _GROK_TEXT_SCENE_NANO_PREFIX + p
    elif brief == "grok_main_prose":
        out = _GROK_MAIN_PROSE_NANO_PREFIX.strip() if not p else _GROK_MAIN_PROSE_NANO_PREFIX + p
    else:
        if brief == "compact_pose_image" and mode not in ("face_swap", "photo_edit"):
            head = (
                _NANO_BANANA_NO_FACE_IDENTITY_PREFIX
                if mode == "no_face"
                else _NANO_COMPACT_IDENTITY_PREFIX
            )
        else:
            head = (
                _NANO_BANANA_FACE_SWAP_IDENTITY_PREFIX
                if mode == "face_swap"
                else _NANO_BANANA_NO_FACE_IDENTITY_PREFIX
                if mode == "no_face"
                else _NANO_BANANA_IDENTITY_LOCK_PREFIX
            )
        out = head.strip() if not p else head + p
        if user_pose_reference_is_last:
            if brief == "compact_pose_image":
                out = out.rstrip() + (
                    _NANO_COMPACT_NO_FACE_LAST_SUFFIX
                    if mode == "no_face"
                    else _NANO_COMPACT_POSE_LAST_SUFFIX
                )
            else:
                out = out.rstrip() + (
                    _nano_banana_pose_last_suffix_no_face(
                        lock_model_hairstyle=lock_model_hairstyle
                    )
                    if mode == "no_face"
                    else _nano_banana_pose_last_suffix(lock_model_hairstyle=lock_model_hairstyle)
                )

    if mode == "no_face" and brief != "compact_pose_image":
        out = (out or "").rstrip() + _WAVESPEED_NO_FACE_SUFFIX
    return out


_FULLFRAME_MASK_PAIR_EN = (
    "[INPUT_PAIR — BINARY MASK, NOT EXTRA PHOTOS] **Image numbering is 1-based in request order.** "
    "**Image 1**: the full-resolution **RGB photograph** to edit — keep framing, palette, shadows, textures, lens/DOF globally unless USER_TEXT overrides. "
    "**Image 2**: a **mask image registered 1:1** with Image 1 (same width×height). "
    "**High luminance / white** = pixels where you **may repaint** according to this JSON brief and USER edits. "
    "**Black / near-black** = **locked pixels** — do **not** change content, anatomy, shading, warp, hallucinate overlays, anime-ify, or background swap outside white; micro-blending is allowed **only along the boundary** so seams stay invisible.\n\n"
)

_WAN_MASK_FULLFRAME_FACE_SWAP_CORE = (
    "[FACE_SWAP — WAN MASK EDIT] Goal: replace **recipient human epidermis** with the saved **MODEL identity** "
    "**only inside high-luminance (white) stencil pixels**. This is a **localized** identity takeover, **not** a global scene redraw.\n\n"
    "**Preserve Image 1 outside white:** pasted **illustrations, meme/cartoon cutouts, stickers, typography**, "
    "**collage overlays**, or **another character** whose silhouette lives in **black/near-black mask** regions "
    "must remain **bitmap-stable** (no removal, restyle-to-photo, or background harmonization justified by matching MODEL). "
    "Do **not** run implicit global denoise/color-unify passes that bleach or repaint locked blacks.\n\n"
    "**Inside white:** MODEL-consistent face + continuous visible skin (per JSON/USER); **grade micro-texture and undertone head-neck-visible torso/arms** "
    "so epidermis reads as **one person** under Image 1's existing **light direction/topology**, without importing studio backlight or pose cues from thumbnails.\n\n"
)

_WAN_MASK_FULLFRAME_IDENTITY_TAIL = (
    "**From Image 3 onward** (when present): portrait references of ONE saved-studio model "
    "**for WHO only** — face shape, facial features, consistent skin grain/tone continuity, hairline/hair palette, plausible body proportions/shape matching that person. "
    "**Do not** steal pose, camera lens/angle, cropping, wardrobe/coverage composition, silhouette edges, shadows layout, backdrop, lighting direction, nor skin micro-pattern **from those portraits**. "
    "Scene/lighting/framing/obvious garment coverage semantics come **only** from Images 1–2; identity references constrain **recipient** anatomy when changing or replacing humans **inside approved white-mask regions**. "
)

_WAN_MASK_FULLFRAME_PHOTO_EDIT_NO_ID = (
    "There are **no** separate identity uploads after Images 1–2 — obey the JSON brief and USER_TEXT strictly; preserve the same recognizable person/outfit/environment **outside locked black** zones.\n\n"
)

_FULLFRAME_PHOTOREAL_APPEND = (
    "Maintain photographic realism (natural skin, sensor-like textures); "
    "**do NOT** anime-ify, illustrative stylize, or swap in an unrelated person's face globally "
    "**unless USER_TEXT explicitly requests** that style/subject pivot."
)


_FULLFRAME_FACE_SWAP_COLLAGE_TAIL = (
    "[FACE_SWAP_COLLAGE_TAIL] Inside **high-luminance (white)** mask stencil only: photoreal MODEL identity skin anatomy as briefed. "
    "**Black-mask pixels MUST stay bitwise locked** to RGB canvas — including pasted **illustrations, meme figures, collage cutouts**, "
    "or any deliberate non-photo layer; never «clean up» the frame by erasing cartoon/2D overlays because they violate photoreal uniformity. "
    "Do NOT global-style-match the scene to remove collaged artwork outside white."
)


def _masked_wave_trailer_suffix(*, studio_mode: str) -> str:
    """
    По умолчанию толкаем к фотореализму — но это ломает намерения face swap с коллажем (рисунки в чёрной маске).
    Для face_swap оставляем явное правило сохранять нерелалистичные вставки вне белой области.
    """
    if (studio_mode or "").strip().lower() == "face_swap":
        return "\n\n" + _FULLFRAME_FACE_SWAP_COLLAGE_TAIL
    return "\n\n" + _FULLFRAME_PHOTOREAL_APPEND


def finalize_masked_fullframe_wan_prompt(
    refined_prompt: str,
    *,
    studio_mode: str,
    lock_model_hairstyle: bool,
    attach_identity_refs: bool,
) -> str:
    """WAN / WAN 2.x order: Image1=canvas, Image2=mask aligned, then identity refs."""
    mode = (studio_mode or "model").strip().lower()
    p = (refined_prompt or "").strip()
    out = _FULLFRAME_MASK_PAIR_EN
    if mode == "photo_edit":
        out += (
            _WAN_MASK_FULLFRAME_IDENTITY_TAIL
            if attach_identity_refs
            else _WAN_MASK_FULLFRAME_PHOTO_EDIT_NO_ID
        )
        merged = out + p if p else out.rstrip()
        return merged.rstrip() + _masked_wave_trailer_suffix(studio_mode=studio_mode)
    if mode == "no_face":
        hair = (
            "**Hairstyle** follows MODEL/JSON thumbnails when hair is unseen on Image 1 — not invented from stray pixels.\n\n"
            if lock_model_hairstyle
            else "**Hairstyle** may follow visible hair on Image 1 when JSON allows POSE-like cues.\n\n"
        )
        if attach_identity_refs:
            out += (
                "**Image 1** defines framing/crop/framing-lock for NO_FACE uploads — **never** widen the canvas to introduce a cranium/head/face omitted from RGB.\n\n"
                + hair
                + _WAN_MASK_FULLFRAME_IDENTITY_TAIL
            )
        else:
            out += (
                "**Image 1** headless/legs/feet framing by design — **Image 2** is mask only; hallucinate anatomical completions **strictly inside white** where pixels exist.\n\n"
                + hair
            )
        merged = out + (p if p else "")
        return (
            merged.rstrip()
            + _WAVESPEED_NO_FACE_SUFFIX
            + _masked_wave_trailer_suffix(studio_mode=studio_mode)
        )
    if mode == "face_swap":
        hair_fs = (
            "**Hairstyle** (cut/color/silhouette) follows MODEL portraits + JSON when the relevant head/skin is masked — "
            "**not** invented from stray Image 1 strands outside the USER's swap intent.\n\n"
            if lock_model_hairstyle
            else "**Hairstyle** may follow visible Image 1 hair when JSON/USER explicitly favors POSE-like continuity.\n\n"
        )
        out += hair_fs + _WAN_MASK_FULLFRAME_FACE_SWAP_CORE.strip() + "\n\n"
        if attach_identity_refs:
            out += _WAN_MASK_FULLFRAME_IDENTITY_TAIL + "\n\n"
        else:
            out += (
                "**No MODEL identity URLs after Images 1–2** — repaint only inside white per JSON/USER while keeping "
                "**all black-locked pixels** identical to Image 1 (including overlays and collage).\n\n"
            )
        merged = out + (p if p else "")
        return merged.rstrip() + _masked_wave_trailer_suffix(studio_mode=studio_mode)
    # studio_mode == model
    if attach_identity_refs:
        out += _WAN_MASK_FULLFRAME_IDENTITY_TAIL
    else:
        out += "**No MODEL identity URLs after Images 1–2** — edits must stay faithful to recognizable subject on Image 1 when JSON dictates.\n\n"
    merged = out + (p if p else "")
    return merged.rstrip() + _masked_wave_trailer_suffix(studio_mode=studio_mode)


_NANO_FULLFRAME_PHOTO_EDIT = (
    _FULLFRAME_MASK_PAIR_EN
    + "**Only Images 1–2 anchor the spatial edit** unless more URLs explicitly exist for identity afterward. "
    + "Honor JSON + USER edits; **never** refactor or restyle blacks; keep **outside-mask** pixels bitwise-stable.\n\n"
)

_NANO_FULLFRAME_MULTI_IDENTITY = (
    "[MULTI_IMAGE — MODEL + BINARY MASK] **Leading images**: studio portrait thumbnails of ONE person — **WHO only**: "
    "face geometry, plausible skin realism, characteristic hair silhouette/tone continuity, torso/limb proportion bias. "
    "**Do NOT** copy pose yaw, cropping window, garments/coverage silhouette, backlight topology, backdrop texture, focal length cues, shadow painting, nor studio lighting setups from thumbnails — derive those solely from Images **N−1** and **N−2** semantics below.\n\n"
    "**Penultimate image (RGB)**: authoritative **composition canvas**: lensing, cropping, viewpoint, posing, textiles/coverage touching skin, ambience, occlusion order, global illumination cues.\n\n"
    "**LAST image**: **spatial mask PNG** (**NOT photographic content**);\n "
    "**white = permissible generation zones** aligning with USER/JSON intents; "
    "**black = frozen pixels**. "
    "**Ignore** pictorial depiction on LAST — treat luminance purely as stencil weights.\n\n"
)

_NANO_FULLFRAME_TAIL_NO_FACE_ATTACH = (
    "**NO_FACE guard:** NEVER rebuild a frontal portrait or skull where **Penultimate RGB** withheld them; thumbnails must not force head apparition into blacks. Body identity obeys thumbnails **only inside white** on visible epidermis.\n\n"
)


def finalize_masked_fullframe_nano_prompt(
    refined_prompt: str,
    *,
    studio_mode: str,
    lock_model_hairstyle: bool,
    attach_identity_refs: bool,
) -> str:
    """
    Nano order when identity refs attach (model/no_face path):
      [...identity thumbnails..., PENULTIMATE=RGB canvas, LAST=aligned mask].

    Nano order when identity absent or photo_edit: [canvas, mask, optional trailing refs unchanged].
    """
    mode = (studio_mode or "model").strip().lower()
    p = (refined_prompt or "").strip()
    trailer = _masked_wave_trailer_suffix(studio_mode=studio_mode)

    if mode == "photo_edit":
        extra = ""
        if attach_identity_refs:
            extra = (
                "\n\n**Images 3+** (when present): MODEL portrait references — constrain face/skin/hair continuity "
                "**primarily inside high-luminance mask zones** without violating black-locked periphery.\n\n"
            )
        merged = (_NANO_FULLFRAME_PHOTO_EDIT.strip() + extra + (p if p else "")).rstrip()
        return merged + trailer

    if attach_identity_refs and mode != "photo_edit":
        hair = (
            "**Hairstyle obeys JSON/MODEL thumbnails — not improvised from penultimate stray flyaways**\n\n"
            if lock_model_hairstyle
            else "**Hairstyle** may loosely match penultimate curls when USER JSON flags POSE_REFERENCE.\n\n"
        )
        no_face_patch = (
            _NANO_FULLFRAME_TAIL_NO_FACE_ATTACH if mode == "no_face" else ""
        )
        head = _NANO_FULLFRAME_MULTI_IDENTITY + hair + no_face_patch
        merged = (head + p) if p else head.rstrip()
        return merged.rstrip() + trailer

    pf = (_FULLFRAME_MASK_PAIR_EN.strip() + "\n\n").rstrip()
    note = "**No MODEL identity thumbnails** after the mask URL — hallucination budget constrained to white stencil interior.\n\n"
    merged = (pf + note + (p if p else "")).rstrip()
    return merged + trailer


# Если .env задал пустой путь или на сервере нет data/prompts — не падаем с 503.
_DEFAULT_IMAGE_STUDIO_SYSTEM = """
You are a prompt builder for the WAN 2.7 Image Edit model.

You will receive:
1. A SKELETON (JSON template with <FILL> and <FROM_MODEL_PROFILE>).
2. Optional REFERENCE_IMAGE — when not "(none)", it is the source of truth for **scene layout, camera geometry, clothing/coverage**, and **pose geometry** (head tilt/yaw/gaze/limbs) plus **how light wraps the figure** (topology of highlights/shadows), not donor identity.
3. A MODEL PROFILE — **identity** only (face, skin, hair, body type); not a replacement for the reference scene or pose.
4. USER_TEXT, 5. OUTPUT/ASPECT.

If REFERENCE_IMAGE has content: fill pose, clothing (only what the reference photo shows; if none — nude/uncovered), photography, background, and **lighting consistency across face and visible body** from the reference, not from profile defaults. **GEOMETRY_LOCK:** do not rotate toward the camera for readability — match reference head/body orientation unless USER_TEXT overrides. The user message has `## HAIRSTYLE_MODE`: **MODEL_LOCK** = `hair_in_scene` from MODEL_PROFILE; **POSE_REFERENCE** = `hair_in_scene` from the reference. Never take clothing from MODEL_PROFILE. **Always take face, body_type, skin tone; hair color + identity baseline from MODEL_PROFILE** — never mimic the reference person's skin. **Synthesize one coherent person**: same light falloff on MODEL identity from neck through limbs. MODEL_PROFILE fills <FROM_MODEL_PROFILE>; no reference face or body copy.
**Consistency:** camera_style + camera_distance + framing + shot_type + hands must be physically possible (no front-camera "selfie" at 1–2 m full body without mirror/tripod/friend). clothing.imperfections must not contradict realism_engine fabric_realism. Keep realism_engine exactly as in the skeleton. **Default to mundane real-life candid energy** (camera roll / citizen photo) for all capture types unless user asks for glamour — fill `photography.snapshot_authenticity` and `the_vibe.life_in_frame`. **must_keep** expands to three coherent plain-English lines per skeleton. Output only valid JSON, no markdown.
""".strip()


def _relative_prompt_path(val: str, default_rel: str) -> str:
    v = (val or "").strip()
    return v if v else default_rel


def _openai_friendly_error(message: str, status_code: int) -> RuntimeError:
    m = (message or "").strip()
    low = m.lower()
    if "something went wrong" in low or "please try again" in low:
        m = (
            f"{m} — типично это временная ошибка API OpenAI (HTTP {status_code}). "
            "Повторите позже, проверьте статус: https://status.openai.com и лимиты/баланс в кабинете."
        )
    return RuntimeError(m)


def load_image_studio_skeleton() -> str:
    rel = _relative_prompt_path(
        settings.image_studio_skeleton_path,
        "data/prompts/image_studio_skeleton.txt",
    )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return (settings.image_studio_skeleton_inline or "").strip()


def load_image_studio_skeleton_compact() -> str:
    path = (BACKEND_DIR / "data/prompts/image_studio_skeleton_compact.txt").resolve()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def load_image_studio_brief_modes_addon() -> str:
    path = (BACKEND_DIR / "data/prompts/image_studio_brief_modes_addon.txt").resolve()
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def prepare_studio_prompt_skeleton_compact() -> str:
    raw = load_image_studio_skeleton_compact()
    if not raw.strip():
        return prepare_studio_prompt_skeleton()
    re_obj = load_canonical_realism_engine()
    if re_obj is None:
        return raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("studio compact skeleton: invalid JSON, using raw: %s", e)
        return raw
    if not isinstance(data, dict):
        return raw
    data["realism_engine"] = re_obj
    return json.dumps(data, ensure_ascii=False, indent=2)


def prepare_studio_prompt_skeleton_for_brief(brief_mode: str) -> str:
    mode = (brief_mode or "full").strip().lower()
    if mode == "compact_pose_image":
        sk = prepare_studio_prompt_skeleton_compact()
        if sk.strip():
            return sk
    return prepare_studio_prompt_skeleton()


def load_image_studio_system() -> str:
    rel = _relative_prompt_path(
        settings.image_studio_system_path,
        "data/prompts/image_studio_system.txt",
    )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        t = path.read_text(encoding="utf-8").strip()
        if t:
            return t
    inline = (settings.image_studio_system_inline or "").strip()
    if inline:
        return inline
    log.warning(
        "image_studio_system: file missing or empty (%s), using built-in default",
        path,
    )
    return _DEFAULT_IMAGE_STUDIO_SYSTEM


def _realism_engine_dict_for_prompt(raw: dict) -> dict:
    """Убрать служебные ключи (_comment и т.д.), чтобы JSON для модели не зашумлять."""
    return {k: v for k, v in raw.items() if isinstance(k, str) and not k.startswith("_")}


def load_canonical_realism_engine() -> dict | None:
    if (settings.image_studio_realism_engine_inline or "").strip():
        try:
            data = json.loads(settings.image_studio_realism_engine_inline)
        except json.JSONDecodeError:
            return None
    else:
        rel = _relative_prompt_path(
            settings.image_studio_realism_engine_path,
            "data/prompts/image_studio_realism_engine.json",
        )
        path = (BACKEND_DIR / rel).resolve()
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    inner: dict | None = None
    if isinstance(data, dict) and "realism_engine" in data and isinstance(
        data["realism_engine"], dict
    ):
        inner = data["realism_engine"]
    elif isinstance(data, dict):
        inner = data
    if inner is None:
        return None
    return _realism_engine_dict_for_prompt(inner)


def format_realism_engine_for_prose_prompt() -> str:
    """
    Канонический realism_engine → компактный descriptive блок для prose-промптов (не JSON).
    """
    re_obj = load_canonical_realism_engine()
    if not re_obj:
        return ""
    parts: list[str] = []
    for key in (
        "skin_realism",
        "hair_realism",
        "fabric_realism",
        "environment_realism",
        "photo_realism",
        "color_grading",
        "capture_authenticity",
        "character_rendering",
        "imperfection_level",
    ):
        val = re_obj.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    if not parts:
        return ""
    return "Capture realism: " + " ".join(parts)


def prepare_studio_prompt_skeleton() -> str:
    """Скелет с подставленным из файла realism_engine; при ошибке разбора — сырой текст."""
    raw = load_image_studio_skeleton()
    if not raw.strip():
        return ""
    re_obj = load_canonical_realism_engine()
    if re_obj is None:
        return raw
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("studio skeleton: invalid JSON, using raw: %s", e)
        return raw
    if not isinstance(data, dict):
        return raw
    data["realism_engine"] = re_obj
    return json.dumps(data, ensure_ascii=False, indent=2)


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t, flags=re.DOTALL)
    return t.strip()


def apply_canonical_realism_to_refined_output(text: str) -> str:
    """После LLM: зафиксировать realism_engine из канонического JSON."""
    re_obj = load_canonical_realism_engine()
    if re_obj is None:
        return text
    raw = _strip_code_fences(text)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        log.warning("refined output: not valid JSON, skip realism merge: %s", e)
        return text
    if not isinstance(data, dict):
        return text
    data["realism_engine"] = re_obj
    return json.dumps(data, ensure_ascii=False, indent=2)


def load_reference_describe_prompt(
    *,
    hairstyle_from_pose_reference: bool = False,
    no_face_framing: bool = False,
) -> str:
    if no_face_framing:
        rel = _relative_prompt_path(
            settings.image_studio_reference_describe_no_face_path,
            "data/prompts/image_studio_reference_describe_no_face.txt",
        )
        path = (BACKEND_DIR / rel).resolve()
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t:
                return t
        log.warning(
            "reference describe (no_face): file missing or empty (%s), using standard describe prompt",
            path,
        )
    if hairstyle_from_pose_reference:
        rel = _relative_prompt_path(
            settings.image_studio_reference_describe_match_pose_hair_path,
            "data/prompts/image_studio_reference_describe_match_pose_hair.txt",
        )
    else:
        rel = _relative_prompt_path(
            settings.image_studio_reference_describe_path,
            "data/prompts/image_studio_reference_describe.txt",
        )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        t = path.read_text(encoding="utf-8").strip()
        if t:
            return t
    if hairstyle_from_pose_reference:
        log.warning(
            "reference describe (pose hair): file missing or empty (%s), using standard describe prompt",
            path,
        )
        return load_reference_describe_prompt(
            hairstyle_from_pose_reference=False, no_face_framing=no_face_framing
        )
    return (settings.image_studio_reference_describe_inline or "").strip()


def load_motion_first_frame_scene_describe_prompt() -> str:
    if (settings.motion_first_frame_scene_describe_inline or "").strip():
        return (settings.motion_first_frame_scene_describe_inline or "").strip()
    rel = _relative_prompt_path(
        settings.motion_first_frame_scene_describe_path,
        "data/prompts/motion_first_frame_scene_describe.txt",
    )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        t = path.read_text(encoding="utf-8").strip()
        if t:
            return t
    return ""


async def describe_motion_video_first_frame_scene_openai(
    *,
    image_bytes: bytes,
    image_media_type: str | None = None,
    credentials: StudioOpenAiCredentials | None = None,
) -> str:
    """
    Первый кадр референс-видео: детальная сцена (поза, свет, одежда, камера, фон),
    без идентичности; надписи/оверлеи игнорируются.
    """
    instruction = load_motion_first_frame_scene_describe_prompt()
    if not instruction:
        raise RuntimeError(
            "Промпт для описания первого кадра видео пуст — задайте "
            "data/prompts/motion_first_frame_scene_describe.txt или "
            "MOTION_FIRST_FRAME_SCENE_DESCRIBE_INLINE"
        )
    model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    mime = (image_media_type or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"
    system = (
        "You follow instructions precisely. Output only the requested English description "
        "with the labeled sections specified in the user message. "
        "No preamble, no markdown headings, no outer JSON."
    )
    user_content: list[dict] = [
        {"type": "text", "text": instruction},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ]
    return await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        max_tokens=4096,
        temperature=0.25,
        credentials=credentials,
    )


async def _chat_completion_text(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.65,
    credentials: StudioOpenAiCredentials | None = None,
    timeout_seconds: float = 120.0,
) -> str:
    cred = credentials
    if cred is None:
        key = (settings.openai_api_key or "").strip()
        if not key:
            raise RuntimeError("openai not configured")
        base = (settings.openai_base_url or "").strip().rstrip("/")
        if not base:
            base = "https://api.openai.com/v1"
        org = (settings.openai_organization or "").strip()
    else:
        key = cred.api_key.strip()
        if not key:
            raise RuntimeError("openai not configured")
        base = cred.base_url.strip().rstrip("/")
        if not base:
            base = "https://api.openai.com/v1"
        org = (cred.organization or "").strip()

    url = f"{base}/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req_headers: dict[str, str] = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if org:
        req_headers["OpenAI-Organization"] = org

    to = max(30.0, float(timeout_seconds))
    async with httpx.AsyncClient(timeout=to) as client:
        r = await client.post(url, headers=req_headers, json=payload)
        req_id = (r.headers.get("x-request-id") or r.headers.get("openai-request-id") or "").strip()

    if r.status_code >= 400:
        err_body = (r.text or "")[:1500]
        log.warning(
            "openai request failed: %s %s request_id=%s url=%s",
            r.status_code,
            err_body,
            req_id or "—",
            url,
        )
        try:
            ej = r.json()
            if isinstance(ej, dict):
                err = ej.get("error")
                if isinstance(err, dict) and err.get("message"):
                    msg = str(err["message"])
                    if req_id and "request id" not in msg.lower():
                        msg = f"{msg} (OpenAI request_id: {req_id})"
                    raise _openai_friendly_error(msg, r.status_code)
                if isinstance(err, str):
                    raise _openai_friendly_error(err, r.status_code)
        except RuntimeError:
            raise
        except Exception:
            pass
        raise RuntimeError(
            f"OpenAI HTTP {r.status_code}"
            + (f" (request_id: {req_id})" if req_id else "")
            + ". Проверьте OPENAI_API_KEY, лимиты и https://status.openai.com"
        )

    data = r.json()
    try:
        out = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        log.warning("openai bad response: %s", data)
        raise RuntimeError("OpenAI response shape unexpected") from e
    text = (out or "").strip()
    if not text:
        raise RuntimeError("OpenAI returned empty content")
    return text


async def chat_completion_openai_compatible_text(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.65,
    credentials: StudioOpenAiCredentials | None = None,
    timeout_seconds: float = 120.0,
) -> str:
    """POST /v1/chat/completions (OpenAI-совместимо, в т.ч. xAI Grok)."""
    return await _chat_completion_text(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        credentials=credentials,
        timeout_seconds=timeout_seconds,
    )


async def describe_reference_image_openai(
    *,
    image_bytes: bytes,
    image_media_type: str | None,
    hairstyle_from_pose_reference: bool = False,
    no_face_framing: bool = False,
    credentials: StudioOpenAiCredentials | None = None,
) -> str:
    """Шаг 1: только визуальное описание референса (поза, одежда, сцена), без финального JSON."""
    instruction = load_reference_describe_prompt(
        hairstyle_from_pose_reference=hairstyle_from_pose_reference,
        no_face_framing=no_face_framing,
    )
    if not instruction:
        raise RuntimeError(
            "Текст запроса для описания референса пуст — задайте файл "
            "data/prompts/image_studio_reference_describe.txt или "
            "IMAGE_STUDIO_REFERENCE_DESCRIBE_INLINE"
        )

    model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    mime = (image_media_type or "image/jpeg").split(";")[0].strip()
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"

    system = (
        "You follow instructions precisely. Output only the requested English description, "
        "no preamble, no markdown, no labels."
    )
    user_content: list[dict] = [
        {"type": "text", "text": instruction},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        },
    ]

    return await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        max_tokens=2048,
        temperature=0.4,
        credentials=credentials,
    )


async def describe_motion_video_frames_openai(
    *,
    frames_jpeg: list[bytes],
    credentials: StudioOpenAiCredentials | None = None,
) -> str:
    """
    Несколько кадров из driving video → краткий English-текст для брифа первого кадра / motion control.
    Использует ту же vision-модель, что и describe_reference_image_openai.
    """
    if not frames_jpeg:
        raise RuntimeError("no video frames for vision")
    model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model
    instruction = (
        "These frames are sampled in order from a short reference video. The video will drive body motion "
        "onto a still image of a different person (identity comes from separate reference photos, not from this video). "
        "In 3-6 short sentences of English, describe: overall movement style, how pose evolves, camera/framing, "
        "visible clothing/coverage, environment and lighting. "
        "Do not name real celebrities. No markdown, no bullet list, plain text only."
    )
    system = (
        "You follow instructions precisely. Output only the requested English description, "
        "no preamble, no markdown."
    )
    user_content: list[dict] = [{"type": "text", "text": instruction}]
    for raw in frames_jpeg[:6]:
        b64 = base64.standard_b64encode(raw).decode("ascii")
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            }
        )
    return await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        max_tokens=1024,
        temperature=0.35,
        credentials=credentials,
    )


def _studio_mode_refiner_block(studio_mode: str) -> str:
    m = (studio_mode or "model").strip().lower()
    if m == "photo_edit":
        return (
            "## STUDIO_MODE: PHOTO_EDIT (correct / retouch uploaded frame)\n"
            "**No saved MODEL_PROFILE** is attached — identity and scene baseline come **only** from REFERENCE_IMAGE (the uploaded/generated still). "
            "Fill JSON so the downstream editor implements **exactly USER_TEXT deltas**— clothes, hues, backdrop, glare, blemish/skin fixes, "
            "object removals, **without** swapping the person for a catalog model or reshaping unspecified anatomy. "
            "Keep **camera geometry and crop** consistent with REFERENCE_IMAGE **unless USER_TEXT explicitly** asks to change framing, lens, angle, distance, rotation, or tilt. "
            "**Do not** invent an alternate hairstyle, outfit, jewelry, tattoos, landmarks, facial structure, ethnicity, gender expression, "
            "**or proportions** unless USER_TEXT directs that change.\n"
        )
    if m == "no_face":
        return (
            "## STUDIO_MODE: NO_FACE_FRAMING\n"
            "Final image must NOT show the subject's face or full head unless REFERENCE_IMAGE text explicitly states they are "
            "in-frame (chin through crown visible). If FRAMING says head/face cropped out → keep them cropped out.\n"
            "Match **REFERENCE_IMAGE framing edges and subject scale** — do **not** zoom out or add vertical headroom to «fit» identity photos.\n"
            "Prefer legs/feet/hands/lower-body/torso-below-neck crops when the reference is a partial-body shot.\n"
            "`subject.identity.face_features`: **minimal or absent** when face is off-frame — do not invent eyes/nose/mouth for readability.\n"
            "Skin continuity: MODEL_PROFILE tones/texture for **visible anatomy only**.\n"
        )
    if m == "face_swap":
        return (
            "## STUDIO_MODE: FACE_SWAP (identity takeover into existing scene bitmap)\n"
            "REFERENCE_IMAGE describes **only** framing/camera/light/room garments on the SOURCE photo whose human must be **removed** aesthetically — MODEL_PROFILE replaces `subject.identity` "
            "**throughout**. User wants **chromatic cohesion**: skin graded believably head→neck→torso/limbs **as one complexion family** baked under scene white balance "
            "**without** zebra striping mismatches. Respect GOAL_POSE/lighting verbatim from REFERENCE_* lines; forbid inventing incompatible lighting pivots solely to brighten face readability.\n"
        )
    return ""


def _build_refiner_user_message(
    *,
    skeleton: str,
    user_text: str,
    reference_scene_description: str | None,
    model_profile_text: str | None,
    model_reference_photos: str | None = None,
    output_aspect_key: str,
    studio_mode: str = "model",
    lock_model_hairstyle: bool = True,
    prompt_brief_mode: str = "full",
) -> str:
    has_ref = bool((reference_scene_description or "").strip())
    photo_edit_mode = (studio_mode or "").strip().lower() == "photo_edit"
    no_face_mode = (studio_mode or "").strip().lower() == "no_face"
    face_swap_mode = (studio_mode or "").strip().lower() == "face_swap"
    brief = (prompt_brief_mode or "full").strip().lower()
    mode_line = "MODEL_LOCK" if lock_model_hairstyle else "POSE_REFERENCE"
    ref_geometry_lock = ""
    if has_ref and not photo_edit_mode and brief == "full":
        if face_swap_mode:
            ref_geometry_lock = (
                "**FACE_SWAP_GEOMETRY_LIGHT:** Preserve **crop/FoV, camera axis, viewpoint, limbs articulation, garment seams, scene-light direction + hardness topology** precisely as described in REFERENCE_IMAGE. "
                "When filling `photography`, match white balance/color temperature ambience from the room **so MODEL identity skin** graded across visible skin reads **chromatically cohesive** under that light — "
                "no «two donors» tonal split between cheeks vs chest vs arms.\n"
            )
        elif no_face_mode:
            ref_geometry_lock = (
                "**GEOMETRY_LOCK:** Match REFERENCE_IMAGE **joint articulation, lean, and torso twist** in `subject.pose`; "
                "keep **`photography`** consistent with CAMERA_DISTANCE / CAMERA_HEIGHT / CAMERA_ANGLE / FRAMING (`framing_crop`, distances, heights, angles). "
                "Do **not** infer head rotation or gaze if face/head are off-frame unless the text describes a tiny visible chin/forehead slice — then only that slice's mechanical orientation. "
                "Do **not** widen framing. MODEL_PROFILE fills **skin/body identity** on visible pixels; **spatial pose** stays on the reference.\n"
            )
        else:
            ref_geometry_lock = (
                "**GEOMETRY_LOCK:** Use REFERENCE_IMAGE sections **HEAD_GEOMETRY**, **POSE**, and **LIGHT_ON_FORM** (or equivalents) verbatim in spirit — "
                "fill `subject.pose`, aligned `photography.view_direction` / `angle` / framing, and `photography.lighting` so **head tilt/yaw**, **gaze vs lens**, and **limb angles** mirror the pose photo; "
                "mirror **highlight/shadow topology** onto MODEL_PROFILE identity skin (direction + hardness, **not** donor complexion). "
                "**Do not** frontalize toward the lens for readability. MODEL_PROFILE defines **appearance** (`subject.identity`); **snapshot geometry + light topology** follows the reference.\n"
            )
    elif has_ref and not photo_edit_mode and brief == "compact_pose_image":
        ref_geometry_lock = (
            "**COMPACT_BRIEF:** Pose/outfit/room/light go to the **pose reference input image**, not into JSON text. "
            "JSON carries **identity_reference** + `scene_from_reference_image` literals only. "
            "MODEL_PROFILE supplies face, skin, **body_proportions** (preserve hourglass/curvy/athletic from profile — "
            "adapt clothing drape to model body, not reference donor silhouette).\n"
        )
    elif has_ref and not photo_edit_mode and brief == "text_scene":
        ref_geometry_lock = (
            "**TEXT_SCENE_BRIEF:** No pose image in the API — copy pose, clothing, background, camera, lighting from "
            "REFERENCE_IMAGE into the JSON scene fields (full skeleton) or top-level `scene_brief`. "
            "MODEL_PROFILE for identity only; do not invent conflicting wardrobe from profile defaults.\n"
        )
    brief_mode_line = ""
    if brief == "compact_pose_image":
        brief_mode_line = "COMPACT_WITH_POSE_IMAGE"
    elif brief == "text_scene":
        brief_mode_line = "TEXT_SCENE_NO_POSE_IMAGE"
    blocks: list[str] = []
    if brief_mode_line:
        blocks.append(f"## PROMPT_BRIEF_MODE\n{brief_mode_line}")
    blocks.extend(
        [
            "## HAIRSTYLE_MODE\n" + mode_line,
            "## SKELETON (JSON template: fill <FILL> placeholders and <FROM_MODEL_PROFILE> markers)",
            skeleton.strip(),
        ]
    )

    # Референс — сразу после скелета, чтобы сцена не утонула в длинном JSON профиля.
    if has_ref:
        if photo_edit_mode:
            blocks.append(
                "## REFERENCE_IMAGE (**input photograph — edit this frame only**)\n"
                "**Baseline:** whoever, whatever, and whichever camera setup the description below reflects — this is the bitmap the API will load. "
                "**Task:** fold **USER_TEXT** in as *targeted* deltas (wardrobe, palette, backdrop, clean-up, illumination, small geometry **if asked**). "
                "**Do not** reshuffle identity, body line, or framing for «profile defaults».\n\n"
                + (reference_scene_description or "").strip()
            )
        elif face_swap_mode:
            blocks.append(
                "## REFERENCE_IMAGE (SOURCE bitmap — incidental sitter likeness **discarded**, MODEL_PROFILE defines `subject.identity`)\n"
                "**Harvest** framing, optics, gestures, textiles/coverage, background primitives, illumination recipe from paragraphs below.\n\n"
                + ref_geometry_lock
                + (reference_scene_description or "").strip()
            )
        elif lock_model_hairstyle:
            ref_intro = (
                "## REFERENCE_IMAGE (scene/pose ref only: pose/hands, clothing/coverage on this photo, camera/framing/light/room — "
                "**not** hairstyle; **not** body type, skin tone, or face; those = MODEL_PROFILE). "
            )
            if no_face_mode:
                coherence = (
                    "**Crop-locked redo:** JSON must match REFERENCE_IMAGE **framing edges and subject scale** — never zoom out to add a head if the reference omits it. "
                    "MODEL_PROFILE gives **skin/body continuity for visible limbs and torso slices only** — not a mandate to render a face or full portrait.\n"
                )
            else:
                coherence = (
                    "**Render as one person:** fill JSON so the edit model **re-synthesizes the full body** of MODEL_PROFILE in this pose and room — not face-only over the reference sitter's body.\n"
                )
            blocks.append(
                ref_intro
                + coherence
                + ref_geometry_lock
                + (reference_scene_description or "").strip()
            )
        else:
            ref_intro = (
                "## REFERENCE_IMAGE (scene/pose ref: pose/hands, clothing/coverage, **hair styling in this shot**, "
                "camera/framing/light/room — **not** body type, skin tone, or face; those = MODEL_PROFILE). "
            )
            if no_face_mode:
                coherence = (
                    "**Crop-locked redo:** JSON must match REFERENCE_IMAGE **framing edges and subject scale** — never zoom out to add a head if the reference omits it. "
                    "MODEL_PROFILE gives **skin/body continuity for visible limbs and torso slices only** — not a mandate to render a face or full portrait.\n"
                )
            else:
                coherence = (
                    "**Render as one person:** fill JSON so the edit model **re-synthesizes the full body** of MODEL_PROFILE in this pose and room — not face-only over the reference sitter's body.\n"
                )
            blocks.append(
                ref_intro
                + coherence
                + ref_geometry_lock
                + (reference_scene_description or "").strip()
            )
    else:
        blocks.append("## REFERENCE_IMAGE\n(none — no input reference image)")

    if photo_edit_mode:
        blocks.append(
            "## MODEL_PROFILE\n"
            "(none — **PHOTO_EDIT**). There is **no** stored profile JSON. Populate **all** fields marked `<FROM_MODEL_PROFILE>` by **paraphrasing the subject already shown in REFERENCE_IMAGE**, "
            "then apply **only** the mutations described in USER_TEXT. Do **not** swap in traits from an imagined «studio model» or blank template defaults that contradict the photograph.\n"
        )
    elif lock_model_hairstyle:
        mp = (
            "## MODEL_PROFILE (identity: face, skin, hair color **and hairstyle**, body type, marks — for <FROM_MODEL_PROFILE> and **`hair_in_scene`**. "
            "If REFERENCE_IMAGE exists: **never** use profile for clothing or accessories — only the reference photo + USER_TEXT. "
            "**Always** use profile for `subject.identity` (face, skin tone, body_type, hair color, hair style, marks) and for **`hair_in_scene`** "
            "**for every visible body part** — one continuous person. Do not copy default outfit/jewelry/posture/scene from profile over the reference layout "
            "**except hairstyle**, which always follows the profile unless USER_TEXT explicitly changes it.)"
        )
        if no_face_mode:
            mp += (
                " **When STUDIO_MODE is NO_FACE_FRAMING:** if the reference crop has **no head/face**, keep `face_features` minimal or absent — "
                "identity still anchors **visible skin** (legs, feet, hands, partial torso); do not invent facial detail for «completeness»."
            )
        blocks.append(mp)
    else:
        mp = (
            "## MODEL_PROFILE (identity: face, skin, hair color, body type, marks — for `subject.identity` / <FROM_MODEL_PROFILE>. "
            "If REFERENCE_IMAGE exists: **never** use profile for clothing or accessories — only the reference photo + USER_TEXT. "
            "**Always** use profile for `subject.identity` (face, skin tone, body_type, hair color traits, marks) — **not** from the reference sitter's face or body. "
            "**`hair_in_scene`** follows REFERENCE_IMAGE when HAIRSTYLE_MODE is POSE_REFERENCE; do not force the profile's default hairstyle if it conflicts with REFERENCE_IMAGE.)"
        )
        if no_face_mode:
            mp += (
                " **When STUDIO_MODE is NO_FACE_FRAMING:** omit rich `face_features` if face is off-frame; **hair_in_scene** only when hair appears in the reference crop."
            )
        blocks.append(mp)
    if model_reference_photos and str(model_reference_photos).strip():
        blocks.append(str(model_reference_photos).strip())
    if not photo_edit_mode:
        if model_profile_text and model_profile_text.strip():
            blocks.append(model_profile_text.strip())
        else:
            blocks.append(
                "(no model selected — use neutral, minimal identity only where required, or from USER_TEXT only)"
            )

    mode_extra = _studio_mode_refiner_block(studio_mode)
    if mode_extra:
        blocks.append(mode_extra.strip())

    u = (user_text or "").strip()
    blocks.append("## USER_TEXT (mood, tweaks; does not override reference layout unless clearly contradictory)\n" + (u if u else "(no additional text)"))
    blocks.append(
        aspect_user_block_english(
            output_aspect_key, preserve_reference_framing=has_ref
        )
    )
    return "\n\n".join(blocks)


async def refine_prompt_via_openai(
    *,
    system_instruction: str,
    skeleton: str,
    user_text: str,
    reference_scene_description: str | None,
    model_profile_text: str | None,
    model_reference_photos: str | None = None,
    output_aspect_key: str,
    studio_mode: str = "model",
    lock_model_hairstyle: bool = True,
    prompt_brief_mode: str = "full",
    credentials: StudioOpenAiCredentials | None = None,
) -> str:
    """Шаг 2: одна сессия чата — system = инструкция, user = шаблон + данные; ответ: JSON-строка."""
    if not (system_instruction or "").strip():
        raise RuntimeError("image studio: empty system instruction")
    model = settings.openai_studio_model
    sys_parts = [system_instruction.strip()]
    addon = load_image_studio_brief_modes_addon()
    if addon and (prompt_brief_mode or "full").strip().lower() != "full":
        sys_parts.append(addon)
    system_full = "\n\n".join(sys_parts)
    user_message = _build_refiner_user_message(
        skeleton=skeleton,
        user_text=user_text,
        reference_scene_description=reference_scene_description,
        model_profile_text=model_profile_text,
        model_reference_photos=model_reference_photos,
        output_aspect_key=output_aspect_key,
        studio_mode=studio_mode,
        lock_model_hairstyle=lock_model_hairstyle,
        prompt_brief_mode=prompt_brief_mode,
    )
    raw = await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system_full},
            {"role": "user", "content": user_message},
        ],
        max_tokens=8192,
        temperature=0.55,
        credentials=credentials,
    )
    return apply_canonical_realism_to_refined_output(raw)


def resolve_studio_prompt_brief_mode(
    *,
    studio_mode: str,
    has_reference_scene: bool,
    has_uploaded_reference_bytes: bool,
    send_pose_reference_to_wavespeed: bool,
) -> str:
    """full | compact_pose_image | text_scene | grok_composed"""
    mode = (studio_mode or "model").strip().lower()
    if mode in ("grok_compose", "model_scene"):
        return "grok_composed"
    if not has_uploaded_reference_bytes or not has_reference_scene:
        return "full"
    mode = (studio_mode or "model").strip().lower()
    if mode not in ("model", "model_scene", "no_face"):
        return "full"
    if send_pose_reference_to_wavespeed:
        return "compact_pose_image"
    return "text_scene"


def assemble_wavespeed_image_edit_prompt(
    refined_raw: str,
    *,
    studio_mode: str,
    user_pose_in_api: bool,
    user_pose_is_last: bool,
    lock_model_hairstyle: bool,
    prompt_brief_mode: str,
    model_profile_text: str | None,
    wave_profile: str,
    reference_scene_description: str | None = None,
    extra_negative: str | None = None,
    output_aspect_key: str = "3:4",
    wavespeed_identity_legend: str | None = None,
) -> str:
    """Позитивный промпт для WaveSpeed; negative в JSON (text scene) или суффикс [NEGATIVE_PROMPT] (prose)."""
    from app.services.studio_prompt_bundle import (
        append_negative_to_wavespeed_prompt,
        prepare_positive_prompt_json,
    )

    positive, negative = prepare_positive_prompt_json(
        refined_raw,
        brief_mode=prompt_brief_mode,
        model_profile_text=model_profile_text,
        reference_scene_description=reference_scene_description,
        extra_negative=extra_negative,
        output_aspect_key=output_aspect_key,
        wavespeed_identity_legend=wavespeed_identity_legend,
    )
    mode = (studio_mode or "model").strip().lower()
    brief = (prompt_brief_mode or "full").strip().lower()
    if (wave_profile or "").strip().lower() == "regular":
        prompt = finalize_nano_banana_studio_prompt(
            positive,
            studio_mode=mode,
            user_photo_edit_first=bool(user_pose_in_api and mode == "photo_edit"),
            user_pose_reference_is_last=user_pose_is_last,
            lock_model_hairstyle=lock_model_hairstyle,
            prompt_brief_mode=brief,
        )
    else:
        prompt = finalize_wavespeed_studio_prompt(
            positive,
            studio_mode=mode,
            user_image_first=user_pose_in_api,
            lock_model_hairstyle=lock_model_hairstyle,
            prompt_brief_mode=brief,
        )
    return append_negative_to_wavespeed_prompt(
        prompt, negative, brief_mode=brief
    )


_DEFAULT_MODEL_PROFILE_GEN_SYSTEM = (
    'Return only JSON: {"model_profile": { ... }} describing identity from photos '
    "(face, hair, skin, body, marks) — not pose, outfit, or scene. English, nested fields."
)


def load_model_profile_gen_system() -> str:
    rel = _relative_prompt_path(
        settings.image_studio_model_profile_gen_system_path,
        "data/prompts/model_profile_from_photos_system.txt",
    )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        t = path.read_text(encoding="utf-8").strip()
        if t:
            return t
    inline = (settings.image_studio_model_profile_gen_system_inline or "").strip()
    if inline:
        return inline
    log.warning("model_profile_gen: system file missing, using built-in default")
    return _DEFAULT_MODEL_PROFILE_GEN_SYSTEM


def load_model_profile_json_template() -> str:
    rel = _relative_prompt_path(
        settings.image_studio_model_profile_template_path,
        "data/prompts/model_profile_template.json",
    )
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file():
        t = path.read_text(encoding="utf-8").strip()
        if t:
            return t
    log.warning("model_profile_gen: template file missing, using minimal schema")
    return '{"model_profile":{"name":"<FILL_NAME>","identity_lock_keywords":"<FILL>"}}'


def _normalize_model_profile_json_output(raw_text: str) -> str:
    t = _strip_code_fences(raw_text)
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Модель вернула не JSON: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError("Ответ должен быть JSON-объектом")
    if "model_profile" not in data:
        data = {"model_profile": data}
    return json.dumps(data, ensure_ascii=False, indent=2)


async def generate_model_profile_json_from_images(
    *, image_items: list[tuple[bytes, str | None]], credentials: StudioOpenAiCredentials | None = None
) -> str:
    """Один vision-запрос: несколько фото одного человека → JSON model_profile."""
    if not image_items:
        raise RuntimeError("Нет изображений")
    system = load_model_profile_gen_system()
    if not system.strip():
        raise RuntimeError("Пустой системный промпт генерации профиля")
    template = load_model_profile_json_template()
    user_content: list[dict] = [
        {
            "type": "text",
            "text": (
                "These reference photos show one person. Fill the JSON schema template below "
                "with traits from THIS person only. Keep the exact same keys and nesting.\n\n"
                f"Number of images: {len(image_items)}.\n\n"
                "JSON SCHEMA TEMPLATE (replace every placeholder value):\n"
                f"{template}"
            ),
        }
    ]
    for raw, mime in image_items:
        m = (mime or "image/jpeg").split(";")[0].strip()
        if m not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            m = "image/jpeg"
        b64 = base64.standard_b64encode(raw).decode("ascii")
        user_content.append(
            {"type": "image_url", "image_url": {"url": f"data:{m};base64,{b64}"}}
        )
    model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model
    raw_text = await _chat_completion_text(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        max_tokens=8192,
        temperature=0.35,
        credentials=credentials,
    )
    return _normalize_model_profile_json_output(raw_text)
