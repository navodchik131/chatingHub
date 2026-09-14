"""Отправка paid media из Unibox (медиатека + Stars Business OWNER)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.telegram.stars_business.bot import create_stars_business_bot
from app.connectors.telegram.stars_business.media_storage import encode_media_paths
from app.connectors.telegram.stars_business.repo import (
    create_order,
    get_connection_for_workspace_user,
    mark_order_failed,
    mark_order_sent,
)
from app.connectors.telegram.stars_business.send import send_paid_media_order
from app.db.models import (
    CompanionMediaAsset,
    CompanionMediaPack,
    Conversation,
    MessageDirection,
    Platform,
    User,
)
from app.db.repo import add_message
from app.services.chat_message_meta import merge_meta_dict
from app.services.companion_media.library import mark_media_sent
from app.services.companion_media.storage import resolve_companion_media_file
from app.services.workspace import workspace_owner_id

log = logging.getLogger(__name__)

# operator_tg_user_id=0 — заказ из кабинета, не из Telegram-бота оператора
UNIBOX_OPERATOR_TG_ID = 0


@dataclass
class ResolvedPaidMedia:
    relative_paths: list[str]
    media_type: str
    asset_ids: list[int]
    star_count: int
    label_name: str
    pack_id: int | None
    asset_id: int | None


def _resolve_pack_media(
    *,
    owner_id: int,
    pack: CompanionMediaPack,
    assets: list[CompanionMediaAsset],
) -> ResolvedPaidMedia:
    if not assets:
        raise HTTPException(status_code=400, detail="В паке нет активных файлов")
    limit = min(int(pack.max_send_count or 4), 10, len(assets))
    picked = assets[:limit]
    paths: list[str] = []
    ids: list[int] = []
    types = {a.media_type for a in picked}
    if "video" in types and len(picked) > 1:
        raise HTTPException(
            status_code=400,
            detail="В paid media только одно видео за раз",
        )
    for asset in picked:
        path = resolve_companion_media_file(owner_id, asset.relative_path)
        if not path or not path.is_file():
            raise HTTPException(
                status_code=502,
                detail=f"Файл медиатеки не найден (asset #{asset.id})",
            )
        paths.append(asset.relative_path.strip().replace("\\", "/"))
        ids.append(int(asset.id))
    media_type = "video" if picked[0].media_type == "video" else "photo"
    stars = int(pack.price_stars or 0)
    return ResolvedPaidMedia(
        relative_paths=paths,
        media_type=media_type,
        asset_ids=ids,
        star_count=stars,
        label_name=pack.name,
        pack_id=int(pack.id),
        asset_id=None,
    )


def _resolve_single_asset_media(
    *,
    owner_id: int,
    asset: CompanionMediaAsset,
) -> ResolvedPaidMedia:
    path = resolve_companion_media_file(owner_id, asset.relative_path)
    if not path or not path.is_file():
        raise HTTPException(
            status_code=502,
            detail=f"Файл медиатеки не найден (asset #{asset.id})",
        )
    media_type = "video" if asset.media_type == "video" else "photo"
    stars = int(asset.price_stars or 0)
    title = (asset.title or "").strip() or f"#{asset.id}"
    return ResolvedPaidMedia(
        relative_paths=[asset.relative_path.strip().replace("\\", "/")],
        media_type=media_type,
        asset_ids=[int(asset.id)],
        star_count=stars,
        label_name=title,
        pack_id=None,
        asset_id=int(asset.id),
    )


async def _assert_conv_and_conn(
    session: AsyncSession,
    *,
    viewer: User,
    conv: Conversation,
) -> tuple[int, object]:
    if not settings.stars_business_configured:
        raise HTTPException(status_code=503, detail="Stars Business не настроен на сервере")
    if conv.platform != Platform.telegram_user:
        raise HTTPException(
            status_code=400,
            detail="Paid media доступен только для диалогов личного Telegram",
        )
    oid = workspace_owner_id(viewer)
    if conv.user_id != oid:
        raise HTTPException(status_code=404, detail="conversation not found")
    conn = await get_connection_for_workspace_user(session, oid)
    if not conn or not conn.is_enabled:
        raise HTTPException(
            status_code=503,
            detail="Подключите Stars Business: OWNER должен добавить бота в Telegram Business",
        )
    return oid, conn


async def send_unibox_paid_media(
    session: AsyncSession,
    *,
    viewer: User,
    conv: Conversation,
    caption: str | None,
    pack_id: int | None = None,
    asset_id: int | None = None,
) -> tuple[int, int]:
    """Пак или один файл — одна цена ⭐ на выбранный объект."""
    oid, conn = await _assert_conv_and_conn(session, viewer=viewer, conv=conv)

    if pack_id is not None:
        pack = await session.scalar(
            select(CompanionMediaPack).where(
                CompanionMediaPack.id == pack_id,
                CompanionMediaPack.user_id == oid,
                CompanionMediaPack.status == "active",
            )
        )
        if not pack:
            raise HTTPException(status_code=404, detail="pack not found")
        if conv.studio_model_id and int(conv.studio_model_id) != int(pack.studio_model_id):
            raise HTTPException(status_code=400, detail="Пак относится к другому персонажу")
        assets = list(
            (
                await session.scalars(
                    select(CompanionMediaAsset)
                    .where(
                        CompanionMediaAsset.pack_id == pack.id,
                        CompanionMediaAsset.user_id == oid,
                        CompanionMediaAsset.status == "active",
                    )
                    .order_by(CompanionMediaAsset.sort_order, CompanionMediaAsset.id)
                )
            ).all()
        )
        media = _resolve_pack_media(owner_id=oid, pack=pack, assets=assets)
    else:
        aid = int(asset_id or 0)
        asset = await session.scalar(
            select(CompanionMediaAsset).where(
                CompanionMediaAsset.id == aid,
                CompanionMediaAsset.user_id == oid,
                CompanionMediaAsset.status == "active",
            )
        )
        if not asset:
            raise HTTPException(status_code=404, detail="asset not found")
        if conv.studio_model_id and int(conv.studio_model_id) != int(asset.studio_model_id):
            raise HTTPException(status_code=400, detail="Файл относится к другому персонажу")
        media = _resolve_single_asset_media(owner_id=oid, asset=asset)

    if media.star_count < 1:
        raise HTTPException(
            status_code=400,
            detail="Укажите цену ⭐ для пака или файла в медиатеке",
        )

    try:
        fan_chat_id = int(conv.external_chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="bad telegram peer id") from exc

    encoded = encode_media_paths(media.relative_paths)
    order = await create_order(
        session,
        owner_tg_user_id=int(conn.owner_tg_user_id),
        operator_tg_user_id=UNIBOX_OPERATOR_TG_ID,
        fan_chat_id=fan_chat_id,
        star_count=media.star_count,
        caption=(caption or "").strip() or None,
        media_relative_path=encoded,
        media_type=media.media_type,
        conversation_id=conv.id,
        pack_id=media.pack_id,
        asset_id=media.asset_id,
        created_by_user_id=viewer.id,
    )
    await session.flush()

    bot = create_stars_business_bot()
    result = await send_paid_media_order(bot, conn=conn, order=order)
    if not result.ok or result.message_id is None:
        await mark_order_failed(session, order, error_code=result.error_code or "SEND_FAILED")
        await session.flush()
        raise HTTPException(
            status_code=502,
            detail=result.error_text or result.error_code or "Не удалось отправить paid media",
        )

    label = f"⭐ Платный контент · {media.label_name} · {media.star_count} ⭐"
    if caption and caption.strip():
        label = f"{caption.strip()}\n\n{label}"

    meta_payload: dict = {
        "order_id": order.id,
        "star_count": media.star_count,
        "status": "sent",
        "telegram_message_id": result.message_id,
    }
    if media.pack_id is not None:
        meta_payload["pack_id"] = media.pack_id
    if media.asset_id is not None:
        meta_payload["asset_id"] = media.asset_id

    meta = merge_meta_dict(None, {"stars_paid_media": meta_payload})
    row = await add_message(
        session,
        conv.id,
        MessageDirection.outbound,
        label,
        None,
        meta=meta,
        platform_message_id=str(result.message_id),
        sender_user_id=viewer.id,
    )
    await mark_order_sent(
        session,
        order,
        platform_message_id=result.message_id,
        unibox_message_id=row.id,
    )
    await mark_media_sent(
        session,
        owner_id=oid,
        conversation_id=conv.id,
        asset_ids=media.asset_ids,
        message_id=row.id,
    )
    await session.flush()
    log.info(
        "unibox paid media sent conv=%s pack=%s asset=%s order=%s tg_msg=%s",
        conv.id,
        media.pack_id,
        media.asset_id,
        order.id,
        result.message_id,
    )
    return row.id, order.id


# Совместимость со старым именем
async def send_unibox_paid_pack(
    session: AsyncSession,
    *,
    viewer: User,
    conv: Conversation,
    pack_id: int,
    caption: str | None,
) -> tuple[int, int]:
    return await send_unibox_paid_media(
        session,
        viewer=viewer,
        conv=conv,
        caption=caption,
        pack_id=pack_id,
    )
