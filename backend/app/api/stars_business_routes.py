"""Stars Business: статус интеграции и отправка paid media из Unibox."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.deps import get_current_user
from app.config import settings
from app.connectors.telegram.stars_business.repo import (
    get_active_connection,
    link_connection_to_workspace_user,
    resolve_connection_for_workspace,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CompanionMediaAsset, Conversation, User
from app.db.session import get_session
from app.schemas import (
    CompanionMediaPackOut,
    MessageOut,
    PaidMediaAssetOptionOut,
    PaidMediaOptionsOut,
    SendPaidMediaIn,
    StarsBusinessLinkIn,
    StarsBusinessStatusOut,
)
from app.services.companion_media.library import list_media_packs
from app.services.companion_media.storage import create_companion_media_access_token
from app.services.chat_messages import message_to_out
from app.services.realtime import hub
from app.services.stars_business_unibox import send_unibox_paid_media, send_unibox_paid_upload
from app.services.workspace import PERM_CHAT, assert_permission, workspace_owner_id
from app.services.workspace_model_access import require_conversation_chat_access

router = APIRouter(tags=["stars-business"])


@router.get("/integrations/stars-business/status", response_model=StarsBusinessStatusOut)
async def stars_business_status(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StarsBusinessStatusOut:
    configured = settings.stars_business_configured
    oid = workspace_owner_id(user)
    conn = await resolve_connection_for_workspace(session, oid) if configured else None
    owner_user = await session.get(User, oid)
    tg_hint = int(owner_user.telegram_id) if owner_user and owner_user.telegram_id else None
    return StarsBusinessStatusOut(
        configured=configured,
        linked=conn is not None and conn.is_enabled,
        owner_tg_user_id=int(conn.owner_tg_user_id) if conn else tg_hint,
        is_enabled=bool(conn.is_enabled) if conn else False,
        user_telegram_id=tg_hint,
    )


@router.post("/integrations/stars-business/link", response_model=StarsBusinessStatusOut)
async def stars_business_link(
    body: StarsBusinessLinkIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StarsBusinessStatusOut:
    """Привязать Business OWNER к workspace (по telegram_id владельца или явному id)."""
    from app.services.workspace import is_workspace_owner

    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Только владелец workspace может привязать OWNER")
    if not settings.stars_business_configured:
        raise HTTPException(status_code=503, detail="Stars Business не настроен")

    oid = workspace_owner_id(user)
    owner_user = await session.get(User, oid)
    tg_id = body.owner_tg_user_id
    if tg_id is None and owner_user and owner_user.telegram_id:
        tg_id = int(owner_user.telegram_id)
    if tg_id is None:
        raise HTTPException(
            status_code=400,
            detail="Укажите owner_tg_user_id или привяжите telegram_id в профиле",
        )

    row = await link_connection_to_workspace_user(
        session,
        workspace_owner_user_id=oid,
        owner_tg_user_id=int(tg_id),
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Business-подключение не найдено — OWNER должен добавить бота в Telegram Business",
        )
    await session.commit()
    return await stars_business_status(user=user, session=session)


@router.get(
    "/conversations/{conv_id}/paid-media-packs",
    response_model=list[CompanionMediaPackOut],
)
async def conversation_paid_media_packs(
    conv_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CompanionMediaPackOut]:
    """Паки с price_stars > 0 для персонажа диалога (операторы чата)."""
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.user_id != oid:
        raise HTTPException(status_code=404, detail="conversation not found")
    await require_conversation_chat_access(session, user, conv_id, oid)
    if not conv.studio_model_id:
        return []
    rows = await list_media_packs(
        session,
        viewer=user,
        studio_model_id=int(conv.studio_model_id),
    )
    priced = [r for r in rows if int(r.get("price_stars") or 0) > 0 and r.get("status") == "active"]
    return [CompanionMediaPackOut.model_validate(r) for r in priced]


@router.get(
    "/conversations/{conv_id}/paid-media-options",
    response_model=PaidMediaOptionsOut,
)
async def conversation_paid_media_options(
    conv_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PaidMediaOptionsOut:
    """Паки и одиночные файлы с price_stars > 0 для Unibox."""
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.user_id != oid:
        raise HTTPException(status_code=404, detail="conversation not found")
    await require_conversation_chat_access(session, user, conv_id, oid)
    packs_out: list[CompanionMediaPackOut] = []
    assets_out: list[PaidMediaAssetOptionOut] = []
    if conv.studio_model_id:
        mid = int(conv.studio_model_id)
        pack_rows = await list_media_packs(session, viewer=user, studio_model_id=mid)
        packs_out = [
            CompanionMediaPackOut.model_validate(r)
            for r in pack_rows
            if int(r.get("price_stars") or 0) > 0 and r.get("status") == "active"
        ]
        asset_rows = (
            await session.scalars(
                select(CompanionMediaAsset).where(
                    CompanionMediaAsset.user_id == oid,
                    CompanionMediaAsset.studio_model_id == mid,
                    CompanionMediaAsset.status == "active",
                    CompanionMediaAsset.price_stars > 0,
                )
                .order_by(CompanionMediaAsset.id.desc())
            )
        ).all()
        for a in asset_rows:
            tok = create_companion_media_access_token(user_id=oid, asset_id=a.id)
            preview = f"/api/companion-media/assets/{a.id}/file?t={tok}"
            assets_out.append(
                PaidMediaAssetOptionOut(
                    id=int(a.id),
                    title=a.title,
                    media_type=a.media_type,
                    price_stars=int(a.price_stars or 0),
                    preview_url=preview,
                )
            )
    return PaidMediaOptionsOut(packs=packs_out, assets=assets_out)


@router.post("/conversations/{conv_id}/send-paid-media", response_model=MessageOut)
async def conversation_send_paid_media(
    conv_id: int,
    body: SendPaidMediaIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageOut:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.user_id != oid:
        raise HTTPException(status_code=404, detail="conversation not found")
    await require_conversation_chat_access(session, user, conv_id, oid)

    msg_id, _order_id = await send_unibox_paid_media(
        session,
        viewer=user,
        conv=conv,
        pack_id=int(body.pack_id) if body.pack_id is not None else None,
        asset_id=int(body.asset_id) if body.asset_id is not None else None,
        caption=body.caption,
    )
    await session.commit()
    from app.db.models import Message

    row = await session.get(Message, msg_id)
    if not row:
        raise HTTPException(status_code=500, detail="message not found after send")
    await session.refresh(row, attribute_names=["attachments"])
    out = message_to_out(row, owner_id=oid)
    await hub.broadcast_user(
        oid,
        {
            "type": "new_message",
            "conversation_id": conv.id,
            "message": out.model_dump(mode="json"),
        },
    )
    return out


@router.post("/conversations/{conv_id}/send-paid-media-upload", response_model=MessageOut)
async def conversation_send_paid_media_upload(
    conv_id: int,
    star_count: int = Form(..., ge=1, le=25_000),
    caption: str | None = Form(default=None),
    media: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MessageOut:
    """Фото/видео с устройства + цена ⭐; до 10 фото одним альбомом."""
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    conv = await session.get(Conversation, conv_id)
    if not conv or conv.user_id != oid:
        raise HTTPException(status_code=404, detail="conversation not found")
    await require_conversation_chat_access(session, user, conv_id, oid)

    if not media:
        raise HTTPException(status_code=400, detail="Нужен хотя бы один файл")
    uploads: list[tuple[bytes, str | None, str | None]] = []
    for part in media:
        raw = await part.read()
        uploads.append((raw, part.content_type, part.filename))
    msg_id, _order_id = await send_unibox_paid_upload(
        session,
        viewer=user,
        conv=conv,
        caption=caption,
        star_count=star_count,
        uploads=uploads,
    )
    await session.commit()
    from app.db.models import Message

    row = await session.get(Message, msg_id)
    if not row:
        raise HTTPException(status_code=500, detail="message not found after send")
    await session.refresh(row, attribute_names=["attachments"])
    out = message_to_out(row, owner_id=oid)
    await hub.broadcast_user(
        oid,
        {
            "type": "new_message",
            "conversation_id": conv.id,
            "message": out.model_dump(mode="json"),
        },
    )
    return out
