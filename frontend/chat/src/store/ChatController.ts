/**
 * Оркестратор: кэш → UI → сеть → WS.
 * При открытии чата сначала отдаём данные из IndexedDB, затем синхронизируем с API.
 */

import {
  fetchConversations,
  fetchFolders,
  fetchMessages,
  fetchNotes,
  createNote,
  markConversationRead,
  sendImageReply,
  sendTextReply,
  patchConversation,
  fetchMe,
} from '../api/chatApi'
import { connectRealtime, type RealtimeConnection } from '../api/realtime'
import { apiFetch } from '../api/client'
import {
  avatarCacheKey,
  getCachedObjectUrl,
  mediaCacheKey,
} from '../cache/blobCache'
import {
  loadConversationsCache,
  saveConversationsCache,
  loadThreadCache,
  saveThreadCache,
} from '../cache/threadCache'
import {
  mapApiConversation,
  mapApiMessages,
  mergeApiMessages,
  mapApiMessage,
} from '../lib/mapMessage'
import type {
  ApiConversation,
  ApiMessage,
  ConversationFolder,
  RealtimeEvent,
  UiChat,
  UserMe,
} from '../types'

export type ChatListener = () => void

export class ChatController {
  me: UserMe | null = null
  chats: UiChat[] = []
  folders: ConversationFolder[] = []
  activeChatId: number | null = null
  loading = true
  error: string | null = null

  /** Индекс первого непрочитанного в открытом треде (линия «Непрочитанные»). */
  unreadAnchor: Record<number, number> = {}
  /** Object URL аватарок convId → url */
  avatarUrls = new Map<number, string>()
  /** Object URL медиа mediaKey → url */
  mediaUrls = new Map<string, string>()

  private listeners = new Set<ChatListener>()
  private ws: RealtimeConnection | null = null
  private readTimer: ReturnType<typeof setTimeout> | null = null
  private threadLoads = new Map<number, Promise<void>>()
  private apiMessages = new Map<number, ApiMessage[]>()

  subscribe(fn: ChatListener): () => void {
    this.listeners.add(fn)
    return () => this.listeners.delete(fn)
  }

  private emit(): void {
    for (const fn of this.listeners) fn()
  }

  get activeChat(): UiChat | null {
    if (this.activeChatId == null) return null
    return this.chats.find((c) => c.id === this.activeChatId) ?? null
  }

  async init(): Promise<void> {
    this.loading = true
    this.emit()

    const cached = await loadConversationsCache()
    if (cached?.length) {
      this.setConversationsFromApi(cached)
      this.loading = false
      this.emit()
    }

    try {
      this.me = await fetchMe()
      const [convs, folds] = await Promise.all([fetchConversations(), fetchFolders()])
      this.folders = folds
      this.setConversationsFromApi(convs)
      await saveConversationsCache(convs)
      void this.prefetchAvatars(convs)
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e)
      if (!this.chats.length) throw e
    } finally {
      this.loading = false
      this.emit()
    }

    this.ws?.close()
    this.ws = connectRealtime((msg) => this.onRealtime(msg))
  }

  destroy(): void {
    this.ws?.close()
    this.ws = null
    if (this.readTimer) clearTimeout(this.readTimer)
  }

  private setConversationsFromApi(rows: ApiConversation[]): void {
    const prevDrafts = new Map(this.chats.map((c) => [c.id, c.draft]))
    const prevMsgs = new Map(this.chats.map((c) => [c.id, c.msgs]))
    this.chats = rows.map((c, i) => {
      const ui = mapApiConversation(c, i)
      ui.draft = prevDrafts.get(c.id) || ''
      const kept = prevMsgs.get(c.id)
      if (kept?.length && c.id === this.activeChatId) ui.msgs = kept
      return ui
    })
  }

  private async prefetchAvatars(rows: ApiConversation[]): Promise<void> {
    for (const c of rows.slice(0, 40)) {
      if (!c.has_avatar && !c.avatar_url) continue
      void this.resolveAvatar(c.id, c.avatar_url)
    }
  }

  async resolveAvatar(convId: number, url?: string | null): Promise<string | null> {
    const cached = this.avatarUrls.get(convId)
    if (cached) return cached
    const chat = this.chats.find((c) => c.id === convId)
    const fetchUrl = url || chat?.avatarUrl || chat?.raw.avatar_url
    if (!fetchUrl) return null
    const key = avatarCacheKey(convId)
    const objectUrl = await getCachedObjectUrl(key, () => apiFetch(fetchUrl), 'avatar')
    if (objectUrl) this.avatarUrls.set(convId, objectUrl)
    return objectUrl
  }

  async resolveMedia(mediaKey: string, url: string): Promise<string | null> {
    const cached = this.mediaUrls.get(mediaKey)
    if (cached) return cached
    const key = mediaCacheKey(url)
    const objectUrl = await getCachedObjectUrl(key, () => apiFetch(url), 'media')
    if (objectUrl) this.mediaUrls.set(mediaKey, objectUrl)
    return objectUrl
  }

  /** Открыть чат: кэш треда сразу, затем свежие сообщения с API. */
  async openChat(convId: number): Promise<void> {
    const chat = this.chats.find((c) => c.id === convId)
    if (!chat) return

    const prevUnread = chat.unread
    chat.unread = 0
    this.activeChatId = convId
    this.emit()

    const cachedApi = await loadThreadCache(convId)
    if (cachedApi?.length) {
      this.apiMessages.set(convId, cachedApi)
      chat.msgs = mapApiMessages(cachedApi, chat)
      if (prevUnread > 0 && chat.msgs.length) {
        this.unreadAnchor[convId] = Math.max(0, chat.msgs.length - prevUnread)
      }
      this.emit()
    }

    void this.syncThread(convId, { markRead: true })
    void this.resolveAvatar(convId)
    void this.loadNotes(convId)
  }

  private async syncThread(convId: number, opts: { markRead?: boolean } = {}): Promise<void> {
    const existing = this.threadLoads.get(convId)
    if (existing) return existing

    const job = (async () => {
      const chat = this.chats.find((c) => c.id === convId)
      if (!chat) return
      try {
        const fresh = await fetchMessages(convId, 80)
        const merged = mergeApiMessages(this.apiMessages.get(convId) || [], fresh)
        this.apiMessages.set(convId, merged)
        await saveThreadCache(convId, merged)
        chat.msgs = mapApiMessages(merged, chat)
        this.emit()
        if (opts.markRead) this.scheduleMarkRead(convId)
      } catch (e) {
        this.error = e instanceof Error ? e.message : String(e)
        this.emit()
      } finally {
        this.threadLoads.delete(convId)
      }
    })()

    this.threadLoads.set(convId, job)
    return job
  }

  scheduleMarkRead(convId: number): void {
    if (this.readTimer) clearTimeout(this.readTimer)
    this.readTimer = setTimeout(() => {
      void markConversationRead(convId).catch(() => {})
      const c = this.chats.find((x) => x.id === convId)
      if (c) c.unread = 0
      delete this.unreadAnchor[convId]
      this.emit()
    }, 350)
  }

  async refreshConversations(): Promise<void> {
    try {
      const convs = await fetchConversations()
      this.setConversationsFromApi(convs)
      await saveConversationsCache(convs)
      this.emit()
    } catch {
      /* ignore background refresh errors */
    }
  }

  private mergeInbound(convId: number, msg: ApiMessage, bumpUnread: boolean): void {
    const chat = this.chats.find((c) => c.id === convId)
    if (!chat) {
      void this.refreshConversations()
      return
    }

    const merged = mergeApiMessages(this.apiMessages.get(convId) || chat.msgs.map((m) => ({
      id: m.id,
      direction: m.out ? 'outbound' : 'inbound',
      text_original: m.text,
      text_translated: m.ru || null,
      created_at: new Date().toISOString(),
    })), [msg])
    this.apiMessages.set(convId, merged)
    void saveThreadCache(convId, merged)

    chat.msgs = mapApiMessages(merged, chat)
    chat.raw.last_message_preview = (msg.text_original || msg.text_translated || '📷').slice(0, 80)

    const isActive = this.activeChatId === convId
    const isInbound = msg.direction === 'inbound'
    if (isActive && isInbound) {
      this.scheduleMarkRead(convId)
    } else if (isInbound && bumpUnread) {
      chat.unread = (chat.unread || 0) + 1
    }

    this.emit()
  }

  private onRealtime(ev: RealtimeEvent): void {
    const convId = Number(ev.conversation_id)
    if (
      ev.type === 'new_message' ||
      ev.type === 'message_created' ||
      ev.type === 'message_updated'
    ) {
      const payload = ev.message
      if (payload?.id && convId) {
        const active = this.activeChatId === convId
        this.mergeInbound(convId, payload, !active)
        if (active) {
          /* flash handled in UI layer via last rendered id */
        }
      } else if (convId) {
        void this.syncThread(convId)
      } else {
        void this.refreshConversations()
      }
      return
    }
    if (ev.type === 'conversation_updated') {
      void this.refreshConversations()
    }
  }

  async sendText(convId: number, text: string, replyTo?: number | null): Promise<void> {
    const chat = this.chats.find((c) => c.id === convId)
    if (!chat || !text.trim()) return

    const tempId = -Date.now()
    const optimistic: ApiMessage = {
      id: tempId,
      direction: 'outbound',
      text_original: text.trim(),
      text_translated: null,
      created_at: new Date().toISOString(),
      pending: true,
    }
    this.mergeInbound(convId, optimistic, false)

    try {
      const sent = await sendTextReply(convId, text, replyTo)
      const withoutPending = (this.apiMessages.get(convId) || []).filter((m) => m.id !== tempId)
      this.apiMessages.set(convId, mergeApiMessages(withoutPending, [sent]))
      chat.msgs = mapApiMessages(this.apiMessages.get(convId)!, chat)
      await saveThreadCache(convId, this.apiMessages.get(convId)!)
      this.emit()
    } catch (e) {
      this.apiMessages.set(
        convId,
        (this.apiMessages.get(convId) || []).filter((m) => m.id !== tempId),
      )
      chat.msgs = mapApiMessages(this.apiMessages.get(convId) || [], chat)
      this.error = e instanceof Error ? e.message : String(e)
      this.emit()
      throw e
    }
  }

  async sendImage(convId: number, text: string, file: File): Promise<void> {
    const chat = this.chats.find((c) => c.id === convId)
    if (!chat) return
    const tempId = -Date.now()
    const blobUrl = URL.createObjectURL(file)
    const optimistic: ApiMessage = {
      id: tempId,
      direction: 'outbound',
      text_original: text.trim(),
      text_translated: null,
      created_at: new Date().toISOString(),
      pending: true,
      attachments: [{ id: tempId, kind: 'image', url: blobUrl, mime_type: file.type || 'image/jpeg' }],
    }
    this.mergeInbound(convId, optimistic, false)
    try {
      const sent = await sendImageReply(convId, text, file)
      URL.revokeObjectURL(blobUrl)
      const withoutPending = (this.apiMessages.get(convId) || []).filter((m) => m.id !== tempId)
      this.apiMessages.set(convId, mergeApiMessages(withoutPending, [sent]))
      chat.msgs = mapApiMessages(this.apiMessages.get(convId)!, chat)
      await saveThreadCache(convId, this.apiMessages.get(convId)!)
      this.emit()
    } catch (e) {
      URL.revokeObjectURL(blobUrl)
      this.apiMessages.set(
        convId,
        (this.apiMessages.get(convId) || []).filter((m) => m.id !== tempId),
      )
      chat.msgs = mapApiMessages(this.apiMessages.get(convId) || [], chat)
      this.error = e instanceof Error ? e.message : String(e)
      this.emit()
      throw e
    }
  }

  async loadNotes(convId: number): Promise<void> {
    const chat = this.chats.find((c) => c.id === convId)
    if (!chat) return
    try {
      const rows = await fetchNotes(convId)
      chat.notes.e = rows.map((n: { content?: string; created_at?: string; kind?: string }) => ({
        d: n.created_at ? new Date(n.created_at).toLocaleDateString('ru-RU') : '',
        t: n.content || '',
        ai: String(n.kind || '').startsWith('ai_'),
      }))
      this.emit()
    } catch {
      /* notes optional */
    }
  }

  async addNote(convId: number, content: string): Promise<void> {
    await createNote(convId, content)
    await this.loadNotes(convId)
  }

  async updateTranslation(convId: number, patch: {
    auto_translate_disabled?: boolean
    outbound_lang?: string | null
  }): Promise<void> {
    await patchConversation(convId, patch)
    await this.refreshConversations()
    const chat = this.chats.find((c) => c.id === convId)
    if (chat) {
      if ('auto_translate_disabled' in patch) {
        const on = !patch.auto_translate_disabled
        chat.tr.in = on
        chat.tr.out = on
      }
      if ('outbound_lang' in patch) {
        chat.tr.lang = (patch.outbound_lang || chat.lang || 'en').toLowerCase()
      }
      this.emit()
    }
  }

  applyLocalMessage(convId: number, uiMsg: ReturnType<typeof mapApiMessage>): void {
    const chat = this.chats.find((c) => c.id === convId)
    if (!chat) return
    const api: ApiMessage = {
      id: uiMsg.id,
      direction: uiMsg.out ? 'outbound' : 'inbound',
      text_original: uiMsg.text,
      text_translated: uiMsg.ru || null,
      created_at: new Date().toISOString(),
    }
    this.mergeInbound(convId, api, false)
  }
}
