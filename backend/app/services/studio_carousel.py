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
            "STORY_BEAT: Hook. CAPTURE: same as master. LIMBS: keep phone hand from master. WARDROBE: unchanged.",
            "STORY_BEAT: Beat. CAPTURE: same grammar. LIMBS: free hand to hair; phone hand unchanged. WARDROBE: unchanged.",
            "STORY_BEAT: Reaction smile. LIMBS: both arms plausible. WARDROBE: unchanged.",
            "STORY_BEAT: Prop lean same room. LIMBS: elbow on prop. WARDROBE: unchanged.",
            "STORY_BEAT: Close emotional beat. LIMBS: explicit L/R arms. WARDROBE: unchanged.",
            "STORY_BEAT: Playful smirk. LIMBS: mirror/selfie rules. WARDROBE: unchanged.",
            "STORY_BEAT: Payoff gaze. LIMBS: stable anatomy. WARDROBE: unchanged.",
            "STORY_BEAT: Coda. LIMBS: match master. WARDROBE: unchanged.",
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
    "\n\n[FIRST_FRAME_MANDATE] Carousel frame #1: apply SHOT_VARIATION with a visible mood/crop/pose "
    "change — same capture grammar as master (selfie stays selfie). Do not return a pixel-identical copy."
)

_CAROUSEL_FOLLOWUP_SHOT_REINFORCE = (
    "\n\n[POSE_MANDATE] This carousel frame must look like a **different photo from the same shoot**: "
    "execute POSE_DELTA and STORY_BEAT fully — new body pose, new expression, and/or new camera distance. "
    "Do NOT return a near-duplicate of the master frame."
)


def carousel_first_shot_reinforce() -> str:
    """Доп. инструкция для первого кадра — модель часто копирует мастер без неё."""
    return _CAROUSEL_FIRST_SHOT_REINFORCE


_CAROUSEL_VARIATION_APPLY = (
    "\n\n[APPLY_SHOT] Execute STORY_BEAT, POSE_DELTA, camera, gaze, and expression from SHOT_VARIATION. "
    "If SHOT_VARIATION includes LIMBS — match left/right arms, phone hand, and leg positions exactly; "
    "no extra limbs or anatomically impossible poses. Preserve capture grammar (selfie stays selfie, "
    "mirror stays mirror). Same room and same garment pieces as master unless NSFW WARDROBE_DELTA "
    "explicitly removes/opens an existing piece. Visible pose/framing change is mandatory."
)

_CAROUSEL_SFW_STORY_HINT = (
    "\n\n[SFW_STORY] Mini-scenario frame — no undressing, no new clothes, no location change. "
    "Same outfit pieces as master throughout."
)

_CAROUSEL_NSFW_STORY_HINT = (
    "\n\n[NSFW_STORY] Execute STORY_BEAT. WARDROBE_DELTA may only open/remove garments already "
    "worn in master — never add or swap outfit. Same room. Preserve face (@Image2) and body fidelity."
)


def append_carousel_shot_reinforce(body: str, *, shot_index: int) -> str:
    """Anti-clone: первый кадр — лёгкий сдвиг; остальные — явная смена позы/кадра."""
    text = (body or "").strip()
    if shot_index == 0:
        text += carousel_first_shot_reinforce()
    else:
        text += _CAROUSEL_FOLLOWUP_SHOT_REINFORCE
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


def build_carousel_grok_wave_prompt(
    *,
    master_scene_context: str,
    shot_variation: str,
    story_sfw: bool = False,
) -> str:
    lock = load_carousel_lock_text()
    base = (master_scene_context or "").strip() or "(master image is source of truth for identity, outfit, room)"
    variation = (shot_variation or "").strip()
    story_hint = _CAROUSEL_SFW_STORY_HINT if story_sfw else ""
    return (
        f"{lock}\n\nBASE_SCENE (from master frame):\n{base}\n\n"
        f"[SHOT_VARIATION — Instagram carousel frame planned from master photo analysis]\n{variation}"
        f"{story_hint}"
        f"{_CAROUSEL_VARIATION_APPLY}"
        f"{_CAROUSEL_IDENTITY_REINFORCE}"
    )


def build_carousel_multi_ref_wave_prompt(
    *,
    master_scene_context: str,
    shot_variation: str,
    ref_binding_block: str,
    story_nsfw: bool = False,
    story_sfw: bool = False,
) -> str:
    """Multi-ref carousel: явные @ImageN роли + shot variation + story mode."""
    lock = load_carousel_lock_text()
    base = (master_scene_context or "").strip() or "(see reference images)"
    variation = (shot_variation or "").strip()
    story_hint = ""
    if story_nsfw:
        story_hint = _CAROUSEL_NSFW_STORY_HINT
    elif story_sfw:
        story_hint = _CAROUSEL_SFW_STORY_HINT
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
        "Analyze THIS master photo like an Instagram creative director. "
        "Plan a SFW mini-story carousel where each swipe shows a clearly different photo from the same shoot: "
        "new poses (sit/stand/lean/walk), new moods/expressions, new camera distances — not subtle clones. "
        "Use furniture/props visible in the room (bed, wall, mirror, window). "
        "Same room, same outfit pieces, no undressing. Respect capture grammar (selfie/mirror/candid/tripod). "
        "Every frame: POSE_DELTA + LIMBS with left/right arms and legs."
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
                "Task: (1) read MASTER_IMAGE — capture grammar, limbs inventory, scene affordances; "
                "(2) design a SFW Instagram carousel arc across FRAME_COUNT frames with scroll-stopping variety; "
                "(3) write exactly FRAME_COUNT img2img briefs with STORY_BEAT, POSE_DELTA, CAPTURE, LIMBS, "
                "CAMERA, GAZE/EXPR, WARDROBE (unchanged).\n\n"
                f"FRAME_COUNT: {n}\n\n"
                f"USER_DIRECTION:\n{direction}\n\n"
                f"MASTER_SCENE_TEXT:\n{scene or '(none — infer everything from MASTER_IMAGE)'}\n\n"
                "Attached: MASTER_IMAGE — base all limb positions and capture grammar on what you see."
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
    # Карусель — больше креатива в планировании поз/настроений, чем у scene compose.
    temp = min(0.78, max(temp, 0.55))
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
        "Plan an 18+ story carousel from this master. "
        "Tease→reveal arc: you may open/remove garments ALREADY worn in master — never add new clothes. "
        "Same room throughout. Respect capture grammar. "
        "Every frame: explicit LIMBS (left/right hands, phone hand, legs)."
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
                "Task: read MASTER_IMAGE, design NSFW story arc across FRAME_COUNT frames, "
                "write briefs with STORY_BEAT, CAPTURE, LIMBS, CAMERA, GAZE/EXPR, WARDROBE_DELTA "
                "(remove/open existing pieces only — no new garments).\n\n"
                f"FRAME_COUNT: {n}\n\nUSER_DIRECTION:\n{direction}\n\n"
                f"MASTER_SCENE_TEXT:\n{scene or '(none)'}\n\n"
                "Refs (@Image2 face, @Image3 body) will be sent to editor — do not contradict them."
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
