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
  fetchStudioModels,
  setMessageReaction,
  createFolder,
  updateFolder,
  deleteFolder,
  addConversationToFolder,
  removeConversationFromFolder,
  analyzeNotes,
  deleteConversation,
} from '../api/chatApi'
import { connectRealtime, type RealtimeConnection } from '../api/realtime'
import { apiFetch } from '../api/client'
import { getCachedObjectUrl, mediaCacheKey } from '../cache/blobCache'
import {
  loadConversationsCache,
  saveConversationsCache,
  loadThreadCache,
  saveThreadCache,
} from '../cache/threadCache'
import { normalizeLangCode } from '../lib/lang'
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
  StudioModel,
  UiChat,
  UserMe,
} from '../types'

export type ChatListener = () => void

/** Размер страницы при подгрузке истории вверх. */
const THREAD_PAGE = 50

export class ChatController {
  me: UserMe | null = null
  /** Персонажи workspace — переключатель в drawer. */
  models: StudioModel[] = []
  chats: UiChat[] = []
  folders: ConversationFolder[] = []
  activeChatId: number | null = null
  loading = true
  error: string | null = null

  /** Индекс первого непрочитанного в открытом треде (линия «Непрочитанные»). */
  unreadAnchor: Record<number, number> = {}
  /** Object URL медиа mediaKey → url */
  mediaUrls = new Map<string, string>()

  private listeners = new Set<ChatListener>()
  private ws: RealtimeConnection | null = null
  private readTimer: ReturnType<typeof setTimeout> | null = null
  /** Fallback если WS пропустил new_message. */
  private pollTimer: ReturnType<typeof setInterval> | null = null
  private threadLoads = new Map<number, Promise<void>>()
  private apiMessages = new Map<number, ApiMessage[]>()
  /** Последняя сигнатура списка — не дергаем UI без изменений (только фоновый refresh). */
  private lastConversationsSig = ''
  /** Есть ли ещё сообщения старше текущей порции. */
  hasMoreMessages: Record<number, boolean> = {}
  /** Идёт подгрузка истории вверх. */
  loadingOlder: Record<number, boolean> = {}

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

  /** Черновик храним на объекте в this.chats — после refresh список пересоздаётся. */
  setDraft(convId: number, draft: string): void {
    const chat = this.chats.find((c) => c.id === convId)
    if (chat) chat.draft = draft
  }

  clearDraft(convId: number): void {
    this.setDraft(convId, '')
  }

  private conversationsSignature(): string {
    return this.chats
      .map(
        (c) =>
          `${c.id}:${c.unread}:${c.raw.updated_at}:${c.raw.last_message_preview ?? ''}:${c.msgs.length ? c.msgs[c.msgs.length - 1]?.id : 0}`,
      )
      .join('|')
  }

  /** emit для фонового refresh списка — без лишнего кадра, если метаданные те же. */
  private emitListIfChanged(): void {
    const sig = this.conversationsSignature()
    if (sig === this.lastConversationsSig) return
    this.lastConversationsSig = sig
    this.emit()
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
      const [convs, folds, models] = await Promise.all([
        fetchConversations(),
        fetchFolders(),
        fetchStudioModels().catch(() => [] as StudioModel[]),
      ])
      this.models = models
      this.folders = folds
      this.setConversationsFromApi(convs)
      await saveConversationsCache(convs)
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e)
      if (!this.chats.length) throw e
    } finally {
      this.loading = false
      this.emit()
    }

    this.ws?.close()
    this.ws = connectRealtime(
      (msg) => this.onRealtime(msg),
      () => {
        void this.refreshConversations()
        if (this.activeChatId != null) void this.syncThread(this.activeChatId)
      },
    )
    this.startPollFallback()
  }

  destroy(): void {
    this.ws?.close()
    this.ws = null
    if (this.readTimer) clearTimeout(this.readTimer)
    if (this.pollTimer) clearInterval(this.pollTimer)
    this.pollTimer = null
  }

  /** Периодическая подтяжка списка/треда — страховка при обрыве WS или MTProto gap. */
  private startPollFallback(): void {
    if (this.pollTimer) clearInterval(this.pollTimer)
    this.pollTimer = setInterval(() => {
      if (document.visibilityState !== 'visible') return
      void this.refreshConversations()
      // Страховка: WS иногда не шлёт message (gap) — тред открытого чата всё равно подтягиваем.
      if (this.activeChatId != null) void this.syncThread(this.activeChatId)
    }, 12_000)
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
    // После пересборки списка — восстановить тред из apiMessages (WS мог обновить между fetch и map).
    const activeId = this.activeChatId
    if (activeId != null) {
      const chat = this.chats.find((c) => c.id === activeId)
      const api = this.apiMessages.get(activeId)
      if (chat && api?.length) {
        chat.msgs = mapApiMessages(api, chat)
      }
    }
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
    void this.loadNotes(convId)
  }

  private async syncThread(convId: number, opts: { markRead?: boolean } = {}): Promise<void> {
    const existing = this.threadLoads.get(convId)
    if (existing) return existing

    const job = (async () => {
      const chat = this.chats.find((c) => c.id === convId)
      if (!chat) return
      try {
        const fresh = await fetchMessages(convId, THREAD_PAGE)
        const merged = mergeApiMessages(this.apiMessages.get(convId) || [], fresh)
        this.hasMoreMessages[convId] = fresh.length >= THREAD_PAGE
        this.apiMessages.set(convId, merged)
        await saveThreadCache(convId, merged)
        chat.msgs = mapApiMessages(merged, chat)
        this.lastConversationsSig = this.conversationsSignature()
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

  /** Подгрузка более старых сообщений при скролле вверх. */
  async loadOlderMessages(convId: number): Promise<boolean> {
    if (this.loadingOlder[convId] || !this.hasMoreMessages[convId]) return false

    const chat = this.chats.find((c) => c.id === convId)
    const merged = this.apiMessages.get(convId) || []
    const oldest = merged.find((m) => m.id > 0)?.id
    if (!chat || !oldest) return false

    this.loadingOlder[convId] = true
    this.emit()

    try {
      const older = await fetchMessages(convId, THREAD_PAGE, oldest)
      this.hasMoreMessages[convId] = older.length >= THREAD_PAGE
      if (!older.length) return false

      const anchor = this.unreadAnchor[convId]
      if (anchor !== undefined) this.unreadAnchor[convId] = anchor + older.length

      const next = mergeApiMessages(older, merged)
      this.apiMessages.set(convId, next)
      await saveThreadCache(convId, next)
      chat.msgs = mapApiMessages(next, chat)
      this.emit()
      return true
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e)
      this.emit()
      return false
    } finally {
      delete this.loadingOlder[convId]
      this.emit()
    }
  }

  scheduleMarkRead(convId: number): void {
    if (this.readTimer) clearTimeout(this.readTimer)
    this.readTimer = setTimeout(() => {
      void markConversationRead(convId).catch(() => {})
      const c = this.chats.find((x) => x.id === convId)
      if (c) c.unread = 0
      delete this.unreadAnchor[convId]
      this.emitListIfChanged()
    }, 350)
  }

  async refreshConversations(): Promise<void> {
    try {
      const convs = await fetchConversations()
      this.setConversationsFromApi(convs)
      await saveConversationsCache(convs)
      this.emitListIfChanged()
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

    this.lastConversationsSig = this.conversationsSignature()
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
      return
    }
    if (ev.type === 'conversation_read') {
      const readId = Number(ev.conversation_id)
      const chat = this.chats.find((c) => c.id === readId)
      if (chat) {
        chat.unread = 0
        if (this.activeChatId === readId) delete this.unreadAnchor[readId]
        this.emitListIfChanged()
      }
    }
  }

  async sendText(convId: number, text: string, replyTo?: number | null): Promise<void> {
    const chat = this.chats.find((c) => c.id === convId)
    if (!chat || !text.trim()) return

    this.clearDraft(convId)

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
    if (text.trim()) this.clearDraft(convId)
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
      const next = rows.map((n: { content?: string; created_at?: string; kind?: string }) => ({
        d: n.created_at ? new Date(n.created_at).toLocaleDateString('ru-RU') : '',
        t: n.content || '',
        ai: String(n.kind || '').startsWith('ai_'),
      }))
      const sig = next.map((n) => `${n.d}:${n.t}`).join('\n')
      const prev = chat.notes.e.map((n) => `${n.d}:${n.t}`).join('\n')
      chat.notes.e = next
      if (sig !== prev) this.emit()
    } catch {
      /* notes optional */
    }
  }

  async addNote(convId: number, content: string): Promise<void> {
    await createNote(convId, content)
    await this.loadNotes(convId)
  }

  async toggleReaction(convId: number, messageId: number, emoji: string): Promise<void> {
    const chat = this.chats.find((c) => c.id === convId)
    if (!chat || messageId <= 0) return
    const updated = await setMessageReaction(convId, messageId, emoji)
    const merged = mergeApiMessages(this.apiMessages.get(convId) || [], [updated])
    this.apiMessages.set(convId, merged)
    chat.msgs = mapApiMessages(merged, chat)
    await saveThreadCache(convId, merged)
    this.emit()
  }

  async createUserFolder(name: string, conversationIds: number[] = []): Promise<ConversationFolder> {
    const folder = await createFolder(name.trim(), conversationIds)
    this.folders = [...this.folders, folder]
    this.emit()
    return folder
  }

  async renameUserFolder(folderId: number, name: string): Promise<void> {
    const folder = await updateFolder(folderId, { name: name.trim() })
    this.folders = this.folders.map((f) => (f.id === folderId ? folder : f))
    this.emit()
  }

  async removeUserFolder(folderId: number): Promise<void> {
    await deleteFolder(folderId)
    this.folders = this.folders.filter((f) => f.id !== folderId)
    this.emit()
  }

  async addChatToFolder(folderId: number, convId: number): Promise<void> {
    const folder = await addConversationToFolder(folderId, convId)
    this.folders = this.folders.map((f) => (f.id === folderId ? folder : f))
    this.emit()
  }

  async removeChatFromFolder(folderId: number, convId: number): Promise<void> {
    const folder = await removeConversationFromFolder(folderId, convId)
    this.folders = this.folders.map((f) => (f.id === folderId ? folder : f))
    this.emit()
  }

  async updateTranslation(convId: number, patch: {
    auto_translate_disabled?: boolean
    outbound_lang?: string | null
  }): Promise<void> {
    await this.updateSettings(convId, patch)
  }

  /** PATCH настроек диалога: перевод, companion, категория. */
  async updateSettings(convId: number, patch: Record<string, unknown>): Promise<void> {
    const updated = await patchConversation(convId, patch)
    const chat = this.chats.find((c) => c.id === convId)
    if (chat) {
      chat.raw = { ...chat.raw, ...updated }
      if ('auto_translate_disabled' in patch) {
        const on = !patch.auto_translate_disabled
        chat.tr.in = on
        chat.tr.out = on
      }
      if ('outbound_lang' in patch) {
        // NULL outbound_lang = авто по user_lang (язык фана)
        const forced = normalizeLangCode(updated.outbound_lang)
        chat.tr.lang = forced || normalizeLangCode(updated.user_lang) || chat.lang || 'en'
      }
      if ('manual_category' in patch) {
        chat.pinned = updated.manual_category === 'vip'
        chat.biz = updated.manual_category === 'bomzh'
      }
      if ('companion_mode_override' in patch) {
        chat.raw.companion_mode_override = updated.companion_mode_override
        chat.raw.effective_companion_mode = updated.effective_companion_mode
      }
    }
    this.emit()
  }

  async runNotesAnalyze(convId: number): Promise<void> {
    await analyzeNotes(convId)
    await this.loadNotes(convId)
  }

  /** Убрать диалог из списка (soft hide на сервере). */
  async hideConversation(convId: number): Promise<void> {
    await deleteConversation(convId)
    this.chats = this.chats.filter((c) => c.id !== convId)
    if (this.activeChatId === convId) this.activeChatId = null
    this.apiMessages.delete(convId)
    this.emit()
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
