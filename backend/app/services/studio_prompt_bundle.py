"""Сборка промпта для WaveSpeed: разделение identity/scene, neg отдельно, без дублей с суффиксами."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import settings
from app.services.studio_openai import (
    _strip_code_fences,
    format_realism_engine_for_prose_prompt,
    load_canonical_realism_engine,
)

log = logging.getLogger(__name__)

# Не включать plastic/smooth/porcelain skin: у edit-моделей (Nano Banana / GPT Image /
# Seedream) negative часто игнорируется или подмешивается в позитив и усиливает «глянец».
from app.services.content_safety import MINOR_CONTENT_NEGATIVE_SUPPLEMENT

_CANONICAL_STUDIO_NEGATIVE = (
    "deformed hands, extra fingers, fused fingers, missing fingers, bad anatomy, "
    "duplicate limbs, extra arms, malformed joints, watermark, text, logo, "
    "uncanny symmetry, Facetune, beauty-filter face, influencer glamour, "
    "dead eyes, glassy eyes, empty stare, CGI, 3d render, heavy fake bokeh, "
    "stock photo, catalog lighting, TikTok reshaped eyes or jaw, composite collage, "
    "face pasted on wrong body, mismatched skin tone face vs body, "
    + MINOR_CONTENT_NEGATIVE_SUPPLEMENT
)

# Слова про «запрет гладкой кожи» — выкидываем из любого negative (Grok / profile always_avoid).
_SKIN_TEXTURE_BAN_NEGATIVE_RE = re.compile(
    r"\b("
    r"plastic\s*skin|smooth\s*skin|porcelain\s*skin|waxy\s*skin|doll\s*skin|"
    r"airbrushed(?:\s*(?:skin|look|face))?|airbrush(?:ed)?|"
    r"beauty[- ]?blur|pore\s*eras(?:e|ure)|over[- ]?retouch(?:ed|ing)?"
    r")\b",
    re.I,
)

_SCENE_FROM_REF_LITERAL = "from_pose_reference_input_image_only"

# Одна фраза иерархии — не дублировать в must_keep / pose_lock / negative.
PRIORITY_IDENTITY_OVER_POSE = (
    "If pose-reference body shape conflicts with model identity, model identity always wins."
)

_COMPACT_MUST_KEEP = [
    "One real person; face, skin, hair, and body shape from identity images (2+)",
    "Pose, framing, background, light, and wardrobe/coverage from pose reference (image 1) only",
    "Natural phone snapshot; visible pores and uneven tone; deep focus, readable background",
]

    # Короткий хвост в КОНЕЦ prose-промпта — у edit-моделей конец весит больше,
    # чем длинный realism_engine в середине после FACE_SWAP-префикса.
EYE_LIVENESS_CODA = (
    "Eyes alive — asymmetric catchlights, subtle squint or soft mid-blink, "
    "moist natural sclera, candid micro-expression; not vacant stare, not glassy doll eyes."
)

_PHONE_CANDID_PHOTO_BASE = (
    "Photoreal phone look — deep focus with background details sharp; "
    "visible skin pores and uneven tone, natural oil sheen where light hits, "
    "fine vellus hair catching sidelight, loose flyaways; mixed white balance, "
    "clipped highlight where sun hits, luminance noise in shadows, "
    "clean natural edge rendering without chromatic fringing or color-split contours, "
    "minor handheld tilt, JPEG compression; "
    "candid unretouched amateur snapshot."
)

PHONE_CANDID_PHOTO_CODA = f"{_PHONE_CANDID_PHOTO_BASE} {EYE_LIVENESS_CODA}"

_SOFT_DOF_PHRASE_RE = re.compile(
    r"\b("
    r"softly\s+blurred|heavily\s+blurred|heavy\s+(?:fake\s+)?bokeh|"
    r"creamy\s+(?:bokeh|background|blur)|"
    r"shallow\s+depth\s+of\s+field|portrait[\s-]?mode\s+bokeh|"
    r"background\s+(?:softly\s+)?(?:blurred|out\s+of\s+focus)|"
    r"blurred\s+(?:indoor\s+)?background|out[- ]of[- ]focus\s+background|"
    r"soft\s+bokeh|dreamy\s+bokeh|"
    r"blurred\s+(?:white\s+)?(?:shelving(?:\s+unit)?|shelf|shelves|backdrop|wall|furniture)|"
    r"(?:shelving(?:\s+unit)?|shelf|shelves|backdrop|furniture)\s+(?:softly\s+)?(?:blurred|out\s+of\s+focus)"
    r")\b",
    re.I,
)

_WORKFLOW_META_BLOCK_RE = re.compile(
    r"(?:^|\n\n)(?:SCENE_DIRECTION|REFERENCE_CONTEXT)[^\n]*\n.*?(?=(?:\n\n(?:SCENE_DIRECTION|REFERENCE_CONTEXT|Photoreal phone look|Capture realism:|\[NEGATIVE_PROMPT\])|\Z))",
    re.I | re.S,
)

_PO_REFU_BOILERPLATE_RE = re.compile(
    r"PRIORITY:\s*match\s+USER_SCENE_REFERENCE[\s\S]*?"
    r"(?:reference wins for pose/camera/light/crop\.?|\Z)",
    re.I,
)

# Только композитные артефакты — не body-shape (конфликт решается в основном промпте).
_GROK_COMPOSE_COMPOSITE_NEGATIVE = (
    "face pasted on wrong body, disconnected neck, composite collage, face swap artifact, floating head"
)

_BODY_SHAPE_NEGATIVE_RE = re.compile(
    r"\b("
    r"reference sitter body|donor body|donor silhouette|wrong bust|wrong waist|wrong hips|"
    r"flat chest|oversized hips|mismatched breast|skinny model on curvy|"
    r"curvy model on flat|pose reference body|reference body volume|sitter body|"
    r"body proportion.*reference|reference.*body proportion"
    r")\b",
    re.I,
)

_NUDE_WARDROBE_NEGATIVE = (
    "clothing from model reference photos, dressed when pose reference is nude, "
    "sportswear, crop top, sports bra, leggings, bikini, lingerie, bodysuit, "
    "outfit copied from character sheet, covering bare skin from pose reference"
)

_NUDE_CLOTHING_RE = re.compile(
    r"\b(nude|naked|topless|bottomless|unclothed|no clothing|no garment|"
    r"no clothes|without clothes|not wearing|bare skin|no top visible|no bra|"
    r"no shirt|no pants|no underwear|fully nude)\b",
    re.I,
)

_COMPACT_IDENTITY_FIELD_MAX = 1200
_COMPACT_SCENE_NOTES_MAX = 8000
# Max chars for "Model identity: …" prepended to WaveSpeed prose (subject + Build + hair).
STUDIO_IDENTITY_LINE_MAX = 1200
# Body proportions clause inside identity line (before final join/truncate).
STUDIO_BODY_PROPORTIONS_MAX = 800

_SCENE_NOTE_KEYS = (
    "POSE:",
    "FRAMING:",
    "HEAD_GEOMETRY",
    "CAMERA_",
    "CLOTHING",
    "BACKGROUND",
    "LIGHT_ON",
    "CAPTURE_TYPE",
    "VIEW_DIRECTION",
    "SHOT_TYPE",
    "BODY_ORIENTATION",
)

# Слова сцены в always_avoid профиля — не тащим в negative (конфликт с балконом, закатом и т.д.)
_SCENE_AVOID_RE = re.compile(
    r"\b("
    r"selfie|bedroom|blanket|morning\s+light|boudoir|kitchen|bathroom|"
    r"gym\s+mirror|hotel\s+room|living\s+room|indoor\s+studio|outdoor\s+villa|"
    r"balcony|rice\s+field|swimming\s+pool|sunset\s+sky|glass\s+railing|"
    r"halter|skirt|crochet|professional\s+studio|catalog\s+lighting"
    r")\b",
    re.I,
)

_QUALITY_AVOID_HINTS = (
    "plastic",
    "anatomy",
    "deform",
    "finger",
    "airbrush",
    "cgi",
    "render",
    "watermark",
    "logo",
    "blur",
    "bokeh",
    "symmetry",
    "facetune",
    "beauty",
    "glamour",
    "stock",
    "makeup",
    "quality",
    "composite",
    "pasted",
    "mismatched",
    "generic",
    "reshaped",
    "jaw",
    "eyes",
    "nudity",
    "over-smil",
)

_IDENTITY_AVOID_HINTS = (
    "ghost skin",
    "pale white",
    "very dark skin",
    "wrong hair",
    "black hair",
    "blonde",
    "red hair",
    "ginger",
    "braid",
    "short hair",
    "straight hair",
    "front-facing camera",
)

_DESC_SCENE_SPLIT_RE = re.compile(
    r"\s*,\s*(?=standing|seated|sitting|laying|lying|leaning|posing|on\s+an?\s+|"
    r"with\s+her\s+|with\s+his\s+|body\s+angled|back\s+facing|facing\s+the\s+camera)",
    re.I,
)


def _strip_body_shape_from_negative(raw: str) -> str:
    """Убрать body-shape формулировки из negative — они не работают как neg и дублируют основной промпт."""
    if not raw or not str(raw).strip():
        return ""
    kept: list[str] = []
    for piece in re.split(r"[,;\n]+", str(raw)):
        t = piece.strip()
        if not t or _BODY_SHAPE_NEGATIVE_RE.search(t):
            continue
        kept.append(t)
    return ", ".join(kept)


def _strip_skin_texture_bans_from_negative(raw: str) -> str:
    """Убрать anti-plastic / smooth-skin термины — edit-модели часто читают их как позитив."""
    if not raw or not str(raw).strip():
        return ""
    kept: list[str] = []
    for piece in re.split(r"[,;\n]+", str(raw)):
        t = piece.strip()
        if not t or _SKIN_TEXTURE_BAN_NEGATIVE_RE.search(t):
            continue
        kept.append(t)
    return ", ".join(kept)


def _prepend_priority_rule(prose: str) -> str:
    body = (prose or "").strip()
    if not body:
        return PRIORITY_IDENTITY_OVER_POSE
    if PRIORITY_IDENTITY_OVER_POSE.lower() in body.lower():
        return body
    return f"{PRIORITY_IDENTITY_OVER_POSE}\n\n{body}"


_MODEL_IDENTITY_LINE_RE = re.compile(r"(?m)^Model identity:\s", re.I)


def inject_wavespeed_model_identity(
    prose: str,
    *,
    model_profile_text: str | None,
    visibility: "IdentityVisibility | None" = None,
    wavespeed_identity_legend: str | None = None,
) -> str:
    """
    Гарантированный блок Model identity для WaveSpeed prose-режимов.
    Вызывается после sanitize — иначе identity-строку с «bust/waist/face» съедает post-filter.
    """
    text = (prose or "").strip()
    if not text:
        return text
    if _MODEL_IDENTITY_LINE_RE.search(text):
        return text

    anchor = grok_figure_anchor_from_profile(
        model_profile_text,
        visibility=visibility,
    ).strip()
    if not anchor and model_profile_text is None and visibility is None:
        return _prepend_priority_rule(text)

    body = text
    leg = (wavespeed_identity_legend or "").strip()
    if leg and "Attached model reference photos" not in body:
        role_hint = ""
        low_leg = leg.lower()
        if "face only" in low_leg and "body only" in low_leg:
            role_hint = (
                " Never swap roles: face refs = likeness only; body refs = proportions only."
            )
        body = f"Attached model reference photos — {leg}.{role_hint}\n\n{body}"

    if anchor:
        body = f"Model identity: {anchor}\n\n{body}"
    return _prepend_priority_rule(body)


_CURVY_BUILD_TOKENS = (
    "large bust",
    "full bust",
    "full-busted",
    "full busted",
    "voluptuous",
    "voluptuous hourglass",
    "soft feminine",
    "soft flat abdomen",
    "soft flat",
    "curvy hourglass",
    "d-cup",
    "c-cup",
    "plus-size",
    "plus size",
)

_LEAN_BUST_TOKENS = (
    "small bust",
    "small high bust",
    "a/b",
    "a-cup",
    "a cup",
    "b-cup",
    "low volume",
)


def _has_curvy_build_signal(text: str) -> bool:
    low = (text or "").lower()
    if any(token in low for token in _CURVY_BUILD_TOKENS):
        return True
    if any(token in low for token in _LEAN_BUST_TOKENS):
        return False
    if "lean athletic" in low:
        return False
    return any(token in low for token in ("pronounced hourglass", "wide hips", "wide hip", "curvy"))


def _profile_prefers_lean_build(text: str) -> bool:
    """True when profile explicitly locks lean / small-bust silhouette."""
    if _has_curvy_build_signal(text):
        return False
    low = (text or "").lower()
    return any(
        token in low
        for token in (
            "lean athletic",
            *_LEAN_BUST_TOKENS,
            "flat defined abdomen",
            "visible abs",
            "visible muscle",
            "ectomorph",
            "slim-fit",
            "not curvy",
            "not plus",
        )
    )


def _profile_prefers_curvy_build(text: str) -> bool:
    if _profile_prefers_lean_build(text):
        return False
    return _has_curvy_build_signal(text)


def _extract_build_clause_from_anchor(anchor: str) -> str:
    text = (anchor or "").strip()
    if not text:
        return ""
    low = text.lower()
    if any(
        marker in low
        for marker in (
            "model body proportions from body_reference",
            "do not copy donor silhouette",
            "visible regions [",
        )
    ) and "build:" not in low:
        return ""
    if "Build:" in text:
        build = text.split("Build:", 1)[1].strip()
        return build.split("Same person", 1)[0].strip().rstrip(".,;")
    if text.lower().startswith("visible regions"):
        parts = text.split(":", 2)
        if len(parts) > 2:
            return parts[-1].split("Same person", 1)[0].strip().rstrip(".,;")
    if len(text) > 220:
        return ""
    return text


def _figure_enforcement_tail_message(build: str) -> str:
    """Profile-aware closing lock — lean vs curvy vs neutral."""
    if _profile_prefers_lean_build(build):
        return (
            f"Mandatory figure lock — lean athletic build with small bust; "
            f"NOT curvy/plus-size, NOT bodybuilder, NOT fashion-catalog slim-with-large-bust; "
            f"match body reference photos exactly: {build}."
        )
    if _profile_prefers_curvy_build(build):
        return (
            f"Mandatory figure lock — voluptuous/curvy hourglass with full bust; "
            f"NOT lean athletic, NOT small bust, NOT fashion-model slim silhouette, NOT visible abs unless in profile; "
            f"match body reference photos exactly: {build}."
        )
    return (
        f"Mandatory figure lock — match body reference photos; "
        f"bust/waist/hip volumes exactly: {build}."
    )


def enrich_wavespeed_json_with_identity(
    positive_json: str,
    *,
    model_profile_text: str | None,
    visibility: "IdentityVisibility | None" = None,
) -> str:
    """JSON brief modes: inject figure lock into constraints (img tags skip prose injection)."""
    raw = (positive_json or "").strip()
    if not raw.startswith("{"):
        return positive_json
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return positive_json
    if not isinstance(data, dict):
        return positive_json

    anchor = grok_figure_anchor_from_profile(model_profile_text, visibility=visibility).strip()
    build = _extract_build_clause_from_anchor(anchor)
    if not build:
        return positive_json

    constraints = data.get("constraints")
    if not isinstance(constraints, dict):
        constraints = {}
        data["constraints"] = constraints
    must_keep = constraints.get("must_keep")
    if not isinstance(must_keep, list):
        must_keep = list(must_keep) if must_keep else []

    figure_line = f"Body proportions locked — {build}"
    if figure_line not in must_keep:
        must_keep.insert(0, figure_line)

    tail_line = _figure_enforcement_tail_message(build)
    if tail_line not in must_keep and len(tail_line) <= 420:
        must_keep.insert(1, tail_line)

    from app.services.studio_character_profile import (
        build_generation_packs,
        parse_profile_document,
    )

    doc = parse_profile_document(model_profile_text)
    if doc:
        neg = build_generation_packs(doc).get("negative_lock") or []
        body_neg = [
            str(x).strip()
            for x in neg
            if str(x).strip()
            and any(
                w in str(x).lower()
                for w in (
                    "bust",
                    "curvy",
                    "shoulder",
                    "stomach",
                    "muscular",
                    "hair",
                    "skin",
                    "waist",
                    "hip",
                    "body",
                )
            )
        ][:6]
        if body_neg:
            never_line = f"Never change identity: {', '.join(body_neg)}"
            if never_line not in must_keep:
                must_keep.append(never_line)

    constraints["must_keep"] = must_keep[:8]
    if build and not data.get("identity_lock"):
        data["identity_lock"] = build

    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def append_figure_lock_enforcement_tail(
    prose: str,
    *,
    model_profile_text: str | None,
    visibility: "IdentityVisibility | None" = None,
) -> str:
    """Короткий повтор Build: в конце prose — WAN/Seedream лучше держит пропорции у хвоста."""
    text = (prose or "").rstrip()
    if not text or "Mandatory figure lock" in text:
        return text
    if visibility is not None and not visibility.include_body_proportions:
        return text
    anchor = grok_figure_anchor_from_profile(
        model_profile_text,
        visibility=visibility,
    ).strip()
    if not anchor:
        return text
    build = _extract_build_clause_from_anchor(anchor)
    if not build or len(build) < 12:
        return text
    tail = _figure_enforcement_tail_message(build)
    if "Photoreal phone look —" in text:
        head, _sep, rest = text.partition("\n\nPhotoreal phone look —")
        return f"{head.rstrip()}\n\n{tail}\n\nPhotoreal phone look —{rest}".strip()
    return f"{text}\n\n{tail}".strip()


def _prepare_grok_scene_prose_body(refined_text: str) -> str:
    return strip_soft_dof_from_scene_prose(
        strip_workflow_meta_from_wavespeed_prose(
            strip_donor_identity_from_scene_prose((refined_text or "").strip())
        )
    )


_WAVESPEED_PROSE_BRIEF_MODES = frozenset(
    {"grok_main_prose", "deterministic_compose", "grok_composed", "grok_composed_text"}
)


def _merge_negative_parts(*parts: str | None) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for block in parts:
        if not block or not str(block).strip():
            continue
        for piece in re.split(r"[,;\n]+", str(block)):
            t = piece.strip().lower()
            if not t or t in seen:
                continue
            if _SKIN_TEXTURE_BAN_NEGATIVE_RE.search(t) or _BODY_SHAPE_NEGATIVE_RE.search(t):
                continue
            seen.add(t)
            out.append(piece.strip())
    return ", ".join(out)


def _is_scene_specific_avoid_term(term: str) -> bool:
    t = term.strip().lower()
    if not t:
        return True
    if _SCENE_AVOID_RE.search(t):
        return True
    if any(
        w in t
        for w in (
            "setting",
            "backdrop",
            "outfit",
            "dress",
            "wardrobe",
            "location",
            "room",
            "beach",
            "street",
            "cafe",
        )
    ):
        return True
    return False


def _keep_avoid_term(term: str) -> bool:
    t = term.strip().lower()
    if not t or _is_scene_specific_avoid_term(term):
        return False
    if _SKIN_TEXTURE_BAN_NEGATIVE_RE.search(t):
        return False
    if any(h in t for h in _QUALITY_AVOID_HINTS):
        return True
    if any(h in t for h in _IDENTITY_AVOID_HINTS):
        return True
    return False


def _filter_avoid_csv(raw: str) -> str:
    kept = [a for a in re.split(r"[,;\n]+", raw) if _keep_avoid_term(a)]
    return ", ".join(kept)


def _parse_model_profile_root(model_profile_text: str | None) -> dict[str, Any] | None:
    if not model_profile_text or not model_profile_text.strip():
        return None
    try:
        data = json.loads(model_profile_text.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    prof = data.get("model_profile")
    return prof if isinstance(prof, dict) else data


def _as_text(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, dict):
        parts = [_as_text(v) for v in val.values() if _as_text(v)]
        return "; ".join(parts)
    if isinstance(val, list):
        return "; ".join(_as_text(v) for v in val if _as_text(v))
    return ""


def _truncate_at_word_boundary(text: str, max_len: int) -> str:
    """Последний резерв: обрезка по границе слова, не посередине предложения."""
    s = (text or "").strip()
    if len(s) <= max_len:
        return s
    if max_len <= 1:
        return "…"
    cut = s[: max_len - 1].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0].rstrip()
    return (cut or s[: max_len - 1].rstrip()) + "…"


def _reference_scene_max_chars() -> int:
    from app.config import settings

    return max(_COMPACT_SCENE_NOTES_MAX, int(getattr(settings, "studio_reference_scene_max_chars", 8000)))


def reference_scene_text_for_prompt(description: str | None) -> str:
    """Полное описание референса для prompt (без выборочного POSE:/FRAMING: фильтра)."""
    raw = (description or "").strip()
    if not raw:
        return ""
    lim = _reference_scene_max_chars()
    if len(raw) <= lim:
        return raw
    return _truncate_at_word_boundary(raw, lim)


def _truncate_identity_field(text: str, *, max_len: int = _COMPACT_IDENTITY_FIELD_MAX) -> str:
    s = (text or "").strip()
    if len(s) <= max_len:
        return s
    return _truncate_at_word_boundary(s, max_len)


def extract_wardrobe_from_reference(description: str | None) -> tuple[str, bool]:
    """Строка CLOTHING из описания референса и флаг «минимальное покрытие / nude»."""
    raw = (description or "").strip()
    if not raw:
        return "", False
    clothing_line = ""
    for line in raw.splitlines():
        t = line.strip()
        if t.upper().startswith("CLOTHING:"):
            clothing_line = t
            break
    probe = clothing_line or raw[:500]
    is_nude = bool(_NUDE_CLOTHING_RE.search(probe))
    if clothing_line:
        return _truncate_identity_field(clothing_line, max_len=320), is_nude
    if is_nude:
        return "CLOTHING: match pose reference image 1 — same nudity/coverage as visible (no garments)", True
    return "", False


def compact_studio_prompt_for_nano_banana(
    prompt: str,
    *,
    max_chars: int | None = None,
) -> str:
    """
    Укорачивает промпт для Nano Banana Pro только если превышает лимит Google / WaveSpeed.
    Сначала убирает realism_engine и negative в JSON; scene_brief / prose режем в последнюю очередь.
    """
    from app.config import settings

    lim = max_chars if max_chars is not None else int(settings.wavespeed_nano_prompt_max_chars)
    lim = max(2000, lim)
    p = (prompt or "").strip()
    if len(p) <= lim:
        return p

    brace = p.find("{")
    if brace < 0:
        return _truncate_at_word_boundary(p, lim)

    prefix = p[:brace]
    raw_json = p[brace:].strip()
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        combined = (prefix + raw_json).strip()
        return combined if len(combined) <= lim else _truncate_at_word_boundary(combined, lim)

    if not isinstance(data, dict):
        return _truncate_at_word_boundary(p, lim)

    data.pop("realism_engine", None)
    cons = data.get("constraints")
    if isinstance(cons, dict) and "avoid" in cons:
        cons = dict(cons)
        cons.pop("avoid", None)
        data["constraints"] = cons
    neg = str(data.get("negative_prompt") or "")
    if len(neg) > 400:
        data["negative_prompt"] = _truncate_at_word_boundary(neg, 400)

    sb = str(data.get("scene_brief") or "").strip()
    compact = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    out = (prefix + compact).strip()
    if len(out) <= lim:
        return out

    if sb:
        overhead = len(out) - len(sb)
        sb_budget = max(800, lim - overhead)
        if len(sb) > sb_budget:
            data["scene_brief"] = _truncate_at_word_boundary(sb, sb_budget)
        compact = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        out = (prefix + compact).strip()
        if len(out) <= lim:
            return out

    return _truncate_at_word_boundary(out, lim)


def nano_banana_preflight_error(
    *,
    wave_profile: str | None,
    reference_scene_description: str | None,
    image_urls: list[str],
) -> str | None:
    """Проверка до вызова Nano Banana; возвращает текст ошибки или None."""
    if (wave_profile or "").strip().lower() != "regular":
        return None
    if not image_urls:
        return (
            "Для режима «Обычные фотографии» (Nano Banana) нужно хотя бы одно изображение "
            "(референс позы или фото модели в кабинете)."
        )
    bad = [
        u
        for u in image_urls
        if not (u or "").strip().lower().startswith("https://")
    ]
    if bad:
        return (
            "WaveSpeed не может скачать референсы: нужны публичные HTTPS-URL "
            "(настройте PUBLIC_APP_URL=https://ваш-домен на сервере)."
        )
    if reference_pose_is_nude_or_minimal_coverage(reference_scene_description):
        return (
            "Режим «Обычные фотографии» (Google Nano Banana) не принимает откровенную наготу "
            "в референсе позы. Переключите тип генерации на «NSFW (WAN)» или загрузите одетый референс."
        )
    return None


def _truncate_profile_clause(text: str, max_len: int = 520) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    cut = t[: max_len + 1].rsplit(" ", 1)[0].rstrip(",;—- ")
    if not cut:
        return t[: max_len - 1].rstrip() + "…"
    return cut + "…"


def _compact_body_proportions_clause(
    body: str,
    *,
    max_parts: int = 5,
    max_len: int = STUDIO_BODY_PROPORTIONS_MAX,
) -> str:
    """Сжать чеклист пропорций в короткую фразу — иначе съедает вес сцены/кожи."""
    body = harmonize_figure_lock_clause(body)
    parts = [p.strip(" .") for p in re.split(r"[;|]+", body or "") if p.strip(" .")]
    if not parts:
        return ""
    return _truncate_profile_clause(", ".join(parts[:max_parts]), max_len)


def strip_soft_dof_from_scene_prose(prose: str) -> str:
    """Убрать портретный soft-bokeh из Grok-сцены — телефон = deep focus."""
    t = (prose or "").strip()
    if not t:
        return t
    t = _SOFT_DOF_PHRASE_RE.sub("background details readable and mostly sharp", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\s+,", ",", t)
    return t.strip()


def extract_creative_notes_from_workflow_description(raw: str | None) -> str:
    """Из workflow USER_NOTES взять только креативный текст сцены — без REFERENCE_CONTEXT."""
    text = (raw or "").strip()
    if not text:
        return ""
    # Только блок SCENE_DIRECTION, если есть.
    m = re.search(
        r"SCENE_DIRECTION:\s*(.*?)(?=\n\nREFERENCE_CONTEXT\b|\Z)",
        text,
        flags=re.I | re.S,
    )
    if m:
        text = m.group(1).strip()
    else:
        # Убрать REFERENCE_CONTEXT целиком, если пришло без заголовка SCENE_DIRECTION.
        text = re.split(r"\n\nREFERENCE_CONTEXT\b", text, maxsplit=1, flags=re.I)[0].strip()
        text = re.sub(r"^SCENE_DIRECTION:\s*", "", text, flags=re.I).strip()
    text = _PO_REFU_BOILERPLATE_RE.sub("", text).strip()
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def strip_workflow_meta_from_wavespeed_prose(prose: str) -> str:
    """Не пускать SCENE_DIRECTION / REFERENCE_CONTEXT в финальный WaveSpeed prompt."""
    t = (prose or "").strip()
    if not t:
        return t
    t = _WORKFLOW_META_BLOCK_RE.sub("", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def phone_candid_photo_coda(*, include_eyes: bool = True) -> str:
    """Photoreal phone tail; eye liveness only when the reference crop shows a face."""
    if include_eyes:
        return PHONE_CANDID_PHOTO_CODA
    return _PHONE_CANDID_PHOTO_BASE


def append_phone_candid_photo_coda(
    prompt: str,
    *,
    brief_mode: str = "full",
    visibility: "IdentityVisibility | None" = None,
) -> str:
    """Гарантированный короткий photoreal-хвост в конце prose-промпта."""
    from app.services.studio_reference_analysis import IdentityVisibility

    mode = (brief_mode or "full").strip().lower()
    if mode in ("grok_composed", "grok_composed_text"):
        return (prompt or "").rstrip()
    include_eyes = visibility is None or bool(getattr(visibility, "include_face", True))
    coda = phone_candid_photo_coda(include_eyes=include_eyes)
    base = (prompt or "").rstrip()
    if not base:
        return coda
    if "Photoreal phone look —" in base:
        if not include_eyes and "Eyes alive —" in base:
            base = base.replace(EYE_LIVENESS_CODA, "").strip()
            base = re.sub(r"\s{2,}", " ", base).rstrip()
        elif include_eyes and "Eyes alive —" not in base and _PHONE_CANDID_PHOTO_BASE.rstrip(".") in base:
            return f"{base} {EYE_LIVENESS_CODA}".strip()
        return base
    # Длинный Capture realism в середине после FACE_SWAP почти не читается — заменяем хвостом.
    if "\n\nCapture realism:" in base:
        base = base.split("\n\nCapture realism:", 1)[0].rstrip()
    elif base.startswith("Capture realism:"):
        base = ""
    if base:
        return f"{base}\n\n{coda}"
    return coda


def grok_figure_anchor_from_profile(
    model_profile_text: str | None,
    visibility: "IdentityVisibility | None" = None,
) -> str:
    """Короткий FIGURE_LOCK для Grok compose — объёмы из профиля только для видимых регионов."""
    from app.services.studio_character_profile import build_figure_anchor_from_profile

    return build_figure_anchor_from_profile(model_profile_text, visibility)


_IDENTITY_OPENER_RE = re.compile(
    r"^(?:A|An|The)\s+.+?(?=\s+(?:takes|stands|sits|lies|holds|wears|poses|leans|kneels|"
    r"walks|selfies|selfie|mirror|films|captures|is\s+standing|is\s+sitting|is\s+holding)\b)",
    re.I | re.DOTALL,
)

_IDENTITY_CLAUSE_RES = (
    re.compile(r"\b\d{1,2}[- ]year[- ]old\b", re.I),
    re.compile(
        r"\b(?:Eurasian|Asian|Caucasian|Latina|Slavic|European|African|mixed[- ]race)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:long|short|shoulder[- ]length)\s+(?:golden\s+)?(?:blonde|blond|brunette|black|brown|auburn|red)\s+(?:wavy|straight|curly)?\s*hair\b",
        re.I,
    ),
    re.compile(
        r"\b(?:black|blonde|blond|brunette|brown|auburn|red|dark|light|grey|gray)\s+hair\b",
        re.I,
    ),
    re.compile(
        r"\b(?:warm\s+)?(?:golden|tan|pale|fair|dark|olive|bronze|caramel|medium[- ]brown)\s+(?:tan\s+)?skin\b",
        re.I,
    ),
    re.compile(
        r"\b(?:large|small|natural|full|perky|prominent)\s+(?:natural\s+)?(?:C[- ]cup|D[- ]cup|B[- ]cup|A[- ]cup|size\s+\d\s+)?(?:breasts|bust)\b",
        re.I,
    ),
    re.compile(r"\b(?:very\s+)?(?:toned|defined|flat|visible)\s+(?:midsection|abs|stomach|six[- ]pack)\b", re.I),
    re.compile(r"\b(?:narrow|wide|slim|tiny|snatched)\s+waist\b", re.I),
    re.compile(r"\b(?:bright|blue|brown|green|hazel|medium[- ]brown)\s+eyes\b", re.I),
    re.compile(r"\boval\s+face\b", re.I),
    re.compile(r"\b(?:hourglass|petite|curvy|athletic|slender|lean)\s+(?:figure|build|body|physique)\b", re.I),
    re.compile(r"\b(?:lean|slim|skinny|athletic)\s+(?:and\s+)?(?:toned|muscular)?\s*(?:woman|man|subject|model)?\b", re.I),
    re.compile(r"\b(?:long\s+)?(?:straight\s+)?lean\s+legs\b", re.I),
)


def harmonize_figure_lock_clause(body: str) -> str:
    """
    Убрать slim/lean/athletic из Build, когда в профиле явный hourglass (waist+hips / WHR)
    и нет явного lean/small-bust якоря.
    """
    text = (body or "").strip()
    if not text:
        return text
    if _profile_prefers_lean_build(text):
        return text
    low = text.lower()
    curvy_signal = (
        "wide hip" in low
        or "hourglass" in low
        or re.search(r"whr\s*0\.[56]", low)
        or ("waist" in low and "hip" in low and re.search(r"\d{2,3}", low))
    )
    if not curvy_signal:
        return text
    slim_terms = re.compile(
        r"\b(lean athletic|lean\s+athletic|ectomorphic|skinny|petite frame|"
        r"fashion[- ]model|long straight lean legs|lean legs|lean build)\b",
        re.I,
    )
    had_slim = bool(slim_terms.search(text))
    cleaned = slim_terms.sub("", text)
    cleaned = re.sub(r"(?:,\s*){2,}", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;")
    if had_slim and curvy_signal and "hourglass" not in cleaned.lower():
        cleaned = f"pronounced hourglass, wide hips, narrow waist; {cleaned}"
    return cleaned


def strip_donor_identity_from_scene_prose(prose: str) -> str:
    """
    Убирает из Grok scene prose описание донора (возраст, этничность, волосы, кожа, грудь…).
    Identity задаётся MODEL_IDENTITY + ref images; prose — только shot/pose/light/room/одежда.
    """
    text = (prose or "").strip()
    if not text:
        return text

    m = _IDENTITY_OPENER_RE.match(text)
    if m and len(m.group(0)) > 35:
        tail = text[m.end() :].lstrip()
        if tail:
            text = tail if re.match(r"^(She|He|The|They)\b", tail, re.I) else f"She {tail}"

    for pat in _IDENTITY_CLAUSE_RES:
        text = pat.sub("", text)

    text = re.sub(r"\bwith\s+,", "", text, flags=re.I)
    text = re.sub(r",\s*,+", ", ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"^\s*,\s*", "", text)
    text = re.sub(r"\s+\.", ".", text)
    return text.strip()


def reference_pose_is_nude_or_minimal_coverage(description: str | None) -> bool:
    return extract_wardrobe_from_reference(description)[1]


def compact_scene_notes_from_reference(description: str | None) -> str:
    """Текст сцены из vision-описания референса (полный текст, без урезания до POSE:/FRAMING:)."""
    return reference_scene_text_for_prompt(description)


def _compact_profile_identity_fields(prof: dict[str, Any] | None) -> dict[str, str]:
    """Сжатый identity для WAN compact — не весь вложенный профиль в одну строку."""
    if not prof:
        return {}
    keywords = _as_text(prof.get("identity_lock_keywords"))
    full = _profile_identity_fields(prof)
    if keywords:
        full["subject"] = _truncate_identity_field(keywords, max_len=300)
    for key in ("face", "hair", "body_proportions"):
        if full.get(key):
            full[key] = _truncate_identity_field(full[key])
    return full


def _profile_identity_fields(prof: dict[str, Any] | None) -> dict[str, str]:
    if not prof:
        return {}
    age = _as_text(prof.get("age"))
    eth = _as_text(prof.get("ethnicity"))
    face = _as_text(prof.get("face_features") or prof.get("face"))
    body = _as_text(
        prof.get("body_type")
        or prof.get("body_proportions")
        or prof.get("body")
    )
    hair_raw = prof.get("hair")
    hair = _as_text(hair_raw)
    if isinstance(hair_raw, dict):
        hair = _as_text(
            {
                "color": hair_raw.get("color"),
                "length": hair_raw.get("length"),
                "style": hair_raw.get("style_default") or hair_raw.get("style"),
            }
        )
    subj_bits = [b for b in (age, eth) if b]
    subject = ""
    if subj_bits:
        subject = f"{', '.join(subj_bits)}"
        if hair:
            subject += f", {hair.split(';')[0].strip()}"
    return {
        "subject": subject,
        "face": face,
        "hair": hair,
        "body_proportions": body,
    }


def _llm_identity_fields(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    id_ref = data.get("identity_reference")
    if isinstance(id_ref, dict):
        for k in ("subject", "face", "hair", "body_proportions"):
            v = _as_text(id_ref.get(k))
            if v:
                out[k] = v
        if out:
            return out

    subj = data.get("subject")
    if not isinstance(subj, dict):
        return out

    desc = _as_text(subj.get("description"))
    if desc:
        parts = _DESC_SCENE_SPLIT_RE.split(desc, maxsplit=1)
        out["subject"] = parts[0].strip()
        if len(parts) > 1 and "hourglass" in desc.lower():
            m = re.search(
                r"(curvy|hourglass|athletic|full\s+round\s+bust|pronounced\s+round\s+glutes)[^.]*",
                desc,
                re.I,
            )
            if m and "body_proportions" not in out:
                out["body_proportions"] = m.group(0).strip()

    ident = subj.get("identity")
    if isinstance(ident, dict):
        if not out.get("face"):
            out["face"] = _as_text(ident.get("face_features"))
        if not out.get("body_proportions"):
            out["body_proportions"] = _as_text(ident.get("body_type"))
        hair_i = ident.get("hair")
        if not out.get("hair") and isinstance(hair_i, dict):
            out["hair"] = _as_text(
                {
                    "color": hair_i.get("color"),
                    "length": hair_i.get("length"),
                    "style": hair_i.get("style_default"),
                }
            )

    body = subj.get("body")
    if isinstance(body, dict):
        frame = _as_text(body.get("frame"))
        chest = _as_text(body.get("chest"))
        legs = _as_text(body.get("legs"))
        skin = body.get("skin")
        skin_t = _as_text(skin.get("tone")) if isinstance(skin, dict) else ""
        parts = [p for p in (frame, chest, legs) if p]
        if parts:
            body_line = "; ".join(parts)
            if skin_t:
                body_line += f"; skin tone {skin_t}"
            if not out.get("body_proportions"):
                out["body_proportions"] = body_line
            elif chest or frame:
                out["body_proportions"] = body_line

    hair_block = subj.get("hair")
    if not out.get("hair") and isinstance(hair_block, dict):
        out["hair"] = _as_text(
            {
                "color": hair_block.get("color"),
                "style": hair_block.get("style"),
                "effect": hair_block.get("effect"),
            }
        )

    return out


def _pick_identity_field(
    key: str,
    *,
    profile: dict[str, str],
    llm: dict[str, str],
) -> str:
    p = profile.get(key, "").strip()
    l = llm.get(key, "").strip()
    if key == "body_proportions":
        return p or l
    if key == "subject":
        if p:
            return p
        return l
    return p or l


def coerce_compact_pose_positive(
    data: dict[str, Any],
    *,
    model_profile_text: str | None,
    reference_scene_description: str | None = None,
    visibility: "IdentityVisibility | None" = None,
) -> dict[str, Any]:
    """
    Жёстко собирает compact JSON: сцена — image 1 + краткие pose_reference_notes;
    identity (включая фигуру) — сжато из профиля/LLM.
    """
    prof_root = _parse_model_profile_root(model_profile_text)
    prof_id = _compact_profile_identity_fields(prof_root)
    llm_id = _llm_identity_fields(data)

    identity = {
        k: _pick_identity_field(k, profile=prof_id, llm=llm_id)
        for k in ("subject", "face", "hair", "body_proportions")
    }
    if visibility is not None:
        from app.services.studio_reference_analysis import filter_identity_reference_dict

        identity = filter_identity_reference_dict(
            {k: v for k, v in identity.items() if v},
            visibility,
        )
    if not any(identity.values()):
        log.warning("compact pose coerce: empty identity_reference, keeping minimal placeholder")
        identity["subject"] = identity["subject"] or "studio model identity from reference photos"

    user_overrides = _as_text(data.get("user_overrides"))

    snapshot = "casual realistic smartphone snapshot, natural phone grain"
    aspect = "3:4"
    ps = data.get("photography_style")
    if isinstance(ps, dict):
        snapshot = _as_text(ps.get("snapshot_authenticity")) or snapshot
        aspect = _as_text(ps.get("aspect_ratio")) or aspect
    else:
        photo = data.get("photography")
        if isinstance(photo, dict):
            aspect = _as_text(photo.get("aspect_ratio")) or aspect
            snap = _as_text(photo.get("camera_style")) or _as_text(photo.get("texture"))
            if snap:
                snapshot = snap

    mood = ""
    life = ""
    tv = data.get("the_vibe")
    if isinstance(tv, dict):
        mood = _as_text(tv.get("mood"))
        life = _as_text(tv.get("life_in_frame") or tv.get("intimacy_level") or tv.get("intimacy"))

    scene_notes = compact_scene_notes_from_reference(reference_scene_description)
    wardrobe_line, ref_nude = extract_wardrobe_from_reference(reference_scene_description)
    scene_pose = scene_notes or _SCENE_FROM_REF_LITERAL
    wardrobe_cov = wardrobe_line or (
        "Match pose reference image 1 exactly for garments or nudity — "
        "do not use clothing from model identity photos"
    )
    return {
        "identity_reference": identity,
        "wardrobe_coverage": wardrobe_cov,
        "pose_reference_is_nude_or_minimal": ref_nude,
        "scene_from_reference_image": {
            "pose_and_composition": scene_pose,
            "wardrobe_and_environment": wardrobe_cov,
            "lighting_and_camera": scene_pose,
            "pose_reference_notes": scene_notes,
        },
        "user_overrides": user_overrides,
        "photography_style": {
            "snapshot_authenticity": snapshot,
            "aspect_ratio": aspect,
        },
        "the_vibe": {
            "mood": mood or "natural",
            "life_in_frame": life or "everyday candid moment",
        },
        "constraints": {"must_keep": list(_COMPACT_MUST_KEEP)},
    }


def _always_avoid_from_profile(model_profile_text: str | None) -> str:
    from app.services.studio_character_profile import profile_negative_traits

    v1_neg = profile_negative_traits(model_profile_text)
    if v1_neg:
        return _filter_avoid_csv(v1_neg)
    prof = _parse_model_profile_root(model_profile_text)
    if not prof:
        return ""
    raw = prof.get("always_avoid")
    if isinstance(raw, list):
        merged = ", ".join(str(x).strip() for x in raw if str(x).strip())
    elif isinstance(raw, str):
        merged = raw.strip()
    else:
        return ""
    return _filter_avoid_csv(merged)


def _avoid_list_from_constraints(data: dict[str, Any]) -> list[str]:
    cons = data.get("constraints")
    if not isinstance(cons, dict):
        return []
    raw = cons.get("avoid")
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip() and _keep_avoid_term(str(x))]
    if isinstance(raw, str) and raw.strip():
        return [a for a in re.split(r"[,;\n]+", raw) if _keep_avoid_term(a)]
    return []


def extract_studio_negative_prompt(
    refined_data: dict[str, Any],
    *,
    model_profile_text: str | None,
) -> str:
    neg = refined_data.pop("negative_prompt", None)
    neg_s = neg.strip() if isinstance(neg, str) else ""
    if neg_s:
        neg_s = _strip_body_shape_from_negative(_filter_avoid_csv(neg_s))
    avoid_parts = _avoid_list_from_constraints(refined_data)
    cons = refined_data.get("constraints")
    if isinstance(cons, dict) and "avoid" in cons:
        cons = dict(cons)
        cons.pop("avoid", None)
        if cons:
            refined_data["constraints"] = cons
        elif "constraints" in refined_data and not cons:
            refined_data.pop("constraints", None)
    avoid_merged = ", ".join(avoid_parts)
    profile_avoid = _always_avoid_from_profile(model_profile_text)
    return _merge_negative_parts(_CANONICAL_STUDIO_NEGATIVE, neg_s, avoid_merged, profile_avoid)


def _merge_grok_scene_negative(
    *,
    model_profile_text: str | None,
    extra_negative: str | None,
    reference_scene_description: str | None,
) -> str:
    grok_neg = _strip_body_shape_from_negative(_filter_avoid_csv((extra_negative or "").strip()))
    negative = _merge_negative_parts(
        _CANONICAL_STUDIO_NEGATIVE,
        _GROK_COMPOSE_COMPOSITE_NEGATIVE,
        grok_neg,
        _always_avoid_from_profile(model_profile_text),
    )
    if reference_pose_is_nude_or_minimal_coverage(reference_scene_description):
        negative = _merge_negative_parts(negative, _NUDE_WARDROBE_NEGATIVE)
    return negative


def build_grok_scene_positive_json(
    grok_prose: str,
    *,
    model_profile_text: str | None,
    output_aspect_key: str = "3:4",
    extra_negative: str | None = None,
    reference_scene_description: str | None = None,
    with_pose_reference: bool = False,
    selfie_capture: bool = False,
) -> tuple[str, str]:
    """
    Grok prose → JSON с realism_engine.
    with_pose_reference: Grok+референс позы (pose lock из input image, identity из refs 2+).
    Иначе: «По промту» без pose bitmap.
    negative не кладём в JSON/prompt — WaveSpeed edit лучше без negative-вставки.
    """
    prose = _prepend_priority_rule((grok_prose or "").strip())
    negative = _merge_grok_scene_negative(
        model_profile_text=model_profile_text,
        extra_negative=extra_negative,
        reference_scene_description=reference_scene_description,
    )
    re_obj = load_canonical_realism_engine()
    aspect = (output_aspect_key or "3:4").strip() or "3:4"

    if selfie_capture:
        from app.services.studio_workflow_selfie import (
            must_keep_for_selfie,
            photography_json_for_selfie,
            selfie_negative_extras,
        )

        negative = _merge_negative_parts(negative, selfie_negative_extras())
        photography = photography_json_for_selfie(aspect, with_pose_reference=with_pose_reference)
        must_keep = must_keep_for_selfie(with_pose_reference=with_pose_reference)
    elif with_pose_reference:
        photography: dict[str, Any] = {
            "aspect_ratio": aspect,
            "pose_from_image_1": "joint angles, crop, camera, background, light, wardrobe coverage",
            "identity_from_model_refs": "face, skin, hair, body shape on visible skin",
        }
        must_keep = list(_COMPACT_MUST_KEEP)
    else:
        photography = {
            "aspect_ratio": aspect,
            "camera_style": "casual smartphone snapshot — not studio or catalog",
            "lighting": "ambient incidental light — no ring-light glamour",
        }
        must_keep = [
            "One real person; identity from model reference images on visible skin",
            "Scene pose, room, and light from scene_brief only",
            "Phone snapshot: pores, uneven tone, deep focus, shadow noise",
        ]

    data: dict[str, Any] = {
        "scene_brief": prose,
        "photography": photography,
        "constraints": {"must_keep": must_keep},
    }
    if re_obj is not None:
        data["realism_engine"] = re_obj

    positive = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return positive, negative


def build_grok_text_scene_positive_json(
    grok_prose: str,
    *,
    model_profile_text: str | None,
    output_aspect_key: str = "3:4",
    extra_negative: str | None = None,
    reference_scene_description: str | None = None,
    selfie_capture: bool = False,
) -> tuple[str, str]:
    """«По промту» без pose reference."""
    return build_grok_scene_positive_json(
        grok_prose,
        model_profile_text=model_profile_text,
        output_aspect_key=output_aspect_key,
        extra_negative=extra_negative,
        reference_scene_description=reference_scene_description,
        with_pose_reference=False,
        selfie_capture=selfie_capture,
    )


def prepare_positive_prompt_json(
    refined_text: str,
    *,
    brief_mode: str,
    model_profile_text: str | None,
    reference_scene_description: str | None = None,
    extra_negative: str | None = None,
    output_aspect_key: str = "3:4",
    wavespeed_identity_legend: str | None = None,
    include_realism_engine: bool = True,
    selfie_capture: bool = False,
    visibility: "IdentityVisibility | None" = None,
) -> tuple[str, str]:
    """
    Возвращает (positive_for_wavespeed, negative_prompt_line).
    brief_mode: full | compact_pose_image | text_scene | grok_composed | grok_composed_text | grok_main_prose
    """
    mode = (brief_mode or "full").strip().lower()
    if mode == "grok_main_prose":
        prose = _prepare_grok_scene_prose_body(refined_text)
        negative = _merge_grok_scene_negative(
            model_profile_text=model_profile_text,
            extra_negative=extra_negative,
            reference_scene_description=reference_scene_description,
        )
        return prose, negative
    if mode == "deterministic_compose":
        prose = _prepare_grok_scene_prose_body(refined_text)
        negative = _merge_grok_scene_negative(
            model_profile_text=model_profile_text,
            extra_negative=extra_negative,
            reference_scene_description=reference_scene_description,
        )
        return prose, negative
    if mode == "grok_composed_text":
        return build_grok_text_scene_positive_json(
            refined_text,
            model_profile_text=model_profile_text,
            output_aspect_key=output_aspect_key,
            extra_negative=extra_negative,
            reference_scene_description=reference_scene_description,
            selfie_capture=selfie_capture,
        )
    if mode == "grok_composed":
        return build_grok_scene_positive_json(
            refined_text,
            model_profile_text=model_profile_text,
            output_aspect_key=output_aspect_key,
            extra_negative=extra_negative,
            reference_scene_description=reference_scene_description,
            with_pose_reference=True,
            selfie_capture=selfie_capture,
        )

    raw = _strip_code_fences(refined_text)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        log.warning("studio prompt bundle: refined output not JSON, pass-through")
        return refined_text.strip(), _CANONICAL_STUDIO_NEGATIVE

    if not isinstance(data, dict):
        return refined_text.strip(), _CANONICAL_STUDIO_NEGATIVE

    mode = (brief_mode or "full").strip().lower()
    if mode == "compact_pose_image":
        data = coerce_compact_pose_positive(
            data,
            model_profile_text=model_profile_text,
            reference_scene_description=reference_scene_description,
            visibility=visibility,
        )

    re_obj = load_canonical_realism_engine()
    if re_obj is not None:
        data["realism_engine"] = re_obj

    negative = extract_studio_negative_prompt(data, model_profile_text=model_profile_text)
    if reference_pose_is_nude_or_minimal_coverage(reference_scene_description):
        negative = _merge_negative_parts(negative, _NUDE_WARDROBE_NEGATIVE)
    if (extra_negative or "").strip():
        negative = _merge_negative_parts(negative, extra_negative.strip())

    positive = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return positive, negative


def append_negative_to_wavespeed_prompt(
    prompt: str,
    negative: str,
    *,
    brief_mode: str = "full",
) -> str:
    """WaveSpeed image-edit имеет только ``prompt`` — отдельного negative нет.

    Вклеивать ``[NEGATIVE_PROMPT] …`` в тот же текст вредно для Nano Banana / GPT Image /
    Seedream / WAN: модели плохо держат отрицание и часто «подхватывают» слова вроде
    smooth/plastic/Facetune как позитив. Claude-style briefs работают лучше без negative.
    ``negative`` оставляем в сигнатуре для логов/совместимости, в prompt не пишем.
    """
    _ = negative, brief_mode
    return (prompt or "").rstrip()
