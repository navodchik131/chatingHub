"""Лента новостей платформы."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlatformNewsLike, PlatformNewsPost, User


def _pick_lang(lang: str | None) -> str:
    return "ru" if str(lang or "").startswith("ru") else "en"


def news_to_dict(
    row: PlatformNewsPost,
    *,
    lang: str,
    likes: int = 0,
    liked: bool = False,
) -> dict[str, Any]:
    ru = lang == "ru"
    return {
        "id": row.id,
        "title": row.title_ru if ru else row.title_en,
        "summary": row.summary_ru if ru else row.summary_en,
        "body": row.body_ru if ru else row.body_en,
        "is_pinned": bool(row.is_pinned),
        "published_at": row.published_at,
        "likes_count": likes,
        "liked_by_me": liked,
    }


async def _like_counts(session: AsyncSession, news_ids: list[int]) -> dict[int, int]:
    if not news_ids:
        return {}
    rows = await session.execute(
        select(PlatformNewsLike.news_id, func.count())
        .where(PlatformNewsLike.news_id.in_(news_ids))
        .group_by(PlatformNewsLike.news_id)
    )
    return {int(nid): int(cnt) for nid, cnt in rows.all()}


async def _liked_ids(session: AsyncSession, user_id: int, news_ids: list[int]) -> set[int]:
    if not news_ids:
        return set()
    rows = await session.scalars(
        select(PlatformNewsLike.news_id).where(
            PlatformNewsLike.user_id == user_id,
            PlatformNewsLike.news_id.in_(news_ids),
        )
    )
    return {int(x) for x in rows.all()}


async def list_platform_news(
    session: AsyncSession,
    *,
    viewer: User,
    lang: str | None = None,
) -> list[dict[str, Any]]:
    lg = _pick_lang(lang)
    rows = list(
        (
            await session.scalars(
                select(PlatformNewsPost).order_by(
                    PlatformNewsPost.is_pinned.desc(),
                    PlatformNewsPost.published_at.desc(),
                )
            )
        ).all()
    )
    ids = [r.id for r in rows]
    likes = await _like_counts(session, ids)
    liked = await _liked_ids(session, viewer.id, ids)
    return [
        news_to_dict(r, lang=lg, likes=likes.get(r.id, 0), liked=r.id in liked)
        for r in rows
    ]


async def get_platform_news(
    session: AsyncSession,
    *,
    viewer: User,
    news_id: int,
    lang: str | None = None,
) -> dict[str, Any]:
    lg = _pick_lang(lang)
    row = await session.get(PlatformNewsPost, news_id)
    if not row:
        raise HTTPException(status_code=404, detail="news not found")
    likes = int(
        await session.scalar(
            select(func.count())
            .select_from(PlatformNewsLike)
            .where(PlatformNewsLike.news_id == news_id)
        )
        or 0
    )
    liked = bool(
        await session.scalar(
            select(PlatformNewsLike.id).where(
                PlatformNewsLike.user_id == viewer.id,
                PlatformNewsLike.news_id == news_id,
            )
        )
    )
    return news_to_dict(row, lang=lg, likes=likes, liked=liked)


async def toggle_platform_news_like(
    session: AsyncSession,
    *,
    viewer: User,
    news_id: int,
) -> dict[str, int | bool]:
    row = await session.get(PlatformNewsPost, news_id)
    if not row:
        raise HTTPException(status_code=404, detail="news not found")
    existing = await session.scalar(
        select(PlatformNewsLike).where(
            PlatformNewsLike.user_id == viewer.id,
            PlatformNewsLike.news_id == news_id,
        )
    )
    if existing:
        await session.delete(existing)
        liked = False
    else:
        session.add(PlatformNewsLike(user_id=viewer.id, news_id=news_id))
        liked = True
    await session.flush()
    likes = int(
        await session.scalar(
            select(func.count())
            .select_from(PlatformNewsLike)
            .where(PlatformNewsLike.news_id == news_id)
        )
        or 0
    )
    return {"liked": liked, "likes_count": likes}
