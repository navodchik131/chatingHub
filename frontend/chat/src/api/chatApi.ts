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

export interface PaidMediaAssetOption {
  id: number
  title: string | null
  media_type: string
  price_stars: number
  preview_url: string | null
}

export interface PaidMediaOptions {
  packs: PaidMediaPack[]
  assets: PaidMediaAssetOption[]
}

/** Паки и одиночные файлы с ⭐ для диалога. */
export async function fetchPaidMediaOptions(convId: number): Promise<PaidMediaOptions> {
  const data = await apiJson<PaidMediaOptions>(`/api/conversations/${convId}/paid-media-options`)
  return {
    packs: Array.isArray(data?.packs) ? data.packs : [],
    assets: Array.isArray(data?.assets) ? data.assets : [],
  }
}

export async function sendPaidMediaUpload(
  convId: number,
  file: File,
  starCount: number,
  caption?: string,
): Promise<ApiMessage> {
  const fd = new FormData()
  fd.append('media', file, file.name || 'media')
  fd.append('star_count', String(Math.max(1, Math.min(25000, starCount))))
  if (caption?.trim()) fd.append('caption', caption.trim())
  const res = await apiFetch(`/api/conversations/${convId}/send-paid-media-upload`, {
    method: 'POST',
    body: fd,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(formatHttpApiError(res, data))
  return data as ApiMessage
}

export async function sendPaidMedia(
  convId: number,
  target: { packId?: number; assetId?: number },
  caption?: string,
): Promise<ApiMessage> {
  const body: Record<string, unknown> = {}
  if (target.packId) body.pack_id = target.packId
  if (target.assetId) body.asset_id = target.assetId
  if (caption?.trim()) body.caption = caption.trim()
  return apiJson<ApiMessage>(`/api/conversations/${convId}/send-paid-media`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
