"""Admin API модерации библиотеки референсов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.db.models import CreatorReference, User
from app.db.session import get_session
from app.schemas import AdminCreatorReferenceOut, AdminCreatorReferenceRejectIn
from app.services.creator_references.library import (
    MODERATION_APPROVED,
    MODERATION_PENDING,
    MODERATION_REJECTED,
    admin_list_references,
    admin_moderate_reference,
)
from app.services.creator_references.storage import resolve_creator_reference_file

router = APIRouter(prefix="/admin/references", tags=["admin"])


@router.get("", response_model=list[AdminCreatorReferenceOut])
async def admin_references_list(
    status: str | None = Query(default=MODERATION_PENDING),
    limit: int = Query(default=200, ge=1, le=500),
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AdminCreatorReferenceOut]:
    rows = await admin_list_references(session, status=status, limit=limit)
    return [AdminCreatorReferenceOut.model_validate(r) for r in rows]


@router.get("/{reference_id}/file")
async def admin_reference_file(
    reference_id: int,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    row = await session.scalar(
        select(CreatorReference).where(CreatorReference.id == reference_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="reference not found")
    path = resolve_creator_reference_file(row.user_id, row.relative_path)
    if not path:
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path, media_type=row.content_type)


@router.post("/{reference_id}/approve", response_model=AdminCreatorReferenceOut)
async def admin_reference_approve(
    reference_id: int,
    admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminCreatorReferenceOut:
    row = await admin_moderate_reference(
        session,
        admin=admin,
        reference_id=reference_id,
        status=MODERATION_APPROVED,
    )
    await session.commit()
    return AdminCreatorReferenceOut.model_validate(row)


@router.post("/{reference_id}/reject", response_model=AdminCreatorReferenceOut)
async def admin_reference_reject(
    reference_id: int,
    body: AdminCreatorReferenceRejectIn,
    admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminCreatorReferenceOut:
    row = await admin_moderate_reference(
        session,
        admin=admin,
        reference_id=reference_id,
        status=MODERATION_REJECTED,
        admin_notes=body.admin_notes,
    )
    await session.commit()
    return AdminCreatorReferenceOut.model_validate(row)
