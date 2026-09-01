"""API библиотеки референсов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas import CreatorReferenceLikeOut, CreatorReferenceOut
from app.services.creator_references.library import (
    create_creator_reference,
    delete_creator_reference,
    list_creator_references,
    toggle_creator_reference_like,
)
from app.services.creator_references.storage import resolve_creator_reference_file
from app.services.workspace import is_workspace_owner, workspace_owner_id

router = APIRouter(prefix="/references", tags=["references"])


def _assert_owner(user: User) -> None:
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="owner only")


@router.get("", response_model=list[CreatorReferenceOut])
async def references_list(
    media_type: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CreatorReferenceOut]:
    _assert_owner(user)
    rows = await list_creator_references(session, viewer=user, media_type=media_type)
    return [CreatorReferenceOut.model_validate(r) for r in rows]


@router.post("", response_model=CreatorReferenceOut)
async def references_create(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorReferenceOut:
    _assert_owner(user)
    raw = await file.read()
    row = await create_creator_reference(
        session,
        viewer=user,
        raw=raw,
        content_type=file.content_type,
        filename=file.filename,
        title=title,
        description=description,
    )
    return CreatorReferenceOut.model_validate(row)


@router.delete("/{reference_id}", status_code=204)
async def references_delete(
    reference_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    _assert_owner(user)
    await delete_creator_reference(session, viewer=user, reference_id=reference_id)


@router.get("/{reference_id}/file")
async def references_file(
    reference_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    _assert_owner(user)
    from sqlalchemy import select

    from app.db.models import CreatorReference

    owner_id = workspace_owner_id(user)
    row = await session.scalar(
        select(CreatorReference).where(
            CreatorReference.id == reference_id,
            CreatorReference.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="reference not found")
    path = resolve_creator_reference_file(owner_id, row.relative_path)
    if not path:
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path, media_type=row.content_type)


@router.post("/{reference_id}/like", response_model=CreatorReferenceLikeOut)
async def references_like(
    reference_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorReferenceLikeOut:
    _assert_owner(user)
    result = await toggle_creator_reference_like(
        session, viewer=user, reference_id=reference_id
    )
    return CreatorReferenceLikeOut.model_validate(result)
