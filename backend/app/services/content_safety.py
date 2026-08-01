"""Age gate: block generation prompts/profiles that depict minors (<18).

NSFW content for adults remains allowed — checks are independent of studio_wave_profile.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings

log = logging.getLogger(__name__)

MINOR_CONTENT_CODE = "minor_content_prohibited"

MINOR_CONTENT_MESSAGE_RU = (
    "ModelMate не поддерживает генерацию контента с несовершеннолетними. "
    "Измените описание, профиль модели или референсы."
)

MINOR_CONTENT_NEGATIVE_SUPPLEMENT = (
    "child, minor, underage, teenager, teen, preteen, schoolgirl, schoolboy, "
    "loli, shota, young girl, young boy, little girl, little boy"
)

# Explicit minor / underage wording (EN + RU). Word boundaries reduce false positives.
_MINOR_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bunder\s*[- ]?age\b",
        r"\bunderage\b",
        r"\bminors?\b(?!\s+(?:details|adjustments?|changes?|issues?|roles?|damage|scratches?|blemishes?|imperfections?|skin|cosmetic|wear|repairs?))",
        r"\bchild(?:ren)?\b",
        r"\bkid[s]?\b",
        r"\bpreteen[s]?\b",
        r"\bteen(?:ager|age|aged)?\b",
        r"\bschool\s*girl[s]?\b",
        r"\bschool\s*boy[s]?\b",
        r"\bschoolgirl[s]?\b",
        r"\bschoolboy[s]?\b",
        r"\bloli\b",
        r"\bshota\b",
        r"\b(?:young|little)\s+(?:girl|boy)\b",
        r"(?<![0-9])(?:1[0-7])\s*(?:year[s]?\s*old|yo|y\.?o\.?|лет|года|год)\b",
        r"(?<![0-9])[0-9]\s*(?:year[s]?\s*old|yo|y\.?o\.?|лет|года|год)\b",
        r"\bage\s*(?:1[0-7]|(?<![0-9])[0-9])\b",
        r"\b(?:1[0-7])\s*(?:years?\s*old|лет|года|год)\b",
        r"\bнесовершеннолетн",
        r"\bреб[её]нок\b",
        r"\bдет(?:и|ск(?:ий|ая|ое|ого|ой|им|ими|ом|их|ими)?)\b",
        r"\bподрост(?:ок|ка|ки|ков|ком|ке|кам|ками)\b",
        r"\bшкольниц",
        r"\bшкольник",
        r"\bмалолетн",
        r"\bjuvenile\s+(?:appearance|look|features|face|body|build|subject)\b",
    )
)

# Adult phrases that must NOT trip teen/minor heuristics alone.
_ADULT_AGE_SAFE_RE = re.compile(
    r"\b(?:1[89]|[2-9]\d|\d{3,})\s*(?:year[s]?\s*old|yo|y\.?o\.?|лет|года|год)\b",
    re.I,
)

_AGE_FIELD_RE = re.compile(r"^\s*(\d{1,3})\s*(?:years?\s*old|yo|y\.?o\.?|лет|года|год)?\s*$", re.I)

_AGE_DECADE_ESTIMATE_RE = re.compile(
    r"\b(?:early|mid|late)[\s-]*(\d{1,2})s?\b",
    re.I,
)

_AGE_COMPACT_DECADE_RE = re.compile(r"\b(\d{2})s\b", re.I)

_AGE_ESTIMATE_ADULT_RE = re.compile(
    r"\b(?:mid|late|early)[\s-]*(?:20|30|40|50)s\b|\b(?:twenty|thirty|forty)[\s-]*(?:one|two|three|four|five|six|seven|eight|nine)\b",
    re.I,
)


def _parse_age_years_from_text(text: str) -> int | None:
    """Parse numeric age from profile age strings like 28, 28 yo, early 28s, early-28s."""
    raw = (text or "").strip()
    if not raw:
        return None
    m = _AGE_FIELD_RE.match(raw)
    if m:
        return int(m.group(1))
    m = _AGE_DECADE_ESTIMATE_RE.search(raw)
    if m:
        return int(m.group(1))
    m = _AGE_COMPACT_DECADE_RE.search(raw)
    if m:
        return int(m.group(1))
    if _AGE_ESTIMATE_ADULT_RE.search(raw):
        m2 = re.search(r"\b(?:early|mid|late)[\s-]*(\d{2})s\b", raw, re.I)
        if m2:
            return int(m2.group(1))
        return 20
    m = re.search(r"\b(\d{1,3})\b", raw)
    return int(m.group(1)) if m else None

# Safety blocklists embedded in model_profile JSON — not user-facing descriptions.
_PROFILE_BLOCKLIST_KEYS = frozenset(
    {
        "always_avoid",
        "never_include",
        "negative_prompt",
        "avoid",
        "blocked_terms",
    }
)

# Grok/LLM prose often negates minors («not a teenager», «no minor») — not a request.
_NEGATED_MINOR_PHRASE_RES: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bnot\s+(?:a\s+)?(?:teen(?:ager)?s?|underage|minor?s?|juvenile|child(?:ren)?)\b",
        r"\bno\s+(?:minor?s?|teen?s?|underage|school\s*girl[s]?|school\s*boy[s]?|child(?:ren)?)\b",
        r"\b(?:never|without)\s+(?:\w+\s+){0,3}(?:teen|minor|underage|schoolgirl|juvenile)\w*\b",
        r"\b(?:must\s+not|do\s+not)\s+(?:\w+\s+){0,5}(?:look\s+like\s+a\s+)?(?:teen|minor|underage|schoolgirl|juvenile)\w*\b",
        r"\bavoid\s+(?:the\s+)?(?:school\s*girl[s]?|school\s*boy[s]?|teen(?:ager)?s?|minor?s?|underage)\w*\b",
        r"\bне\s+(?:\w+\s+){0,2}(?:подрост\w+|несовершеннолет\w+|школьниц\w+|реб[её]н\w+)\b",
    )
)

_BLOCKLIST_CSV_RE = re.compile(
    r"(?:\b(?:child(?:ren)?|minor?s?|under\s*[- ]?age|underage|teen(?:ager)?s?|preteen[s]?|"
    r"school\s*girl[s]?|school\s*boy[s]?|schoolgirl[s]?|schoolboy[s]?|loli|shota|"
    r"young\s+girl[s]?|young\s+boy[s]?|little\s+girl[s]?|little\s+boy[s]?)\b\s*,?\s*){2,}",
    re.I,
)


def minor_content_http_exception(reason: str | None = None) -> HTTPException:
    detail: dict[str, str] = {
        "code": MINOR_CONTENT_CODE,
        "message": MINOR_CONTENT_MESSAGE_RU,
    }
    if reason:
        detail["debug_reason"] = reason[:200]
    return HTTPException(status_code=403, detail=detail)


def _strip_blocklist_keys_from_json(value: Any) -> Any:
    """Remove safety blocklist fields from parsed JSON before regex scans."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, val in value.items():
            if key in _PROFILE_BLOCKLIST_KEYS:
                continue
            if key == "constraints" and isinstance(val, dict):
                cons = {
                    ck: cv for ck, cv in val.items() if ck not in _PROFILE_BLOCKLIST_KEYS
                }
                if cons:
                    out[key] = _strip_blocklist_keys_from_json(cons)
                continue
            out[key] = _strip_blocklist_keys_from_json(val)
        return out
    if isinstance(value, list):
        return [_strip_blocklist_keys_from_json(x) for x in value]
    return value


def text_for_minor_content_regex(text: str) -> str:
    """Strip embedded negative/avoid lists from JSON prompt payloads before regex."""
    raw = (text or "").strip()
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    sanitized = _strip_blocklist_keys_from_json(data)
    return json.dumps(sanitized, ensure_ascii=False)


def sanitize_text_for_minor_regex(text: str) -> str:
    """Strip JSON blocklists, negated safety lines, and CSV minor-ban lists before regex."""
    raw = text_for_minor_content_regex(text)
    for pat in _NEGATED_MINOR_PHRASE_RES:
        raw = pat.sub(" ", raw)
    raw = _BLOCKLIST_CSV_RE.sub(" ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def find_minor_content_violation(text: str) -> str | None:
    """Return a short reason if *text* requests or describes minors, else None."""
    raw = sanitize_text_for_minor_regex(text)
    if not raw:
        return None
    if _ADULT_AGE_SAFE_RE.search(raw):
        return None
    for pat in _MINOR_TEXT_PATTERNS:
        if pat.search(raw):
            return f"blocked pattern: {pat.pattern}"
    return None


def _extract_profile_age(profile: dict[str, Any]) -> str | None:
    def _from_dict(data: dict[str, Any]) -> str | None:
        for key in ("age", "apparent_age", "estimated_age", "возраст"):
            val = data.get(key)
            if val is None:
                continue
            if isinstance(val, (int, float)):
                return str(int(val))
            if isinstance(val, str) and val.strip():
                return val.strip()
        return None

    hit = _from_dict(profile)
    if hit:
        return hit
    for val in profile.values():
        if isinstance(val, dict):
            nested = _extract_profile_age(val)
            if nested:
                return nested
    return None


def extract_profile_age_years(profile_text: str | None) -> int | None:
    """Return numeric age from model_profile JSON when clearly >= 0, else None."""
    raw = (profile_text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\b(?:1[89]|[2-9]\d|\d{3,})\b", raw)
        return int(m.group(0)) if m else None
    if not isinstance(data, dict):
        return None
    mp = data.get("model_profile")
    if not isinstance(mp, dict):
        mp = data
    age_raw = _extract_profile_age(mp) if isinstance(mp, dict) else None
    if age_raw is not None:
        if isinstance(age_raw, (int, float)):
            return int(age_raw)
        years = _parse_age_years_from_text(str(age_raw))
        if years is not None:
            return years
    if isinstance(mp, dict):
        ikw = mp.get("identity_lock_keywords")
        if isinstance(ikw, str) and ikw.strip():
            years = _parse_age_years_from_text(ikw)
            if years is not None:
                return years
    return None


def profile_declares_adult_age(profile_text: str | None) -> bool:
    years = extract_profile_age_years(profile_text)
    return years is not None and years >= 18


def validate_profile_age_value(age_raw: str | int | float | None) -> str | None:
    if age_raw is None:
        return None
    text = str(age_raw).strip()
    if not text:
        return None
    if find_minor_content_violation(text):
        return "profile age wording indicates a minor"
    if isinstance(age_raw, (int, float)):
        years = int(age_raw)
    else:
        years = _parse_age_years_from_text(text)
    if years is not None:
        if years < 18:
            return f"profile age {years} < 18"
        return None
    return None


def validate_profile_age_only(profile_text: str | None) -> str | None:
    raw = (profile_text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    mp = data.get("model_profile")
    if not isinstance(mp, dict):
        mp = data
    return validate_profile_age_value(_extract_profile_age(mp) if isinstance(mp, dict) else None)


def validate_model_profile_dict(profile_root: dict[str, Any]) -> str | None:
    mp = profile_root.get("model_profile")
    if not isinstance(mp, dict):
        mp = profile_root
    if not isinstance(mp, dict):
        return None
    age_raw = _extract_profile_age(mp)
    reason = validate_profile_age_value(age_raw)
    if reason:
        return reason
    years = None
    if age_raw is not None:
        if isinstance(age_raw, (int, float)):
            years = int(age_raw)
        else:
            years = _parse_age_years_from_text(str(age_raw).strip())
    if years is not None and years >= 18:
        return None
    for key, val in mp.items():
        if key in _PROFILE_BLOCKLIST_KEYS:
            continue
        if isinstance(val, str) and val.strip():
            hit = find_minor_content_violation(val)
            if hit:
                return f"profile {key}: {hit}"
    cons = mp.get("constraints")
    if isinstance(cons, dict):
        for key, val in cons.items():
            if key in _PROFILE_BLOCKLIST_KEYS:
                continue
            if isinstance(val, str) and val.strip():
                hit = find_minor_content_violation(val)
                if hit:
                    return f"profile constraints.{key}: {hit}"
    return None


def validate_model_profile_text(profile_text: str | None) -> str | None:
    raw = (profile_text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return find_minor_content_violation(raw) and "profile text mentions minors"
    if isinstance(data, dict):
        return validate_model_profile_dict(data)
    return None


def collect_minor_content_violations(
    *,
    texts: list[str] | None = None,
    profile_text: str | None = None,
) -> list[str]:
    reasons: list[str] = []
    for t in texts or []:
        hit = find_minor_content_violation(t)
        if hit:
            reasons.append(hit)
    prof = validate_model_profile_text(profile_text)
    if prof:
        reasons.append(prof)
    return reasons


async def _openai_moderation_flags_minors(text: str) -> bool:
    key = (settings.openai_api_key or "").strip()
    if not key:
        return False
    chunk = text.strip()
    if len(chunk) < 3:
        return False
    if len(chunk) > 8000:
        chunk = chunk[:8000]
    base = (settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {key}"}
    org = (settings.openai_organization or "").strip()
    if org:
        headers["OpenAI-Organization"] = org
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{base}/moderations",
                headers=headers,
                json={"input": chunk, "model": "omni-moderation-latest"},
            )
        if r.status_code >= 400:
            log.warning("content_safety moderation HTTP %s: %s", r.status_code, r.text[:200])
            return False
        payload = r.json()
        results = payload.get("results")
        if not isinstance(results, list):
            return False
        for row in results:
            if not isinstance(row, dict):
                continue
            cats = row.get("category_scores") or row.get("categories") or {}
            if isinstance(cats, dict):
                score = cats.get("sexual/minors")
                if score is True or (isinstance(score, (int, float)) and score >= 0.65):
                    return True
            if row.get("flagged") and isinstance(cats, dict) and cats.get("sexual/minors"):
                return True
    except Exception as e:
        log.warning("content_safety moderation failed: %s", e)
    return False


async def assert_studio_generation_allowed(
    *,
    description: str = "",
    prompt: str = "",
    negative_prompt: str = "",
    refined_prompt: str = "",
    profile_text: str | None = None,
    reference_analysis_json: str | None = None,
    use_moderation: bool = True,
) -> None:
    """Raise HTTP 403 if any supplied text/profile indicates minors."""
    _ = negative_prompt, use_moderation  # OpenAI moderation removed — too many false positives on adult NSFW.

    if profile_declares_adult_age(profile_text):
        age_reason = validate_profile_age_only(profile_text)
        if age_reason:
            log.info("content_safety adult profile age block: %s", age_reason)
            raise minor_content_http_exception(age_reason)
        for t in (description, prompt):
            hit = find_minor_content_violation(t)
            if hit:
                log.info("content_safety user prompt block (adult profile): %s", hit)
                raise minor_content_http_exception(hit)
        return

    raw_texts = [
        description,
        prompt,
        refined_prompt,
        reference_analysis_json or "",
    ]
    reasons = collect_minor_content_violations(texts=raw_texts, profile_text=profile_text)
    if reasons:
        log.info("content_safety regex block: %s", reasons[:3])
        raise minor_content_http_exception(reasons[0])
