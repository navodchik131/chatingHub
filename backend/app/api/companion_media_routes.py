"""API медиатеки companion bot."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import CompanionMediaAsset, User
from app.db.session import get_session
from app.schemas import (
    CompanionMediaAssetFromGenerationIn,
    CompanionMediaAssetOut,
    CompanionMediaAssetPatchIn,
    CompanionMediaPackIn,
    CompanionMediaPackOut,
    CompanionMediaPackPatchIn,
    CompanionMediaReindexOut,
    CompanionMediaSearchIn,
    CompanionMediaSearchOut,
)
from app.services.companion_media.library import (
    create_media_asset_from_generation,
    create_media_asset_from_upload,
    create_media_pack,
    delete_media_asset,
    delete_media_pack,
    list_media_assets,
    list_media_packs,
    reindex_media_embeddings,
    update_media_asset,
    update_media_pack,
)
from app.services.companion_media.search import pick_companion_media
from app.services.companion_media.storage import (
    decode_companion_media_access_token,
    resolve_companion_media_file,
)
from app.services.workspace import is_workspace_owner, workspace_owner_id

router = APIRouter(prefix="/companion-media", tags=["companion-media"])


def _assert_owner(user: User) -> None:
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="owner only")


@router.get("/packs", response_model=list[CompanionMediaPackOut])
async def companion_media_packs_list(
    studio_model_id: int = Query(ge=1),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CompanionMediaPackOut]:
    _assert_owner(user)
    rows = await list_media_packs(session, viewer=user, studio_model_id=studio_model_id)
    return [CompanionMediaPackOut.model_validate(r) for r in rows]


@router.post("/packs", response_model=CompanionMediaPackOut)
async def companion_media_packs_create(
    body: CompanionMediaPackIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompanionMediaPackOut:
    _assert_owner(user)
    row = await create_media_pack(session, viewer=user, data=body.model_dump())
    await session.commit()
    return CompanionMediaPackOut.model_validate(row)


@router.patch("/packs/{pack_id}", response_model=CompanionMediaPackOut)
async def companion_media_packs_patch(
    pack_id: int,
    body: CompanionMediaPackPatchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompanionMediaPackOut:
    _assert_owner(user)
    row = await update_media_pack(
        session,
        viewer=user,
        pack_id=pack_id,
        data=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    return CompanionMediaPackOut.model_validate(row)


@router.delete("/packs/{pack_id}", status_code=204)
async def companion_media_packs_delete(
    pack_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    _assert_owner(user)
    await delete_media_pack(session, viewer=user, pack_id=pack_id)
    await session.commit()


@router.get("/assets", response_model=list[CompanionMediaAssetOut])
async def companion_media_assets_list(
    studio_model_id: int = Query(ge=1),
    pack_id: int | None = Query(default=None, ge=1),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CompanionMediaAssetOut]:
    _assert_owner(user)
    rows = await list_media_assets(
        session,
        viewer=user,
        studio_model_id=studio_model_id,
        pack_id=pack_id,
    )
    return [CompanionMediaAssetOut.model_validate(r) for r in rows]


@router.post("/assets/upload", response_model=CompanionMediaAssetOut)
async def companion_media_assets_upload(
    studio_model_id: int = Form(ge=1),
    file: UploadFile = File(...),
    pack_id: int | None = Form(default=None),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    tier: str | None = Form(default="teaser"),
    price_usd_cents: int | None = Form(default=0),
    sort_order: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompanionMediaAssetOut:
    _assert_owner(user)
    raw = await file.read()
    tag_list: list[str] | None = None
    if tags and tags.strip():
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    row = await create_media_asset_from_upload(
        session,
        viewer=user,
        studio_model_id=studio_model_id,
        raw=raw,
        content_type=file.content_type,
        filename=file.filename,
        data={
            "pack_id": pack_id,
            "title": title,
            "description": description,
            "tags": tag_list,
            "tier": tier,
            "price_usd_cents": price_usd_cents,
            "sort_order": sort_order,
        },
    )
    await session.commit()
    return CompanionMediaAssetOut.model_validate(row)


@router.post("/assets/from-generation", response_model=CompanionMediaAssetOut)
async def companion_media_assets_from_generation(
    body: CompanionMediaAssetFromGenerationIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompanionMediaAssetOut:
    _assert_owner(user)
    row = await create_media_asset_from_generation(
        session,
        viewer=user,
        studio_model_id=body.studio_model_id,
        studio_generation_id=body.studio_generation_id,
        data=body.model_dump(exclude={"studio_model_id", "studio_generation_id"}),
    )
    await session.commit()
    return CompanionMediaAssetOut.model_validate(row)


@router.patch("/assets/{asset_id}", response_model=CompanionMediaAssetOut)
async def companion_media_assets_patch(
    asset_id: int,
    body: CompanionMediaAssetPatchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompanionMediaAssetOut:
    _assert_owner(user)
    row = await update_media_asset(
        session,
        viewer=user,
        asset_id=asset_id,
        data=body.model_dump(exclude_unset=True),
    )
    await session.commit()
    return CompanionMediaAssetOut.model_validate(row)


@router.delete("/assets/{asset_id}", status_code=204)
async def companion_media_assets_delete(
    asset_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    _assert_owner(user)
    await delete_media_asset(session, viewer=user, asset_id=asset_id)
    await session.commit()


@router.get("/assets/{asset_id}/file")
async def companion_media_asset_file(
    asset_id: int,
    t: str = Query(..., min_length=10),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Публичная раздача по JWT-токену (для <img src> без Bearer)."""
    try:
        owner_id, aid = decode_companion_media_access_token(t)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token") from None
    if aid != asset_id:
        raise HTTPException(status_code=404, detail="not found")

    row = await session.scalar(
        select(CompanionMediaAsset).where(
            CompanionMediaAsset.id == asset_id,
            CompanionMediaAsset.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    path = resolve_companion_media_file(owner_id, row.relative_path)
    if not path:
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path, media_type=row.content_type)


@router.post("/reindex", response_model=CompanionMediaReindexOut)
async def companion_media_reindex(
    studio_model_id: int = Query(ge=1),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompanionMediaReindexOut:
    _assert_owner(user)
    stats = await reindex_media_embeddings(
        session, viewer=user, studio_model_id=studio_model_id
    )
    await session.commit()
    return CompanionMediaReindexOut.model_validate(stats)


@router.post("/search", response_model=CompanionMediaSearchOut)
async def companion_media_search(
    body: CompanionMediaSearchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CompanionMediaSearchOut:
    _assert_owner(user)
    owner_id = workspace_owner_id(user)
    result = await pick_companion_media(
        session,
        owner_id=owner_id,
        studio_model_id=body.studio_model_id,
        query=body.query,
        conversation_id=body.conversation_id,
        expand_pack=body.expand_pack,
        tier=body.tier,
    )
    return CompanionMediaSearchOut.model_validate(result)
