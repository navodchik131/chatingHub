from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone
from io import BytesIO
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.jwt_utils import decode_token
from app.config import BACKEND_DIR, settings
from app.connectors.telegram.bot_for_user import open_telegram_bot_for_owner
from app.connectors.telegram.state import get_telegram_api_status
from app.db.models import (
    BotResponseEvent,
    BotResponseEventStatus,
    FanvueConnection,
    Message,
    MessageAttachment,
    MessageDirection,
    Platform,
    TelegramConnection,
    User,
)
from app.db.repo import (
    add_message,
    count_rows,
    get_conversation,
    get_last_message,
    list_conversations,
    list_messages,
    mark_conversation_read,
    unread_inbound_count,
)
from app.db.session import SessionLocal, get_session
from app.schemas import (
    CompanionDraftApproveIn,
    CompanionDraftOut,
    CompanionRatingIn,
    ConversationNoteCreateIn,
    ConversationNoteOut,
    ConversationNotePatchIn,
    ConversationOut,
    ConversationPatchIn,
    ConversationWithPreview,
    MessageOut,
    MessageReactionIn,
    ReplyIn,
)
from app.services.chat_attachment import (
    decode_chat_attachment_access_token,
    decode_chat_media_public_token,
    resolve_chat_attachment_file,
    save_chat_image_bytes,
)
from app.services.chat_messages import (
    add_message_attachment,
    load_messages_for_api,
    message_preview_text,
    message_to_out,
)
from app.services.chat_outbound import (
    resolve_outbound_image,
    send_fanvue_outbound,
    send_instagram_outbound,
    send_telegram_outbound,
    set_telegram_message_reaction,
)
from app.services.chat_ingest import broadcast_message_updated
from app.services.chat_message_meta import (
    REACTION_EMOJIS,
    parse_reactions,
    platform_message_id_from_meta,
    reactions_to_json,
    resolve_reply_target,
    toggle_owner_reaction,
)
from app.services.crypto_secret import decrypt_secret
from app.services.realtime import hub
from app.services.translation import translate_from_russian
from app.services.studio_grok_motion import grok_motion_api_configured
from app.services.studio_grok_scene_compose import grok_scene_compose_configured
from app.services.plan_catalog import catalog_public_dict
from app.services.plan_entitlements import assert_chat_allowed_for_plan
from app.services.studio_image_pricing import image_pricing_public_dict
from app.services.studio_motion_pricing import (
    motion_video_credit_cost,
    motion_video_duration_seconds,
    motion_video_pricing_public,
)
from app.services.wavespeed_client import studio_wan_edit_tier_switch_available
from app.services.workspace import (
    PERM_CHAT,
    assert_permission,
    is_workspace_owner,
    workspace_owner_id,
    resolve_billing_user,
)
from app.services.conversation_notes import (
    analyze_conversation_notes,
    create_manual_note,
    delete_note,
    list_conversation_notes,
    update_manual_note,
)
from app.services.companion_bot.orchestrator import approve_and_send_companion_draft
from app.services.companion_bot.send import broadcast_companion_message
from app.services.platform_connections import (
    resolve_fanvue_connection_for_conversation,
    resolve_instagram_connection_for_conversation,
    resolve_telegram_connection_for_conversation,
)
from app.services.workspace_model_access import (
    filter_conversations_for_member,
    require_conversation_chat_access,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


async def _require_chat_plan(session: AsyncSession, user: User) -> None:
    billing = await resolve_billing_user(session, user)
    assert_chat_allowed_for_plan(billing.subscription)


@router.get("/health")
async def api_health(session: AsyncSession = Depends(get_session)) -> dict:
    try:
        from sqlalchemy import text

        await session.execute(text("SELECT 1"))
    except Exception:
        return {"ok": False, "mode": "saas", "database": "down"}

    db_path = ""
    if settings.database_url.startswith("sqlite+aiosqlite"):
        rest = settings.database_url.replace("sqlite+aiosqlite:///", "", 1)
        db_path = rest
    n_conv, n_msg = await count_rows(session)
    registered_users = int(
        await session.scalar(
            select(func.count(User.id)).where(User.parent_user_id.is_(None))
        )
        or 0
    )
    tg = get_telegram_api_status()
    return {
        "ok": True,
        "mode": "saas",
        "database_file": db_path,
        "backend_dir": str(BACKEND_DIR),
        "conversations_count": n_conv,
        "messages_count": n_msg,
        "legacy_telegram_polling": bool(
            (settings.legacy_bot_token or "").strip() and settings.legacy_user_id > 0
        ),
        "telegram_api_reachable": tg.get("reachable"),
        "telegram_bot_username": tg.get("username"),
        "telegram_api_error": tg.get("error"),
        "telegram_proxy_configured": bool((settings.telegram_proxy or "").strip()),
        "yookassa_configured": settings.yookassa_configured,
        "billing_require_active_subscription": settings.billing_require_active_subscription,
        "billing_price_managed_month_rub": settings.billing_price_managed_month_rub,
        "billing_price_byok_month_rub": settings.billing_price_byok_month_rub,
        "signup_bonus_credits": settings.signup_bonus_credits,
        "demo_generations_grant": settings.demo_generations_grant,
        "studio_image_pricing": image_pricing_public_dict(),
        "marketing_beta_creators_count": registered_users,
        "billing_catalog": catalog_public_dict(),
        "billing_credit_pack_price_rub": settings.billing_credit_pack_price_rub,
        "billing_credit_pack_credits": settings.billing_credit_pack_credits,
        "billing_credits_min_purchase": settings.billing_credits_min_purchase,
        "billing_credits_bulk_from": settings.billing_credits_bulk_from,
        "billing_credits_unit_price_rub": float(settings.billing_credits_unit_price_rub),
        "billing_credits_bulk_unit_price_rub": float(settings.billing_credits_bulk_unit_price_rub),
        "openai_studio_configured": bool((settings.openai_api_key or "").strip()),
        "wavespeed_platform_configured": bool((settings.wavespeed_platform_api_key or "").strip()),
        "studio_prompt_credit_cost": settings.credit_cost_studio_prompt_refine,
        "studio_inpaint_credit_cost": settings.credit_cost_studio_inpaint,
        "studio_upscale_credit_cost": settings.credit_cost_studio_upscale,
        "studio_wan_edit_tier_switch": studio_wan_edit_tier_switch_available(),
        "studio_allow_prompt_only": settings.studio_allow_prompt_only,
        "studio_regional_masked_edit": settings.studio_regional_masked_edit,
        "studio_carousel_credit_cost": settings.credit_cost_studio_carousel_shot,
        "studio_generations_retention_days": settings.studio_generations_retention_days,
        "studio_generations_retention_interval_hours": settings.studio_generations_retention_interval_hours,
        "studio_motion_video_pricing": motion_video_pricing_public(),
        "studio_motion_control_credit_cost": motion_video_credit_cost(
            motion_video_duration_seconds(None),
            has_motion_reference_video=False,
        ),
        "studio_motion_video_provider": "seedance_t2v",
        "studio_seedance_t2v_duration_default": settings.wavespeed_seedance_20_t2v_duration,
        "studio_seedance_t2v_duration_min": settings.studio_motion_video_duration_min,
        "studio_seedance_t2v_duration_max": settings.studio_motion_video_duration_max,
        "studio_seedance_t2v_prompt_max_chars": settings.studio_seedance_t2v_prompt_max_chars,
        "studio_seedance_t2v_default_resolution": settings.wavespeed_seedance_20_t2v_resolution,
        "studio_seedance_t2v_resolutions": ["480p", "720p", "1080p"],
        "studio_seedance_t2v_variants": ["standard", "mini"],
        "studio_seedance_i2v_duration_min": settings.studio_motion_video_duration_min,
        "studio_seedance_i2v_duration_max": settings.studio_motion_video_duration_max,
        "studio_grok_motion_timeline_enabled": settings.studio_grok_motion_timeline_enabled,
        "studio_grok_motion_configured": grok_motion_api_configured(),
        "studio_grok_scene_compose_configured": grok_scene_compose_configured(),
        "web_push_configured": settings.web_push_configured,
    }

@router.get("/conversations", response_model=list[ConversationWithPreview])
async def api_list_conversations(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ConversationWithPreview]:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    convs = await list_conversations(session, oid)
    convs = await filter_conversations_for_member(session, user, convs)
    out: list[ConversationWithPreview] = []
    for c in convs:
        last = await get_last_message(session, c.id, oid)
        preview = message_preview_text(last) if last else None
        unread = await unread_inbound_count(session, c.id, oid)
        base = ConversationOut.model_validate(c)
        out.append(
            ConversationWithPreview.model_validate(
                {
                    **base.model_dump(),
                    "last_message_preview": preview,
                    "unread_count": unread,
                }
            )
        )
    return out


@router.post("/conversations/{conv_id}/read")
async def api_mark_read(
    conv_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    await require_conversation_chat_access(session, user, conv_id, oid)
    await mark_conversation_read(session, conv_id, oid)
    await session.commit()
    return {"ok": True}


@router.get("/conversations/{conv_id}/avatar")
async def api_conversation_avatar(
    conv_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> Response:
    """Фото профиля собеседника (Telegram), прокси через бэкенд — токен бота не светится во фронте."""
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    if conv.platform != Platform.telegram or not (conv.telegram_photo_file_id or "").strip():
        raise HTTPException(status_code=404, detail="no avatar")

    bot, close_bot = await open_telegram_bot_for_owner(
        session, oid, telegram_connection_id=conv.telegram_connection_id
    )
    if not bot:
        raise HTTPException(
            status_code=503,
            detail="Нет доступа к Telegram Bot API: подключите бота или legacy polling.",
        )
    try:
        tg_file = await bot.get_file(conv.telegram_photo_file_id)
        if not tg_file.file_path:
            raise HTTPException(status_code=404, detail="no avatar")
        buf = BytesIO()
        await bot.download_file(tg_file.file_path, buf)
        data = buf.getvalue()
    finally:
        if close_bot:
            await bot.session.close()

    media_type = mimetypes.guess_type(tg_file.file_path)[0] or "application/octet-stream"
    return Response(content=data, media_type=media_type)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def api_messages(
    conv_id: int,
    limit: int = Query(40, ge=1, le=200),
    before: int | None = Query(
        None,
        description="Подгрузка истории: сообщения с id строго меньше этого значения",
    ),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    await require_conversation_chat_access(session, user, conv_id, oid)
    rows = await list_messages(
        session, conv_id, oid, limit=limit, before_id=before
    )
    return await load_messages_for_api(session, rows, owner_id=oid)


@router.get("/chat/attachment")
async def api_chat_attachment(
    t: str = Query(..., min_length=10),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Публичная раздача вложения чата по JWT (для <img src>)."""
    try:
        uid, aid = decode_chat_attachment_access_token(t)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token") from None
    stmt = (
        select(MessageAttachment)
        .where(MessageAttachment.id == aid)
        .options(
            selectinload(MessageAttachment.message).selectinload(Message.conversation)
        )
    )
    att = (await session.execute(stmt)).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="not found")
    msg = att.message
    if not msg:
        raise HTTPException(status_code=404, detail="not found")
    conv = msg.conversation
    if not conv or conv.user_id != uid:
        raise HTTPException(status_code=404, detail="not found")
    path = resolve_chat_attachment_file(uid, att.relative_path)
    if not path:
        raise HTTPException(status_code=404, detail="file missing")
    media = att.mime_type or mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return FileResponse(path, media_type=media)


@router.get("/chat/media-public")
async def api_chat_media_public(
    t: str = Query(..., min_length=10),
) -> FileResponse:
    """Публичная раздача медиа для Instagram outbound (Meta fetch по URL)."""
    try:
        uid, rel = decode_chat_media_public_token(t)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token") from None
    path = resolve_chat_attachment_file(uid, rel)
    if not path:
        raise HTTPException(status_code=404, detail="file missing")
    media = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return FileResponse(path, media_type=media)


@router.patch("/conversations/{conv_id}", response_model=ConversationOut)
async def api_patch_conversation(
    conv_id: int,
    body: ConversationPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ConversationOut:
    """Обновление настроек диалога (язык исходящих и т.д.)."""
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)

    if "outbound_lang" in body.model_fields_set:
        conv.outbound_lang = body.outbound_lang
    if "studio_model_id" in body.model_fields_set:
        raise HTTPException(
            status_code=400,
            detail="Модель назначается на подключении в кабинете «Интеграции», а не на каждом диалоге.",
        )
    if "auto_translate_disabled" in body.model_fields_set:
        if body.auto_translate_disabled is not None:
            conv.auto_translate_disabled = bool(body.auto_translate_disabled)
    if "companion_mode_override" in body.model_fields_set:
        conv.companion_mode_override = body.companion_mode_override
    await session.commit()
    await session.refresh(conv)
    return ConversationOut.model_validate(conv)


@router.post("/conversations/{conv_id}/reply", response_model=MessageOut)
async def api_reply(
    conv_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageOut:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    from app.db.models import Message, Subscription
    from app.services.plan_entitlements import assert_dialog_activity_allowed, month_start_utc

    content_type = (request.headers.get("content-type") or "").lower()
    text_ru = ""
    upload: UploadFile | None = None
    studio_generation_id: int | None = None
    reply_to_message_id: int | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        text_ru = str(form.get("text") or "").strip()
        raw_sg = form.get("studio_generation_id")
        if raw_sg not in (None, ""):
            try:
                studio_generation_id = int(str(raw_sg).strip())
            except ValueError as e:
                raise HTTPException(status_code=400, detail="invalid studio_generation_id") from e
        raw_reply = form.get("reply_to_message_id")
        if raw_reply not in (None, ""):
            try:
                reply_to_message_id = int(str(raw_reply).strip())
            except ValueError as e:
                raise HTTPException(status_code=400, detail="invalid reply_to_message_id") from e
        img_field = form.get("image")
        if img_field is not None and hasattr(img_field, "read"):
            upload = img_field  # type: ignore[assignment]
    else:
        try:
            data = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail="invalid body") from e
        body = ReplyIn.model_validate(data)
        text_ru = body.text.strip()
        reply_to_message_id = body.reply_to_message_id

    image_pair = await resolve_outbound_image(
        session,
        owner_id=oid,
        upload=upload,
        studio_generation_id=studio_generation_id,
    )
    if not text_ru and not image_pair:
        raise HTTPException(status_code=400, detail="empty message")

    start = month_start_utc()
    has_msg_this_month = await session.scalar(
        select(Message.id)
        .where(Message.conversation_id == conv_id, Message.created_at >= start)
        .limit(1)
    )
    if not has_msg_this_month:
        sub = await session.scalar(select(Subscription).where(Subscription.user_id == oid))
        await assert_dialog_activity_allowed(session, oid, sub)

    conv = await require_conversation_chat_access(session, user, conv_id, oid)

    reply_target = await resolve_reply_target(
        session, conv_id=conv.id, reply_to_message_id=reply_to_message_id
    )
    if reply_to_message_id and not reply_target:
        raise HTTPException(status_code=400, detail="reply_to_message_id not found in conversation")

    no_translate = bool(conv.auto_translate_disabled)
    outgoing = text_ru
    stored_original = text_ru
    stored_translated: str | None = None
    if text_ru and not no_translate:
        forced = (conv.outbound_lang or "").strip().lower()
        target_lang = forced if forced else (conv.user_lang or "en").strip().lower() or "en"
        outgoing = await translate_from_russian(text_ru, target_lang)
        if not (outgoing or "").strip():
            outgoing = text_ru
        stored_translated = outgoing or None

    image_bytes: bytes | None = None
    image_mime: str | None = None
    if image_pair:
        image_bytes, image_mime = image_pair

    platform_message_id: str | None = None
    if conv.platform == Platform.telegram:
        row_tg = await resolve_telegram_connection_for_conversation(session, conv, oid)
        if not row_tg:
            raise HTTPException(
                status_code=503,
                detail="Подключите Telegram-бота в настройках интеграций",
            )
        token = decrypt_secret(row_tg.bot_token_encrypted)
        try:
            tid = int(conv.external_topic_id)
            cid = int(conv.external_chat_id)
        except ValueError as e:
            raise HTTPException(status_code=500, detail="bad telegram ids") from e
        tg_reply_id: int | None = None
        if reply_target:
            tg_reply_id = None
            if reply_target.platform_message_id:
                try:
                    tg_reply_id = int(reply_target.platform_message_id)
                except ValueError:
                    tg_reply_id = None
            if tg_reply_id is None:
                from app.services.chat_message_meta import platform_message_id_from_meta

                raw = platform_message_id_from_meta(reply_target.meta)
                if raw:
                    try:
                        tg_reply_id = int(raw)
                    except ValueError:
                        tg_reply_id = None
        sent_id = await send_telegram_outbound(
            token=token,
            chat_id=cid,
            topic_id=tid,
            text=outgoing,
            image_bytes=image_bytes,
            image_mime=image_mime,
            reply_to_telegram_message_id=tg_reply_id,
        )
        if sent_id is not None:
            platform_message_id = str(sent_id)
    elif conv.platform == Platform.fanvue:
        row_fv = await resolve_fanvue_connection_for_conversation(session, conv, oid)
        if not row_fv:
            raise HTTPException(
                status_code=503,
                detail="Подключите Fanvue в настройках интеграций",
            )
        from app.services.fanvue_connection import ensure_fanvue_access_token

        fv_tok = await ensure_fanvue_access_token(session, row_fv)
        fv_reply_uuid = None
        if reply_target:
            fv_reply_uuid = reply_target.platform_message_id or platform_message_id_from_meta(
                reply_target.meta
            )
        platform_message_id = await send_fanvue_outbound(
            access_token=fv_tok,
            fan_uuid=conv.external_chat_id,
            text=outgoing,
            image_bytes=image_bytes,
            image_mime=image_mime,
            reply_to_message_uuid=fv_reply_uuid,
        )
    elif conv.platform == Platform.instagram:
        row_ig = await resolve_instagram_connection_for_conversation(session, conv, oid)
        if not row_ig:
            raise HTTPException(
                status_code=503,
                detail="Подключите Instagram в настройках интеграций",
            )
        from app.services.instagram_connection import ensure_instagram_access_token

        ig_tok = await ensure_instagram_access_token(session, row_ig)
        platform_message_id = await send_instagram_outbound(
            access_token=ig_tok,
            ig_user_id=row_ig.instagram_user_id,
            recipient_id=conv.external_chat_id,
            owner_id=oid,
            text=outgoing,
            image_bytes=image_bytes,
            image_mime=image_mime,
        )
    else:
        raise HTTPException(status_code=400, detail="unknown platform")

    conv.updated_at = datetime.now(timezone.utc)
    row = await add_message(
        session,
        conv.id,
        MessageDirection.outbound,
        stored_original,
        stored_translated,
        meta=None,
        reply_to_message_id=reply_to_message_id,
        platform_message_id=platform_message_id,
    )
    if image_bytes:
        try:
            rel, mime = save_chat_image_bytes(
                owner_id=oid,
                raw=image_bytes,
                content_type=image_mime,
            )
            await add_message_attachment(
                session,
                message_id=row.id,
                relative_path=rel,
                mime_type=mime,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    await mark_conversation_read(session, conv.id, oid)
    await session.commit()
    await session.refresh(row)
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
    if conv.platform == Platform.fanvue:
        from app.services.fanvue_inbox_poll import background_sync_fanvue_chat

        background_tasks.add_task(
            background_sync_fanvue_chat,
            oid,
            conv.external_chat_id,
            conv.user_display_name or "",
        )
    return out


@router.post(
    "/conversations/{conv_id}/messages/{message_id}/reactions",
    response_model=MessageOut,
)
async def api_message_reaction(
    conv_id: int,
    message_id: int,
    body: MessageReactionIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageOut:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    row = await session.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conv.id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="message not found")
    emoji = body.emoji.strip()
    if emoji not in REACTION_EMOJIS:
        raise HTTPException(status_code=400, detail="unsupported emoji")

    reactions = toggle_owner_reaction(parse_reactions(row.reactions_json), emoji)
    row.reactions_json = reactions_to_json(reactions)

    if conv.platform == Platform.telegram:
        tg_id_raw = row.platform_message_id or platform_message_id_from_meta(row.meta)
        if tg_id_raw:
            row_tg = await resolve_telegram_connection_for_conversation(session, conv, oid)
            if row_tg:
                token = decrypt_secret(row_tg.bot_token_encrypted)
                try:
                    cid = int(conv.external_chat_id)
                    tg_mid = int(tg_id_raw)
                    topic_id = int(conv.external_topic_id)
                except ValueError:
                    cid = 0
                    tg_mid = 0
                    topic_id = 0
                if cid and tg_mid:
                    owner_has_emoji = any(
                        r.get("actor") == "owner" and r.get("emoji") == emoji
                        for r in reactions
                    )
                    try:
                        await set_telegram_message_reaction(
                            token=token,
                            chat_id=cid,
                            telegram_message_id=tg_mid,
                            emoji=emoji if owner_has_emoji else None,
                            topic_id=topic_id or None,
                        )
                    except Exception as e:
                        log.warning(
                            "telegram set_message_reaction failed conv=%s msg=%s "
                            "chat=%s tg_msg=%s topic=%s emoji=%s: %s",
                            conv.id,
                            row.id,
                            cid,
                            tg_mid,
                            topic_id,
                            emoji if owner_has_emoji else None,
                            e,
                        )

    await session.commit()
    await session.refresh(row, attribute_names=["attachments"])
    reply_preview = None
    if row.reply_to_message_id:
        parent = await session.get(Message, row.reply_to_message_id)
        if parent:
            reply_preview = (parent.text_original or parent.text_translated or "")[:160]
    await broadcast_message_updated(
        session,
        owner_user_id=oid,
        conv_id=conv.id,
        row=row,
    )
    return message_to_out(row, owner_id=oid, reply_preview=reply_preview)


@router.get("/conversations/{conv_id}/notes", response_model=list[ConversationNoteOut])
async def api_list_conversation_notes(
    conv_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ConversationNoteOut]:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    items = await list_conversation_notes(session, conv=conv, viewer=user)
    return [ConversationNoteOut.model_validate(x) for x in items]


@router.post("/conversations/{conv_id}/notes", response_model=ConversationNoteOut)
async def api_create_conversation_note(
    conv_id: int,
    body: ConversationNoteCreateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ConversationNoteOut:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    item = await create_manual_note(
        session,
        conv=conv,
        author=user,
        content=body.content,
        is_pinned=body.is_pinned,
    )
    return ConversationNoteOut.model_validate(item)


@router.patch("/conversations/{conv_id}/notes/{note_id}", response_model=ConversationNoteOut)
async def api_patch_conversation_note(
    conv_id: int,
    note_id: int,
    body: ConversationNotePatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ConversationNoteOut:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    item = await update_manual_note(
        session,
        conv=conv,
        note_id=note_id,
        actor=user,
        owner_id=oid,
        content=body.content if "content" in body.model_fields_set else None,
        is_pinned=body.is_pinned if "is_pinned" in body.model_fields_set else None,
    )
    return ConversationNoteOut.model_validate(item)


@router.delete("/conversations/{conv_id}/notes/{note_id}", status_code=204)
async def api_delete_conversation_note(
    conv_id: int,
    note_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    await delete_note(session, conv=conv, note_id=note_id, actor=user, owner_id=oid)


@router.post("/conversations/{conv_id}/notes/analyze", response_model=list[ConversationNoteOut])
async def api_analyze_conversation_notes(
    conv_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ConversationNoteOut]:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    items = await analyze_conversation_notes(
        session, conv=conv, viewer=user, owner_id=oid
    )
    return [ConversationNoteOut.model_validate(x) for x in items]


@router.get(
    "/conversations/{conv_id}/companion-drafts",
    response_model=list[CompanionDraftOut],
)
async def api_list_companion_drafts(
    conv_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[CompanionDraftOut]:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    rows = list(
        (
            await session.scalars(
                select(BotResponseEvent)
                .where(
                    BotResponseEvent.conversation_id == conv.id,
                    BotResponseEvent.status == BotResponseEventStatus.draft,
                )
                .order_by(BotResponseEvent.id.asc())
            )
        ).all()
    )
    return [
        CompanionDraftOut(
            id=r.id,
            conversation_id=r.conversation_id,
            trigger_message_id=r.trigger_message_id,
            draft_text=r.draft_text,
            target_lang=r.target_lang,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post(
    "/conversations/{conv_id}/companion-drafts/{event_id}/approve",
    response_model=MessageOut,
)
async def api_approve_companion_draft(
    conv_id: int,
    event_id: int,
    body: CompanionDraftApproveIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageOut:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    event = await session.scalar(
        select(BotResponseEvent).where(
            BotResponseEvent.id == event_id,
            BotResponseEvent.conversation_id == conv.id,
        )
    )
    if not event or event.status != BotResponseEventStatus.draft:
        raise HTTPException(status_code=404, detail="Черновик не найден")
    try:
        row = await approve_and_send_companion_draft(
            session,
            owner_user_id=oid,
            conv=conv,
            event=event,
            text_override=body.text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.warning("companion draft approve failed: %s", e)
        event.status = BotResponseEventStatus.failed
        await session.commit()
        raise HTTPException(status_code=502, detail="Не удалось отправить ответ") from e
    await session.commit()
    await session.refresh(row, attribute_names=["attachments"])
    await broadcast_companion_message(owner_id=oid, conv_id=conv.id, row=row)
    return message_to_out(row, owner_id=oid)


@router.post(
    "/conversations/{conv_id}/companion-drafts/{event_id}/reject",
    status_code=204,
)
async def api_reject_companion_draft(
    conv_id: int,
    event_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    event = await session.scalar(
        select(BotResponseEvent).where(
            BotResponseEvent.id == event_id,
            BotResponseEvent.conversation_id == conv.id,
        )
    )
    if not event or event.status != BotResponseEventStatus.draft:
        raise HTTPException(status_code=404, detail="Черновик не найден")
    event.status = BotResponseEventStatus.rejected
    await session.commit()


@router.post(
    "/conversations/{conv_id}/messages/{message_id}/companion-rating",
    response_model=MessageOut,
)
async def api_companion_message_rating(
    conv_id: int,
    message_id: int,
    body: CompanionRatingIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageOut:
    assert_permission(user, PERM_CHAT)
    await _require_chat_plan(session, user)
    oid = workspace_owner_id(user)
    conv = await require_conversation_chat_access(session, user, conv_id, oid)
    row = await session.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conv.id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="message not found")
    event = await session.scalar(
        select(BotResponseEvent).where(BotResponseEvent.outbound_message_id == row.id)
    )
    if not event:
        raise HTTPException(status_code=404, detail="Ответ бота не найден")
    event.operator_rating = int(body.rating)
    await session.commit()
    await session.refresh(row, attribute_names=["attachments"])
    return message_to_out(
        row,
        owner_id=oid,
        operator_rating=event.operator_rating,
        bot_response_event_id=event.id,
    )


@router.websocket("/ws")
async def websocket_updates(
    ws: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    if not token:
        await ws.close(code=4401)
        return
    try:
        uid = int(decode_token(token))
    except ValueError:
        await ws.close(code=4401)
        return
    async with SessionLocal() as s:
        u = await s.get(User, uid)
        if not u or not u.is_active:
            await ws.close(code=4401)
            return
        wid = workspace_owner_id(u)
    await hub.connect(ws, wid)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        log.debug("ws disconnected")
    finally:
        await hub.disconnect(ws, wid)
