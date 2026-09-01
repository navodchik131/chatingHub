"""API библиотеки референсов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import CreatorReference, User
from app.db.session import get_session
from app.schemas import CreatorReferenceLikeOut, CreatorReferenceOut, CreatorReferencePatchIn
from app.services.creator_references.library import (
    create_creator_reference,
    delete_creator_reference,
    list_approved_references,
    list_my_references,
    resolve_reference_file_for_token,
    toggle_creator_reference_like,
    update_creator_reference_tags,
)
from app.services.creator_references.storage import decode_creator_reference_access_token
from app.services.workspace import is_workspace_owner

router = APIRouter(prefix="/references", tags=["references"])


def _assert_owner(user: User) -> None:
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="owner only")


@router.get("", response_model=list[CreatorReferenceOut])
async def references_list(
    media_type: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CreatorReferenceOut]:
    _assert_owner(user)
    rows = await list_approved_references(
        session,
        viewer=user,
        media_type=media_type,
        tag=tag,
    )
    return [CreatorReferenceOut.model_validate(r) for r in rows]


@router.get("/mine", response_model=list[CreatorReferenceOut])
async def references_mine(
    media_type: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CreatorReferenceOut]:
    _assert_owner(user)
    rows = await list_my_references(session, viewer=user, media_type=media_type)
    return [CreatorReferenceOut.model_validate(r) for r in rows]


@router.post("", response_model=CreatorReferenceOut)
async def references_create(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    upload_batch_id: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorReferenceOut:
    _assert_owner(user)
    raw = await file.read()
    tag_list: list[str] | None = None
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    row = await create_creator_reference(
        session,
        viewer=user,
        raw=raw,
        content_type=file.content_type,
        filename=file.filename,
        title=title,
        description=description,
        tags=tag_list,
        upload_batch_id=upload_batch_id,
    )
    await session.commit()
    return CreatorReferenceOut.model_validate(row)


@router.patch("/{reference_id}", response_model=CreatorReferenceOut)
async def references_patch(
    reference_id: int,
    body: CreatorReferencePatchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorReferenceOut:
    _assert_owner(user)
    if body.tags is None:
        raise HTTPException(status_code=400, detail="tags required")
    row = await update_creator_reference_tags(
        session,
        viewer=user,
        reference_id=reference_id,
        tags=body.tags,
    )
    await session.commit()
    return CreatorReferenceOut.model_validate(row)


@router.delete("/{reference_id}", status_code=204)
async def references_delete(
    reference_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    _assert_owner(user)
    await delete_creator_reference(session, viewer=user, reference_id=reference_id)
    await session.commit()


@router.get("/{reference_id}/file")
async def references_file(
    reference_id: int,
    t: str = Query(..., min_length=10),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    try:
        token_owner_id, rid = decode_creator_reference_access_token(t)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token") from None
    if rid != reference_id:
        raise HTTPException(status_code=404, detail="not found")

    row = await session.scalar(
        select(CreatorReference).where(CreatorReference.id == reference_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="reference not found")
    path = resolve_reference_file_for_token(row=row, token_owner_id=token_owner_id)
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
    await session.commit()
    return CreatorReferenceLikeOut.model_validate(result)
