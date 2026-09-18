"""Face swap: pass 1 dress+pose на сером фоне, pass 2 замена персонажа на реф-сцене."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, settings

log = logging.getLogger(__name__)

_PASS1 = "face_swap_dress_pose_pass1.txt"
_PASS2 = "face_swap_dress_pose_pass2.txt"


def _prompt_candidates(filename: str) -> list[Path]:
    return [
        (BACKEND_DIR / "data" / "prompts" / filename).resolve(),
        (BACKEND_DIR / "_bundled_prompts" / filename).resolve(),
    ]


def _read_prompt_file(filename: str) -> str:
    for path in _prompt_candidates(filename):
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
    tried = ", ".join(str(p) for p in _prompt_candidates(filename))
    raise RuntimeError(f"Two-pass face swap prompt missing (tried: {tried})")


def face_swap_two_pass_enabled() -> bool:
    """Dress+pose → swap; выключается classic single-pass."""
    if not getattr(settings, "studio_face_swap_two_pass", True):
        return False
    from app.services.studio_face_swap_seedream_v5 import face_swap_classic_enabled

    if face_swap_classic_enabled(""):
        return False
    from app.services.studio_anchor_pipeline import face_swap_mannequin_prep_enabled

    return face_swap_mannequin_prep_enabled()


def dress_pose_prep_cache_key(
    *,
    scene_bytes: bytes,
    wave_profile: str,
    body_image_id: int | None,
    face_image_id: int | None,
    detail_image_ids: list[int] | None = None,
) -> str:
    """Кэш pass 1: тело+лицо+реф(+детали) → модель в одежде и позе рефа на сером фоне."""
    h = hashlib.sha256()
    wp = (wave_profile or "nsfw").strip().lower()
    details = ",".join(str(i) for i in sorted(detail_image_ids or []))
    h.update(
        f"dress_pose_v6|{wp}|b{body_image_id or 0}|f{face_image_id or 0}|d{details}".encode()
    )
    h.update(hashlib.sha256(scene_bytes).digest())
    return h.hexdigest()


def extract_scene_section_block(
    scene_text: str,
    section: str,
    *,
    strip_header: bool = False,
) -> str:
    """Текст секции POSE / CAMERA / CROP / OUTFIT из Grok SCENE_ANALYSIS."""
    from app.services.studio_anchor_pipeline import extract_scene_section_from_scene_text

    block = extract_scene_section_from_scene_text(scene_text, section)
    if not strip_header or not block:
        return block
    head, _, rest = block.partition("\n")
    if head.strip().rstrip(":").upper() == section.strip().upper():
        return rest.strip()
    return block


def _visibility_face_line(scene_text: str) -> str:
    """Строка `- Face: …` из VISIBILITY — там же отметка partially visible."""
    m = re.search(r"(?im)^\s*[-*]?\s*face\s*:\s*(.+)$", scene_text or "")
    return m.group(1).strip() if m else ""


def build_crop_lock_block(
    scene_description: str,
    *,
    image_label: str,
    neutral_background: bool = False,
) -> str:
    """Жёсткий лок кадра: не дорисовывать то, что обрезано рамкой рефа."""
    crop = extract_scene_section_block(scene_description, "CROP").strip()
    face_line = _visibility_face_line(scene_description)
    lines = [
        f"CROP LOCK (mandatory — match only the framing geometry of {image_label}):",
        f"- Any body part cut off by the frame edge in {image_label} must stay cut off in the output.",
        "- Do not zoom out, do not widen the crop, do not shift the camera to reveal more of the body.",
        "- Do not complete or reconstruct a head, face, limb, or any body part that the frame cuts off.",
        "- If only part of the face is inside the frame (for example only chin, lips and jaw), keep exactly "
        "that part visible and keep the rest outside the frame — never render the whole face.",
        "- Keep the same distance from the camera and the same subject scale within the frame.",
    ]
    if neutral_background:
        lines.append(
            f"- This is framing only: do NOT copy the background, room, furniture, bedding, or "
            f"scene lighting of {image_label}. The background stays a plain neutral gray studio backdrop."
        )
    if crop:
        lines.append("")
        lines.append(crop)
    if face_line:
        lines.append("")
        lines.append(f"Face in frame: {face_line}")
    return "\n".join(lines)


def _frame_parts_block(vis: Any) -> str:
    """Короткая сводка «что в кадре» для image-edit (без плейсхолдеров Grok)."""
    from app.services.studio_anchor_pipeline import AnchorVisibility

    v = vis if isinstance(vis, AnchorVisibility) else AnchorVisibility()

    def yn(flag: bool) -> str:
        return "in frame" if flag else "out of frame"

    return (
        "PARTS IN FRAME (keep exactly this — do not add what is out of frame):\n"
        f"- Face: {yn(v.face)}\n"
        f"- Hair: {yn(v.hair)}\n"
        f"- Upper body (torso, chest, arms): {yn(v.upper)}\n"
        f"- Lower body (hips, legs, feet): {yn(v.lower)}"
    )


def reference_aspect_key(scene_bytes: bytes, fallback: str) -> str:
    """Аспект pass 1 = аспект рефа, иначе рамка кадра и кроп не совпадут."""
    from app.services.studio_aspect import ASPECT_PRESETS, normalize_aspect_key

    try:
        fb = normalize_aspect_key(fallback)
    except Exception:
        fb = "9:16"
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(scene_bytes)) as im:
            w, h = im.size
    except Exception:
        return fb
    if not w or not h:
        return fb
    ratio = w / h
    best = min(
        ASPECT_PRESETS.items(),
        key=lambda kv: abs((kv[1][0] / kv[1][1]) - ratio),
    )
    return best[0]


def _images_by_kind(model_images: list[Any]) -> dict[str, list[Any]]:
    by_kind: dict[str, list[Any]] = {}
    for im in model_images or []:
        k = str(getattr(im, "image_kind", "") or "other").strip().lower()
        by_kind.setdefault(k, []).append(im)
    return by_kind


def pick_two_pass_body_image(
    model_images: list[Any],
    *,
    wave_profile: str,
    fallback: Any | None = None,
) -> Any | None:
    """NSFW: Image 1 = «Обнажённое тело целиком», иначе обычное фото тела."""
    by_kind = _images_by_kind(model_images)
    order = ["body", "turnaround"]
    if (wave_profile or "nsfw").strip().lower() != "regular":
        order = ["nude_full", "body", "turnaround"]
    for kind in order:
        rows = by_kind.get(kind) or []
        if rows:
            return rows[0]
    return fallback


def parse_intimate_view(scene_text: str) -> tuple[str | None, bool]:
    """Из блока INTIMATE VIEW: ракурс промежности (front/back/bottom) и обнажена ли грудь."""
    text = scene_text or ""
    crotch = ""
    m = re.search(r"(?im)^\s*[-*]?\s*crotch(?:\s+area)?\s*:\s*(.+)$", text)
    if m:
        crotch = m.group(1).strip().lower()
    view: str | None = None
    if crotch and "not in frame" not in crotch and "covered" not in crotch:
        if "below" in crotch or "underneath" in crotch or "from under" in crotch:
            view = "bottom"
        elif "rear" in crotch or "behind" in crotch or "back" in crotch:
            view = "back"
        elif "front" in crotch or "bare" in crotch:
            view = "front"

    chest = ""
    m2 = re.search(r"(?im)^\s*[-*]?\s*chest(?:\s+area)?\s*:\s*(.+)$", text)
    if m2:
        chest = m2.group(1).strip().lower()
    breasts_bare = bool(chest) and "bare" in chest and "not in frame" not in chest
    return view, breasts_bare


_GENITAL_KIND_BY_VIEW = {
    "front": "genitals_front",
    "back": "genitals_back",
    "bottom": "genitals_bottom",
}

_DETAIL_LABEL = {
    "genitals_front": "the genital area seen from the front",
    "genitals_back": "the genital area seen from behind",
    "genitals_bottom": "the genital area seen from below",
    "genitals": "the intimate anatomy",
    "breasts": "the breasts and nipples",
}


def pick_nsfw_detail_images(
    model_images: list[Any],
    *,
    wave_profile: str,
    scene_description: str,
    vis: Any | None = None,
) -> list[tuple[str, Any]]:
    """Доп. референсы детализации: гениталии нужного ракурса + грудь (только NSFW)."""
    if (wave_profile or "nsfw").strip().lower() == "regular":
        return []
    from app.services.studio_anchor_pipeline import AnchorVisibility

    v = vis if isinstance(vis, AnchorVisibility) else AnchorVisibility()
    by_kind = _images_by_kind(model_images)
    view, breasts_bare = parse_intimate_view(scene_description)
    picked: list[tuple[str, Any]] = []

    if v.lower and view:
        candidates = [_GENITAL_KIND_BY_VIEW[view], "genitals"]
        # Нет фото нужного ракурса — берём любой интимный референс.
        candidates += [k for k in _GENITAL_KIND_BY_VIEW.values() if k != candidates[0]]
        for kind in candidates:
            rows = by_kind.get(kind) or []
            if rows:
                picked.append((kind, rows[0]))
                break

    if v.upper and breasts_bare:
        rows = by_kind.get("breasts") or []
        if rows:
            picked.append(("breasts", rows[0]))
    return picked


def build_detail_reference_lines(details: list[tuple[str, Any]], *, first_index: int) -> str:
    """Строки «Image N …» для доп. NSFW-референсов в промпте pass 1."""
    if not details:
        return ""
    lines = [
        "ADDITIONAL MODEL ANATOMY REFERENCES "
        "(same woman — use ONLY for anatomical accuracy in that area):"
    ]
    for offset, (kind, _im) in enumerate(details):
        label = _DETAIL_LABEL.get(kind, "an intimate anatomy area")
        lines.append(
            f"- Image {first_index + offset}: close-up reference of {label}. "
            "Use it only for the shape, proportions and skin detail of that area. "
            "Never take pose, framing, background, clothing or lighting from it."
        )
    return "\n".join(lines)


def _model_marks_snippet(filtered_anchor: str, model_profile_text: str | None) -> str:
    """Краткий контекст тату/пирсингов модели для pass 1 (не с рефа)."""
    src = (filtered_anchor or model_profile_text or "").strip()
    if not src:
        return (
            "No tattoos or piercings documented for this model — output must have none; "
            "do not copy any from image 3."
        )
    picked: list[str] = []
    for line in src.splitlines():
        low = line.lower()
        if any(
            k in low
            for k in (
                "tattoo",
                "pierc",
                "freckle",
                "mole",
                "scar",
                "birthmark",
                "distinguishing",
                "jewelry",
                "body mod",
                "no tattoo",
                "no pierc",
            )
        ):
            s = line.strip()
            if s:
                picked.append(s)
    if picked:
        return "MODEL MARKS (keep only these on the model):\n" + "\n".join(picked[:24])
    if re.search(r"(?i)no\s+tattoo|without\s+tattoo|has_tattoos.?false", src):
        return "MODEL MARKS: Profile indicates no tattoos — output none; do not copy from image 3."
    return (
        "MODEL MARKS: Use only freckles, moles, tattoos, and piercings visible on model images 1–2; "
        "never from image 3."
    )


def _body_lock_snippet(filtered_anchor: str, model_profile_text: str | None) -> str:
    """Фигура модели для pass 1: edit Image 1, не копировать тело с рефа."""
    src = (filtered_anchor or model_profile_text or "").strip()
    if not src:
        return (
            "- Keep bust, waist, hips, abdomen, limb thickness and overall build exactly as in image 1. "
            "Do not interpolate toward the body of the woman in image 3."
        )
    from app.services.studio_anchor_pipeline import parse_anchor_sections

    sections = parse_anchor_sections(src)
    parts: list[str] = []
    for header in ("UPPER BODY", "LOWER BODY", "GENERAL BUILD"):
        lines = [ln.strip() for ln in sections.get(header, []) if ln.strip()]
        if lines:
            parts.append(f"{header}:")
            parts.extend(lines[:12])
    if parts:
        return "\n".join(parts)
    compact = re.sub(r"\s+", " ", src)
    if len(compact) > 700:
        compact = compact[:697].rstrip() + "…"
    return compact


def _body_difference_snippet(filtered_anchor: str, model_profile_text: str | None) -> str:
    """Кратко: фигура модели для pass 2 (не копировать реф-персонажа)."""
    src = (filtered_anchor or model_profile_text or "").strip()
    if not src:
        return (
            "Use the body shape, proportions and skin tone from image 2 only; "
            "do not match the reference person's physique from image 1."
        )
    compact = re.sub(r"\s+", " ", src)
    if len(compact) > 900:
        compact = compact[:897].rstrip() + "…"
    return compact


PASS1_FINAL_RULES = (
    "FINAL RULES (mandatory):\n"
    "- This is an edit of image 1. The output person is the woman from image 1 after a pose/wardrobe change.\n"
    "- From image 3 take ONLY: the outfit, the pose (joint angles), the camera angle and the crop.\n"
    "- Do NOT mix or average two bodies. If image 3 has a different bust, waist, hips, thighs or height — ignore that.\n"
    "- Take NOTHING else from image 3: not background, room, bed, furniture, props, lighting, face, body, skin or hair.\n"
    "- The output background is a plain neutral gray studio backdrop with soft even lighting.\n"
    "- The outfit must actually change: replace whatever image 1 is wearing with the garments from image 3, "
    "fitted onto image 1's unchanged body."
)


def build_dress_pose_pass1_prompt(
    *,
    scene_description: str,
    visibility_block: str = "",
    filtered_anchor: str = "",
    model_profile_text: str | None = None,
    vis: Any | None = None,
    detail_refs: list[tuple[str, Any]] | None = None,
) -> str:
    """Pass 1: WaveSpeed [body, face, reference]."""
    from app.services.studio_anchor_pipeline import (
        AnchorVisibility,
        two_pass_pass1_identity_marks_block,
    )

    v = vis if isinstance(vis, AnchorVisibility) else AnchorVisibility()
    template = _read_prompt_file(_PASS1)
    pose = extract_scene_section_block(scene_description, "POSE", strip_header=True) or (
        "Match the full body pose, limb placement and gaze from image 3 exactly."
    )
    camera = extract_scene_section_block(scene_description, "CAMERA", strip_header=True) or (
        "Match the camera angle, height, distance and crop from image 3 exactly."
    )
    outfit = extract_scene_section_block(scene_description, "OUTFIT", strip_header=True) or (
        "Every garment visible on the person in image 3, including underwear, stockings and accessories."
    )
    out = (
        template.replace("{{POSE_DESCRIPTION}}", pose.strip())
        .replace("{{CAMERA_DESCRIPTION}}", camera.strip())
        .replace("{{OUTFIT_DESCRIPTION}}", outfit.strip())
        .replace(
            "{{BODY_LOCK}}",
            _body_lock_snippet(filtered_anchor, model_profile_text).strip(),
        )
    )
    marks_ctx = _model_marks_snippet(filtered_anchor, model_profile_text)
    # Доп. референсы идут после ref: image 1 body, 2 face, 3 ref, далее детализация.
    detail_lines = build_detail_reference_lines(detail_refs or [], first_index=4)
    blocks = [
        out,
        detail_lines,
        marks_ctx,
        two_pass_pass1_identity_marks_block(v),
        _frame_parts_block(v),
        build_crop_lock_block(
            scene_description, image_label="image 3", neutral_background=True
        ),
        PASS1_FINAL_RULES,
    ]
    _ = visibility_block  # clay-блок с плейсхолдерами в image-edit промпт не идёт
    return "\n\n".join(b.strip() for b in blocks if b and b.strip())


def dress_pose_pass1_prep_error_fatal(message: str | None) -> bool:
    """Ошибки pass1, при которых нельзя идти в pass2 (цензура / policy)."""
    from app.services.wavespeed_client import wavespeed_is_sensitive_content_error

    if wavespeed_is_sensitive_content_error(message):
        return True
    low = (message or "").lower()
    return (
        "safety" in low
        or "guideline" in low
        or "policy" in low
        or "moderation" in low
        or "content filter" in low
        or ("nsfw" in low and "not allowed" in low)
    )


def dress_pose_pass1_echoes_reference(result_bytes: bytes, scene_bytes: bytes) -> bool:
    """
    WaveSpeed иногда «успешно» отдаёт почти тот же кадр, что реф (лицо не модели).
    Такой pass1 нельзя скармливать в pass2.
    """
    if len(result_bytes) < 64 or len(scene_bytes) < 64:
        return True
    if result_bytes == scene_bytes:
        return True
    if hashlib.sha256(result_bytes).digest() == hashlib.sha256(scene_bytes).digest():
        return True
    try:
        from io import BytesIO

        from PIL import Image

        def _thumb_rgb(raw: bytes) -> list[tuple[int, int, int]]:
            im = Image.open(BytesIO(raw)).convert("RGB")
            im = im.resize((48, 48))
            return list(im.getdata())

        a = _thumb_rgb(result_bytes)
        b = _thumb_rgb(scene_bytes)
        if len(a) != len(b):
            return False
        mean_abs = sum(
            abs(x[0] - y[0]) + abs(x[1] - y[1]) + abs(x[2] - y[2]) for x, y in zip(a, b)
        ) / (len(a) * 3)
        # Порог: pass1 с серым фоном и телом модели заметно отличается от цветного рефа.
        return mean_abs < 12.0
    except Exception as e:
        log.debug("dress_pose pass1 similarity check skipped: %s", e)
        return False


def assert_valid_dress_pose_pass1(*, result_bytes: bytes, scene_bytes: bytes) -> None:
    """Pass2 только после валидного pass1 (модель на сером), не echo референса."""
    if dress_pose_pass1_echoes_reference(result_bytes, scene_bytes):
        raise RuntimeError(
            "Face swap pass 1 не подменил персонажа (кадр совпадает с референсом). "
            "Pass 2 не запускаем — попробуйте другую модель, профиль SFW/NSFW или другой референс."
        )


def build_dress_pose_pass2_prompt(
    *,
    filtered_anchor: str,
    model_profile_text: str | None,
    visibility_block: str = "",
    vis: Any | None = None,
    scene_description: str = "",
) -> str:
    """Pass 2: WaveSpeed [reference, pass1 result, face]."""
    from app.services.studio_anchor_pipeline import (
        AnchorVisibility,
        SCENE_OVERLAY_EXCLUSION_BLOCK,
        two_pass_pass2_identity_marks_block,
    )

    v = vis if isinstance(vis, AnchorVisibility) else AnchorVisibility()
    template = _read_prompt_file(_PASS2)
    body_diff = _body_difference_snippet(filtered_anchor, model_profile_text)
    blocks = [
        template.replace("{{BODY_DIFFERENCE}}", body_diff),
        two_pass_pass2_identity_marks_block(v),
        SCENE_OVERLAY_EXCLUSION_BLOCK,
        _frame_parts_block(v),
        build_crop_lock_block(scene_description, image_label="image 1"),
    ]
    _ = visibility_block  # clay-блок с плейсхолдерами в image-edit промпт не идёт
    return "\n\n".join(b.strip() for b in blocks if b and b.strip())
