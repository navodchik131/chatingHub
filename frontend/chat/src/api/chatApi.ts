import type { ApiConversation, ApiMessage, ConversationFolder, UserMe } from '../types'
import { apiFetch, apiJson } from './client'

export async function fetchMe(): Promise<UserMe> {
  return apiJson<UserMe>('/api/auth/me')
}

export async function fetchConversations(): Promise<ApiConversation[]> {
  const rows = await apiJson<ApiConversation[]>('/api/conversations')
  return Array.isArray(rows) ? rows : []
}

export async function fetchMessages(convId: number, limit = 80): Promise<ApiMessage[]> {
  const rows = await apiJson<ApiMessage[]>(`/api/conversations/${convId}/messages?limit=${limit}`)
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
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Send failed')
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
