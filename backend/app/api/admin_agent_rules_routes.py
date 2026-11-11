"""Admin API: правила генерации агента (что запрещено)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.db.models import AgentContentRule, User
from app.db.session import get_session
from app.services.agent_rules import DEFAULT_RULES, ensure_defaults, list_rules, rule_out

router = APIRouter(prefix="/admin/agent-rules", tags=["admin"])


class RuleIn(BaseModel):
    title: str = Field(min_length=3, max_length=2000)
    prompt_zh: str = Field(default="", max_length=2000)
    prompt_en: str = Field(default="", max_length=2000)
    enabled: bool = True
    sort: int = Field(default=100, ge=0, le=100000)


class RulePatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=2000)
    prompt_zh: str | None = Field(default=None, max_length=2000)
    prompt_en: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None
    sort: int | None = Field(default=None, ge=0, le=100000)


async def _get(session: AsyncSession, rule_id: int) -> AgentContentRule:
    await ensure_defaults(session)
    r = await session.scalar(select(AgentContentRule).where(AgentContentRule.id == rule_id))
    if r is None:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    return r


@router.get("")
async def rules_list(_admin: User = Depends(get_platform_admin), session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    return [rule_out(r) for r in await list_rules(session)]


@router.post("")
async def rules_create(body: RuleIn, _admin: User = Depends(get_platform_admin),
                       session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    r = AgentContentRule(title=body.title.strip(), prompt_zh=body.prompt_zh.strip(), prompt_en=body.prompt_en.strip(),
                         enabled=body.enabled, sort=body.sort, locked=False)
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return rule_out(r)


@router.patch("/{rule_id}")
async def rules_update(rule_id: int, body: RulePatch, _admin: User = Depends(get_platform_admin),
                       session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    r = await _get(session, rule_id)
    if r.locked:
        raise HTTPException(status_code=403, detail="Базовое правило нельзя менять или выключать")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(r, k, v.strip() if isinstance(v, str) else v)
    await session.commit()
    await session.refresh(r)
    return rule_out(r)


@router.delete("/{rule_id}")
async def rules_delete(rule_id: int, _admin: User = Depends(get_platform_admin),
                       session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    r = await _get(session, rule_id)
    if r.locked:
        raise HTTPException(status_code=403, detail="Базовое правило нельзя удалить")
    await session.delete(r)
    await session.commit()
    return {"ok": True}


@router.post("/reset/{code}")
async def rules_reset(code: str, _admin: User = Depends(get_platform_admin),
                      session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Вернуть стандартное правило по умолчанию (текст и включённость), если его меняли или удалили."""
    d = next((x for x in DEFAULT_RULES if x["code"] == code), None)
    if d is None:
        raise HTTPException(status_code=404, detail="Нет такого правила по умолчанию")
    r = await session.scalar(select(AgentContentRule).where(AgentContentRule.code == code))
    if r is None:
        r = AgentContentRule(**d, enabled=True)
        session.add(r)
    else:
        r.title, r.prompt_zh, r.prompt_en, r.enabled, r.sort = d["title"], d["prompt_zh"], d["prompt_en"], True, d["sort"]
    await session.commit()
    await session.refresh(r)
    return rule_out(r)
