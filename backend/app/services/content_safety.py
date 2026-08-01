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
        r"\bminor[s]?\b",
        r"\bchild(?:ren)?\b",
        r"\bkid[s]?\b",
        r"\bpreteen[s]?\b",
        r"\bteen(?:ager|age|aged)?\b",
        r"\bjuv(?:enile|enility)\b",
        r"\bschool\s*girl[s]?\b",
        r"\bschool\s*boy[s]?\b",
        r"\bschoolgirl[s]?\b",
        r"\bschoolboy[s]?\b",
        r"\bloli\b",
        r"\bshota\b",
        r"\b(?:young|little)\s+(?:girl|boy)\b",
        r"\b(?:year[s]?\s*old|yo|y\.?o\.?)\s*(?:1[0-7]|[0-9])\b",
        r"\b(?:1[0-7]|[0-9])\s*(?:year[s]?\s*old|yo|y\.?o\.?)\b",
        r"\bage\s*(?:1[0-7]|[0-9])\b",
        r"\b(?:1[0-7]|[0-9])\s*(?:years?\s*old|лет|года|год)\b",
        r"\bнесовершеннолетн",
        r"\bреб[её]нок\b",
        r"\bдет(?:и|ск(?:ий|ая|ое|ого|ой|им|ими|ом|их|ими)?)\b",
        r"\bподрост(?:ок|ка|ки|ков|ком|ке|кам|ками)\b",
        r"\bшкольниц",
        r"\bшкольник",
        r"\bмалолетн",
    )
)

# Adult phrases that must NOT trip teen/minor heuristics alone.
_ADULT_AGE_SAFE_RE = re.compile(
    r"\b(?:1[89]|[2-9]\d|\d{3,})\s*(?:year[s]?\s*old|yo|y\.?o\.?|лет|года|год)\b",
    re.I,
)

_AGE_FIELD_RE = re.compile(r"^\s*(\d{1,3})\s*(?:years?\s*old|yo|y\.?o\.?|лет|года|год)?\s*$", re.I)


def minor_content_http_exception() -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "code": MINOR_CONTENT_CODE,
            "message": MINOR_CONTENT_MESSAGE_RU,
        },
    )


def find_minor_content_violation(text: str) -> str | None:
    """Return a short reason if *text* requests or describes minors, else None."""
    raw = (text or "").strip()
    if not raw:
        return None
    if _ADULT_AGE_SAFE_RE.search(raw):
        return None
    for pat in _MINOR_TEXT_PATTERNS:
        if pat.search(raw):
            return f"blocked pattern: {pat.pattern}"
    return None


def _extract_profile_age(profile: dict[str, Any]) -> str | None:
    for key in ("age", "apparent_age", "estimated_age"):
        val = profile.get(key)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return str(int(val))
        if isinstance(val, str) and val.strip():
            return val.strip()
    subject = profile.get("subject")
    if isinstance(subject, dict):
        identity = subject.get("identity")
        if isinstance(identity, dict):
            for key in ("age", "apparent_age", "estimated_age"):
                val = identity.get(key)
                if val is None:
                    continue
                if isinstance(val, (int, float)):
                    return str(int(val))
                if isinstance(val, str) and val.strip():
                    return val.strip()
    return None


def validate_profile_age_value(age_raw: str | int | float | None) -> str | None:
    if age_raw is None:
        return None
    text = str(age_raw).strip()
    if not text:
        return None
    if find_minor_content_violation(text):
        return "profile age wording indicates a minor"
    m = _AGE_FIELD_RE.match(text)
    if m:
        years = int(m.group(1))
        if years < 18:
            return f"profile age {years} < 18"
        return None
    # Non-numeric estimates: teen/minor keywords already caught above.
    return None


def validate_model_profile_dict(profile_root: dict[str, Any]) -> str | None:
    mp = profile_root.get("model_profile")
    if not isinstance(mp, dict):
        mp = profile_root
    if not isinstance(mp, dict):
        return None
    reason = validate_profile_age_value(_extract_profile_age(mp))
    if reason:
        return reason
    for key in ("appearance", "bio", "personality", "description", "summary"):
        val = mp.get(key)
        if isinstance(val, str) and val.strip():
            hit = find_minor_content_violation(val)
            if hit:
                return f"profile {key}: {hit}"
    return None


def validate_model_profile_text(profile_text: str | None) -> str | None:
    raw = (profile_text or "").strip()
    if not raw:
        return None
    if find_minor_content_violation(raw):
        return "profile text mentions minors"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
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
    # negative_prompt часто содержит блок-лист («teen», «young girl») — не проверяем regex'ом.
    texts_for_regex = [
        description,
        prompt,
        refined_prompt,
        reference_analysis_json or "",
    ]
    reasons = collect_minor_content_violations(texts=texts_for_regex, profile_text=profile_text)
    if reasons:
        raise minor_content_http_exception()

    if not use_moderation:
        return

    combined = "\n".join(t.strip() for t in texts_for_regex if (t or "").strip())
    if profile_text and profile_text.strip():
        combined = f"{combined}\n{profile_text.strip()}"
    if combined and await _openai_moderation_flags_minors(combined):
        raise minor_content_http_exception()
