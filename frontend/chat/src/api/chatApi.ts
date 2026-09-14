import type { ApiConversation, ApiMessage, ConversationFolder, StudioModel, UserMe } from '../types'
import { formatHttpApiError } from './errors'
import { apiFetch, apiJson } from './client'

export async function fetchMe(): Promise<UserMe> {
  return apiJson<UserMe>('/api/auth/me')
}

/** Список персонажей workspace — для переключателя диалогов. */
export async function fetchStudioModels(): Promise<StudioModel[]> {
  const rows = await apiJson<StudioModel[]>('/api/studio/models')
  return Array.isArray(rows) ? rows : []
}

export async function fetchConversations(): Promise<ApiConversation[]> {
  const rows = await apiJson<ApiConversation[]>('/api/conversations')
  return Array.isArray(rows) ? rows : []
}

export async function fetchMessages(
  convId: number,
  limit = 80,
  before?: number,
): Promise<ApiMessage[]> {
  let url = `/api/conversations/${convId}/messages?limit=${limit}`
  if (before != null && before > 0) url += `&before=${before}`
  const rows = await apiJson<ApiMessage[]>(url)
  return Array.isArray(rows) ? rows : []
}

export async function markConversationRead(convId: number): Promise<void> {
  await apiJson(`/api/conversations/${convId}/read`, { method: 'POST', body: '{}' })
}

export async function sendTextReply(
  convId: number,
  text: string,
  replyToMessageId?: number | null,
): Promise<ApiMessage> {
  const body: Record<string, unknown> = { text: text.trim() }
  if (replyToMessageId) body.reply_to_message_id = replyToMessageId
  return apiJson<ApiMessage>(`/api/conversations/${convId}/reply`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function sendImageReply(convId: number, text: string, file: File): Promise<ApiMessage> {
  const fd = new FormData()
  if (text.trim()) fd.append('text', text.trim())
  fd.append('image', file, file.name || 'photo.jpg')
  const res = await apiFetch(`/api/conversations/${convId}/reply`, { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(formatHttpApiError(res, data))
  return data as ApiMessage
}

export async function patchConversation(convId: number, patch: Record<string, unknown>): Promise<ApiConversation> {
  return apiJson<ApiConversation>(`/api/conversations/${convId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function fetchFolders(): Promise<ConversationFolder[]> {
  const rows = await apiJson<ConversationFolder[]>('/api/conversation-folders')
  return Array.isArray(rows) ? rows : []
}

export async function fetchNotes(convId: number): Promise<unknown[]> {
  const rows = await apiJson<unknown[]>(`/api/conversations/${convId}/notes?auto_refresh=false`)
  return Array.isArray(rows) ? rows : []
}

export async function createNote(convId: number, content: string): Promise<void> {
  await apiJson(`/api/conversations/${convId}/notes`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

export async function setMessageReaction(
  convId: number,
  messageId: number,
  emoji: string,
): Promise<ApiMessage> {
  return apiJson<ApiMessage>(`/api/conversations/${convId}/messages/${messageId}/reactions`, {
    method: 'POST',
    body: JSON.stringify({ emoji }),
  })
}

export async function createFolder(name: string, conversationIds: number[] = []): Promise<ConversationFolder> {
  return apiJson<ConversationFolder>('/api/conversation-folders', {
    method: 'POST',
    body: JSON.stringify({ name, conversation_ids: conversationIds }),
  })
}

export async function updateFolder(
  folderId: number,
  patch: { name?: string; conversation_ids?: number[] },
): Promise<ConversationFolder> {
  return apiJson<ConversationFolder>(`/api/conversation-folders/${folderId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function deleteFolder(folderId: number): Promise<void> {
  await apiFetch(`/api/conversation-folders/${folderId}`, { method: 'DELETE' })
}

export async function addConversationToFolder(folderId: number, convId: number): Promise<ConversationFolder> {
  // Бэкенд принимает POST (не PUT) — иначе 405 Method Not Allowed.
  return apiJson<ConversationFolder>(`/api/conversation-folders/${folderId}/conversations/${convId}`, {
    method: 'POST',
    body: '{}',
  })
}

export async function removeConversationFromFolder(folderId: number, convId: number): Promise<ConversationFolder> {
  return apiJson<ConversationFolder>(`/api/conversation-folders/${folderId}/conversations/${convId}`, {
    method: 'DELETE',
  })
}

/** AI-анализ переписки → заметки. */
export async function analyzeNotes(convId: number): Promise<unknown[]> {
  const rows = await apiJson<unknown[]>(`/api/conversations/${convId}/notes/analyze`, {
    method: 'POST',
    body: '{}',
  })
  return Array.isArray(rows) ? rows : []
}

/** Мягкое удаление диалога из списка. */
export async function deleteConversation(convId: number): Promise<void> {
  await apiFetch(`/api/conversations/${convId}`, { method: 'DELETE' })
}

export interface PaidMediaPack {
  id: number
  name: string
  price_stars: number
  asset_count: number
  max_send_count: number
}

/** Паки медиатеки с ценой ⭐ для диалога (telegram_user + Stars Business). */
export async function fetchPaidMediaPacks(convId: number): Promise<PaidMediaPack[]> {
  const rows = await apiJson<PaidMediaPack[]>(`/api/conversations/${convId}/paid-media-packs`)
  return Array.isArray(rows) ? rows : []
}

export async function sendPaidMediaPack(
  convId: number,
  packId: number,
  caption?: string,
): Promise<ApiMessage> {
  const body: Record<string, unknown> = { pack_id: packId }
  if (caption?.trim()) body.caption = caption.trim()
  return apiJson<ApiMessage>(`/api/conversations/${convId}/send-paid-media`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
