"""Seedance Director debug tool: Grok instruction → Seedance 2.0/2.5 prompts → WaveSpeed T2V."""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, settings

log = logging.getLogger(__name__)

CAMERA_MODES: dict[str, dict[str, str]] = {
    "A": {
        "id": "A",
        "label_en": "SELFIE — she films herself, front camera",
        "label_ru": "Селфи — телефон в руке на вытянутой руке",
        "brief": "Camera mode A — SELFIE. She films herself with the front camera at arm's length.",
    },
    "B": {
        "id": "B",
        "label_en": "SOMEONE ELSE FILMING — standing still",
        "label_ru": "Снимает друг, стоя сбоку",
        "brief": "Camera mode B — SOMEONE ELSE FILMING, standing still beside her.",
    },
    "C": {
        "id": "C",
        "label_en": "PROPPED — phone resting, nobody touching it",
        "label_ru": "Телефон стоит, никто не держит",
        "brief": "Camera mode C — PROPPED. Phone resting on a surface, untouched during the take.",
    },
    "D": {
        "id": "D",
        "label_en": "WALKING WITH HER — operator moving",
        "label_ru": "Оператор идёт рядом",
        "brief": "Camera mode D — WALKING WITH HER. Operator moving alongside or backwards in front of her.",
    },
    "E": {
        "id": "E",
        "label_en": "MIRROR — phone visible in frame",
        "label_ru": "Зеркало — телефон виден в кадре, рука перекрывает часть",
        "brief": "Camera mode E — MIRROR. She films her reflection; phone and raised arm are visible in frame.",
    },
}

_INSTRUCTION_NAME = "seedance_director_instruction.txt"


def _director_instruction_candidates() -> list[Path]:
    """data/prompts (Docker volume) → _bundled_prompts (образ) — как у Grok compose."""
    ordered = [
        (BACKEND_DIR / "data" / "prompts" / _INSTRUCTION_NAME).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / _INSTRUCTION_NAME).resolve(),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for path in ordered:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def load_seedance_director_instruction() -> str:
    for path in _director_instruction_candidates():
        if path.is_file():
            raw = path.read_text(encoding="utf-8")
            if "{{MY_BRIEF_BLOCK}}" not in raw:
                raise RuntimeError(
                    f"seedance director instruction missing {{{{MY_BRIEF_BLOCK}}}}: {path}"
                )
            return raw
    tried = ", ".join(str(p) for p in _director_instruction_candidates())
    raise RuntimeError(f"seedance director instruction not found (tried: {tried})")


def normalize_camera_mode(raw: str | None) -> str:
    m = (raw or "A").strip().upper()
    if m in CAMERA_MODES:
        return m
    aliases = {
        "SELFIE": "A",
        "FRIEND": "B",
        "OTHER": "B",
        "PROPPED": "C",
        "STATIC": "C",
        "WALKING": "D",
        "OPERATOR": "D",
        "MIRROR": "E",
    }
    return aliases.get(m, "A")


def normalize_aspect(raw: str | None) -> str:
    a = (raw or "9:16").strip()
    if a in ("9:16", "16:9", "1:1", "3:4", "4:3"):
        return a
    return "9:16"


def format_label_for_aspect(aspect: str) -> str:
    if aspect == "16:9":
        return "Horizontal 16:9"
    if aspect == "9:16":
        return "Vertical 9:16"
    return aspect


@dataclass
class DirectorImageRef:
    role: str
    filename: str = ""
    data: bytes = b""
    mime: str = "image/jpeg"


@dataclass
class DirectorPiece:
    version: str  # "2.0" | "2.5"
    piece_id: str  # "1a", "1b", …
    span: str = ""
    start_frame: str = ""
    prompt: str = ""


@dataclass
class DirectorComposeResult:
    raw_text: str
    pieces: list[DirectorPiece] = field(default_factory=list)
    assumed: str = ""
    instruction_chars: int = 0
    image_count: int = 0


def build_my_brief_block(
    *,
    what_happens: str,
    duration_seconds: int,
    aspect_ratio: str,
    camera_mode: str,
    image_roles: list[str],
) -> str:
    mode = CAMERA_MODES[normalize_camera_mode(camera_mode)]
    lines: list[str] = [
        "WHAT HAPPENS:",
        (what_happens or "").strip() or "(not specified — invent the smallest real moment that fits)",
        "",
        f"DURATION: {int(duration_seconds)} seconds",
        f"FORMAT: {format_label_for_aspect(normalize_aspect(aspect_ratio))} ({normalize_aspect(aspect_ratio)})",
        "",
        f"CAMERA MODE (mandatory — paste this mode's full block from section 1b into every STYLE BLOCK):",
        mode["brief"],
        f"Mode id: {mode['id']}. {mode['label_en']}",
        "",
        "REFERENCE IMAGES — count and roles (Image N = attachment order):",
    ]
    if not image_roles:
        lines.append("(no images attached)")
    else:
        for i, role in enumerate(image_roles, start=1):
            r = (role or "").strip() or "unspecified reference"
            lines.append(f"Image {i} — {r}")
        lines.append("")
        lines.append(
            "Use the image count to decide Set 1 (three images: first frame / face / body) "
            "or Set 2 (two images: character / location) from section 2. "
            "If the count is neither 2 nor 3, still bind every attached image by the roles above "
            "and invent the smallest consistent set rules that fit."
        )
    return "\n".join(lines)


def assemble_director_instruction(
    *,
    what_happens: str,
    duration_seconds: int,
    aspect_ratio: str,
    camera_mode: str,
    image_roles: list[str],
) -> str:
    template = load_seedance_director_instruction()
    brief = build_my_brief_block(
        what_happens=what_happens,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        camera_mode=camera_mode,
        image_roles=image_roles,
    )
    return template.replace("{{MY_BRIEF_BLOCK}}", brief)


_HEADER_RE = re.compile(
    r"(?im)^\s*Seedance\s+(2\.0|2\.5)\s*[—\-–]\s*(\d+[a-z])\s*[—\-–]\s*([^\n]+)\s*$"
)
_START_FRAME_RE = re.compile(r"(?im)^\s*Start frame:\s*(.+?)\s*$")
_ASSUMED_RE = re.compile(r"(?im)^\s*Assumed:\s*(.+?)\s*$")
_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_-]*)\s*\n([\s\S]*?)```")


def parse_director_response(raw: str) -> DirectorComposeResult:
    text = (raw or "").strip()
    assumed_m = _ASSUMED_RE.search(text)
    assumed = assumed_m.group(1).strip() if assumed_m else ""

    pieces: list[DirectorPiece] = []
    # Prefer fenced blocks with a header line above each fence.
    for m in _FENCE_RE.finditer(text):
        block = m.group(1).strip()
        before = text[: m.start()]
        header_lines = [ln.strip() for ln in before.splitlines() if ln.strip()]
        header = header_lines[-1] if header_lines else ""
        start_frame = ""
        if len(header_lines) >= 2 and header_lines[-1].lower().startswith("start frame:"):
            start_frame = header_lines[-1].split(":", 1)[1].strip()
            header = header_lines[-2]
        elif len(header_lines) >= 2:
            # header then Start frame on next line before fence
            for i in range(len(header_lines) - 1, max(-1, len(header_lines) - 4), -1):
                hm = _HEADER_RE.match(header_lines[i])
                if hm:
                    header = header_lines[i]
                    # look forward for Start frame between header and fence
                    for j in range(i + 1, len(header_lines)):
                        sm = _START_FRAME_RE.match(header_lines[j])
                        if sm:
                            start_frame = sm.group(1).strip()
                            break
                    break
        hm = _HEADER_RE.match(header)
        if not hm:
            # Try scanning a few lines above
            found = None
            for ln in reversed(header_lines[-6:]):
                found = _HEADER_RE.match(ln)
                if found:
                    break
            if not found:
                continue
            hm = found
        pieces.append(
            DirectorPiece(
                version=hm.group(1),
                piece_id=hm.group(2).lower(),
                span=hm.group(3).strip(),
                start_frame=start_frame,
                prompt=block,
            )
        )

    if not pieces:
        # Fallback: split by headers without relying on fences
        matches = list(_HEADER_RE.finditer(text))
        for i, hm in enumerate(matches):
            start = hm.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()
            sm = _START_FRAME_RE.search(chunk)
            start_frame = sm.group(1).strip() if sm else ""
            if sm:
                chunk = (chunk[: sm.start()] + chunk[sm.end() :]).strip()
            # Strip wrapping fences if present
            fm = _FENCE_RE.search(chunk)
            prompt = fm.group(1).strip() if fm else chunk
            if assumed and prompt.endswith(f"Assumed: {assumed}"):
                prompt = prompt[: -len(f"Assumed: {assumed}")].strip()
            pieces.append(
                DirectorPiece(
                    version=hm.group(1),
                    piece_id=hm.group(2).lower(),
                    span=hm.group(3).strip(),
                    start_frame=start_frame,
                    prompt=prompt,
                )
            )

    return DirectorComposeResult(
        raw_text=text,
        pieces=pieces,
        assumed=assumed,
        image_count=0,
    )


def _image_data_url(data: bytes, mime: str) -> str:
    m = (mime or "image/jpeg").split(";")[0].strip()
    if m not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        m = "image/jpeg"
    b64 = base64.standard_b64encode(data).decode("ascii")
    return f"data:{m};base64,{b64}"


async def compose_seedance_director_prompts(
    *,
    images: list[DirectorImageRef],
    what_happens: str,
    duration_seconds: int,
    aspect_ratio: str,
    camera_mode: str,
    credentials: Any = None,
) -> DirectorComposeResult:
    from app.services.studio_grok_motion import (
        _grok_fps_stills_model,
        grok_motion_studio_credentials,
    )
    from app.services.studio_grok_scene_compose import (
        _grok_scene_compose_model,
        grok_scene_compose_configured,
    )
    from app.services.studio_openai import chat_completion_openai_compatible_text

    if not images:
        raise RuntimeError("Нужна хотя бы одна фотография")
    brief = (what_happens or "").strip()
    if not brief:
        raise RuntimeError("Заполните бриф (что происходит)")

    roles = [im.role for im in images]
    instruction = assemble_director_instruction(
        what_happens=brief,
        duration_seconds=max(1, int(duration_seconds)),
        aspect_ratio=aspect_ratio,
        camera_mode=camera_mode,
        image_roles=roles,
    )

    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": instruction},
        {
            "type": "text",
            "text": (
                f"Attached images in order ({len(images)}). "
                "Bind them by the roles listed in MY BRIEF."
            ),
        },
    ]
    for i, im in enumerate(images, start=1):
        role = (im.role or "").strip() or "unspecified"
        user_content.append(
            {
                "type": "text",
                "text": f"--- Image {i}: {role} ---",
            }
        )
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": _image_data_url(im.data, im.mime)},
            }
        )

    if grok_scene_compose_configured():
        model = (_grok_scene_compose_model() or "").strip() or _grok_fps_stills_model()
        creds = credentials or grok_motion_studio_credentials()
    else:
        if not credentials:
            raise RuntimeError("Grok/LLM не настроен")
        model = (settings.openai_studio_model_vision or "").strip() or settings.openai_studio_model
        creds = credentials

    text = await chat_completion_openai_compatible_text(
        model=model,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=16000,
        temperature=0.35,
        credentials=creds,
        timeout_seconds=300.0,
    )
    result = parse_director_response(text or "")
    result.instruction_chars = len(instruction)
    result.image_count = len(images)
    if not result.pieces:
        log.warning("seedance director: no pieces parsed, raw_len=%s", len(result.raw_text))
    return result


def variant_for_piece_version(version: str) -> str:
    v = (version or "").strip()
    if v == "2.5":
        return "seedance_25"
    return "standard"


def duration_from_span(span: str, *, fallback: int, version: str) -> int:
    """Parse '0.0–10.0s' / '0-15s' into integer seconds for the API."""
    s = (span or "").strip().lower().replace("–", "-").replace("—", "-")
    m = re.search(r"([\d.]+)\s*-\s*([\d.]+)\s*s?", s)
    if m:
        try:
            start = float(m.group(1))
            end = float(m.group(2))
            dur = int(round(max(1.0, end - start)))
        except ValueError:
            dur = int(fallback)
    else:
        dur = int(fallback)
    if (version or "").strip() == "2.5":
        return max(4, min(30, dur))
    return max(4, min(15, dur))
