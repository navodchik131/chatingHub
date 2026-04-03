import EmojiPicker, { type EmojiClickData, Theme } from 'emoji-picker-react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import './App.css'

type Platform = 'telegram' | 'fanvue'

interface Conversation {
  id: number
  platform: Platform
  external_chat_id: string
  external_topic_id: string
  user_display_name: string | null
  user_lang: string | null
  updated_at: string
  last_message_preview: string | null
  unread_count?: number
}

interface ChatMessage {
  id: number
  direction: 'inbound' | 'outbound'
  text_original: string
  text_translated: string | null
  created_at: string
}

function platformLabel(p: Platform): string {
  if (p === 'telegram') return 'Telegram'
  return 'Fanvue'
}

interface HealthInfo {
  ok: boolean
  database_file: string
  backend_dir: string
  conversations_count: number
  messages_count: number
  telegram_bot_configured: boolean
  telegram_api_reachable?: boolean | null
  telegram_bot_username?: string | null
  telegram_api_error?: string | null
  telegram_proxy_configured?: boolean
  fanvue_webhook_secret_configured?: boolean
  fanvue_access_token_configured?: boolean
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [emojiOpen, setEmojiOpen] = useState(false)
  const [showJumpDown, setShowJumpDown] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const sendingRef = useRef(false)
  const messagesContainerRef = useRef<HTMLDivElement | null>(null)
  const composerRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const lastTextareaSelRef = useRef({ start: 0, end: 0 })
  const emojiWrapRef = useRef<HTMLDivElement | null>(null)
  const prevMsgLenRef = useRef(0)

  const loadHealth = useCallback(async () => {
    const r = await fetch('/api/health')
    if (!r.ok) return
    const data: HealthInfo = await r.json()
    setHealth(data)
  }, [])

  const loadConversations = useCallback(async () => {
    const r = await fetch('/api/conversations')
    if (!r.ok) throw new Error('Не удалось загрузить диалоги')
    const data: Conversation[] = await r.json()
    setConversations(data)
  }, [])

  const loadMessages = useCallback(async (id: number) => {
    const r = await fetch(`/api/conversations/${id}/messages`)
    if (!r.ok) throw new Error('Не удалось загрузить сообщения')
    const data: ChatMessage[] = await r.json()
    setMessages(data)
  }, [])

  useEffect(() => {
    loadHealth().catch(() => {
      /* backend down */
    })
    loadConversations().catch((e) => setError(String(e)))
  }, [loadConversations, loadHealth])

  useEffect(() => {
    prevMsgLenRef.current = 0
    setShowJumpDown(false)
  }, [selectedId])

  useEffect(() => {
    if (selectedId == null) {
      setMessages([])
      return
    }
    setMessages([])
    let cancelled = false
    setLoading(true)
    setError(null)
    loadMessages(selectedId)
      .then(async () => {
        if (cancelled) return
        await fetch(`/api/conversations/${selectedId}/read`, { method: 'POST' })
        void loadConversations()
      })
      .catch((e) => setError(String(e)))
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedId, loadMessages, loadConversations])

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}/api/ws`)
    wsRef.current = ws
    ws.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data as string) as {
          type: string
          conversation_id: number
          message?: ChatMessage
        }
        if (payload.type === 'new_message') {
          void loadHealth()
          if (selectedId === payload.conversation_id && payload.message) {
            const mid = Number(payload.message.id)
            setMessages((prev) => {
              if (prev.some((m) => Number(m.id) === mid)) return prev
              return [...prev, payload.message!]
            })
            void fetch(`/api/conversations/${selectedId}/read`, { method: 'POST' })
          }
          void loadConversations()
        }
      } catch {
        /* ignore */
      }
    }
    ws.onerror = () => {
      /* dev: backend may be down */
    }
    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [loadConversations, loadHealth, selectedId])

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (emojiWrapRef.current?.contains(t)) return
      setEmojiOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const scrollToBottom = useCallback((smooth: boolean) => {
    const el = messagesContainerRef.current
    if (!el) return
    const top = el.scrollHeight - el.clientHeight
    if (smooth) {
      el.scrollTo({ top, behavior: 'smooth' })
    } else {
      el.scrollTop = top
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight - el.clientHeight
      })
    }
    setShowJumpDown(false)
  }, [])

  const displayMessages = useMemo(() => {
    const byId = new Map<number, ChatMessage>()
    for (const x of messages) {
      const id = Number(x.id)
      if (!Number.isFinite(id)) continue
      if (!byId.has(id)) byId.set(id, x)
    }
    return [...byId.values()].sort(
      (a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    )
  }, [messages])

  useLayoutEffect(() => {
    const container = messagesContainerRef.current
    if (!container || selectedId == null) return

    if (loading) {
      return
    }

    const len = displayMessages.length
    const prev = prevMsgLenRef.current

    if (len === 0) {
      prevMsgLenRef.current = 0
      return
    }

    // Первая загрузка истории — сразу вниз без анимации
    if (prev === 0 && len > 0) {
      prevMsgLenRef.current = len
      requestAnimationFrame(() => scrollToBottom(false))
      return
    }

    if (len > prev) {
      const dist =
        container.scrollHeight - container.scrollTop - container.clientHeight
      if (dist < 96) {
        requestAnimationFrame(() => scrollToBottom(true))
      } else {
        setShowJumpDown(true)
      }
    }

    prevMsgLenRef.current = len
  }, [displayMessages, loading, selectedId, scrollToBottom])

  const onEmojiPick = useCallback((data: EmojiClickData) => {
    const emoji = data.emoji
    const ta = textareaRef.current
    let start: number
    let end: number
    if (ta && document.activeElement === ta) {
      start = ta.selectionStart
      end = ta.selectionEnd
    } else {
      ;({ start, end } = lastTextareaSelRef.current)
    }
    setDraft((d) => {
      const safeStart = Math.min(Math.max(0, start), d.length)
      const safeEnd = Math.min(Math.max(safeStart, end), d.length)
      const next = d.slice(0, safeStart) + emoji + d.slice(safeEnd)
      const cursor = safeStart + emoji.length
      lastTextareaSelRef.current = { start: cursor, end: cursor }
      requestAnimationFrame(() => {
        const el = textareaRef.current
        if (!el) return
        el.focus()
        try {
          el.setSelectionRange(cursor, cursor)
        } catch {
          /* ignore */
        }
      })
      return next
    })
  }, [])

  const sendReply = async () => {
    if (selectedId == null || !draft.trim()) return
    if (sendingRef.current) return
    sendingRef.current = true
    setError(null)
    try {
      const r = await fetch(`/api/conversations/${selectedId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: draft.trim() }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError((err as { detail?: string }).detail ?? r.statusText)
        return
      }
      const msg: ChatMessage = await r.json()
      const mid = Number(msg.id)
      setMessages((prev) => {
        if (prev.some((m) => Number(m.id) === mid)) return prev
        return [...prev, msg]
      })
      setDraft('')
      setEmojiOpen(false)
      void loadHealth()
      void loadConversations()
      requestAnimationFrame(() => scrollToBottom(true))
    } finally {
      sendingRef.current = false
    }
  }

  const selected = conversations.find((c) => c.id === selectedId)

  return (
    <div className="app">
      <div className="app-bg" aria-hidden />
      <header className="top">
        <div className="top-brand">
          <span className="logo-dot" />
          <div>
            <h1>Chating Hub</h1>
            <p className="sub">
              Входящие с переводом на русский · ответ по-русски уйдёт на языке собеседника
            </p>
          </div>
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}

      {health?.telegram_bot_configured && health.telegram_api_reachable === false && (
        <div className="banner error">
          Нет связи с Telegram API (обычно блокировка исходящего HTTPS к api.telegram.org).
          Включите VPN или задайте <code>TELEGRAM_PROXY</code> в <code>backend/.env</code> и
          перезапустите сервер. Детали: {health.telegram_api_error ?? '—'}
        </div>
      )}

      {health && (
        <div className="health-strip" title={health.database_file}>
          База: {health.conversations_count} диалогов, {health.messages_count} сообщений
          · Telegram:{' '}
          {!health.telegram_bot_configured ? (
            <span className="warn">нет BOT_TOKEN</span>
          ) : health.telegram_api_reachable === true ? (
            <span className="ok">
              API OK @{health.telegram_bot_username ?? '?'}
            </span>
          ) : health.telegram_api_reachable === false ? (
            <span className="warn">API недоступен</span>
          ) : (
            <span className="muted">проверка…</span>
          )}
          {health.telegram_proxy_configured ? (
            <span className="ok"> · прокси</span>
          ) : null}
          {health.fanvue_access_token_configured != null ? (
            <span title="Fanvue API для отправки ответов">
              {' '}
              · Fanvue:{' '}
              {health.fanvue_access_token_configured ? (
                <span className="ok">токен задан</span>
              ) : (
                <span className="warn">нет FANVUE_ACCESS_TOKEN</span>
              )}
            </span>
          ) : null}
        </div>
      )}

      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-head">
            <h2>Диалоги</h2>
            <span className="sidebar-hint">{conversations.length}</span>
          </div>
          {conversations.length === 0 && (
            <p className="muted empty-hint">Подключите бота к Direct messages канала.</p>
          )}
          <ul className="conv-list">
            {conversations.map((c) => {
              const unread = c.unread_count ?? 0
              const hasUnread = unread > 0 && c.id !== selectedId
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    className={
                      c.id === selectedId
                        ? 'conv active'
                        : hasUnread
                          ? 'conv has-unread'
                          : 'conv'
                    }
                    onClick={() => setSelectedId(c.id)}
                  >
                    <span className="conv-row-top">
                      <span className="plat">{platformLabel(c.platform)}</span>
                      {unread > 0 ? (
                        <span className="unread-badge" title="Непрочитанных">
                          {unread > 99 ? '99+' : unread}
                        </span>
                      ) : null}
                    </span>
                    <span className="name">{c.user_display_name ?? 'Без имени'}</span>
                    {c.user_lang && (
                      <span className="lang" title="Язык">
                        {c.user_lang}
                      </span>
                    )}
                    {c.last_message_preview && (
                      <span className="preview">{c.last_message_preview}</span>
                    )}
                  </button>
                </li>
              )
            })}
          </ul>
        </aside>

        <main className="thread">
          {!selected && (
            <div className="empty-thread">
              <div className="empty-card">
                <p className="empty-title">Выберите диалог</p>
                <p className="empty-sub">Слева список переписок с канала</p>
              </div>
            </div>
          )}
          {selected && (
            <>
              <div className="thread-head">
                <div className="thread-avatar" aria-hidden>
                  {(selected.user_display_name ?? '?').slice(0, 1).toUpperCase()}
                </div>
                <div className="thread-head-text">
                  <h3>{selected.user_display_name ?? 'Диалог'}</h3>
                  <span className="meta">
                    {platformLabel(selected.platform)} · topic {selected.external_topic_id}
                  </span>
                </div>
              </div>

              <div className="thread-body">
                {loading ? (
                  <div className="messages-loading">
                    <span className="skeleton-line" />
                    <span className="skeleton-line short" />
                  </div>
                ) : (
                  <div
                    className="messages-scroll"
                    ref={messagesContainerRef}
                    role="log"
                    aria-live="polite"
                    aria-relevant="additions"
                  >
                    {displayMessages.map((m) => (
                      <article
                        key={m.id}
                        className={
                          m.direction === 'inbound'
                            ? 'bubble in msg-enter'
                            : 'bubble out msg-enter'
                        }
                      >
                        {m.direction === 'inbound' ? (
                          <>
                            <div className="ru">{m.text_translated ?? m.text_original}</div>
                            <div className="orig" title="Оригинал">
                              {m.text_original}
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="ru">{m.text_original}</div>
                            <div className="orig" title="Ушло пользователю">
                              → {m.text_translated ?? '—'}
                            </div>
                          </>
                        )}
                        <time>
                          {new Date(m.created_at).toLocaleString('ru-RU', {
                            day: '2-digit',
                            month: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </time>
                      </article>
                    ))}
                    <div className="messages-end" aria-hidden />
                  </div>
                )}

                {showJumpDown && !loading && (
                  <button
                    type="button"
                    className="jump-down"
                    onClick={() => scrollToBottom(true)}
                  >
                    Новые сообщения ↓
                  </button>
                )}

                <div className="composer-shell" ref={composerRef}>
                  <div className="composer-inner" ref={emojiWrapRef}>
                    <div className="composer-toolbar">
                      <button
                        type="button"
                        className="icon-btn"
                        title="Эмодзи"
                        aria-expanded={emojiOpen}
                        aria-haspopup="dialog"
                        onClick={() => setEmojiOpen((o) => !o)}
                      >
                        <span className="icon-emoji" aria-hidden>
                          🙂
                        </span>
                      </button>
                      {emojiOpen && (
                        <div className="emoji-popover">
                          <EmojiPicker
                            theme={Theme.DARK}
                            onEmojiClick={onEmojiPick}
                            width={320}
                            height={380}
                            lazyLoadEmojis
                          />
                        </div>
                      )}
                    </div>
                    <textarea
                      ref={textareaRef}
                      rows={3}
                      placeholder="Ответ по-русски…"
                      value={draft}
                      onSelect={(e) => {
                        const t = e.currentTarget
                        lastTextareaSelRef.current = {
                          start: t.selectionStart,
                          end: t.selectionEnd,
                        }
                      }}
                      onBlur={(e) => {
                        const t = e.currentTarget
                        lastTextareaSelRef.current = {
                          start: t.selectionStart,
                          end: t.selectionEnd,
                        }
                      }}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                          e.preventDefault()
                          void sendReply()
                        }
                      }}
                    />
                    <div className="composer-actions">
                      <span className="hint">Ctrl+Enter — отправить</span>
                      <button
                        type="button"
                        className="send-btn"
                        onClick={() => void sendReply()}
                        disabled={!draft.trim()}
                      >
                        Отправить
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  )
}
