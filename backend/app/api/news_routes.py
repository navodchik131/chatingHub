"""API новостей платформы."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas import PlatformNewsLikeOut, PlatformNewsOut
from app.services.platform_news.feed import (
    get_platform_news,
    list_platform_news,
    toggle_platform_news_like,
)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=list[PlatformNewsOut])
async def news_list(
    lang: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PlatformNewsOut]:
    rows = await list_platform_news(session, viewer=user, lang=lang)
    return [PlatformNewsOut.model_validate(r) for r in rows]


@router.get("/{news_id}", response_model=PlatformNewsOut)
async def news_detail(
    news_id: int,
    lang: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PlatformNewsOut:
    row = await get_platform_news(session, viewer=user, news_id=news_id, lang=lang)
    return PlatformNewsOut.model_validate(row)


@router.post("/{news_id}/like", response_model=PlatformNewsLikeOut)
async def news_like(
    news_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PlatformNewsLikeOut:
    result = await toggle_platform_news_like(session, viewer=user, news_id=news_id)
    return PlatformNewsLikeOut.model_validate(result)
