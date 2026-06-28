"""Структурированная персона модели для AI-компаньона."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class CompanionPersona(BaseModel):
    age: str | None = Field(default=None, max_length=32)
    city: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    personality: str | None = Field(default=None, max_length=2000)
    hobbies: str | None = Field(default=None, max_length=2000)
    interests: str | None = Field(default=None, max_length=2000)
    lifestyle: str | None = Field(default=None, max_length=2000)
    speaking_style: str | None = Field(default=None, max_length=1000)
    backstory: str | None = Field(default=None, max_length=4000)


def parse_companion_persona(raw: str | None) -> CompanionPersona:
    if not (raw or "").strip():
        return CompanionPersona()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return CompanionPersona()
    if not isinstance(data, dict):
        return CompanionPersona()
    return CompanionPersona.model_validate(data)


def companion_persona_to_json(persona: CompanionPersona | dict[str, Any] | None) -> str | None:
    if persona is None:
        return None
    if isinstance(persona, CompanionPersona):
        obj = persona.model_dump(exclude_none=True)
    else:
        obj = {k: v for k, v in persona.items() if v is not None and str(v).strip()}
    if not obj:
        return None
    return json.dumps(obj, ensure_ascii=False)


def format_companion_persona_block(
    *,
    name: str,
    profile_text: str,
    persona: CompanionPersona,
) -> str:
    lines: list[str] = [f"Name: {name}"]
    appearance = (profile_text or "").strip()
    if appearance:
        lines.append(f"Appearance / visual profile:\n{appearance}")

    if persona.age and persona.age.strip():
        lines.append(f"Age: {persona.age.strip()}")
    loc_parts = [p for p in (persona.city, persona.country) if p and p.strip()]
    if loc_parts:
        lines.append(f"Lives in: {', '.join(loc_parts)}")
    if persona.timezone and persona.timezone.strip():
        lines.append(f"Timezone: {persona.timezone.strip()}")
    if persona.personality and persona.personality.strip():
        lines.append(f"Personality: {persona.personality.strip()}")
    if persona.hobbies and persona.hobbies.strip():
        lines.append(f"Hobbies: {persona.hobbies.strip()}")
    if persona.interests and persona.interests.strip():
        lines.append(f"Interests: {persona.interests.strip()}")
    if persona.lifestyle and persona.lifestyle.strip():
        lines.append(f"Lifestyle / daily life: {persona.lifestyle.strip()}")
    if persona.speaking_style and persona.speaking_style.strip():
        lines.append(f"Texting style: {persona.speaking_style.strip()}")
    if persona.backstory and persona.backstory.strip():
        lines.append(f"Backstory: {persona.backstory.strip()}")
    return "\n".join(lines)
