"""CRUD медиатеки companion bot и построение embedding-текста."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CompanionMediaAsset,
    CompanionMediaPack,
    CompanionMediaSendLog,
    Conversation,
    StudioGeneration,
    User,
    UserStudioModel,
)
from app.services.companion_bot.style_embeddings import embed_texts
from app.services.companion_media.storage import (
    copy_studio_file_to_companion_media,
    create_companion_media_access_token,
    delete_companion_media_file,
    save_companion_media_file,
)
from app.services.studio_keys import load_owner_studio_billing, studio_llm_credentials
from app.services.workspace import workspace_owner_id

log = logging.getLogger(__name__)

MEDIA_STATUSES = frozenset({"active", "disabled"})
MEDIA_TIERS = frozenset({"free", "teaser", "paid"})
MEDIA_TYPES = frozenset({"photo", "video"})
DEFAULT_PACK_SEND_COUNT = 4
MAX_PACK_SEND_COUNT = 10


def parse_tags_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(t).strip() for t in parsed if str(t).strip()]


def dump_tags_json(tags: list[str] | None) -> str | None:
    cleaned = [str(t).strip() for t in (tags or []) if str(t).strip()]
    if not cleaned:
        return None
    return json.dumps(cleaned, ensure_ascii=False)


def build_asset_embed_text(
    *,
    title: str | None,
    description: str | None,
    tags: list[str] | None,
    pack_name: str | None = None,
    pack_description: str | None = None,
    pack_tags: list[str] | None = None,
    media_type: str | None = None,
    price_usd_cents: int | None = None,
) -> str:
    """Текст для embedding: title + description + tags + контекст серии."""
    parts: list[str] = []
    if title and title.strip():
        parts.append(title.strip())
    if description and description.strip():
        parts.append(description.strip())
    tag_set = list(tags or [])
    if pack_tags:
        tag_set.extend(pack_tags)
    tag_set = sorted({t.strip().lower() for t in tag_set if t.strip()})
    if tag_set:
        parts.append("tags: " + ", ".join(tag_set))
    if pack_name and pack_name.strip():
        parts.append(f"series: {pack_name.strip()}")
    if pack_description and pack_description.strip():
        parts.append(pack_description.strip())
    if media_type:
        parts.append(f"type: {media_type}")
    if price_usd_cents and price_usd_cents > 0:
        parts.append(f"price usd: {price_usd_cents / 100:.2f}")
    return "\n".join(parts).strip()


async def _assert_studio_model(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int,
) -> UserStudioModel:
    row = await session.scalar(
        select(UserStudioModel).where(
            UserStudioModel.id == studio_model_id,
            UserStudioModel.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="studio model not found")
    return row


async def _get_pack_owned(
    session: AsyncSession,
    *,
    owner_id: int,
    pack_id: int,
) -> CompanionMediaPack:
    row = await session.scalar(
        select(CompanionMediaPack).where(
            CompanionMediaPack.id == pack_id,
            CompanionMediaPack.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="media pack not found")
    return row


async def _get_asset_owned(
    session: AsyncSession,
    *,
    owner_id: int,
    asset_id: int,
) -> CompanionMediaAsset:
    row = await session.scalar(
        select(CompanionMediaAsset).where(
            CompanionMediaAsset.id == asset_id,
            CompanionMediaAsset.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="media asset not found")
    return row


def pack_to_dict(row: CompanionMediaPack, *, asset_count: int = 0) -> dict[str, Any]:
    return {
        "id": row.id,
        "studio_model_id": row.studio_model_id,
        "name": row.name,
        "description": row.description,
        "tags": parse_tags_json(row.tags_json),
        "max_send_count": row.max_send_count,
        "status": row.status,
        "asset_count": asset_count,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def asset_to_dict(
    row: CompanionMediaAsset,
    *,
    pack_name: str | None = None,
    sent_count: int = 0,
    fan_count: int = 0,
    owner_id: int | None = None,
) -> dict[str, Any]:
    preview_url = f"/api/companion-media/assets/{row.id}/file"
    if owner_id is not None:
        tok = create_companion_media_access_token(user_id=owner_id, asset_id=row.id)
        preview_url = f"{preview_url}?t={tok}"
    return {
        "id": row.id,
        "studio_model_id": row.studio_model_id,
        "pack_id": row.pack_id,
        "pack_name": pack_name,
        "sort_order": row.sort_order,
        "media_type": row.media_type,
        "relative_path": row.relative_path,
        "content_type": row.content_type,
        "studio_generation_id": row.studio_generation_id,
        "title": row.title,
        "description": row.description,
        "tags": parse_tags_json(row.tags_json),
        "has_embedding": bool(row.embedding_json),
        "tier": row.tier,
        "price_usd_cents": int(row.price_usd_cents or 0),
        "status": row.status,
        "sent_count": sent_count,
        "fan_count": fan_count,
        "preview_url": preview_url,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def _load_asset_stats(
    session: AsyncSession,
    asset_ids: list[int],
) -> dict[int, dict[str, int]]:
    if not asset_ids:
        return {}
    rows = await session.execute(
        select(
            CompanionMediaSendLog.asset_id,
            func.count(),
            func.count(func.distinct(CompanionMediaSendLog.conversation_id)),
        )
        .where(CompanionMediaSendLog.asset_id.in_(asset_ids))
        .group_by(CompanionMediaSendLog.asset_id)
    )
    out: dict[int, dict[str, int]] = {}
    for asset_id, sent_count, fan_count in rows.all():
        out[int(asset_id)] = {
            "sent_count": int(sent_count or 0),
            "fan_count": int(fan_count or 0),
        }
    return out


async def list_media_packs(
    session: AsyncSession,
    *,
    viewer: User,
    studio_model_id: int,
) -> list[dict[str, Any]]:
    owner_id = workspace_owner_id(viewer)
    await _assert_studio_model(session, owner_id=owner_id, studio_model_id=studio_model_id)
    rows = list(
        (
            await session.scalars(
                select(CompanionMediaPack)
                .where(
                    CompanionMediaPack.user_id == owner_id,
                    CompanionMediaPack.studio_model_id == studio_model_id,
                )
                .order_by(CompanionMediaPack.id.desc())
            )
        ).all()
    )
    counts: dict[int, int] = {}
    if rows:
        pack_ids = [r.id for r in rows]
        count_rows = await session.execute(
            select(CompanionMediaAsset.pack_id, func.count())
            .where(
                CompanionMediaAsset.pack_id.in_(pack_ids),
                CompanionMediaAsset.user_id == owner_id,
            )
            .group_by(CompanionMediaAsset.pack_id)
        )
        counts = {int(pid): int(cnt) for pid, cnt in count_rows.all() if pid is not None}
    return [pack_to_dict(r, asset_count=counts.get(r.id, 0)) for r in rows]


async def create_media_pack(
    session: AsyncSession,
    *,
    viewer: User,
    data: dict[str, Any],
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    studio_model_id = int(data["studio_model_id"])
    await _assert_studio_model(session, owner_id=owner_id, studio_model_id=studio_model_id)

    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    max_send = int(data.get("max_send_count") or DEFAULT_PACK_SEND_COUNT)
    if max_send < 1 or max_send > MAX_PACK_SEND_COUNT:
        raise HTTPException(status_code=400, detail="invalid max_send_count")

    status = (data.get("status") or "active").strip().lower()
    if status not in MEDIA_STATUSES:
        raise HTTPException(status_code=400, detail="invalid status")

    row = CompanionMediaPack(
        user_id=owner_id,
        studio_model_id=studio_model_id,
        name=name[:128],
        description=(data.get("description") or "").strip() or None,
        tags_json=dump_tags_json(data.get("tags")),
        max_send_count=max_send,
        status=status,
    )
    session.add(row)
    await session.flush()
    return pack_to_dict(row, asset_count=0)


async def update_media_pack(
    session: AsyncSession,
    *,
    viewer: User,
    pack_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    row = await _get_pack_owned(session, owner_id=owner_id, pack_id=pack_id)

    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        row.name = name[:128]
    if "description" in data:
        row.description = (data.get("description") or "").strip() or None
    if "tags" in data:
        row.tags_json = dump_tags_json(data.get("tags"))
    if "max_send_count" in data and data["max_send_count"] is not None:
        max_send = int(data["max_send_count"])
        if max_send < 1 or max_send > MAX_PACK_SEND_COUNT:
            raise HTTPException(status_code=400, detail="invalid max_send_count")
        row.max_send_count = max_send
    if "status" in data and data["status"] is not None:
        status = str(data["status"]).strip().lower()
        if status not in MEDIA_STATUSES:
            raise HTTPException(status_code=400, detail="invalid status")
        row.status = status

    row.updated_at = datetime.now(timezone.utc)
    await session.flush()

    asset_count = int(
        await session.scalar(
            select(func.count())
            .select_from(CompanionMediaAsset)
            .where(
                CompanionMediaAsset.pack_id == row.id,
                CompanionMediaAsset.user_id == owner_id,
            )
        )
        or 0
    )
    return pack_to_dict(row, asset_count=asset_count)


async def delete_media_pack(
    session: AsyncSession,
    *,
    viewer: User,
    pack_id: int,
) -> None:
    owner_id = workspace_owner_id(viewer)
    row = await _get_pack_owned(session, owner_id=owner_id, pack_id=pack_id)
    # pack_id у ассетов станет NULL (ondelete SET NULL)
    await session.delete(row)


async def list_media_assets(
    session: AsyncSession,
    *,
    viewer: User,
    studio_model_id: int,
    pack_id: int | None = None,
) -> list[dict[str, Any]]:
    owner_id = workspace_owner_id(viewer)
    await _assert_studio_model(session, owner_id=owner_id, studio_model_id=studio_model_id)

    q = select(CompanionMediaAsset).where(
        CompanionMediaAsset.user_id == owner_id,
        CompanionMediaAsset.studio_model_id == studio_model_id,
    )
    if pack_id is not None:
        q = q.where(CompanionMediaAsset.pack_id == pack_id)
    q = q.order_by(
        CompanionMediaAsset.pack_id.asc().nullsfirst(),
        CompanionMediaAsset.sort_order.asc(),
        CompanionMediaAsset.id.asc(),
    )
    rows = list((await session.scalars(q)).all())

    pack_names: dict[int, str] = {}
    pack_ids = {r.pack_id for r in rows if r.pack_id}
    if pack_ids:
        packs = list(
            (
                await session.scalars(
                    select(CompanionMediaPack).where(CompanionMediaPack.id.in_(pack_ids))
                )
            ).all()
        )
        pack_names = {p.id: p.name for p in packs}

    stats = await _load_asset_stats(session, [r.id for r in rows])
    return [
        asset_to_dict(
            r,
            pack_name=pack_names.get(r.pack_id) if r.pack_id else None,
            sent_count=stats.get(r.id, {}).get("sent_count", 0),
            fan_count=stats.get(r.id, {}).get("fan_count", 0),
            owner_id=owner_id,
        )
        for r in rows
    ]


async def _embed_asset_row(
    session: AsyncSession,
    *,
    asset: CompanionMediaAsset,
    owner_id: int,
) -> None:
    pack: CompanionMediaPack | None = None
    if asset.pack_id:
        pack = await session.get(CompanionMediaPack, asset.pack_id)

    text = build_asset_embed_text(
        title=asset.title,
        description=asset.description,
        tags=parse_tags_json(asset.tags_json),
        pack_name=pack.name if pack else None,
        pack_description=pack.description if pack else None,
        pack_tags=parse_tags_json(pack.tags_json) if pack else None,
        media_type=asset.media_type,
        price_usd_cents=int(asset.price_usd_cents or 0),
    )
    if not text:
        asset.embedding_json = None
        return

    billing = await load_owner_studio_billing(session, owner_id)
    credentials = studio_llm_credentials(billing)
    vectors = await embed_texts([text], credentials=credentials)
    vec = vectors[0] if vectors else []
    asset.embedding_json = json.dumps(vec) if vec else None
    asset.updated_at = datetime.now(timezone.utc)


async def create_media_asset_from_upload(
    session: AsyncSession,
    *,
    viewer: User,
    studio_model_id: int,
    raw: bytes,
    content_type: str | None,
    filename: str | None,
    data: dict[str, Any],
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    await _assert_studio_model(session, owner_id=owner_id, studio_model_id=studio_model_id)

    rel, mime, media_type = save_companion_media_file(
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        raw=raw,
        content_type=content_type,
        filename=filename,
    )
    return await _create_asset_row(
        session,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        relative_path=rel,
        content_type=mime,
        media_type=media_type,
        data=data,
    )


async def create_media_asset_from_generation(
    session: AsyncSession,
    *,
    viewer: User,
    studio_model_id: int,
    studio_generation_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    await _assert_studio_model(session, owner_id=owner_id, studio_model_id=studio_model_id)

    gen = await session.scalar(
        select(StudioGeneration).where(
            StudioGeneration.id == studio_generation_id,
            StudioGeneration.user_id == owner_id,
        )
    )
    if not gen:
        raise HTTPException(status_code=404, detail="studio generation not found")
    rel_src = (gen.relative_path or "").strip()
    if not rel_src:
        raise HTTPException(status_code=400, detail="generation has no stored file")

    rel, mime, media_type = copy_studio_file_to_companion_media(
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        source_relative_path=rel_src,
        content_type=gen.content_type,
    )
    row_dict = await _create_asset_row(
        session,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        relative_path=rel,
        content_type=mime,
        media_type=media_type,
        data={
            **data,
            "studio_generation_id": studio_generation_id,
            "description": data.get("description")
            or (gen.prompt_excerpt or gen.refined_prompt or "").strip()[:2000]
            or None,
        },
    )
    return row_dict


async def _create_asset_row(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int,
    relative_path: str,
    content_type: str,
    media_type: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    pack_id = data.get("pack_id")
    pack: CompanionMediaPack | None = None
    if pack_id is not None:
        pack = await _get_pack_owned(session, owner_id=owner_id, pack_id=int(pack_id))
        if pack.studio_model_id != studio_model_id:
            raise HTTPException(status_code=400, detail="pack belongs to another model")

    tier = (data.get("tier") or "teaser").strip().lower()
    if tier not in MEDIA_TIERS:
        raise HTTPException(status_code=400, detail="invalid tier")
    price_usd_cents = int(data.get("price_usd_cents") or 0)
    if price_usd_cents < 0 or price_usd_cents > 500_000:
        raise HTTPException(status_code=400, detail="invalid price_usd_cents")
    status = (data.get("status") or "active").strip().lower()
    if status not in MEDIA_STATUSES:
        raise HTTPException(status_code=400, detail="invalid status")

    sort_order = int(data.get("sort_order") or 0)
    if pack_id is not None and sort_order == 0:
        max_sort = await session.scalar(
            select(func.max(CompanionMediaAsset.sort_order)).where(
                CompanionMediaAsset.pack_id == int(pack_id)
            )
        )
        sort_order = int(max_sort or 0) + 1

    row = CompanionMediaAsset(
        user_id=owner_id,
        studio_model_id=studio_model_id,
        pack_id=int(pack_id) if pack_id is not None else None,
        sort_order=sort_order,
        media_type=media_type if media_type in MEDIA_TYPES else "photo",
        relative_path=relative_path,
        content_type=content_type,
        studio_generation_id=data.get("studio_generation_id"),
        title=(data.get("title") or "").strip()[:256] or None,
        description=(data.get("description") or "").strip() or None,
        tags_json=dump_tags_json(data.get("tags")),
        tier=tier,
        price_usd_cents=price_usd_cents,
        status=status,
    )
    session.add(row)
    await session.flush()

    try:
        await _embed_asset_row(session, asset=row, owner_id=owner_id)
    except Exception as e:
        log.warning("companion media embed on create failed asset=%s: %s", row.id, e)

    pack_name = pack.name if pack else None
    stats = await _load_asset_stats(session, [row.id])
    st = stats.get(row.id, {})
    return asset_to_dict(
        row,
        pack_name=pack_name,
        sent_count=st.get("sent_count", 0),
        fan_count=st.get("fan_count", 0),
        owner_id=owner_id,
    )


async def update_media_asset(
    session: AsyncSession,
    *,
    viewer: User,
    asset_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    row = await _get_asset_owned(session, owner_id=owner_id, asset_id=asset_id)
    reembed = False

    if "title" in data:
        row.title = (data.get("title") or "").strip()[:256] or None
        reembed = True
    if "description" in data:
        row.description = (data.get("description") or "").strip() or None
        reembed = True
    if "tags" in data:
        row.tags_json = dump_tags_json(data.get("tags"))
        reembed = True
    if "tier" in data and data["tier"] is not None:
        tier = str(data["tier"]).strip().lower()
        if tier not in MEDIA_TIERS:
            raise HTTPException(status_code=400, detail="invalid tier")
        row.tier = tier
    if "price_usd_cents" in data and data["price_usd_cents"] is not None:
        price_usd_cents = int(data["price_usd_cents"])
        if price_usd_cents < 0 or price_usd_cents > 500_000:
            raise HTTPException(status_code=400, detail="invalid price_usd_cents")
        row.price_usd_cents = price_usd_cents
    if "status" in data and data["status"] is not None:
        status = str(data["status"]).strip().lower()
        if status not in MEDIA_STATUSES:
            raise HTTPException(status_code=400, detail="invalid status")
        row.status = status
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = int(data["sort_order"])
    if "pack_id" in data:
        pack_id = data.get("pack_id")
        if pack_id is None:
            row.pack_id = None
        else:
            pack = await _get_pack_owned(session, owner_id=owner_id, pack_id=int(pack_id))
            if pack.studio_model_id != row.studio_model_id:
                raise HTTPException(status_code=400, detail="pack belongs to another model")
            row.pack_id = pack.id
        reembed = True

    row.updated_at = datetime.now(timezone.utc)
    await session.flush()

    if reembed:
        try:
            await _embed_asset_row(session, asset=row, owner_id=owner_id)
        except Exception as e:
            log.warning("companion media embed on update failed asset=%s: %s", row.id, e)

    pack_name = None
    if row.pack_id:
        pack = await session.get(CompanionMediaPack, row.pack_id)
        pack_name = pack.name if pack else None
    stats = await _load_asset_stats(session, [row.id])
    st = stats.get(row.id, {})
    return asset_to_dict(
        row,
        pack_name=pack_name,
        sent_count=st.get("sent_count", 0),
        fan_count=st.get("fan_count", 0),
        owner_id=owner_id,
    )


async def get_media_asset_owned(
    session: AsyncSession,
    *,
    viewer: User,
    asset_id: int,
) -> CompanionMediaAsset:
    owner_id = workspace_owner_id(viewer)
    return await _get_asset_owned(session, owner_id=owner_id, asset_id=asset_id)


async def delete_media_asset(
    session: AsyncSession,
    *,
    viewer: User,
    asset_id: int,
) -> None:
    owner_id = workspace_owner_id(viewer)
    row = await _get_asset_owned(session, owner_id=owner_id, asset_id=asset_id)
    delete_companion_media_file(row.relative_path)
    await session.delete(row)


async def reindex_media_embeddings(
    session: AsyncSession,
    *,
    viewer: User,
    studio_model_id: int,
) -> dict[str, int]:
    owner_id = workspace_owner_id(viewer)
    await _assert_studio_model(session, owner_id=owner_id, studio_model_id=studio_model_id)
    rows = list(
        (
            await session.scalars(
                select(CompanionMediaAsset).where(
                    CompanionMediaAsset.user_id == owner_id,
                    CompanionMediaAsset.studio_model_id == studio_model_id,
                    CompanionMediaAsset.status == "active",
                )
            )
        ).all()
    )
    ok = 0
    failed = 0
    for row in rows:
        try:
            await _embed_asset_row(session, asset=row, owner_id=owner_id)
            ok += 1
        except Exception as e:
            failed += 1
            log.warning("companion media reindex failed asset=%s: %s", row.id, e)
    await session.flush()
    return {"indexed": ok, "failed": failed, "total": len(rows)}


async def get_sent_asset_ids(
    session: AsyncSession,
    *,
    conversation_id: int,
) -> set[int]:
    rows = await session.scalars(
        select(CompanionMediaSendLog.asset_id).where(
            CompanionMediaSendLog.conversation_id == conversation_id
        )
    )
    return {int(x) for x in rows.all()}


async def mark_media_sent(
    session: AsyncSession,
    *,
    owner_id: int,
    conversation_id: int,
    asset_ids: list[int],
    message_id: int | None = None,
) -> list[int]:
    """Записывает отправку; возвращает id реально новых записей."""
    conv = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == owner_id,
        )
    )
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")

    already = await get_sent_asset_ids(session, conversation_id=conversation_id)
    created: list[int] = []
    for aid in asset_ids:
        if aid in already:
            continue
        asset = await session.scalar(
            select(CompanionMediaAsset).where(
                CompanionMediaAsset.id == aid,
                CompanionMediaAsset.user_id == owner_id,
            )
        )
        if not asset:
            continue
        session.add(
            CompanionMediaSendLog(
                asset_id=aid,
                conversation_id=conversation_id,
                message_id=message_id,
            )
        )
        created.append(aid)
        already.add(aid)
    await session.flush()
    return created
