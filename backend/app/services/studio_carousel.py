from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

from app.config import BACKEND_DIR, settings
from app.services.studio_grok_motion import (
    _grok_fps_stills_model,
    grok_motion_studio_credentials,
)
from app.services.studio_openai import (
    StudioOpenAiCredentials,
    _strip_code_fences,
    chat_completion_openai_compatible_text,
)

log = logging.getLogger(__name__)


def _read_text(rel: str) -> str:
    p = (BACKEND_DIR / rel).resolve()
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return ""


def _grok_carousel_prompt_candidates() -> list[Path]:
    rel = (getattr(settings, "grok_carousel_compose_system_path", None) or "").strip()
    name = "grok_carousel_compose_system.txt"
    if rel:
        name = (BACKEND_DIR / rel).name
    ordered = [
        (BACKEND_DIR / rel).resolve() if rel else None,
        (BACKEND_DIR / "data" / "prompts" / name).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / name).resolve(),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for item in ordered:
        if item is None or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def load_grok_carousel_compose_system() -> str:
    inline = (getattr(settings, "grok_carousel_compose_system_inline", None) or "").strip()
    if inline:
        return inline
    for path in _grok_carousel_prompt_candidates():
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t:
                return t
    raise RuntimeError(
        "Промпт Grok carousel пуст: добавьте grok_carousel_compose_system.txt "
        "или GROK_CAROUSEL_COMPOSE_SYSTEM_INLINE"
    )


def _extract_json_object(text: str) -> dict | None:
    """Best-effort extract of a top-level JSON object (allows leading/trailing noise)."""
    raw = (text or "").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def parse_carousel_grok_prompts(raw: str, *, count: int) -> list[str]:
    """Parse Grok JSON or «Prompt 1: …» blocks into exactly `count` strings."""
    text = _strip_code_fences(raw or "").strip()
    if not text:
        raise RuntimeError("Grok carousel: пустой ответ")

    data = _extract_json_object(text)
    if data is not None:
        prompts = data.get("prompts")
        if isinstance(prompts, list):
            out = [str(p).strip() for p in prompts if str(p).strip()]
            if len(out) >= count:
                master_read = data.get("master_read")
                if isinstance(master_read, dict) and master_read:
                    log.info(
                        "carousel grok master_read capture=%s camera=%s pose=%s gaze=%s expression=%s",
                        str(master_read.get("capture_type") or "")[:40],
                        str(master_read.get("camera") or "")[:80],
                        str(master_read.get("pose") or "")[:80],
                        str(master_read.get("gaze") or "")[:80],
                        str(master_read.get("expression") or "")[:80],
                    )
                return out[:count]

    found: list[tuple[int, str]] = []
    pattern = re.compile(
        r"(?im)^\s*Prompt\s+(\d+)\s*[:\.]?\s*(.+?)(?=^\s*Prompt\s+\d+\s*[:\.]|\Z)",
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        body = m.group(2).strip()
        if body:
            found.append((int(m.group(1)), body))
    if found:
        found.sort(key=lambda x: x[0])
        out = [p for _, p in found]
        if len(out) >= count:
            return out[:count]

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    numbered = []
    for ln in lines:
        m = re.match(r"^\d+[\).\]]\s*(.+)", ln)
        if m:
            numbered.append(m.group(1).strip())
    if len(numbered) >= count:
        return numbered[:count]

    raise RuntimeError(
        f"Grok carousel: не удалось разобрать {count} промптов из ответа "
        f"(получено {len(found) or len(numbered) or 0})"
    )


def load_carousel_lock_text() -> str:
    t = _read_text("data/prompts/image_studio_carousel_lock.txt")
    if t:
        return t
    return (
        "[CAROUSEL_SCENE_LOCK] Keep same person, outfit, and room as the master image; "
        "only change camera and pose as instructed in SHOT_VARIATION."
    )


def load_carousel_variation_blocks() -> list[str]:
    raw = _read_text("data/prompts/image_studio_carousel_variations.txt")
    if not raw:
        return [
            "[SIDE:LEFT_3Q] Camera LEFT three-quarter ~35°; face visible. Same exact face as master.",
            "[SIDE:RIGHT_3Q] Camera RIGHT three-quarter ~35°; opposite side from LEFT. Same exact face as master.",
            "[SIDE:BACK_R] Behind-right; over-shoulder partial face must match master. Same hair, outfit, body.",
            "[POSE:FULL] Full body; new stance and arm pose. Face visible. Same exact face as master.",
            "[SIDE:PROFILE_R] Near-profile right ~60°; face readable. Same exact face as master.",
            "[SIDE:LOW_L] Low angle front-left three-quarter. Same exact face as master.",
            "[SIDE:BACK_L] Behind-left; over-shoulder glance; partial face matches master.",
            "[POSE:CLOSE] Medium-close; expression change. Same exact face as master.",
        ]
    parts = [b.strip() for b in raw.split("\n---\n") if b.strip()]
    return parts if parts else [
        "Camera: eye level, medium shot; small pose adjustment only; lock outfit and room."
    ]


_CAROUSEL_VARIATION_ORDER = (
    1,  # RIGHT three-quarter first — break from typical left-facing master
    2,  # back over right shoulder
    0,  # LEFT three-quarter
    6,  # back over left shoulder
    3,  # full-body pose change
    4,  # near-profile right
    5,  # low angle left
    7,  # close expression variant
)


def carousel_variation_at(shot_index: int) -> str:
    blocks = load_carousel_variation_blocks()
    if not blocks:
        return "Camera: medium three-quarter; small pose change. Same person as master."
    order = _CAROUSEL_VARIATION_ORDER
    idx = order[shot_index % len(order)] % len(blocks)
    return blocks[idx]


_CAROUSEL_IDENTITY_REINFORCE = (
    "\n\n[IDENTITY_REINFORCE] Same person as the master input — match face whenever visible; "
    "match hair, outfit, body, and skin on any visible skin. Never swap to a different model."
)

_CAROUSEL_FIRST_SHOT_REINFORCE = (
    "\n\n[FIRST_FRAME_MANDATE] Carousel frame #1: output MUST differ clearly from the master input — "
    "apply SHOT_VARIATION camera/pose/crop/expression changes; never return an unchanged copy."
)


def carousel_first_shot_reinforce() -> str:
    """Доп. инструкция для первого кадра — модель часто копирует мастер без неё."""
    return _CAROUSEL_FIRST_SHOT_REINFORCE


_CAROUSEL_VARIATION_APPLY = (
    "\n\n[APPLY_SHOT] Execute this frame's camera geometry, crop, body pose, gaze, expression, "
    "and any prop interaction from SHOT_VARIATION. Preserve the master's capture grammar "
    "(selfie stays selfie, mirror stays mirror). Do not keep the master's identical pose/angle "
    "unless SHOT_VARIATION says so."
)


def append_carousel_shot_reinforce(body: str, *, shot_index: int) -> str:
    """Усиливает промпт для кадра 0 — anti-clone."""
    text = (body or "").strip()
    if shot_index == 0:
        text += carousel_first_shot_reinforce()
    return text


def build_carousel_wave_prompt(*, master_refined_json: str, shot_index: int) -> str:
    lock = load_carousel_lock_text()
    v = carousel_variation_at(shot_index)
    base = (master_refined_json or "").strip()
    return (
        f"{lock}\n\nBASE_SCENE_JSON (source of truth for styling — do not delete identity or wardrobe cues):\n"
        f"{base}\n\n[SHOT_VARIATION — this frame only]\n{v}"
        f"{_CAROUSEL_VARIATION_APPLY}"
        f"{_CAROUSEL_IDENTITY_REINFORCE}"
    )


def build_carousel_grok_wave_prompt(*, master_scene_context: str, shot_variation: str) -> str:
    lock = load_carousel_lock_text()
    base = (master_scene_context or "").strip() or "(master image is source of truth for identity, outfit, room)"
    variation = (shot_variation or "").strip()
    return (
        f"{lock}\n\nBASE_SCENE (from master frame):\n{base}\n\n"
        f"[SHOT_VARIATION — Instagram carousel frame planned from master photo analysis]\n{variation}"
        f"{_CAROUSEL_VARIATION_APPLY}"
        f"{_CAROUSEL_IDENTITY_REINFORCE}"
    )


def build_carousel_multi_ref_wave_prompt(
    *,
    master_scene_context: str,
    shot_variation: str,
    ref_binding_block: str,
    story_nsfw: bool = False,
) -> str:
    """Multi-ref carousel: явные @ImageN роли + shot variation."""
    lock = load_carousel_lock_text()
    base = (master_scene_context or "").strip() or "(see reference images)"
    variation = (shot_variation or "").strip()
    story_hint = ""
    if story_nsfw:
        story_hint = (
            "\n\n[NSFW_STORY] Execute the STORY_BEAT in SHOT_VARIATION. "
            "Wardrobe changes only as explicitly described in the beat. "
            "Preserve face (@Image2), outfit anchor (@Image3), and anatomy (@Image4) fidelity."
        )
    refs = (ref_binding_block or "").strip()
    refs_block = f"\n\n{refs}\n" if refs else "\n"
    return (
        f"{lock}{refs_block}\n"
        f"BASE_SCENE (text context):\n{base}\n\n"
        f"[SHOT_VARIATION — this carousel frame only]\n{variation}"
        f"{story_hint}"
        f"{_CAROUSEL_VARIATION_APPLY}"
        f"{_CAROUSEL_IDENTITY_REINFORCE}"
    )


def static_carousel_variations(count: int) -> list[str]:
    n = max(2, min(8, int(count)))
    return [carousel_variation_at(i) for i in range(n)]


def _carousel_grok_vision_model() -> str:
    m = (settings.grok_scene_compose_model or "").strip()
    return m if m else _grok_fps_stills_model()


async def grok_compose_carousel_prompts(
    *,
    master_image_bytes: bytes,
    master_image_mime: str | None,
    user_direction: str,
    count: int,
    master_scene_text: str | None = None,
    credentials: StudioOpenAiCredentials | None = None,
) -> list[str]:
    """Grok vision: analyze master photo → N Instagram carousel img2img shot briefs."""
    if not master_image_bytes:
        raise RuntimeError("Grok carousel: нет MASTER_IMAGE")
    creds = credentials or grok_motion_studio_credentials()
    system = load_grok_carousel_compose_system()
    n = max(2, min(8, int(count)))
    direction = (user_direction or "").strip() or (
        "Plan a scroll-stopping Instagram carousel tailored to THIS exact master photo. "
        "First classify capture type (selfie / mirror selfie / candid / fixed camera) and "
        "keep that grammar in every frame. Be creatively bold: vary emotions when the mood "
        "allows, use real camera moves (high/low, punch-in detail crops, wider pull-back), "
        "and natural prop/environment interactions when the scene supports them — same person, "
        "outfit, and room throughout. Avoid generic near-duplicate three-quarters."
    )
    scene = (master_scene_text or "").strip()

    ref_mime = (master_image_mime or "image/jpeg").split(";")[0].strip()
    if ref_mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        ref_mime = "image/jpeg"
    ref_b64 = base64.standard_b64encode(master_image_bytes).decode("ascii")

    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                "Task: (1) read MASTER_IMAGE — capture grammar (selfie/mirror/candid), environment, "
                "camera, pose, gaze, expression, framing; "
                "(2) design FRAME_COUNT complementary Instagram frames that stay faithful to capture "
                "grammar but feel creatively distinct (emotions, camera height/distance, detail crops, "
                "prop interaction when natural); "
                "(3) write exactly FRAME_COUNT img2img SHOT_VARIATION briefs.\n\n"
                f"FRAME_COUNT: {n}\n\n"
                f"USER_DIRECTION:\n{direction}\n\n"
                f"MASTER_SCENE_TEXT:\n{scene or '(none — infer everything from MASTER_IMAGE)'}\n\n"
                "Attached: MASTER_IMAGE — base your decisions on what you actually see."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:{ref_mime};base64,{ref_b64}"},
        },
    ]

    model = _carousel_grok_vision_model()
    # Carousel planning needs more creative latitude than deterministic scene compose.
    temp = float(settings.grok_scene_compose_temperature)
    temp = min(1.0, max(temp, 0.68))
    raw_out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system + "\n\nFollow the output JSON format exactly. No markdown fences.",
            },
            {"role": "user", "content": user_parts},
        ],
        max_tokens=int(settings.grok_scene_compose_max_tokens),
        temperature=temp,
        credentials=creds,
        timeout_seconds=float(settings.grok_scene_compose_timeout_seconds),
    )
    prompts = parse_carousel_grok_prompts(raw_out, count=n)
    log.info("carousel grok composed shots=%s model=%s", len(prompts), model)
    return prompts


def _grok_carousel_nsfw_story_prompt_candidates() -> list[Path]:
    rel = (getattr(settings, "grok_carousel_nsfw_story_compose_system_path", None) or "").strip()
    name = "grok_carousel_nsfw_story_compose_system.txt"
    if rel:
        name = (BACKEND_DIR / rel).name
    ordered = [
        (BACKEND_DIR / rel).resolve() if rel else None,
        (BACKEND_DIR / "data" / "prompts" / name).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / name).resolve(),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for item in ordered:
        if item is None or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def load_grok_carousel_nsfw_story_compose_system() -> str:
    inline = (getattr(settings, "grok_carousel_nsfw_story_compose_system_inline", None) or "").strip()
    if inline:
        return inline
    for path in _grok_carousel_nsfw_story_prompt_candidates():
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t:
                return t
    raise RuntimeError(
        "NSFW carousel story prompt пуст: добавьте grok_carousel_nsfw_story_compose_system.txt"
    )


async def grok_compose_carousel_story_prompts(
    *,
    master_image_bytes: bytes,
    master_image_mime: str | None,
    user_direction: str,
    count: int,
    master_scene_text: str | None = None,
    credentials: StudioOpenAiCredentials | None = None,
) -> list[str]:
    """Grok vision: NSFW story arc → N carousel briefs with narrative escalation."""
    if not master_image_bytes:
        raise RuntimeError("Grok NSFW carousel: нет MASTER_IMAGE")
    creds = credentials or grok_motion_studio_credentials()
    system = load_grok_carousel_nsfw_story_compose_system()
    n = max(2, min(8, int(count)))
    direction = (user_direction or "").strip() or (
        "Plan an NSFW carousel story arc from this master photo. "
        "Progress the scenario naturally — tease, partial reveal, interaction with clothing/props — "
        "not just camera rotations. Same person and room throughout."
    )
    scene = (master_scene_text or "").strip()
    ref_mime = (master_image_mime or "image/jpeg").split(";")[0].strip()
    if ref_mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        ref_mime = "image/jpeg"
    ref_b64 = base64.standard_b64encode(master_image_bytes).decode("ascii")
    user_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                "Task: read MASTER_IMAGE, design a NSFW story arc across FRAME_COUNT frames, "
                "write exactly FRAME_COUNT img2img briefs with STORY_BEAT + camera + pose.\n\n"
                f"FRAME_COUNT: {n}\n\nUSER_DIRECTION:\n{direction}\n\n"
                f"MASTER_SCENE_TEXT:\n{scene or '(none)'}\n\n"
                "Additional refs (@Image2 face, @Image3 outfit, @Image4 anatomy) will be sent to the editor — "
                "briefs must not contradict them."
            ),
        },
        {"type": "image_url", "image_url": {"url": f"data:{ref_mime};base64,{ref_b64}"}},
    ]
    model = _carousel_grok_vision_model()
    temp = min(1.0, max(float(settings.grok_scene_compose_temperature), 0.72))
    raw_out = await chat_completion_openai_compatible_text(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system + "\n\nFollow the output JSON format exactly. No markdown fences.",
            },
            {"role": "user", "content": user_parts},
        ],
        max_tokens=int(settings.grok_scene_compose_max_tokens),
        temperature=temp,
        credentials=creds,
        timeout_seconds=float(settings.grok_scene_compose_timeout_seconds),
    )
    prompts = parse_carousel_grok_prompts(raw_out, count=n)
    log.info("carousel grok NSFW story composed shots=%s model=%s", len(prompts), model)
    return prompts
