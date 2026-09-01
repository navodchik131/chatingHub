"""CRUD библиотеки референсов (общая лента + модерация)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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

MODERATION_PENDING = "pending"
MODERATION_APPROVED = "approved"
MODERATION_REJECTED = "rejected"


def _normalize_tags(tags: list[str] | None) -> list[str]:
    """Уникальные теги в нижнем регистре, без пустых."""
    if not tags:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = str(raw or "").strip().lower()[:48]
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out[:24]


def _tags_from_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return _normalize_tags([str(x) for x in parsed])


def _tags_to_json(tags: list[str] | None) -> str | None:
    normalized = _normalize_tags(tags)
    return json.dumps(normalized, ensure_ascii=False) if normalized else None


def _row_has_tag(row: CreatorReference, tag: str | None) -> bool:
    if not tag:
        return True
    return tag.strip().lower() in _tags_from_json(row.tags_json)


def reference_to_dict(
    row: CreatorReference,
    *,
    likes: int = 0,
    liked: bool = False,
    viewer_owner_id: int | None = None,
) -> dict[str, Any]:
    preview_url = f"/api/references/{row.id}/file"
    if viewer_owner_id is not None:
        tok = create_creator_reference_access_token(
            user_id=viewer_owner_id,
            reference_id=row.id,
        )
        preview_url = f"{preview_url}?t={tok}"
    return {
        "id": row.id,
        "user_id": row.user_id,
        "title": row.title,
        "description": row.description,
        "tags": _tags_from_json(row.tags_json),
        "upload_batch_id": row.upload_batch_id,
        "media_type": row.media_type,
        "content_type": row.content_type,
        "likes_count": likes,
        "liked_by_me": liked,
        "preview_url": preview_url,
        "moderation_status": row.moderation_status or MODERATION_PENDING,
        "is_mine": viewer_owner_id is not None and row.user_id == viewer_owner_id,
        "admin_notes": row.admin_notes,
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


def _serialize_rows(
    rows: list[CreatorReference],
    *,
    viewer: User,
    likes: dict[int, int],
    liked: set[int],
) -> list[dict[str, Any]]:
    owner_id = workspace_owner_id(viewer)
    return [
        reference_to_dict(
            r,
            likes=likes.get(r.id, 0),
            liked=r.id in liked,
            viewer_owner_id=owner_id,
        )
        for r in rows
    ]


async def list_approved_references(
    session: AsyncSession,
    *,
    viewer: User,
    media_type: str | None = None,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    """Общая библиотека — только одобренные материалы всех пользователей."""
    q = select(CreatorReference).where(
        CreatorReference.moderation_status == MODERATION_APPROVED
    )
    if media_type in ("photo", "video"):
        q = q.where(CreatorReference.media_type == media_type)
    q = q.order_by(CreatorReference.id.desc())
    rows = list((await session.scalars(q)).all())
    norm_tag = tag.strip().lower() if tag else None
    if norm_tag:
        rows = [r for r in rows if _row_has_tag(r, norm_tag)]
    ids = [r.id for r in rows]
    likes = await _like_counts(session, ids)
    liked = await _liked_ids(session, viewer.id, ids)
    return _serialize_rows(rows, viewer=viewer, likes=likes, liked=liked)


async def list_my_references(
    session: AsyncSession,
    *,
    viewer: User,
    media_type: str | None = None,
) -> list[dict[str, Any]]:
    """Загрузки текущего workspace — любой статус модерации."""
    owner_id = workspace_owner_id(viewer)
    q = select(CreatorReference).where(CreatorReference.user_id == owner_id)
    if media_type in ("photo", "video"):
        q = q.where(CreatorReference.media_type == media_type)
    q = q.order_by(CreatorReference.id.desc())
    rows = list((await session.scalars(q)).all())
    ids = [r.id for r in rows]
    likes = await _like_counts(session, ids)
    liked = await _liked_ids(session, viewer.id, ids)
    return _serialize_rows(rows, viewer=viewer, likes=likes, liked=liked)


async def create_creator_reference(
    session: AsyncSession,
    *,
    viewer: User,
    raw: bytes,
    content_type: str | None,
    filename: str | None,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    upload_batch_id: str | None = None,
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    rel, mime, media_type = save_creator_reference_file(
        owner_id=owner_id,
        raw=raw,
        content_type=content_type,
        filename=filename,
    )
    batch = (upload_batch_id or "").strip()[:32] or None
    row = CreatorReference(
        user_id=owner_id,
        title=(title or "").strip()[:256] or None,
        description=(description or "").strip() or None,
        tags_json=_tags_to_json(tags),
        upload_batch_id=batch,
        media_type=media_type,
        relative_path=rel,
        content_type=mime,
        moderation_status=MODERATION_PENDING,
    )
    session.add(row)
    await session.flush()
    return reference_to_dict(row, likes=0, liked=False, viewer_owner_id=owner_id)


async def update_creator_reference_tags(
    session: AsyncSession,
    *,
    viewer: User,
    reference_id: int,
    tags: list[str],
    apply_to_batch: bool = True,
) -> dict[str, Any]:
    """Теги можно менять только у своих материалов до одобрения."""
    owner_id = workspace_owner_id(viewer)
    row = await session.scalar(
        select(CreatorReference).where(
            CreatorReference.id == reference_id,
            CreatorReference.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="reference not found")
    if row.moderation_status == MODERATION_APPROVED:
        raise HTTPException(status_code=400, detail="approved references cannot be edited")

    payload = _tags_to_json(tags)
    targets = [row]
    if apply_to_batch and row.upload_batch_id:
        targets = list(
            (
                await session.scalars(
                    select(CreatorReference).where(
                        CreatorReference.user_id == owner_id,
                        CreatorReference.upload_batch_id == row.upload_batch_id,
                    )
                )
            ).all()
        )
    for target in targets:
        if target.moderation_status != MODERATION_APPROVED:
            target.tags_json = payload
    await session.flush()

    ids = [r.id for r in targets]
    likes = await _like_counts(session, ids)
    liked = await _liked_ids(session, viewer.id, ids)
    return reference_to_dict(
        row,
        likes=likes.get(row.id, 0),
        liked=row.id in liked,
        viewer_owner_id=owner_id,
    )


async def delete_creator_reference(
    session: AsyncSession,
    *,
    viewer: User,
    reference_id: int,
) -> None:
    """Удалить можно только свои неодобренные материалы."""
    owner_id = workspace_owner_id(viewer)
    row = await session.scalar(
        select(CreatorReference).where(
            CreatorReference.id == reference_id,
            CreatorReference.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="reference not found")
    if row.moderation_status == MODERATION_APPROVED:
        raise HTTPException(status_code=400, detail="approved references cannot be deleted")
    delete_creator_reference_file(row.relative_path)
    await session.delete(row)


async def toggle_creator_reference_like(
    session: AsyncSession,
    *,
    viewer: User,
    reference_id: int,
) -> dict[str, Any]:
    row = await session.scalar(
        select(CreatorReference).where(CreatorReference.id == reference_id)
    )
    if not row or row.moderation_status != MODERATION_APPROVED:
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


async def admin_list_references(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    q = select(CreatorReference)
    if status in (MODERATION_PENDING, MODERATION_APPROVED, MODERATION_REJECTED):
        q = q.where(CreatorReference.moderation_status == status)
    q = q.order_by(CreatorReference.id.desc()).limit(limit)
    rows = list((await session.scalars(q)).all())
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "title": r.title,
            "tags": _tags_from_json(r.tags_json),
            "upload_batch_id": r.upload_batch_id,
            "media_type": r.media_type,
            "moderation_status": r.moderation_status,
            "admin_notes": r.admin_notes,
            "preview_url": f"/api/admin/references/{r.id}/file",
            "created_at": r.created_at,
        }
        for r in rows
    ]


async def admin_moderate_reference(
    session: AsyncSession,
    *,
    admin: User,
    reference_id: int,
    status: str,
    admin_notes: str | None = None,
) -> dict[str, Any]:
    if status not in (MODERATION_APPROVED, MODERATION_REJECTED):
        raise HTTPException(status_code=400, detail="invalid status")
    row = await session.scalar(
        select(CreatorReference).where(CreatorReference.id == reference_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="reference not found")
    row.moderation_status = status
    row.moderated_at = datetime.now(timezone.utc)
    row.moderated_by_id = admin.id
    if admin_notes is not None:
        row.admin_notes = (admin_notes or "").strip() or None
    await session.flush()
    return {
        "id": row.id,
        "user_id": row.user_id,
        "title": row.title,
        "tags": _tags_from_json(row.tags_json),
        "upload_batch_id": row.upload_batch_id,
        "media_type": row.media_type,
        "moderation_status": row.moderation_status,
        "admin_notes": row.admin_notes,
        "preview_url": f"/api/admin/references/{row.id}/file",
        "created_at": row.created_at,
    }


def resolve_reference_file_for_token(
    *,
    row: CreatorReference,
    token_owner_id: int,
):
    """Файл доступен владельцу или если материал одобрен в общей библиотеке."""
    if row.moderation_status != MODERATION_APPROVED and row.user_id != token_owner_id:
        return None
    return resolve_creator_reference_file(row.user_id, row.relative_path)
