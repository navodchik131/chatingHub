"""CRUD для пользовательских папок диалогов."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, ConversationFolder, ConversationFolderItem


async def list_conversation_folders(
    session: AsyncSession,
    *,
    owner_id: int,
) -> list[tuple[ConversationFolder, list[int]]]:
    stmt = (
        select(ConversationFolder)
        .where(ConversationFolder.user_id == owner_id)
        .options(selectinload(ConversationFolder.items))
        .order_by(ConversationFolder.sort_order.asc(), ConversationFolder.id.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    out: list[tuple[ConversationFolder, list[int]]] = []
    for folder in rows:
        conv_ids = sorted({int(x.conversation_id) for x in folder.items})
        out.append((folder, conv_ids))
    return out


async def create_conversation_folder(
    session: AsyncSession,
    *,
    owner_id: int,
    name: str,
    conversation_ids: list[int] | None = None,
) -> tuple[ConversationFolder, list[int]]:
    trimmed = (name or "").strip()
    if not trimmed:
        raise ValueError("Укажите название папки")
    if len(trimmed) > 64:
        trimmed = trimmed[:64]

    max_order = (
        await session.execute(
            select(func.coalesce(func.max(ConversationFolder.sort_order), -1)).where(
                ConversationFolder.user_id == owner_id
            )
        )
    ).scalar_one()
    folder = ConversationFolder(
        user_id=owner_id,
        name=trimmed,
        sort_order=int(max_order) + 1,
    )
    session.add(folder)
    await session.flush()

    conv_ids = await _set_folder_members(
        session, owner_id=owner_id, folder=folder, conversation_ids=conversation_ids or []
    )
    return folder, conv_ids


async def update_conversation_folder(
    session: AsyncSession,
    *,
    owner_id: int,
    folder_id: int,
    name: str | None = None,
    sort_order: int | None = None,
    conversation_ids: list[int] | None = None,
) -> tuple[ConversationFolder, list[int]]:
    folder = await _require_folder(session, owner_id=owner_id, folder_id=folder_id)
    if name is not None:
        trimmed = name.strip()
        if not trimmed:
            raise ValueError("Укажите название папки")
        folder.name = trimmed[:64]
    if sort_order is not None:
        folder.sort_order = int(sort_order)

    if conversation_ids is not None:
        conv_ids = await _set_folder_members(
            session, owner_id=owner_id, folder=folder, conversation_ids=conversation_ids
        )
    else:
        await session.refresh(folder, attribute_names=["items"])
        conv_ids = sorted({int(x.conversation_id) for x in folder.items})

    return folder, conv_ids


async def delete_conversation_folder(
    session: AsyncSession,
    *,
    owner_id: int,
    folder_id: int,
) -> None:
    folder = await _require_folder(session, owner_id=owner_id, folder_id=folder_id)
    await session.delete(folder)


async def add_conversation_to_folder(
    session: AsyncSession,
    *,
    owner_id: int,
    folder_id: int,
    conversation_id: int,
) -> list[int]:
    folder = await _require_folder(session, owner_id=owner_id, folder_id=folder_id)
    await _assert_conversation_owned(session, owner_id=owner_id, conversation_id=conversation_id)
    existing = (
        await session.execute(
            select(ConversationFolderItem).where(
                ConversationFolderItem.folder_id == folder.id,
                ConversationFolderItem.conversation_id == conversation_id,
            )
        )
    ).scalar_one_or_none()
    if not existing:
        session.add(
            ConversationFolderItem(folder_id=folder.id, conversation_id=conversation_id)
        )
        await session.flush()
    await session.refresh(folder, attribute_names=["items"])
    return sorted({int(x.conversation_id) for x in folder.items})


async def remove_conversation_from_folder(
    session: AsyncSession,
    *,
    owner_id: int,
    folder_id: int,
    conversation_id: int,
) -> list[int]:
    folder = await _require_folder(session, owner_id=owner_id, folder_id=folder_id)
    await session.execute(
        delete(ConversationFolderItem).where(
            ConversationFolderItem.folder_id == folder.id,
            ConversationFolderItem.conversation_id == conversation_id,
        )
    )
    await session.flush()
    await session.refresh(folder, attribute_names=["items"])
    return sorted({int(x.conversation_id) for x in folder.items})


async def _require_folder(
    session: AsyncSession, *, owner_id: int, folder_id: int
) -> ConversationFolder:
    folder = await session.get(ConversationFolder, folder_id)
    if not folder or folder.user_id != owner_id:
        raise ValueError("Папка не найдена")
    return folder


async def _assert_conversation_owned(
    session: AsyncSession, *, owner_id: int, conversation_id: int
) -> None:
    conv = await session.get(Conversation, conversation_id)
    if not conv or conv.user_id != owner_id or conv.is_hidden:
        raise ValueError("Диалог не найден")


async def _set_folder_members(
    session: AsyncSession,
    *,
    owner_id: int,
    folder: ConversationFolder,
    conversation_ids: list[int],
) -> list[int]:
    unique_ids: list[int] = []
    seen: set[int] = set()
    for raw in conversation_ids:
        cid = int(raw)
        if cid in seen:
            continue
        seen.add(cid)
        await _assert_conversation_owned(session, owner_id=owner_id, conversation_id=cid)
        unique_ids.append(cid)

    await session.execute(
        delete(ConversationFolderItem).where(ConversationFolderItem.folder_id == folder.id)
    )
    for cid in unique_ids:
        session.add(ConversationFolderItem(folder_id=folder.id, conversation_id=cid))
    await session.flush()
    return unique_ids
