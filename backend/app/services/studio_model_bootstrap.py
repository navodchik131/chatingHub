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
    "Integrate a face into an existing scene. Substitute the face in the reference image "
    "with the face from the donor image. The objective is a seamless merge: the new face must "
    "inherit the exact expression, pose, and lighting interaction from the reference, while its "
    "color attributes (hair and eyes) are adapted from the donor for a perfectly harmonious and "
    "natural result."
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

MODEL_SHEET_ASPECT_KEY = "16:9"


def resolve_face_merge_prompt(user_prompt: str | None) -> str:
    p = (user_prompt or "").strip()
    return p if p else DEFAULT_FACE_MERGE_PROMPT


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
