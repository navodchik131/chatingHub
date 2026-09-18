"""Anchor Studio prompts — exact copy from anchor-studio_3.html.

Used for Face Swap (Mode A: with scene photo) and From-reference (Mode B: scene as text).
Image contract (единый порядок для всех профилей WaveSpeed):
  Mode A face_swap: Image1=face, Image2=body (raw or headless dressed), Image3=scene or gray mannequin canvas
  Mode A model_scene: Image1=face, Image2=body+outfit (dressed), Image3=scene photo
  Mode B: Image1=face, Image2=body+outfit (dressed); scene described in text only
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exact strings from anchor-studio_3.html
# ---------------------------------------------------------------------------

REALISM_BLOCK = (
    "Realism: visible skin pores especially on cheeks and nose bridge, fine vellus hair "
    "catching the light, subtle natural asymmetry, natural skin tone variation, no beauty "
    "filter, no plastic skin, no over-smoothing, no AI-perfect symmetry."
)

# Сцена-реф часто с OnlyFans/IG водяными знаками — при scene-first edit canvas их нельзя сохранять.
SCENE_OVERLAY_EXCLUSION_BLOCK = (
    "OVERLAYS_AND_TEXT (mandatory): The scene reference may contain watermarks, copyright "
    "notices, captions, subtitles, logos, stickers, social handles, @usernames, URLs, "
    "link-in-bio or profile links, platform branding (OnlyFans, Fansly, Instagram, "
    "Telegram, etc.), timecode, or UI overlays. Do NOT reproduce, preserve, or transfer "
    "any of them into the output — rebuild those areas as clean photograph (skin, fabric, "
    "hair, or environment). No on-screen text or graphics."
)

VISIBILITY_ONLY_PROMPT = """Look at this photo and determine only which parts of the person are visible in frame. Output in this EXACT format, nothing else:

VISIBILITY:
- Face: [visible / not visible — if not visible, briefly state why: turned away, cropped out, obscured]
- Hair: [visible / not visible]
- Upper body (torso, chest, arms): [visible / not visible]
- Lower body (hips, legs, feet): [visible / not visible]"""

IDENTITY_ANALYSIS_PROMPT = """Analyze these reference photos of the same person and produce a structured identity anchor for use in AI image generation prompts. Base every detail strictly on what is visible in the photos — do not invent or assume anything you cannot see. Cross-check consistency across all provided photos before finalizing each attribute.

Output in this EXACT format, with these exact section headers on their own line (used for automated parsing — do not rename, merge, or reorder them):

FACE:
- Face shape: [oval / round / heart / square / oblong]
- Cheekbones: [subtle / defined / high and prominent]
- Jawline: [description]
- Chin: [pointed / rounded / squared]
- Nose: [shape, bridge width, tip shape]
- Lips: [thin/medium/full, cupid's bow, natural color]
- Eyes: [shape, color, spacing, brow shape/thickness]
- Distinguishing marks: [freckles, moles, dimples — only if clearly visible]
- Skin tone and undertone: [description]

HAIR:
- Color: [base + highlights/lowlights]
- Texture: [straight/wavy/curly]
- Length: [specific]
- Typical part/style: [description]

UPPER BODY:
- Bust: [relative size]
- Shoulders and arms: [description]
- Waist: [narrow/average]

LOWER BODY:
- Hips: [narrow/average/wide relative to waist]
- Legs: [proportionally long/average, shape]
- Feet: [if relevant/visible]

GENERAL BUILD:
- Overall build: [description, not just a label]
- Height impression: [tall/average/petite]
- Muscle tone: [toned/soft/athletic]

Write every section in plain, concrete, physically descriptive language — avoid subjective terms like "beautiful," "stunning," or "perfect." Output ONLY the structured anchor, no preamble or explanation. Keep each section's bullets under its own header even if a photo doesn't show that area well — just note "not clearly visible in source photos" for that bullet rather than guessing."""

SCENE_ANALYSIS_PROMPT = """Analyze this photo and produce a detailed scene description for use in an AI image generation prompt. The goal is to describe everything EXCEPT the person's identity — do not describe face, body proportions, skin tone, or any physical identity trait. Assume the person will be replaced with someone else; you are only capturing the scene, pose, and technical photography details.

Output in this exact structure:

ENVIRONMENT:
- Location/setting: [description]
- Background elements: [description]
- Time of day / atmosphere: [if inferable]

CAMERA:
- Shot type: [close-up / medium / full body / etc.]
- Camera angle: [eye-level / low / high / from above / etc.]
- Camera distance and implied lens: [description]
- Framing: [what's included/cropped]

CROP:
- Head and face crop: [whole head in frame / top of head cut off / forehead cut off / eyes cut off — only nose, mouth and chin in frame / only chin and lips in frame / head fully out of frame]
- Top edge cuts: [what the upper frame edge cuts through]
- Bottom edge cuts: [what the lower frame edge cuts through, e.g. mid-thigh, knees, calves, feet included]
- Left/right edge cuts: [what the side edges cut through, e.g. raised arm cut at elbow]
- Body parts entirely outside the frame: [list them, or "none"]

POSE:
- Overall body position: [description]
- Torso and shoulders: [orientation]
- Head position: [tilt, gaze direction]
- Arms and hands: [exact position and action]
- Legs and feet (if visible): [stance]
- Overall energy: [relaxed/dynamic/candid/posed]

EXPRESSION:
- Mouth: [closed / open, smile type — subtle closed-lip smile / full toothy smile / smirk / neutral / laughing]
- Eyes: [both open naturally / one eye winking / squinting / wide / soft gaze]
- Eyebrows: [relaxed / raised / one raised]
- Overall expression descriptor: [playful, laughing, serious, coy, teasing, etc.]

LIGHTING:
- Primary light source: [type and position]
- Light quality: [soft/hard/mixed]
- Color temperature: [warm/neutral/cool]
- Shadow behavior: [description]
- Secondary/fill light or reflections: [if visible]

OUTFIT (garment description only, not fit on a specific body):
- Each visible garment: type, color, pattern, material impression, silhouette

MOOD/STYLE:
- Overall photographic style: [description]
- Grain, sharpness, color grading impression: [if notable]

VISIBILITY:
- Face: [fully visible / partially visible — state exactly which facial parts are inside the frame and which are cut off / not visible — state why: turned away, cropped out of frame, obscured by hair/object/angle]
- Hair: [visible / not visible]
- Upper body (torso, chest, arms): [visible / not visible]
- Lower body (hips, legs, feet): [visible / not visible]

INTIMATE VIEW (viewing geometry only — no identity, no anatomy detail):
- Crotch area: [not in frame / covered by clothing / bare — front view / bare — rear view from behind / bare — view from below / bare — other angle]
- Chest area: [not in frame / covered by clothing / partially bare / fully bare]

Do not include: face shape, facial features, eye color, hair color/style, skin tone, body build, bust/waist/hip proportions, height, or any other identity-related detail.

OVERLAYS (ignore completely — do NOT describe or transcribe):
- Watermarks, captions, subtitles, logos, stickers, social handles, @usernames, URLs, platform branding (OnlyFans, Fansly, Instagram, etc.), timecode, channel bugs, UI overlays, or any on-image text/graphics.
- Describe the underlying scene as if those overlays did not exist.

Output ONLY the structured description, no preamble or explanation."""

# Wardrobe prep is not in the HTML file itself — Image 2 is assumed already dressed.
# This prompt produces that Image 2 from model body + scene/outfit donor.
DRESS_BODY_PROMPT = """Image 1 = body proportions reference of the target person (identity body only).
Image 2 = outfit / wardrobe donor (garments only — ignore the person wearing them).

Dress the person from Image 1 in the exact clothing from Image 2.
Keep Image 1 body shape, proportions, skin tone, and pose framing as close as practical.
Transfer from Image 2 only: garment types, colors, patterns, materials, silhouette and fit adapted to Image 1's body.
Do not copy the face or identity of the person in Image 2.
Do not copy skin marks, tattoos, scars, or body hair from Image 2 — those belong to the model identity only.
Neutral clean background preferred. Photorealistic result."""

# Face swap mannequin prep — тексты в data/prompts (и _bundled_prompts в образе).
_FACE_SWAP_PROMPT_FILES = {
    "mannequin_sfw": "face_swap_mannequin_sfw.txt",
    "mannequin_nsfw": "face_swap_mannequin_nsfw.txt",
    "dressed_headless": "face_swap_dressed_body_headless.txt",
}


def _face_swap_prompt_candidates(filename: str) -> list[Path]:
    ordered = [
        (BACKEND_DIR / "data" / "prompts" / filename).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / filename).resolve(),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for path in ordered:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _read_first_nonempty_face_swap_prompt(filename: str) -> str | None:
    for path in _face_swap_prompt_candidates(filename):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return None


def face_swap_uses_seedream_prep_prompts(wave_model_id: str) -> bool:
    """Seedream агрессивно «упрощает» тело — отдельные промпты с geometry lock."""
    model = (wave_model_id or "").strip().lower()
    return model.startswith("seedream")


def mannequin_final_dressed_first(wave_model_id: str) -> bool:
    """Финал face swap: dressed body = Image 1 (edit canvas), манекен последним — только pose."""
    return face_swap_uses_seedream_prep_prompts(wave_model_id)


def _face_swap_mannequin_filename(*, wave_profile: str, wave_model_id: str) -> str:
    wp = (wave_profile or "nsfw").strip().lower()
    base = "face_swap_mannequin_sfw" if wp == "regular" else "face_swap_mannequin_nsfw"
    if face_swap_uses_seedream_prep_prompts(wave_model_id):
        return f"{base}_seedream.txt"
    return f"{base}.txt"


def _face_swap_dressed_headless_filename(*, wave_model_id: str) -> str:
    if face_swap_uses_seedream_prep_prompts(wave_model_id):
        return "face_swap_dressed_body_headless_seedream.txt"
    return "face_swap_dressed_body_headless.txt"


def load_face_swap_mannequin_prompt(*, wave_profile: str, wave_model_id: str = "") -> str:
    """Pass 1 clay prep (SFW / NSFW templates)."""
    from app.services.studio_face_swap_clay import load_clay_prep_template

    _ = wave_model_id
    return load_clay_prep_template(wave_profile=wave_profile)


def load_face_swap_dressed_body_headless_prompt(*, wave_model_id: str = "") -> str:
    fname = _face_swap_dressed_headless_filename(wave_model_id=wave_model_id)
    text = _read_first_nonempty_face_swap_prompt(fname)
    if text:
        return text
    text = _read_first_nonempty_face_swap_prompt("face_swap_dressed_body_headless.txt")
    if text:
        return text
    tried = ", ".join(str(p) for p in _face_swap_prompt_candidates(fname))
    raise RuntimeError(f"Face swap headless dress prompt not found (tried: {tried})")


def face_swap_mannequin_prep_enabled() -> bool:
    from app.config import settings

    return bool(getattr(settings, "studio_face_swap_mannequin_prep", True))


def face_swap_mannequin_prep_enabled_for_model(wave_model_id: str) -> bool:
    """Манекен выключен при classic face swap (Grok master, без prep)."""
    from app.services.studio_face_swap_seedream_v5 import face_swap_classic_enabled

    if face_swap_classic_enabled(wave_model_id):
        return False
    return face_swap_mannequin_prep_enabled()

# Родинки/тату/шрамы/пирсинг — только с модели, никогда с рефа или глины.
IDENTITY_MARKS_BLOCK = (
    "SKIN MARKS AND BODY MODS (mandatory): Freckles, moles, birthmarks, scars, tattoos, piercings, "
    "and body jewelry come ONLY from the model identity (model profile text + model reference photos). "
    "NEVER copy tattoos, piercings, scars, moles, or jewelry from Image 1 (clay/scene donor) — even if "
    "they are large or central in the frame. If the model profile and model refs show no tattoos and "
    "no piercings, the output must have none — remove every tattoo and piercing visible on the clay donor."
)

UPPER_BODY_MARKS_BLOCK = (
    "Visible chest, décolletage, neck, shoulders, arms, hands, stomach, and any other exposed skin "
    "must NOT keep the sitter's tattoos, piercings, moles, scars, or birthmarks from Image 1. "
    "Apply only what the model identity defines; otherwise clean bare skin with no ink and no metal jewelry "
    "unless the model wears the same item in her reference photos."
)


def identity_marks_block(vis: AnchorVisibility) -> str:
    """Блок про родинки/тату: усиление когда в кадре торс (бюст, до груди)."""
    if vis.upper or vis.lower:
        return f"{IDENTITY_MARKS_BLOCK}\n{UPPER_BODY_MARKS_BLOCK}"
    return IDENTITY_MARKS_BLOCK


# Two-pass face swap pass 1: Image1=body, Image2=face, Image3=reference (одежда/поза).
TWO_PASS_PASS1_IDENTITY_MARKS = (
    "SKIN MARKS AND BODY MODS (mandatory): Tattoos, piercings, scars, moles, birthmarks, freckles, "
    "and body jewelry come ONLY from the model — image 1 (body), image 2 (face), and MODEL MARKS below. "
    "NEVER copy any tattoo, piercing, scar, mole, or jewelry from image 3 (reference person), even if "
    "large or central on the reference. If the model has no tattoos or piercings in her photos and profile, "
    "the output must have none — strip every tattoo and piercing visible on the reference while keeping "
    "only clothing and pose from image 3."
)

TWO_PASS_PASS1_UPPER_MARKS = (
    "Exposed skin in the output (neck, chest, arms, stomach, legs if visible) must show only the model's "
    "documented marks — not the reference sitter's ink or metal from image 3."
)

# Two-pass pass 2: Image1=scene ref, Image2=pass1 model, Image3=face.
TWO_PASS_PASS2_IDENTITY_MARKS = (
    "SKIN MARKS AND BODY MODS (mandatory): Tattoos, piercings, scars, moles, and jewelry come ONLY from "
    "the model in image 2 and image 3 — NEVER from the original sitter in image 1 (scene reference). "
    "If the model has no tattoos or piercings, remove all ink and piercings copied from the reference scene."
)

TWO_PASS_PASS2_UPPER_MARKS = (
    "Do not preserve the original person's tattoos, piercings, or skin marks from image 1 on the final photo — "
    "only what the model identity defines in image 2 and image 3."
)


def two_pass_pass1_identity_marks_block(vis: AnchorVisibility) -> str:
    if vis.upper or vis.lower:
        return f"{TWO_PASS_PASS1_IDENTITY_MARKS}\n{TWO_PASS_PASS1_UPPER_MARKS}"
    return TWO_PASS_PASS1_IDENTITY_MARKS


def two_pass_pass2_identity_marks_block(vis: AnchorVisibility) -> str:
    if vis.upper or vis.lower:
        return f"{TWO_PASS_PASS2_IDENTITY_MARKS}\n{TWO_PASS_PASS2_UPPER_MARKS}"
    return TWO_PASS_PASS2_IDENTITY_MARKS

# Жёсткий лок лица — модели часто «держат» лицо со scene ref без явного запрета.
FACE_IDENTITY_LOCK_BLOCK = (
    "CRITICAL FACE REPLACEMENT: The output face must be unmistakably the person from the "
    "facial identity reference image — never the original sitter from the scene reference. "
    "Do not blend, average, or softly merge faces. Structural features (eye shape, nose, lips, "
    "jawline, cheek structure, face oval) come only from the facial identity reference. "
    "If the body/outfit reference shows any face, ignore it completely for facial identity."
)


def anchor_mode_a_scene_first(
    *,
    wave_profile: str,
    wave_model_id: str = "",
    mannequin_scene: bool = False,
) -> bool:
    """Seedream edit: сцена первой (edit canvas). WAN/Nano — identity-first.

    Манекен нельзя ставить первым: Seedream клеится к силуэту Image 1, серое тело «замораживает» пропорции.
    """
    _ = wave_profile
    if mannequin_scene:
        return False
    model = (wave_model_id or "").strip().lower()
    return model.startswith("seedream")


def order_mode_a_image_urls(
    *,
    face_url: str,
    dressed_url: str,
    scene_url: str,
    scene_first: bool = False,
    extra_face_copies: int = 0,
    mannequin_dressed_first: bool = False,
) -> list[str]:
    """Identity-first: face→body→scene. Mannequin+Seedream final: dressed→face→mannequin."""
    copies = max(0, min(int(extra_face_copies), 3))
    if mannequin_dressed_first:
        urls = [dressed_url, face_url]
        urls.extend([face_url] * copies)
        urls.append(scene_url)
        return urls
    if scene_first:
        urls = [scene_url, face_url]
        urls.extend([face_url] * copies)
        urls.append(dressed_url)
        return urls
    urls = [face_url]
    urls.extend([face_url] * copies)
    urls.extend([dressed_url, scene_url])
    return urls


def order_mode_a_face_closeup_urls(
    *,
    face_url: str,
    scene_url: str,
    scene_first: bool = False,
    duplicate_face: bool = False,
) -> list[str]:
    """Close-up: identity-first face→scene; Seedream scene-first scene→face."""
    if scene_first:
        urls = [scene_url, face_url]
        if duplicate_face:
            urls.append(face_url)
        return urls
    urls = [face_url, scene_url]
    if duplicate_face:
        urls.insert(1, face_url)
    return urls


def detect_face_closeup_scene(
    vis: AnchorVisibility,
    scene_description: str = "",
) -> bool:
    """Только чистый headshot: лицо в кадре, торс/ноги вне кропа. Бюст/до груди — полный Mode A."""
    if not vis.face:
        return False
    if vis.upper or vis.lower:
        return False
    t = (scene_description or "").lower()
    # Явный face-only framing из анализа сцены.
    if re.search(r"face only|head only|forehead to chin|no (visible )?(torso|chest|shoulders)", t, re.I):
        return True
    return True  # face visible, upper/lower not visible


def detect_bust_portrait_scene(
    vis: AnchorVisibility,
    scene_description: str = "",
) -> bool:
    """Только tight chest-up / крупное лицо в кадре — не любой кадр с видимым торсом."""
    if not (vis.face and vis.upper):
        return False
    # Полный рост / по колено — обычный Mode A, не bust.
    if vis.lower:
        return False
    t = (scene_description or "").lower()
    bust_framing = re.search(
        r"chest[- ]?up|bust(?:\s|/|-)|head and shoulders|shoulders up|"
        r"tight crop|close[- ]?up|portrait crop|face (?:fills|dominates|large)|"
        r"forehead to (?:chest|breast|upper chest)|shot type:\s*close",
        t,
        re.I,
    )
    hand_on_face = re.search(
        r"(hand|finger|knuckle).{0,40}(lip|mouth|chin|cheek)|"
        r"(lip|mouth|chin|cheek).{0,40}(hand|finger)",
        t,
        re.I,
    )
    return bool(bust_framing or hand_on_face)


BUST_PORTRAIT_FACE_BLOCK = (
    "BUST PORTRAIT FACE SWAP: Tight chest-up framing — the scene sitter's face is large in the crop. "
    "The output MUST show the model identity face, not the scene sitter. "
    "If a hand, finger, hair, or object touches the lips, chin, or cheek, keep that contact pose exactly "
    "but replace all visible facial skin and underlying bone structure with the model identity — "
    "including skin around and behind the hand. "
    "When several face reference images are provided, they depict the SAME model and must fully override the scene face."
)


def hairstyle_style_block(
    *,
    lock_hairstyle_style: bool,
    identity_face_image_label: str = "Image 1",
) -> str:
    """Укладка/часть/длина — с модели или с рефа; цвет волос всегда с модели."""
    face_ref = (identity_face_image_label or "Image 1").strip()
    color_rule = (
        f"Hair color always comes from the model identity ({face_ref} + profile anchor) — "
        "never from the scene donor."
    )
    if lock_hairstyle_style:
        return (
            f"{color_rule} "
            "Hairstyle style, part, texture, and length also come from the model identity — "
            "do not copy the scene person's haircut, bun, ponytail, or styling from the scene donor."
        )
    return (
        f"{color_rule} "
        "Hairstyle style, part, texture, and length may follow the scene donor — "
        "copy the visible haircut/styling from the scene while keeping model hair color."
    )

ANCHOR_HEADERS = ["FACE", "HAIR", "UPPER BODY", "LOWER BODY", "GENERAL BUILD"]

_CACHE_ROOT = BACKEND_DIR / "data" / "studio_anchor_cache"


@dataclass(frozen=True)
class AnchorVisibility:
    face: bool = True
    hair: bool = True
    upper: bool = True
    lower: bool = True

    def cache_key_part(self) -> str:
        return f"f{int(self.face)}h{int(self.hair)}u{int(self.upper)}l{int(self.lower)}"


def parse_anchor_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {h: [] for h in ANCHOR_HEADERS}
    current: str | None = None
    header_re = re.compile(r"^(FACE|HAIR|UPPER BODY|LOWER BODY|GENERAL BUILD):\s*$", re.I)
    for line in (text or "").split("\n"):
        m = header_re.match(line.strip())
        if m:
            current = next(
                (h for h in ANCHOR_HEADERS if h.lower() == m.group(1).lower()),
                None,
            )
            continue
        if current:
            sections[current].append(line)
    return sections


def filter_anchor_by_visibility(text: str, vis: AnchorVisibility) -> str:
    sections = parse_anchor_sections(text)
    matched = any(any(l.strip() for l in sections[h]) for h in ANCHOR_HEADERS)
    if not matched:
        return text

    parts: list[str] = []
    if vis.face and any(l.strip() for l in sections["FACE"]):
        parts.append("FACE:\n" + "\n".join(sections["FACE"]).strip())
    if vis.hair and any(l.strip() for l in sections["HAIR"]):
        parts.append("HAIR:\n" + "\n".join(sections["HAIR"]).strip())
    if vis.upper and any(l.strip() for l in sections["UPPER BODY"]):
        parts.append("UPPER BODY:\n" + "\n".join(sections["UPPER BODY"]).strip())
    if vis.lower and any(l.strip() for l in sections["LOWER BODY"]):
        parts.append("LOWER BODY:\n" + "\n".join(sections["LOWER BODY"]).strip())
    if (vis.upper or vis.lower) and any(l.strip() for l in sections["GENERAL BUILD"]):
        parts.append("GENERAL BUILD:\n" + "\n".join(sections["GENERAL BUILD"]).strip())
    return "\n\n".join(parts)


def clay_visibility_prompt_block(vis: AnchorVisibility) -> str:
    """Инструкции Grok clay prep/final: не описывать то, чего нет в кадре рефа."""
    def yn(v: bool) -> str:
        return "yes" if v else "no"

    lines = [
        "FRAME VISIBILITY (mandatory — match the reference crop exactly):",
        f"- Face visible in frame: {yn(vis.face)}",
        f"- Hair visible in frame: {yn(vis.hair)}",
        f"- Upper body (torso, chest, arms) visible: {yn(vis.upper)}",
        f"- Lower body (hips, legs, feet) visible: {yn(vis.lower)}",
        "",
        "PROMPT RULES FROM VISIBILITY:",
    ]
    if not vis.face:
        lines.append(
            "- Do NOT fill [FACE] or describe facial features, eyes, lips, or expression. "
            "Do not turn the head or widen framing to reveal a face."
        )
    if not vis.hair:
        lines.append(
            "- Do NOT fill [HAIR] with color/style detail beyond what is already implied by the clay/scene mass."
        )
    if not vis.upper:
        lines.append(
            "- Do NOT describe bust, chest, waist, or arms in [BODY]/identity — upper body is out of frame."
        )
    if not vis.lower:
        lines.append(
            "- Do NOT describe hips, legs, feet, or crotch in [BODY]/[INTIMATE] — lower body is out of frame. "
            "[INTIMATE] must be: not applicable — lower body not in frame."
        )
    ex = exclusion_notes(vis)
    if ex:
        lines.append("")
        lines.append(ex)
    return "\n".join(lines)


def exclusion_notes(vis: AnchorVisibility) -> str:
    notes: list[str] = []
    if not vis.face:
        notes.append(
            "The face is not visible in this scene (turned away, cropped out of frame, or obscured) — "
            "do not turn the head or angle the camera to reveal it, do not invent facial features. "
            "Keep the framing exactly as implied by the scene."
        )
    if not vis.hair:
        notes.append(
            "Hair is not clearly visible in this scene — do not add or emphasize visible hair detail "
            "beyond what the composition already implies."
        )
    if not vis.upper:
        notes.append(
            "The upper body is not visible in this frame — do not reveal it or reframe the shot to show it."
        )
    if not vis.lower:
        notes.append(
            "The lower body/legs are not visible in this frame — do not reveal them or reframe the shot to show them."
        )
    return " ".join(notes)


_SCENE_SECTION_HEADERS = re.compile(
    r"^(ENVIRONMENT|CAMERA|CROP|POSE|EXPRESSION|LIGHTING|OUTFIT|MOOD|VISIBILITY|"
    r"INTIMATE VIEW|MOOD/STYLE|OVERLAYS):\s*$",
    re.I,
)


def extract_scene_section_from_scene_text(text: str, section: str) -> str:
    """Блок POSE / CAMERA / … из Grok scene analysis."""
    raw = (text or "").strip()
    name = (section or "").strip().upper()
    if not raw or not name:
        return ""
    header_re = re.compile(rf"^{re.escape(name)}:\s*$", re.I)
    lines = raw.split("\n")
    out: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if header_re.match(stripped):
            in_section = True
            out.append(f"{name}:")
            continue
        if in_section:
            if _SCENE_SECTION_HEADERS.match(stripped) and not stripped.upper().startswith(name):
                break
            out.append(line)
    block = "\n".join(out).strip()
    if not block:
        # Строка вида POSE: one line …
        m = re.search(rf"(?im)^{re.escape(name)}:\s*(.+)$", raw)
        if m:
            return f"{name}: {m.group(1).strip()}"
        return ""
    if name != "VISIBILITY" and not re.search(r"(?im)^\s*-\s+", block) and ":" in block:
        after = block.split(":", 1)[1].strip()
        if after:
            return block
    if name != "VISIBILITY" and not re.search(r"(?im)^\s*-\s+", block):
        return ""
    return block


def extract_expression_block_from_scene_text(text: str) -> str:
    """Блок EXPRESSION из Grok scene analysis (оригинальный реф до mannequin)."""
    return extract_scene_section_from_scene_text(text, "EXPRESSION")


def format_scene_expression_prompt_block(expression_block: str) -> str:
    """Вставка в финальный face swap — эмоция с исходного рефа (текст Grok), не с mannequin."""
    block = (expression_block or "").strip()
    if not block:
        return ""
    return (
        "SCENE_EXPRESSION (from original reference photo — NOT part of identity; "
        "apply on the MODEL face bone structure, do not default to neutral):\n"
        f"{block}\n"
    )


def parse_visibility_from_scene_text(text: str) -> AnchorVisibility:
    vis = AnchorVisibility()
    t = (text or "").lower()

    def check(label: str) -> bool | None:
        m = re.search(rf"{label}[^\n]*:\s*([^\n]*)", t, re.I)
        if not m:
            return None
        chunk = m.group(1)
        if re.search(r"not visible", chunk, re.I):
            return False
        if re.search(r"visible", chunk, re.I):
            return True
        return None

    face = check("face")
    hair = check("hair")
    upper = check("upper body")
    lower = check("lower body")
    return AnchorVisibility(
        face=vis.face if face is None else face,
        hair=vis.hair if hair is None else hair,
        upper=vis.upper if upper is None else upper,
        lower=vis.lower if lower is None else lower,
    )


def visibility_from_identity_visibility(vis: Any) -> AnchorVisibility:
    """Map studio IdentityVisibility → AnchorVisibility."""
    if vis is None:
        return AnchorVisibility()
    return AnchorVisibility(
        face=bool(getattr(vis, "include_face", True)),
        hair=bool(getattr(vis, "include_hair", True)),
        upper=bool(getattr(vis, "include_body_proportions", True)),
        lower=bool(getattr(vis, "include_body_proportions", True)),
    )


def build_mode_a_prompt(
    *,
    filtered_anchor: str,
    vis: AnchorVisibility,
    notes: str = "",
    lock_hairstyle_style: bool = True,
    scene_first: bool = False,
    bust_portrait: bool = False,
    extra_face_copies: int = 0,
    raw_body_ref: bool = True,
    mannequin_scene: bool = False,
    dressed_first: bool = False,
    scene_expression_block: str = "",
) -> str:
    """Face-swap WITH scene photo — Mode A: Image1=face/body/scene or scene/face/body (Seedream)."""
    exclusions = exclusion_notes(vis)
    face_count = 1 + max(0, min(int(extra_face_copies), 3))
    if scene_first:
        scene_i = 1
        face_i = 2
        body_i = 2 + face_count
    elif dressed_first and mannequin_scene:
        body_i = 1
        face_i = 2
        scene_i = 2 + face_count
    else:
        face_i = 1
        body_i = face_count + 1
        scene_i = face_count + 2

    face_ref_label = (
        f"Images {face_i}–{face_i + extra_face_copies} = the SAME facial identity reference (repeated for emphasis). "
        if bust_portrait and extra_face_copies > 0
        else f"Image {face_i} = facial identity reference only. "
    )

    if raw_body_ref:
        body_line = (
            f"Image {body_i} = body proportions reference only (build, silhouette, limb proportions, skin tone family). "
            f"Do NOT copy outfit from this image — dress the model in the clothing visible in Image {scene_i}."
        )
    else:
        if mannequin_scene:
            body_line = (
                f"Image {body_i} = authoritative MODEL body proportions AND outfit (headless dressed prep). "
                f"Transfer bust size, waist width, hip width, limb build, skin tone, and garments from Image {body_i} "
                f"onto the pose from Image {scene_i}. Image {body_i} fully overrides the simplified gray body on "
                f"Image {scene_i} — never copy the original sitter's figure from the mannequin canvas."
            )
        else:
            body_line = (
                f"Image {body_i} = body proportions and outfit reference. The person's body shape and the clothing "
                "shown here should be transferred exactly as-is."
            )

    if bust_portrait:
        expr_rule = (
            f"Copy expression MOOD from Image {scene_i} (smile intensity, lip parting, teeth visibility, "
            f"eye state, brow position, head tilt) but apply it ONLY on the MODEL bone structure from "
            "the face reference image(s) — never keep the scene sitter's face shape or likeness."
        )
    elif mannequin_scene:
        if (scene_expression_block or "").strip():
            expr_rule = (
                f"Structural facial features (eye shape, nose, lips, jaw, face oval) come only from Image {face_i}. "
                "Facial EXPRESSION is not identity — follow the SCENE_EXPRESSION block below exactly "
                "(mouth, tongue, teeth, eye state, brows, overall mood from the original reference photo). "
                f"Apply that performance on Image {face_i} bone structure. Match head tilt/gaze from Image {scene_i} pose. "
                "Do NOT use a neutral studio face when SCENE_EXPRESSION is provided."
            )
        else:
            expr_rule = (
                f"Structural facial features come only from Image {face_i}. Match head tilt, gaze direction, and "
                f"overall expression mood from the pose on Image {scene_i} (mannequin canvas has no face to copy — "
                "use head orientation and scene context only). Apply that mood on the MODEL bone structure from "
                f"Image {face_i}; do not invent the original sitter's face or micro-expression from memory."
            )
    else:
        expr_rule = (
            f"Do not blend structural facial features — eye shape, nose shape, lip shape, face shape, "
            f"jawline — between Image {face_i} and Image {scene_i}. However, facial expression must be copied exactly "
            f"from Image {scene_i}: smile type and intensity, whether teeth are showing, eye state "
            "(wide open / squinting / winking), eyebrow position, and head tilt. Facial expression is "
            f"not part of identity — it must follow Image {scene_i}, not default to neutral."
        )

    if mannequin_scene:
        scene_intro = (
            f"Image {scene_i} = gray mannequin pose canvas: matte gray featureless stand-in with the exact "
            "pose, camera angle, framing, lighting, background, and garment-coverage silhouette from the "
            "original photo. No human identity remains on this canvas — only geometry, light, and gray "
            "clothing shapes.\n"
        )
        replace_line = (
            f"Replace every visible gray mannequin surface in Image {scene_i} (skin and gray fabric) with "
            f"the photoreal model identity from Image {face_i} and body proportions/outfit from Image {body_i}.\n"
        )
        no_preserve_line = (
            f"Do not leave final matte gray mannequin visible on skin or clothes. "
            f"Use Image {body_i} for bust size, waist width, hip width, and outfit/nudity level — "
            f"not the simplified mannequin proportions on Image {scene_i}.\n"
        )
        if dressed_first:
            no_preserve_line += (
                f"Image {body_i} is the body/outfit canvas: do NOT rescale the figure to match gray body mass "
                f"on Image {scene_i}. Only re-articulate limbs and head to match Image {scene_i} pose.\n"
            )
    else:
        scene_intro = (
            f"Image {scene_i} = target scene: recreate this exact pose, camera angle, framing, and lighting. "
            f"The scene reference donates geometry, light, and wardrobe coverage only — never the sitter's "
            "tattoos, moles, scars, birthmarks, face, or body identity.\n"
        )
        replace_line = (
            f"Replace the person in Image {scene_i} entirely with the identity from Image {face_i} "
            f"and the body proportions from Image {body_i}.\n"
        )
        no_preserve_line = (
            f"Do not preserve the body silhouette, bust size, waist width, hip width, face, or outfit of "
            f"the person in Image {scene_i} — replace all of it with the model identity references.\n"
        )

    prompt = (
        scene_intro
        + f"{face_ref_label}Use this face, and only this face.\n"
        f"{body_line}\n"
        "\n"
        f"{replace_line}"
        "\n"
        f"{filtered_anchor}\n"
        "\n"
        f"{no_preserve_line}"
        "\n"
        f"Preserve exactly from Image {scene_i}: pose, camera distance and angle, framing, lighting direction "
        "and color temperature, shadows, background.\n"
        "\n"
        f"{expr_rule}"
    )
    if bust_portrait:
        prompt += f"\n\n{BUST_PORTRAIT_FACE_BLOCK}"
    prompt += f"\n\n{FACE_IDENTITY_LOCK_BLOCK}"
    prompt += f"\n\n{identity_marks_block(vis)}"
    prompt += f"\n\n{hairstyle_style_block(lock_hairstyle_style=lock_hairstyle_style, identity_face_image_label=f'Image {face_i}')}"
    expr_from_grok = format_scene_expression_prompt_block(scene_expression_block)
    if expr_from_grok:
        prompt += f"\n\n{expr_from_grok}"
    if exclusions:
        prompt += f"\n\n{exclusions}"
    prompt += f"\n\n{SCENE_OVERLAY_EXCLUSION_BLOCK}"
    prompt += f"\n\n{REALISM_BLOCK}"
    if (notes or "").strip():
        prompt += f"\n\n{notes.strip()}"
    return prompt


def build_mode_a_face_closeup_prompt(
    *,
    filtered_anchor: str,
    vis: AnchorVisibility,
    notes: str = "",
    lock_hairstyle_style: bool = True,
    scene_first: bool = False,
    duplicate_face: bool = False,
) -> str:
    """Close-up face swap: identity-first or Seedream scene-first."""
    exclusions = exclusion_notes(vis)
    if scene_first:
        scene_i = 1
        face_i = 2
        if duplicate_face:
            face_ref_extra = f" Images {face_i}–{face_i + 1} are the SAME identity."
        else:
            face_ref_extra = ""
    else:
        face_i = 1
        scene_i = 3 if duplicate_face else 2
        face_ref_extra = ""

    prompt = (
        f"Image {scene_i} = target close-up portrait scene: keep the exact crop, head scale in frame, "
        "camera distance, head angle, gaze, lighting, shadows, and background.\n"
        f"Image {face_i} = facial identity reference ONLY.{face_ref_extra} The output must show THIS person's face — "
        "not the original sitter from the scene reference.\n"
        "\n"
        f"Replace the entire face in Image {scene_i} with the identity from Image {face_i}. "
        f"Do not preserve the original sitter's bone structure, eye shape, nose, lips, jaw, or skin identity.\n"
        "\n"
        f"{filtered_anchor}\n"
        "\n"
        f"Preserve from Image {scene_i} ONLY: framing, crop edges, head pose, gaze vs lens, lighting on skin, "
        "background, and expression mood — but expression must be applied on top of Image {face_i} bone structure, "
        f"not by keeping the stranger's face.\n"
        f"Do not zoom out, widen the frame, or reveal body parts not present in Image {scene_i}."
    )
    prompt += (
        "\n\nCRITICAL CLOSE-UP FACE SWAP: This is a tight face/portrait frame. "
        "Identity likeness from the facial reference image is the top priority — "
        "never output the scene sitter's face even if expression/lighting match the scene."
    )
    prompt += f"\n\n{FACE_IDENTITY_LOCK_BLOCK}"
    prompt += f"\n\n{identity_marks_block(vis)}"
    prompt += f"\n\n{hairstyle_style_block(lock_hairstyle_style=lock_hairstyle_style)}"
    if exclusions:
        prompt += f"\n\n{exclusions}"
    prompt += f"\n\n{SCENE_OVERLAY_EXCLUSION_BLOCK}"
    prompt += f"\n\n{REALISM_BLOCK}"
    if (notes or "").strip():
        prompt += f"\n\n{notes.strip()}"
    return prompt


def build_mode_b_prompt(
    *,
    filtered_anchor: str,
    scene_description: str,
    vis: AnchorVisibility,
    notes: str = "",
    lock_hairstyle_style: bool = True,
) -> str:
    """Face-swap WITHOUT scene photo — exact Mode B from HTML."""
    exclusions = exclusion_notes(vis)
    prompt = (
        "Image 1 = facial identity reference.\n"
        "Image 2 = body and outfit reference.\n"
        "\n"
        "Scene, pose, and lighting to recreate (described, not shown as reference):\n"
        f"{scene_description}\n"
        "\n"
        "Place the identity from Image 1 and Image 2 into this exact scene, pose, camera angle, "
        "and lighting as described above.\n"
        "\n"
        "Facial expression must match the EXPRESSION described above exactly — smile type, eye state, "
        "eyebrow position — applied on top of the identity's facial structure from Image 1. Expression "
        "is not part of identity and must not default to neutral.\n"
        "\n"
        f"{filtered_anchor}"
    )
    prompt += f"\n\n{identity_marks_block(vis)}"
    prompt += f"\n\n{hairstyle_style_block(lock_hairstyle_style=lock_hairstyle_style)}"
    if exclusions:
        prompt += f"\n\n{exclusions}"
    prompt += f"\n\n{REALISM_BLOCK}"
    if (notes or "").strip():
        prompt += f"\n\n{notes.strip()}"
    return prompt


def profile_text_to_identity_anchor(model_profile_text: str | None) -> str:
    """
    Convert our stored profile (JSON v1 or free text) into FACE/HAIR/... anchor text.
    If already in anchor format, return as-is.
    """
    raw = (model_profile_text or "").strip()
    if not raw:
        return ""
    if parse_anchor_sections(raw) and any(
        any(l.strip() for l in parse_anchor_sections(raw)[h]) for h in ANCHOR_HEADERS
    ):
        return raw

    try:
        from app.services.studio_character_profile import (
            build_generation_packs,
            parse_profile_document,
        )
    except Exception:
        return raw

    doc = parse_profile_document(raw)
    if not doc:
        return raw

    packs = build_generation_packs(doc)
    face = str(packs.get("face_lock") or "").strip()
    hair = str(packs.get("hair_lock") or "").strip()
    figure = str(packs.get("figure_lock") or "").strip()
    summary = str(packs.get("short_prompt_summary") or "").strip()

    # Prefer nested v1 sections when present
    head = doc.get("head_and_face") if isinstance(doc.get("head_and_face"), dict) else {}
    hair_d = doc.get("hair") if isinstance(doc.get("hair"), dict) else {}
    body = doc.get("body") if isinstance(doc.get("body"), dict) else {}

    def _line(label: str, value: Any) -> str:
        t = str(value or "").strip()
        return f"- {label}: {t}" if t else ""

    face_lines = [
        _line("Face shape", head.get("face_shape") or face or "not clearly visible in source photos"),
        _line("Cheekbones", head.get("cheekbones") or "not clearly visible in source photos"),
        _line("Jawline", head.get("jawline") or "not clearly visible in source photos"),
        _line("Chin", head.get("chin") or "not clearly visible in source photos"),
        _line("Nose", head.get("nose") or "not clearly visible in source photos"),
        _line("Lips", head.get("lips") or "not clearly visible in source photos"),
        _line("Eyes", head.get("eyes") or "not clearly visible in source photos"),
        _line("Distinguishing marks", head.get("marks") or head.get("distinguishing_marks") or "not clearly visible in source photos"),
        _line("Skin tone and undertone", head.get("skin") or head.get("skin_tone") or "not clearly visible in source photos"),
    ]
    hair_lines = [
        _line("Color", hair_d.get("color") or hair or "not clearly visible in source photos"),
        _line("Texture", hair_d.get("texture") or "not clearly visible in source photos"),
        _line("Length", hair_d.get("length") or "not clearly visible in source photos"),
        _line("Typical part/style", hair_d.get("style") or hair_d.get("part") or "not clearly visible in source photos"),
    ]
    upper_lines = [
        _line("Bust", body.get("bust") or "not clearly visible in source photos"),
        _line("Shoulders and arms", body.get("shoulders") or body.get("arms") or "not clearly visible in source photos"),
        _line("Waist", body.get("waist") or "not clearly visible in source photos"),
    ]
    lower_lines = [
        _line("Hips", body.get("hips") or "not clearly visible in source photos"),
        _line("Legs", body.get("legs") or "not clearly visible in source photos"),
        _line("Feet", body.get("feet") or "not clearly visible in source photos"),
    ]
    build_lines = [
        _line("Overall build", body.get("build") or figure or summary or "not clearly visible in source photos"),
        _line("Height impression", body.get("height") or "not clearly visible in source photos"),
        _line("Muscle tone", body.get("muscle_tone") or "not clearly visible in source photos"),
    ]

    def _block(title: str, lines: list[str]) -> str:
        clean = [x for x in lines if x]
        return f"{title}:\n" + ("\n".join(clean) if clean else "- not clearly visible in source photos")

    return "\n\n".join(
        [
            _block("FACE", face_lines),
            _block("HAIR", hair_lines),
            _block("UPPER BODY", upper_lines),
            _block("LOWER BODY", lower_lines),
            _block("GENERAL BUILD", build_lines),
        ]
    )


def pick_genitals_image(imgs: list[Any]) -> Any | None:
    """Снимок модели с kind=genitals (интимная анатомия) для NSFW финала."""
    for im in imgs or []:
        if (getattr(im, "image_kind", None) or "other").lower() == "genitals":
            return im
    return None


def pick_face_and_body_images(imgs: list[Any]) -> tuple[Any | None, Any | None]:
    """Pick one face + one body (or turnaround) from studio model images."""
    by_kind: dict[str, list[Any]] = {}
    for im in imgs or []:
        k = str(getattr(im, "image_kind", None) or "other").lower()
        by_kind.setdefault(k, []).append(im)
    face = (by_kind.get("face") or [None])[0]
    body = (by_kind.get("body") or by_kind.get("turnaround") or [None])[0]
    if face is None and imgs:
        face = imgs[0]
    if body is None and len(imgs) > 1:
        body = imgs[1]
    elif body is None:
        body = face
    return face, body


def dressed_body_cache_key(
    *,
    model_id: int,
    face_image_id: int | None,
    body_image_id: int | None,
    scene_bytes: bytes,
    vis: AnchorVisibility,
    headless: bool = False,
    wave_model_id: str = "",
) -> str:
    h = hashlib.sha256()
    # v2 + sd — headless dress; отдельный кэш для Seedream prep-промптов.
    if headless:
        tag = (
            "dress_headless_v2_sd"
            if face_swap_uses_seedream_prep_prompts(wave_model_id)
            else "dress_headless_v2"
        )
    else:
        tag = "dress"
    h.update(f"{tag}|m{model_id}|f{face_image_id}|b{body_image_id}|{vis.cache_key_part()}".encode())
    h.update(hashlib.sha256(scene_bytes).digest())
    return h.hexdigest()


def mannequin_scene_cache_key(
    *,
    scene_bytes: bytes,
    wave_profile: str,
    wave_model_id: str = "",
    body_image_id: int | None = None,
) -> str:
    """Кэш pass 1 clay: сцена + профиль + тело модели (NSFW [BODY])."""
    h = hashlib.sha256()
    wp = (wave_profile or "nsfw").strip().lower()
    h.update(f"clay_prep_v2|{wp}|b{body_image_id or 0}".encode())
    h.update(hashlib.sha256(scene_bytes).digest())
    _ = wave_model_id
    return h.hexdigest()


def cache_paths(key: str) -> tuple[Path, Path]:
    _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    return _CACHE_ROOT / f"{key}.jpg", _CACHE_ROOT / f"{key}.json"


def load_cached_dressed_body(key: str) -> bytes | None:
    img_path, meta_path = cache_paths(key)
    if not img_path.is_file():
        return None
    raw = img_path.read_bytes()
    if len(raw) < 64:
        return None
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not meta.get("ok"):
                return None
        except Exception:
            pass
    return raw


def save_cached_dressed_body(key: str, image_bytes: bytes, *, meta: dict[str, Any] | None = None) -> Path:
    img_path, meta_path = cache_paths(key)
    img_path.write_bytes(image_bytes)
    payload = {"ok": True, **(meta or {})}
    meta_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return img_path


def invalidate_dressed_body_cache(key: str) -> None:
    """Сброс pass1/pass-prep кэша после цензуры или битого результата — не тащим в pass 2."""
    img_path, meta_path = cache_paths(key)
    for path in (img_path, meta_path):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            log.warning("could not delete dressed-body cache %s", path)


def should_use_anchor_pipeline(*, studio_mode: str, has_scene_bytes: bool, has_model: bool) -> bool:
    mode = (studio_mode or "").strip().lower()
    if not has_model:
        return False
    if mode == "face_swap" and has_scene_bytes:
        return True
    if mode == "model_scene" and has_scene_bytes:
        return True
    return False
