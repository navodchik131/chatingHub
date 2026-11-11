"""Правила генерации агента: правила по умолчанию и неизменность базовых."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import AgentContentRule
from app.services.agent_rules import DEFAULT_RULES, ensure_defaults, list_rules


async def _run() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AgentContentRule.__table__.create)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        rows = await list_rules(s)
        assert [r.code for r in rows] == [d["code"] for d in DEFAULT_RULES]
        minors = next(r for r in rows if r.code == "minors")
        nud = next(r for r in rows if r.code == "nudity")
        # базовое правило испортили в базе напрямую — восстанавливается; обычное остаётся как админ задал
        minors.enabled = False
        minors.title = "x"
        nud.enabled = False
        await s.commit()
        await ensure_defaults(s)
        on = await list_rules(s, only_enabled=True)
        codes = {r.code for r in on}
        assert "minors" in codes and "nudity" not in codes
        assert next(r for r in on if r.code == "minors").title == DEFAULT_RULES[0]["title"]
        # удалили обычное правило — повторно не появляется
        await s.delete(nud)
        await s.commit()
        assert "nudity" not in {r.code for r in await list_rules(s)}
    await engine.dispose()


def test_agent_rules_defaults_and_locked() -> None:
    asyncio.run(_run())
