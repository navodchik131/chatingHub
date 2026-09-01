"""CRUD библиотеки референсов."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CreatorReference, CreatorReferenceLike, User
from app.services.creator_references.storage import (
    create_creator_reference_access_token,
    delete_creator_reference_file,
    resolve_creator_reference_file,
    save_creator_reference_file,
)
from app.services.workspace import workspace_owner_id


def reference_to_dict(row: CreatorReference, *, likes: int = 0, liked: bool = False, owner_id: int | None = None) -> dict[str, Any]:
    preview_url = f"/api/references/{row.id}/file"
    if owner_id is not None:
        tok = create_creator_reference_access_token(user_id=owner_id, reference_id=row.id)
        preview_url = f"{preview_url}?t={tok}"
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "media_type": row.media_type,
        "content_type": row.content_type,
        "likes_count": likes,
        "liked_by_me": liked,
        "preview_url": preview_url,
        "created_at": row.created_at,
    }


async def _like_counts(session: AsyncSession, ref_ids: list[int]) -> dict[int, int]:
    if not ref_ids:
        return {}
    rows = await session.execute(
        select(CreatorReferenceLike.reference_id, func.count())
        .where(CreatorReferenceLike.reference_id.in_(ref_ids))
        .group_by(CreatorReferenceLike.reference_id)
    )
    return {int(rid): int(cnt) for rid, cnt in rows.all()}


async def _liked_ids(session: AsyncSession, user_id: int, ref_ids: list[int]) -> set[int]:
    if not ref_ids:
        return set()
    rows = await session.scalars(
        select(CreatorReferenceLike.reference_id).where(
            CreatorReferenceLike.user_id == user_id,
            CreatorReferenceLike.reference_id.in_(ref_ids),
        )
    )
    return {int(x) for x in rows.all()}


async def list_creator_references(
    session: AsyncSession,
    *,
    viewer: User,
    media_type: str | None = None,
) -> list[dict[str, Any]]:
    owner_id = workspace_owner_id(viewer)
    q = select(CreatorReference).where(CreatorReference.user_id == owner_id)
    if media_type in ("photo", "video"):
        q = q.where(CreatorReference.media_type == media_type)
    q = q.order_by(CreatorReference.id.desc())
    rows = list((await session.scalars(q)).all())
    ids = [r.id for r in rows]
    likes = await _like_counts(session, ids)
    liked = await _liked_ids(session, viewer.id, ids)
    return [
        reference_to_dict(r, likes=likes.get(r.id, 0), liked=r.id in liked, owner_id=owner_id)
        for r in rows
    ]


async def create_creator_reference(
    session: AsyncSession,
    *,
    viewer: User,
    raw: bytes,
    content_type: str | None,
    filename: str | None,
    title: str | None,
    description: str | None,
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    rel, mime, media_type = save_creator_reference_file(
        owner_id=owner_id,
        raw=raw,
        content_type=content_type,
        filename=filename,
    )
    row = CreatorReference(
        user_id=owner_id,
        title=(title or "").strip()[:256] or None,
        description=(description or "").strip() or None,
        media_type=media_type,
        relative_path=rel,
        content_type=mime,
    )
    session.add(row)
    await session.flush()
    return reference_to_dict(row, likes=0, liked=False, owner_id=owner_id)


async def delete_creator_reference(
    session: AsyncSession,
    *,
    viewer: User,
    reference_id: int,
) -> None:
    owner_id = workspace_owner_id(viewer)
    row = await session.scalar(
        select(CreatorReference).where(
            CreatorReference.id == reference_id,
            CreatorReference.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="reference not found")
    delete_creator_reference_file(row.relative_path)
    await session.delete(row)


async def toggle_creator_reference_like(
    session: AsyncSession,
    *,
    viewer: User,
    reference_id: int,
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    row = await session.scalar(
        select(CreatorReference).where(
            CreatorReference.id == reference_id,
            CreatorReference.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="reference not found")
    existing = await session.scalar(
        select(CreatorReferenceLike).where(
            CreatorReferenceLike.user_id == viewer.id,
            CreatorReferenceLike.reference_id == reference_id,
        )
    )
    if existing:
        await session.delete(existing)
        liked = False
    else:
        session.add(CreatorReferenceLike(user_id=viewer.id, reference_id=reference_id))
        liked = True
    await session.flush()
    likes = int(
        await session.scalar(
            select(func.count())
            .select_from(CreatorReferenceLike)
            .where(CreatorReferenceLike.reference_id == reference_id)
        )
        or 0
    )
    return {"liked": liked, "likes_count": likes}
