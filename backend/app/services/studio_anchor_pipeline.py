"""Anchor Studio prompts — exact copy from anchor-studio_3.html.

Used for Face Swap (Mode A: with scene photo) and From-reference (Mode B: scene as text).
Image contract:
  Mode A: Image1=face, Image2=body+outfit (dressed), Image3=scene photo
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
- Face: [visible / not visible — if not visible, state why: turned away, cropped out of frame, obscured by hair/object/angle]
- Hair: [visible / not visible]
- Upper body (torso, chest, arms): [visible / not visible]
- Lower body (hips, legs, feet): [visible / not visible]

Do not include: face shape, facial features, eye color, hair color/style, skin tone, body build, bust/waist/hip proportions, height, or any other identity-related detail. Output ONLY the structured description, no preamble or explanation."""

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

# Родинки/тату/шрамы — только с модели, никогда с scene donor (Image 3 / текст сцены).
IDENTITY_MARKS_BLOCK = (
    "Skin marks (freckles, moles, birthmarks, scars, tattoos): copy ONLY from the model identity "
    "(face reference image + model profile anchor text). NEVER copy marks, tattoos, or scars "
    "from the scene donor — even if they appear prominently on the scene person."
)

# Жёсткий лок лица — модели часто «держат» лицо со scene ref без явного запрета.
FACE_IDENTITY_LOCK_BLOCK = (
    "CRITICAL FACE REPLACEMENT: The output face must be unmistakably the person from the "
    "facial identity reference image — never the original sitter from the scene reference. "
    "Do not blend, average, or softly merge faces. Structural features (eye shape, nose, lips, "
    "jawline, cheek structure, face oval) come only from the facial identity reference. "
    "If the body/outfit reference shows any face, ignore it completely for facial identity."
)


def anchor_mode_a_scene_first(*, wave_profile: str) -> bool:
    """WAN/Seedream: scene первым (canvas). Nano regular: identity первым, scene последним."""
    return (wave_profile or "").strip().lower() != "regular"


def order_mode_a_image_urls(
    *,
    face_url: str,
    dressed_url: str,
    scene_url: str,
    scene_first: bool,
) -> list[str]:
    if scene_first:
        return [scene_url, face_url, dressed_url]
    return [face_url, dressed_url, scene_url]


def order_mode_a_face_closeup_urls(
    *,
    face_url: str,
    scene_url: str,
    scene_first: bool,
    duplicate_face: bool = False,
) -> list[str]:
    """Крупный план лица: только scene + face (без dressed body). WAN — дублируем face для веса."""
    if scene_first:
        urls = [scene_url, face_url]
        if duplicate_face:
            urls.append(face_url)
        return urls
    return [face_url, scene_url]


def detect_face_closeup_scene(
    vis: AnchorVisibility,
    scene_description: str = "",
) -> bool:
    """Кадр в основном лицо — dressed body только мешает финальному swap."""
    if not vis.face:
        return False
    t = (scene_description or "").lower()
    if re.search(r"shot type[^\n:]*:\s*[^\n]*close[- ]?up", t, re.I):
        return True
    if re.search(r"close[- ]?up", t, re.I) and not vis.upper:
        return True
    # Лицо в кадре, торс/ноги вне кропа — типичный headshot.
    if not vis.upper and not vis.lower:
        return True
    return False


def detect_face_closeup_from_bytes(scene_bytes: bytes) -> bool:
    """Fallback без Grok: квадратный/портретный tight crop часто = headshot."""
    if not scene_bytes or len(scene_bytes) < 64:
        return False
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(scene_bytes)) as im:
            w, h = im.size
        short = min(w, h)
        long = max(w, h)
        if short < 320:
            return True
        if long / max(short, 1) <= 1.4 and short >= 480:
            return True
    except Exception:
        return False
    return False


def hairstyle_style_block(*, lock_hairstyle_style: bool) -> str:
    """Укладка/часть/длина — с модели или с рефа; цвет волос всегда с модели."""
    color_rule = (
        "Hair color always comes from the model identity (Image 1 + profile anchor) — "
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
) -> str:
    """Face-swap WITH scene photo — Mode A (HTML), с порядком картинок под WaveSpeed."""
    exclusions = exclusion_notes(vis)
    if scene_first:
        # WAN / Seedream: Image 1 = scene canvas, Image 2 = face, Image 3 = dressed body.
        scene_i, face_i, body_i = 1, 2, 3
    else:
        # Nano regular: identity first, scene last (как _nano_banana_reorder).
        face_i, body_i, scene_i = 1, 2, 3

    prompt = (
        f"Image {scene_i} = target scene: recreate this exact pose, camera angle, framing, and lighting.\n"
        f"Image {face_i} = facial identity reference only. Use this face, and only this face.\n"
        f"Image {body_i} = body proportions and outfit reference. The person's body shape and the clothing "
        "shown here should be transferred exactly as-is.\n"
        "\n"
        f"Replace the person in Image {scene_i} entirely with the identity from Image {face_i} and Image {body_i}.\n"
        "\n"
        f"{filtered_anchor}\n"
        "\n"
        f"Do not preserve the body silhouette, bust size, waist width, hip width, face, or outfit of "
        f"the person in Image {scene_i} — replace all of it with Image {face_i} and Image {body_i}.\n"
        "\n"
        f"Preserve exactly from Image {scene_i}: pose, camera distance and angle, framing, lighting direction "
        "and color temperature, shadows, background.\n"
        "\n"
        f"Do not blend structural facial features — eye shape, nose shape, lip shape, face shape, "
        f"jawline — between Image {face_i} and Image {scene_i}. However, facial expression must be copied exactly "
        f"from Image {scene_i}: smile type and intensity, whether teeth are showing, eye state "
        "(wide open / squinting / winking), eyebrow position, and head tilt. Facial expression is "
        f"not part of identity — it must follow Image {scene_i}, not default to neutral."
    )
    prompt += f"\n\n{FACE_IDENTITY_LOCK_BLOCK}"
    prompt += f"\n\n{IDENTITY_MARKS_BLOCK}"
    prompt += f"\n\n{hairstyle_style_block(lock_hairstyle_style=lock_hairstyle_style)}"
    if exclusions:
        prompt += f"\n\n{exclusions}"
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
) -> str:
    """Face-swap close-up: только scene + face (2–3 URL), без body/outfit ref."""
    exclusions = exclusion_notes(vis)
    if scene_first:
        scene_i, face_i = 1, 2
    else:
        face_i, scene_i = 1, 2

    prompt = (
        f"Image {scene_i} = target close-up portrait scene: keep the exact crop, head scale in frame, "
        "camera distance, head angle, gaze, lighting, shadows, and background.\n"
        f"Image {face_i} = facial identity reference ONLY. The output must show THIS person's face — "
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
    prompt += f"\n\n{IDENTITY_MARKS_BLOCK}"
    prompt += f"\n\n{hairstyle_style_block(lock_hairstyle_style=lock_hairstyle_style)}"
    if exclusions:
        prompt += f"\n\n{exclusions}"
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
    prompt += f"\n\n{IDENTITY_MARKS_BLOCK}"
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
) -> str:
    h = hashlib.sha256()
    h.update(f"m{model_id}|f{face_image_id}|b{body_image_id}|{vis.cache_key_part()}".encode())
    h.update(hashlib.sha256(scene_bytes).digest())
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


def should_use_anchor_pipeline(*, studio_mode: str, has_scene_bytes: bool, has_model: bool) -> bool:
    mode = (studio_mode or "").strip().lower()
    if not has_model:
        return False
    if mode == "face_swap" and has_scene_bytes:
        return True
    if mode == "model_scene" and has_scene_bytes:
        return True
    return False
