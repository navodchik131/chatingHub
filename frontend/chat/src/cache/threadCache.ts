/**
 * Кэш списка диалогов и тредов (последние сообщения) в IndexedDB.
 */

import type { ApiConversation, ApiMessage, ConversationsCacheEntry, ThreadCacheEntry } from '../types'
import { idbGet, idbSet } from './idb'

const CONV_KEY = 'list'
const THREAD_PREFIX = 'thread:'

export async function loadConversationsCache(): Promise<ApiConversation[] | null> {
  const hit = await idbGet<ConversationsCacheEntry>('conversations', CONV_KEY)
  if (!hit?.items?.length) return null
  return hit.items
}

export async function saveConversationsCache(items: ApiConversation[]): Promise<void> {
  const entry: ConversationsCacheEntry = { items, savedAt: Date.now() }
  await idbSet('conversations', CONV_KEY, entry)
}

export async function loadThreadCache(convId: number): Promise<ApiMessage[] | null> {
  const hit = await idbGet<ThreadCacheEntry>('threads', `${THREAD_PREFIX}${convId}`)
  if (!hit?.messages?.length) return null
  return hit.messages
}

export async function saveThreadCache(convId: number, messages: ApiMessage[]): Promise<void> {
  const last = messages.length ? messages[messages.length - 1] : null
  const entry: ThreadCacheEntry = {
    convId,
    messages,
    savedAt: Date.now(),
    lastMessageId: last?.id ?? null,
  }
  await idbSet('threads', `${THREAD_PREFIX}${convId}`, entry)
}

export type PersonaFilter = number | 'all' | 'none'

export async function loadUiSettings(): Promise<{
  theme: string
  accent: string
  activePersonaId?: PersonaFilter
} | null> {
  return idbGet('meta', 'ui')
}

export async function saveUiSettings(
  theme: string,
  accent: string,
  activePersonaId?: PersonaFilter,
): Promise<void> {
  await idbSet('meta', 'ui', { theme, accent, activePersonaId })
}
