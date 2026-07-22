"""Промпты и константы для вкладки «База модели» (face merge + развёртка)."""

from __future__ import annotations

import logging
from urllib.parse import quote

from app.config import BACKEND_DIR
from app.db.models import StudioGeneration
from app.services.studio_image_token import (
    create_generation_image_access_token,
    create_pose_reference_access_token,
)
from app.services.studio_pose_reference import save_pose_reference_bytes
from app.services.wavespeed_client import format_wavespeed_user_error, wavespeed_upload_image_bytes

log = logging.getLogger(__name__)

DEFAULT_FACE_MERGE_PROMPT = (
    "Take the two reference faces I provided and blend them into ONE completely new, unique woman — "
    "she should look like a real person who could be the result of mixing these two faces, not a copy of either one. "
    "Merge their eye shape, nose, lips, jawline, cheekbones and skin tone naturally so the final face is a believable "
    "new individual with her own identity.\n\n"
    "Generate a single hyper-realistic studio portrait of her:\n\n"
    "POSE & FRAMING:\n"
    "- Body at a subtle 3/4 angle, but head and gaze turned straight toward the camera, looking directly into the lens.\n"
    "- Framed from the head to mid-torso, centered and well-composed.\n\n"
    "BACKGROUND & LIGHT:\n"
    "- Smooth neutral grey seamless studio backdrop, evenly lit.\n"
    "- Soft professional studio lighting with gentle directional shadows and natural depth on the face, "
    "subtle rim light separating hair from the background.\n\n"
    "SKIN (very important — must look real):\n"
    "- Realistic human skin with visible fine pores, natural micro-texture and subtle imperfections.\n"
    "- Delicate peach-fuzz visible on the cheeks and jaw in the light, faint natural skin tone variation, "
    "no uniform flat color.\n"
    "- Natural asymmetry, real subsurface scattering giving the skin a soft living translucency.\n"
    "- Absolutely NO plastic, waxy, airbrushed or AI-smooth skin.\n\n"
    "EYES (must look alive):\n"
    "- Crisp detailed irises with fine radial fibers and natural depth, clear defined limbal ring.\n"
    "- Realistic catchlights reflecting the studio light, moist natural eye surface.\n"
    "- Individual lower and upper lashes, natural tear line, soft realistic under-eye texture.\n\n"
    "HAIR (detailed structure):\n"
    "- Individual strands visible with natural flyaways, realistic strand-by-strand detail and depth.\n"
    "- Natural shine and directional flow, soft volume at the roots, defined texture rather than a solid mass.\n"
    "- Realistic hairline with fine baby hairs framing the face.\n\n"
    "QUALITY:\n"
    "- Photorealistic, shot like a professional DSLR portrait with an 85mm lens at f/2, shallow natural depth of field.\n"
    "- Sharp tack-focus on the eyes, ultra-detailed, high resolution, natural color grading.\n"
    "- Calm confident expression, natural light makeup.\n\n"
    "Do NOT copy either reference face exactly. Do NOT create a collage or two faces. "
    "Avoid plastic skin, over-retouching, distorted proportions or extra faces."
)

DEFAULT_BODY_COMPOSE_PROMPT = (
    "I provided two reference images. Use them like this:\n"
    "- IMAGE 1 (the face photo): take the FACE and head from here — the facial features, bone structure, "
    "skin tone, hair and overall identity of the face must come entirely from Image 1.\n"
    "- IMAGE 2 (the full-body photo): take the BODY from here — the body shape, proportions, build, "
    "figure and posture come from Image 2.\n\n"
    "Combine them into ONE seamless, believable real woman: the face from Image 1 placed naturally on the body "
    "from Image 2, with skin tone and lighting matched perfectly so there is no visible seam or mismatch "
    "between face, neck and body. She must look like a single real person photographed in one shot.\n\n"
    "Generate a single hyper-realistic full-body studio portrait of her:\n\n"
    "POSE & FRAMING:\n"
    "- Full body visible from head to feet, standing upright.\n"
    "- She faces straight toward the camera, head and gaze directed forward into the lens, "
    "natural relaxed confident stance.\n"
    "- Well-composed, centered, full figure in frame with a little space above the head and below the feet.\n\n"
    "BACKGROUND & LIGHT:\n"
    "- Smooth neutral grey seamless studio backdrop, evenly lit.\n"
    "- Soft professional studio lighting with gentle directional shadows, natural depth, "
    "subtle rim light separating her from the background.\n\n"
    "SKIN (must look real):\n"
    "- Realistic human skin with visible fine pores, natural micro-texture and subtle imperfections.\n"
    "- Delicate peach-fuzz catching the light, faint natural tone variation, real subsurface scattering, "
    "natural asymmetry.\n"
    "- Consistent realistic skin texture across face, neck, arms and body.\n"
    "- Absolutely NO plastic, waxy, airbrushed or AI-smooth skin.\n\n"
    "EYES (must look alive):\n"
    "- Crisp detailed irises with fine radial fibers, clear limbal ring, realistic catchlights, moist natural surface.\n"
    "- Individual upper and lower lashes, natural tear line.\n\n"
    "HAIR (detailed structure):\n"
    "- Individual strands with natural flyaways, strand-by-strand detail, natural shine and flow, soft root volume.\n"
    "- Realistic hairline with fine baby hairs framing the face.\n\n"
    "QUALITY:\n"
    "- Photorealistic, shot like a professional full-body DSLR portrait with a 50mm lens, "
    "sharp detail across the whole figure.\n"
    "- Tack-sharp focus on the face and eyes, ultra-detailed, high resolution, natural color grading.\n"
    "- Calm confident expression, natural light makeup.\n\n"
    "Do NOT change the identity of the face from Image 1. Keep the body proportions faithful to Image 2. "
    "Avoid plastic skin, distorted or extra limbs, warped hands, mismatched skin tone between face and body, "
    "extra faces or collage look."
)

DEFAULT_MODEL_SHEET_PROMPT = (
    "Сделай на нейтральном сером фоне раскладку персонажа с картинки, треть раскладки слева — "
    "крупный план лица, остальное — крупные планы вид справа, вид слева, вид сзади. "
    "В полный рост спереди и в полный рост сзади. "
    "Одежда - черный топ с глубоким декольте черные спортивные шорты из облегающего материала"
)

# Workflow turnaround: character sheet + белая сетка на лице (moderation guide).
_WORKFLOW_FACE_GRID_INSTRUCTION = (
    "On EVERY panel where the face is clearly visible, overlay a white guide grid on the face: "
    "front face close-up, left and right face profile close-ups, and the face area in full-body "
    "front and full-body side panels when the face is shown. "
    "Grid style: crisp bright white lines, clearly visible (~65–75% opacity, 2–3 px stroke) — "
    "not faint or washed-out; like a neutral wireframe overlay. "
    "The grid must NOT hide eyes, nose, mouth, or facial structure; identity stays fully readable. "
    "Do NOT add any grid on back-of-head panels, rear views where only the back of the head/hair is "
    "visible, full-body back panel, or any panel where the face is not visible."
)

DEFAULT_WORKFLOW_SHEET_PROMPT = (
    "On a neutral gray background, create a character turnaround sheet from the source image. "
    "Left third: large front face close-up. "
    "Remaining panels: face right profile, face left profile, back of head (no face visible); "
    "full body front, full body left side, full body right side, full body back. "
    "Keep the exact same outfit, colors, and styling as the source image. "
    f"{_WORKFLOW_FACE_GRID_INSTRUCTION}"
)

# Один кадр (первый кадр workflow) — лёгкая зернистость вместо сетки на лице.
WORKFLOW_SINGLE_FRAME_FILM_GRAIN_INSTRUCTION = (
    "Apply subtle natural film grain and fine photographic noise across the whole image — "
    "especially on skin, face, and shadow areas — like a high-ISO candid photo. "
    "Keep it realistic and unobtrusive. "
    "Do NOT add grid, mesh, wireframe, or face-tracking overlays."
)


def append_workflow_first_frame_film_grain(prompt: str) -> str:
    """Добавляет инструкцию зернистости для первого кадра workflow."""
    body = (prompt or "").strip()
    marker = "film grain"
    if marker in body.lower():
        return body
    if body:
        return f"{body}\n\n{WORKFLOW_SINGLE_FRAME_FILM_GRAIN_INSTRUCTION}"
    return WORKFLOW_SINGLE_FRAME_FILM_GRAIN_INSTRUCTION


def append_workflow_first_frame_face_grid(prompt: str) -> str:
    """Deprecated alias — первый кадр использует film grain, не сетку."""
    return append_workflow_first_frame_film_grain(prompt)


MODEL_SHEET_ASPECT_KEY = "16:9"


def resolve_face_merge_prompt(user_prompt: str | None) -> str:
    p = (user_prompt or "").strip()
    return p if p else DEFAULT_FACE_MERGE_PROMPT


def resolve_body_compose_prompt(user_prompt: str | None) -> str:
    p = (user_prompt or "").strip()
    return p if p else DEFAULT_BODY_COMPOSE_PROMPT


def resolve_model_sheet_prompt(user_prompt: str | None) -> str:
    p = (user_prompt or "").strip()
    return p if p else DEFAULT_MODEL_SHEET_PROMPT


def resolve_workflow_model_sheet_prompt(user_prompt: str | None) -> str:
    """Развёртка для workflow: ракурсы + сетка на лице + одежда с первого кадра."""
    extra = (user_prompt or "").strip()
    base = DEFAULT_WORKFLOW_SHEET_PROMPT
    if extra:
        return f"{base}\n\nAdditional wardrobe/scene notes from user:\n{extra}"
    return base


def _guess_upload_filename(content_type: str, label: str) -> str:
    ct = (content_type or "").lower()
    ext = "png" if "png" in ct else "webp" if "webp" in ct else "jpg"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:32] or "image"
    return f"{safe}.{ext}"


def _public_pose_url(*, owner_id: int, raw: bytes, content_type: str, pub: str) -> str:
    fid = save_pose_reference_bytes(
        owner_id=owner_id,
        raw=raw,
        content_type=content_type or "image/jpeg",
    )
    ptok = create_pose_reference_access_token(user_id=owner_id, file_id=fid)
    return f"{pub}/api/studio/public-pose-reference?t={quote(ptok, safe='')}"


def _read_generation_file_bytes(row: StudioGeneration) -> bytes | None:
    rel = (row.relative_path or "").strip()
    if not rel:
        return None
    path = (BACKEND_DIR / rel).resolve()
    if not str(path).startswith(str(BACKEND_DIR.resolve())):
        return None
    if not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


async def wavespeed_image_url_for_bootstrap(
    *,
    api_key: str,
    owner_id: int,
    pub: str,
    raw: bytes,
    content_type: str,
    label: str,
) -> str:
    """Сначала WaveSpeed Media upload; при сбое — публичный URL с нашего сервера."""
    fname = _guess_upload_filename(content_type, label)
    try:
        return await wavespeed_upload_image_bytes(
            api_key=api_key,
            data=raw,
            filename=fname,
            content_type=content_type or "image/jpeg",
        )
    except Exception as e:
        log.warning("bootstrap %s: wavespeed upload failed, public URL fallback: %s", label, e)
        return _public_pose_url(
            owner_id=owner_id,
            raw=raw,
            content_type=content_type,
            pub=pub,
        )


async def wavespeed_url_for_bootstrap_generation(
    *,
    api_key: str,
    owner_id: int,
    pub: str,
    row: StudioGeneration,
) -> str:
    raw = _read_generation_file_bytes(row)
    if raw:
        ct = (row.content_type or "image/png").strip() or "image/png"
        return await wavespeed_image_url_for_bootstrap(
            api_key=api_key,
            owner_id=owner_id,
            pub=pub,
            raw=raw,
            content_type=ct,
            label=f"gen{row.id}",
        )
    tok = create_generation_image_access_token(user_id=owner_id, generation_id=row.id)
    return f"{pub}/api/studio/public-generation-image?t={quote(tok, safe='')}"


def humanize_wavespeed_provider_error(message: str) -> str:
    return format_wavespeed_user_error(message)
