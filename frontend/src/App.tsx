import EmojiPicker, { type EmojiClickData, Theme } from 'emoji-picker-react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { apiFetch, getToken, setToken } from './api'
import {
  getPushSubscriptionState,
  subscribeWebPush,
  unsubscribeWebPush,
  webPushEnvironmentOk,
} from './webPush'
import { formatApiErrorDetail } from './apiErrors'
import { AuthPanel } from './AuthPanel'
import './App.css'
import {
  DEFAULT_MEMBER_PERMISSIONS,
  MEMBER_PERMISSION_LABELS,
  PERM_INTEGRATIONS,
  PERM_STUDIO_GENERATE,
  PERM_STUDIO_MODELS,
  hasAllBits,
  togglePermission,
} from './workspacePermissions'

type Platform = 'telegram' | 'fanvue'

interface Conversation {
  id: number
  platform: Platform
  external_chat_id: string
  external_topic_id: string
  user_display_name: string | null
  user_lang: string | null
  /** Принудительный язык исходящих (ISO); null/undefined = авто по user_lang */
  outbound_lang?: string | null
  updated_at: string
  last_message_preview: string | null
  unread_count?: number
  has_avatar?: boolean
}

/** Языки для перевода исходящих (совпадают с типичными целями DeepL/Google). */
const OUTBOUND_LANG_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Авто (по переписке)' },
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
  { value: 'fr', label: 'Français' },
  { value: 'es', label: 'Español' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Português' },
  { value: 'ru', label: 'Русский' },
  { value: 'uk', label: 'Українська' },
  { value: 'pl', label: 'Polski' },
  { value: 'tr', label: 'Türkçe' },
  { value: 'nl', label: 'Nederlands' },
  { value: 'sv', label: 'Svenska' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'zh', label: '中文' },
]

interface ChatMessage {
  id: number
  direction: 'inbound' | 'outbound'
  text_original: string
  text_translated: string | null
  created_at: string
  /** Локальный черновик до ответа сервера (перевод ещё готовится). */
  pending?: boolean
}

function platformLabel(p: Platform): string {
  if (p === 'telegram') return 'Telegram'
  return 'Fanvue'
}

/** Загрузка аватара с авторизацией (JWT не передать через обычный src у img). */
function useConversationAvatarBlob(convId: number | null, hasAvatar: boolean) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (convId == null || !hasAvatar) {
      setUrl((u) => {
        if (u) URL.revokeObjectURL(u)
        return null
      })
      return
    }
    let cancelled = false
    void (async () => {
      const r = await apiFetch(`/api/conversations/${convId}/avatar`)
      if (cancelled || !r.ok) return
      const blob = await r.blob()
      if (cancelled) return
      const u = URL.createObjectURL(blob)
      setUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return u
      })
    })()
    return () => {
      cancelled = true
      setUrl((u) => {
        if (u) URL.revokeObjectURL(u)
        return null
      })
    }
  }, [convId, hasAvatar])

  return url
}

function ConvAvatarThumb({ conv }: { conv: Conversation }) {
  const url = useConversationAvatarBlob(conv.id, Boolean(conv.has_avatar))
  const letter = (conv.user_display_name ?? '?').slice(0, 1).toUpperCase()
  return (
    <span className="conv-avatar" aria-hidden>
      {url ? <img src={url} alt="" /> : letter}
    </span>
  )
}

function ThreadAvatar({ conv }: { conv: Conversation }) {
  const url = useConversationAvatarBlob(conv.id, Boolean(conv.has_avatar))
  const letter = (conv.user_display_name ?? '?').slice(0, 1).toUpperCase()
  return (
    <div className="thread-avatar" aria-hidden>
      {url ? <img src={url} alt="" /> : letter}
    </div>
  )
}

/** Миниатюра в горизонтальной ленте чатов (PWA / мобильный). */
function ChatStripItem({
  conv,
  active,
  onSelect,
}: {
  conv: Conversation
  active: boolean
  onSelect: () => void
}) {
  const url = useConversationAvatarBlob(conv.id, Boolean(conv.has_avatar))
  const letter = (conv.user_display_name ?? '?').slice(0, 1).toUpperCase()
  const unread = conv.unread_count ?? 0
  return (
    <button
      type="button"
      className={`chat-strip-item ${active ? 'is-active' : ''}`}
      onClick={onSelect}
      title={conv.user_display_name ?? 'Диалог'}
      aria-label={conv.user_display_name ?? 'Диалог'}
      aria-current={active ? 'true' : undefined}
    >
      <span className="chat-strip-item-inner">
        {url ? <img src={url} alt="" /> : <span className="chat-strip-letter">{letter}</span>}
        {unread > 0 ? <span className="chat-strip-unread" aria-label="Непрочитанные" /> : null}
      </span>
    </button>
  )
}

interface HealthInfo {
  ok: boolean
  mode?: string
  database_file?: string
  backend_dir?: string
  conversations_count?: number
  messages_count?: number
  legacy_telegram_polling?: boolean
  telegram_api_reachable?: boolean | null
  telegram_bot_username?: string | null
  telegram_api_error?: string | null
  telegram_proxy_configured?: boolean
  stripe_configured?: boolean
  openai_studio_configured?: boolean
  studio_prompt_credit_cost?: number
  web_push_configured?: boolean
}

interface UserMe {
  id: number
  email: string
  subscription_status: string
  credits_balance: number
  is_workspace_owner: boolean
  workspace_owner_id: number
  member_login: string | null
  permissions_mask: number
  owner_email: string
}

interface WorkspaceMemberRow {
  id: number
  member_login: string
  permissions_mask: number
  is_active: boolean
}

interface IntegrationStatus {
  telegram_configured: boolean
  telegram_bot_username: string | null
  fanvue_configured: boolean
  fanvue_creator_uuid: string | null
  fanvue_webhook_url: string | null
  telegram_webhook_url: string | null
  telegram_webhook_registered?: boolean
  integration_hint?: string | null
  wavespeed_configured?: boolean
}

interface StudioModelImage {
  id: number
  url: string
}

interface UserStudioModel {
  id: number
  name: string
  profile_text: string
  image_count: number
  images?: StudioModelImage[]
}

type AccountCabinetTab = 'integrations' | 'models' | 'team'

interface StudioAspectPreset {
  key: string
  label: string
  size: string
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
  const [outboundLangBusy, setOutboundLangBusy] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const selectedIdRef = useRef<number | null>(null)
  const pendingOutboundIdRef = useRef(0)
  const messagesContainerRef = useRef<HTMLDivElement | null>(null)
  const composerRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const lastTextareaSelRef = useRef({ start: 0, end: 0 })
  const emojiWrapRef = useRef<HTMLDivElement | null>(null)
  const prevMsgLenRef = useRef(0)

  const [isMobileLayout, setIsMobileLayout] = useState(false)
  const [authReady, setAuthReady] = useState(false)
  const [authed, setAuthed] = useState(false)
  const [me, setMe] = useState<UserMe | null>(null)
  const {
    isOwner,
    canChat,
    canStudioGenerate,
    canStudioModels,
    canIntegrations,
    canStudioAny,
    hasAnyMainSection,
  } = useMemo(() => {
    if (!me) {
      return {
        isOwner: false,
        canChat: false,
        canStudioGenerate: false,
        canStudioModels: false,
        canIntegrations: false,
        canStudioAny: false,
        hasAnyMainSection: false,
      }
    }
    const owner = me.is_workspace_owner
    const m = me.permissions_mask
    const chat = owner || hasAllBits(m, 1)
    const gen = owner || hasAllBits(m, PERM_STUDIO_GENERATE)
    const models = owner || hasAllBits(m, PERM_STUDIO_MODELS)
    const integ = owner || hasAllBits(m, PERM_INTEGRATIONS)
    const studioAny = owner || !!(m & (PERM_STUDIO_GENERATE | PERM_STUDIO_MODELS))
    return {
      isOwner: owner,
      canChat: chat,
      canStudioGenerate: gen,
      canStudioModels: models,
      canIntegrations: integ,
      canStudioAny: studioAny,
      hasAnyMainSection: chat || studioAny,
    }
  }, [me])

  const [accountOpen, setAccountOpen] = useState(false)
  const [accountTab, setAccountTab] = useState<AccountCabinetTab>('integrations')
  const [workspaceMembers, setWorkspaceMembers] = useState<WorkspaceMemberRow[]>([])
  const [teamBusy, setTeamBusy] = useState(false)
  const [newTeamLogin, setNewTeamLogin] = useState('')
  const [newTeamPassword, setNewTeamPassword] = useState('')
  const [newTeamMask, setNewTeamMask] = useState(DEFAULT_MEMBER_PERMISSIONS)
  const [memberEditPassword, setMemberEditPassword] = useState<Record<number, string>>({})
  const [memberMaskEdits, setMemberMaskEdits] = useState<Record<number, number>>({})
  const [integ, setInteg] = useState<IntegrationStatus | null>(null)
  const [modelDrafts, setModelDrafts] = useState<Record<number, { name: string; profile_text: string }>>(
    {},
  )
  const [modelSavingId, setModelSavingId] = useState<number | null>(null)
  const [tgToken, setTgToken] = useState('')
  const [fvToken, setFvToken] = useState('')
  const [fvCreator, setFvCreator] = useState('')
  const [fvSecret, setFvSecret] = useState('')

  const [appSection, setAppSection] = useState<'chat' | 'studio'>('chat')
  const [studioDesc, setStudioDesc] = useState('')
  const [studioFile, setStudioFile] = useState<File | null>(null)
  const [studioBusy, setStudioBusy] = useState(false)
  const [studioModels, setStudioModels] = useState<UserStudioModel[]>([])
  const [studioSelectedModelId, setStudioSelectedModelId] = useState<number | null>(null)
  const [newModelName, setNewModelName] = useState('')
  const [newModelProfile, setNewModelProfile] = useState('')
  const [newModelFiles, setNewModelFiles] = useState<File[]>([])
  const [wsApiKey, setWsApiKey] = useState('')
  const [webPushState, setWebPushState] = useState<
    'unknown' | 'loading' | 'on' | 'off' | 'denied' | 'unsupported' | 'no_vapid'
  >('unknown')
  const [pushBusy, setPushBusy] = useState(false)
  const [studioGenImageUrl, setStudioGenImageUrl] = useState<string | null>(null)
  const [studioWavespeedMsg, setStudioWavespeedMsg] = useState<string | null>(null)
  const [studioAspectPresets, setStudioAspectPresets] = useState<StudioAspectPreset[]>([])
  const [studioOutputAspect, setStudioOutputAspect] = useState('9:16')

  useEffect(() => {
    selectedIdRef.current = selectedId
  }, [selectedId])

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 720px)')
    const apply = () => setIsMobileLayout(mq.matches)
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  useEffect(() => {
    const boot = async () => {
      const t = getToken()
      if (!t) {
        setAuthed(false)
        setAuthReady(true)
        return
      }
      const r = await apiFetch('/api/auth/me')
      if (!r.ok) {
        setToken(null)
        setAuthed(false)
      } else {
        setMe((await r.json()) as UserMe)
        setAuthed(true)
      }
      setAuthReady(true)
    }
    void boot()
  }, [])

  const refreshMe = useCallback(async () => {
    const r = await apiFetch('/api/auth/me')
    if (r.ok) setMe((await r.json()) as UserMe)
  }, [])

  const refreshWorkspaceMembers = useCallback(async () => {
    const r = await apiFetch('/api/workspace/members')
    if (r.ok) setWorkspaceMembers((await r.json()) as WorkspaceMemberRow[])
  }, [])

  const refreshIntegrations = useCallback(async () => {
    const r = await apiFetch('/api/integrations')
    if (r.ok) setInteg((await r.json()) as IntegrationStatus)
  }, [])

  const enableWebPush = useCallback(async () => {
    setPushBusy(true)
    setError(null)
    try {
      await subscribeWebPush()
      setWebPushState('on')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setPushBusy(false)
    }
  }, [])

  const disableWebPush = useCallback(async () => {
    setPushBusy(true)
    setError(null)
    try {
      await unsubscribeWebPush()
      setWebPushState('off')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setPushBusy(false)
    }
  }, [])

  const loadStudioModels = useCallback(async () => {
    const r = await apiFetch('/api/studio/models')
    if (r.ok) setStudioModels((await r.json()) as UserStudioModel[])
  }, [])

  useEffect(() => {
    setModelDrafts(
      Object.fromEntries(
        studioModels.map((m) => [m.id, { name: m.name, profile_text: m.profile_text }]),
      ) as Record<number, { name: string; profile_text: string }>,
    )
  }, [studioModels])

  useEffect(() => {
    if (!me || !accountOpen) return
    if (accountTab === 'models' && !canStudioModels) setAccountTab('integrations')
    if (accountTab === 'team' && !isOwner) setAccountTab('integrations')
  }, [me, accountOpen, accountTab, canStudioModels, isOwner])

  useEffect(() => {
    if (!me) return
    if (appSection === 'chat' && !canChat && canStudioAny) setAppSection('studio')
    if (appSection === 'studio' && !canStudioAny && canChat) setAppSection('chat')
  }, [me?.id, appSection, canChat, canStudioAny])

  useEffect(() => {
    if (authed && accountOpen) void refreshIntegrations()
  }, [authed, accountOpen, refreshIntegrations])

  useEffect(() => {
    if (!authed) return
    const needModels =
      (appSection === 'studio' && canStudioAny) ||
      (accountOpen && accountTab === 'models' && canStudioModels)
    if (needModels) void loadStudioModels()
  }, [authed, accountOpen, accountTab, appSection, canStudioAny, canStudioModels, loadStudioModels])

  useEffect(() => {
    if (authed && accountOpen && accountTab === 'team' && isOwner) void refreshWorkspaceMembers()
  }, [authed, accountOpen, accountTab, isOwner, refreshWorkspaceMembers])

  useEffect(() => {
    setMemberMaskEdits(Object.fromEntries(workspaceMembers.map((x) => [x.id, x.permissions_mask])))
  }, [workspaceMembers])

  useEffect(() => {
    if (authed && appSection === 'studio') void refreshIntegrations()
  }, [authed, appSection, refreshIntegrations])

  useEffect(() => {
    if (!authed || appSection !== 'studio') return
    fetch('/api/studio/output-aspects')
      .then((r) => r.json())
      .then((d: { aspects?: StudioAspectPreset[] }) => {
        if (Array.isArray(d.aspects) && d.aspects.length > 0) setStudioAspectPresets(d.aspects)
      })
      .catch(() => {
        /* ignore */
      })
  }, [authed, appSection])

  const loadHealth = useCallback(async () => {
    const r = await fetch('/api/health')
    if (!r.ok) return
    const data: HealthInfo = await r.json()
    setHealth(data)
  }, [])

  const loadConversations = useCallback(async () => {
    const r = await apiFetch('/api/conversations')
    if (!r.ok) throw new Error('Не удалось загрузить диалоги')
    const data: Conversation[] = await r.json()
    setConversations(data)
  }, [])

  const loadMessages = useCallback(async (id: number) => {
    const r = await apiFetch(`/api/conversations/${id}/messages`)
    if (!r.ok) throw new Error('Не удалось загрузить сообщения')
    const data: ChatMessage[] = await r.json()
    setMessages(data)
  }, [])

  useEffect(() => {
    loadHealth().catch(() => {
      /* backend down */
    })
    if (!authed || !canChat) return
    loadConversations().catch((e) => setError(String(e)))
  }, [loadConversations, loadHealth, authed, canChat])

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('conv')
    if (!q) return
    const id = parseInt(q, 10)
    if (Number.isNaN(id)) return
    if (conversations.some((c) => c.id === id)) {
      setSelectedId(id)
    }
  }, [conversations])

  useEffect(() => {
    if (!accountOpen || accountTab !== 'integrations' || !authed || !canChat) return
    if (!health?.web_push_configured) {
      setWebPushState('no_vapid')
      return
    }
    if (!webPushEnvironmentOk()) {
      setWebPushState('unsupported')
      return
    }
    if (Notification.permission === 'denied') {
      setWebPushState('denied')
      return
    }
    setWebPushState('loading')
    void getPushSubscriptionState().then((s) => {
      setWebPushState(s ? 'on' : 'off')
    })
  }, [accountOpen, accountTab, authed, canChat, health?.web_push_configured])

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
        await apiFetch(`/api/conversations/${selectedId}/read`, { method: 'POST' })
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
    if (!authed) return
    const tok = getToken()
    if (!tok) return

    let cancelled = false
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let attempt = 0
    let ws: WebSocket | null = null

    const onMessage = (ev: MessageEvent) => {
      try {
        const payload = JSON.parse(ev.data as string) as {
          type: string
          conversation_id: number
          message?: ChatMessage
        }
        if (payload.type === 'new_message') {
          void loadHealth()
          const sid = selectedIdRef.current
          if (sid != null && sid === payload.conversation_id && payload.message) {
            const mid = Number(payload.message.id)
            const incoming = payload.message as ChatMessage
            setMessages((prev) => {
              if (prev.some((m) => Number(m.id) === mid)) return prev
              let next = prev
              if (incoming.direction === 'outbound') {
                const txt = incoming.text_original
                const i = next.findIndex(
                  (m) => m.pending && m.direction === 'outbound' && m.text_original === txt,
                )
                if (i !== -1) {
                  next = next.slice(0, i).concat(next.slice(i + 1))
                }
              }
              return [...next, incoming]
            })
            void apiFetch(`/api/conversations/${sid}/read`, { method: 'POST' })
          }
          void loadConversations()
        }
      } catch {
        /* ignore */
      }
    }

    const connect = () => {
      if (cancelled) return
      const t = getToken()
      if (!t) return
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
      const q = encodeURIComponent(t)
      ws = new WebSocket(`${proto}//${location.host}/api/ws?token=${q}`)
      wsRef.current = ws
      ws.onopen = () => {
        attempt = 0
      }
      ws.onmessage = onMessage
      ws.onerror = () => {
        /* dev: backend may be down */
      }
      ws.onclose = () => {
        wsRef.current = null
        if (cancelled) return
        const delay = Math.min(30_000, 800 * 2 ** Math.min(attempt, 6))
        attempt += 1
        retryTimer = setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (retryTimer) clearTimeout(retryTimer)
      ws?.close()
      wsRef.current = null
    }
  }, [loadConversations, loadHealth, authed])

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

  const saveOutboundLang = async (convId: number, raw: string) => {
    const v = raw === '' ? null : raw
    setError(null)
    setOutboundLangBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ outbound_lang: v }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(err) || r.statusText)
        return
      }
      const updated = (await r.json()) as Conversation
      setConversations((prev) => prev.map((c) => (c.id === convId ? { ...c, ...updated } : c)))
    } catch {
      setError('Не удалось сохранить язык ответа')
    } finally {
      setOutboundLangBusy(false)
    }
  }

  const sendReply = async () => {
    if (selectedId == null || !draft.trim()) return
    const convId = selectedId
    const text = draft.trim()
    pendingOutboundIdRef.current -= 1
    const tempId = pendingOutboundIdRef.current
    const optimistic: ChatMessage = {
      id: tempId,
      direction: 'outbound',
      text_original: text,
      text_translated: null,
      created_at: new Date().toISOString(),
      pending: true,
    }
    setError(null)
    setDraft('')
    setEmojiOpen(false)
    setMessages((prev) => [...prev, optimistic])
    requestAnimationFrame(() => scrollToBottom(true))
    try {
      const r = await apiFetch(`/api/conversations/${convId}/reply`, {
        method: 'POST',
        body: JSON.stringify({ text }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(err) || r.statusText)
        setMessages((prev) => {
          if (selectedIdRef.current !== convId) return prev
          return prev.filter((m) => m.id !== tempId)
        })
        setDraft((d) => (d.trim() ? `${text}\n\n${d}` : text))
        return
      }
      const msg: ChatMessage = await r.json()
      const mid = Number(msg.id)
      setMessages((prev) => {
        if (selectedIdRef.current !== convId) return prev
        const without = prev.filter((m) => m.id !== tempId)
        if (without.some((m) => Number(m.id) === mid)) return without
        return [...without, msg]
      })
      void loadHealth()
      void loadConversations()
      void refreshMe()
      requestAnimationFrame(() => scrollToBottom(true))
    } catch {
      setMessages((prev) => {
        if (selectedIdRef.current !== convId) return prev
        return prev.filter((m) => m.id !== tempId)
      })
      setDraft((d) => (d.trim() ? `${text}\n\n${d}` : text))
      setError('Не удалось отправить сообщение')
    }
  }

  const refineStudioPrompt = async () => {
    setError(null)
    if (!studioDesc.trim() && !studioFile && studioSelectedModelId == null) {
      setError('Добавьте описание, референс и/или выберите сохранённую модель.')
      return
    }
    setStudioBusy(true)
    setStudioGenImageUrl(null)
    setStudioWavespeedMsg(null)
    try {
      const fd = new FormData()
      fd.append('description', studioDesc.trim())
      if (studioSelectedModelId != null) fd.append('model_id', String(studioSelectedModelId))
      if (studioFile) fd.append('image', studioFile)
      fd.append('output_aspect', studioOutputAspect)
      fd.append('generate_wavespeed', '1')
      fd.append('wavespeed_single_reference', '1')
      const r = await apiFetch('/api/studio/refine-prompt', { method: 'POST', body: fd })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      const data = (await r.json()) as {
        refined_prompt: string
        reference_scene_description?: string | null
        generated_image_url?: string | null
        wavespeed_message?: string | null
      }
      setStudioGenImageUrl(data.generated_image_url?.trim() || null)
      setStudioWavespeedMsg(data.wavespeed_message?.trim() || null)
      void refreshMe()
    } catch (e) {
      setError(e instanceof TypeError && e.message === 'Failed to fetch' ? 'Сеть: не удалось связаться с сервером (проверьте, что бэкенд запущен и порт / proxy).' : (e instanceof Error ? e.message : 'Неизвестная ошибка запроса'))
    } finally {
      setStudioBusy(false)
    }
  }

  const saveWavespeed = async () => {
    setError(null)
    const k = wsApiKey.trim()
    if (k.length < 8) {
      setError('Вставьте API-ключ WaveSpeed (личный кабинет wavespeed.ai).')
      return
    }
    const r = await apiFetch('/api/integrations/wavespeed', {
      method: 'PUT',
      body: JSON.stringify({ api_key: k }),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    setWsApiKey('')
    setInteg((await r.json()) as IntegrationStatus)
  }

  const createStudioModel = async () => {
    setError(null)
    const name = newModelName.trim()
    if (!name) {
      setError('Укажите название модели.')
      return
    }
    const fd = new FormData()
    fd.append('name', name)
    fd.append('profile_text', newModelProfile.trim())
    for (const f of newModelFiles) fd.append('images', f)
    const r = await apiFetch('/api/studio/models', { method: 'POST', body: fd })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    setNewModelName('')
    setNewModelProfile('')
    setNewModelFiles([])
    void loadStudioModels()
  }

  const deleteStudioModel = async (id: number) => {
    setError(null)
    const r = await apiFetch(`/api/studio/models/${id}`, { method: 'DELETE' })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    if (studioSelectedModelId === id) setStudioSelectedModelId(null)
    void loadStudioModels()
  }

  const patchStudioModel = async (id: number) => {
    const d = modelDrafts[id]
    if (!d) return
    setError(null)
    setModelSavingId(id)
    try {
      const r = await apiFetch(`/api/studio/models/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: d.name.trim(), profile_text: d.profile_text }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      void loadStudioModels()
    } finally {
      setModelSavingId(null)
    }
  }

  const appendStudioModelImages = async (id: number, files: FileList | null) => {
    if (!files?.length) return
    setError(null)
    setModelSavingId(id)
    try {
      const fd = new FormData()
      for (const f of Array.from(files)) fd.append('images', f)
      const r = await apiFetch(`/api/studio/models/${id}/images`, { method: 'POST', body: fd })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      void loadStudioModels()
    } finally {
      setModelSavingId(null)
    }
  }

  const deleteStudioModelImage = async (modelId: number, imageId: number) => {
    setError(null)
    const r = await apiFetch(`/api/studio/models/${modelId}/images/${imageId}`, {
      method: 'DELETE',
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    void loadStudioModels()
  }

  const saveTelegram = async () => {
    setError(null)
    const tok = tgToken.trim()
    if (tok.length < 15) {
      setError('Вставьте полный токен бота от BotFather (обычно длиннее 40 символов).')
      return
    }
    const r = await apiFetch('/api/integrations/telegram', {
      method: 'PUT',
      body: JSON.stringify({ bot_token: tok }),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    setTgToken('')
    setInteg((await r.json()) as IntegrationStatus)
    void refreshMe()
  }

  const saveFanvue = async () => {
    setError(null)
    const r = await apiFetch('/api/integrations/fanvue', {
      method: 'PUT',
      body: JSON.stringify({
        access_token: fvToken.trim(),
        creator_uuid: fvCreator.trim(),
        webhook_signing_secret: fvSecret.trim(),
      }),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    setFvToken('')
    setFvSecret('')
    setInteg((await r.json()) as IntegrationStatus)
    void refreshMe()
  }

  const createWorkspaceMember = async () => {
    setError(null)
    const login = newTeamLogin.trim().toLowerCase()
    if (login.length < 3) {
      setError('Логин сотрудника: от 3 символов (латиница, цифры, подчёркивание).')
      return
    }
    if (newTeamPassword.length < 8) {
      setError('Пароль сотрудника: минимум 8 символов.')
      return
    }
    setTeamBusy(true)
    try {
      const r = await apiFetch('/api/workspace/members', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          member_login: login,
          password: newTeamPassword,
          permissions_mask: newTeamMask,
        }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      setNewTeamLogin('')
      setNewTeamPassword('')
      setNewTeamMask(DEFAULT_MEMBER_PERMISSIONS)
      void refreshWorkspaceMembers()
    } finally {
      setTeamBusy(false)
    }
  }

  const saveWorkspaceMemberRow = async (row: WorkspaceMemberRow) => {
    setError(null)
    const mask = memberMaskEdits[row.id] ?? row.permissions_mask
    const pwd = (memberEditPassword[row.id] || '').trim()
    if (pwd.length > 0 && pwd.length < 8) {
      setError('Новый пароль: минимум 8 символов или оставьте поле пустым.')
      return
    }
    setTeamBusy(true)
    try {
      const body: { permissions_mask: number; password?: string } = { permissions_mask: mask }
      if (pwd.length >= 8) body.password = pwd
      const r = await apiFetch(`/api/workspace/members/${row.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      setMemberEditPassword((p) => ({ ...p, [row.id]: '' }))
      void refreshWorkspaceMembers()
    } finally {
      setTeamBusy(false)
    }
  }

  const setWorkspaceMemberActive = async (row: WorkspaceMemberRow, active: boolean) => {
    setError(null)
    const r = await apiFetch(`/api/workspace/members/${row.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: active }),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    void refreshWorkspaceMembers()
  }

  const removeWorkspaceMember = async (id: number) => {
    if (!window.confirm('Удалить участника? Его доступ будет отозван.')) return
    setError(null)
    const r = await apiFetch(`/api/workspace/members/${id}`, { method: 'DELETE' })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    void refreshWorkspaceMembers()
  }

  const startCheckout = async () => {
    setError(null)
    const r = await apiFetch('/api/billing/checkout', { method: 'POST' })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    const data = (await r.json()) as { url: string }
    window.location.href = data.url
  }

  if (!authReady) {
    return (
      <div className="app">
        <div className="app-bg" aria-hidden />
        <p className="muted" style={{ padding: '2rem' }}>
          Загрузка…
        </p>
      </div>
    )
  }

  if (!authed) {
    return (
      <div className="app app-auth">
        <div className="app-bg" aria-hidden />
        <header className="top top-auth">
          <div className="top-brand">
            <span className="logo-mark" aria-hidden />
            <div>
              <h1>Chating Hub</h1>
              <p className="sub">SaaS-кабинет: регистрация и подключение своих ботов</p>
            </div>
          </div>
        </header>
        <main className="auth-page">
          <AuthPanel
            onSuccess={async () => {
              const r = await apiFetch('/api/auth/me')
              if (r.ok) setMe((await r.json()) as UserMe)
              setAuthed(true)
            }}
          />
        </main>
      </div>
    )
  }

  const selected = conversations.find((c) => c.id === selectedId)

  const showThreadDock = Boolean(
    isMobileLayout && selectedId != null && appSection === 'chat' && canChat,
  )

  const layoutClass = [
    'layout',
    isMobileLayout ? 'mobile' : '',
    isMobileLayout && selectedId != null ? 'thread-focus' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const appClass = [
    'app',
    isMobileLayout && selectedId != null ? 'mobile-chat-open' : '',
    showThreadDock ? 'with-thread-dock' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={appClass}>
      <div className="app-bg" aria-hidden />
      {showThreadDock ? (
        <header className="thread-mobile-dock">
          <div className="thread-mobile-dock-inner">
            <button
              type="button"
              className="thread-mobile-dock-back"
              onClick={() => setSelectedId(null)}
              aria-label="Назад к списку диалогов"
            >
              <span aria-hidden>‹</span>
            </button>
            <div
              className="thread-mobile-dock-scroll"
              role="tablist"
              aria-label="Другие диалоги"
            >
              {conversations.map((c) => (
                <ChatStripItem
                  key={c.id}
                  conv={c}
                  active={c.id === selectedId}
                  onSelect={() => setSelectedId(c.id)}
                />
              ))}
            </div>
          </div>
        </header>
      ) : null}
      <header className="top">
        <div className="top-brand">
          <span className="logo-mark" aria-hidden />
          <div>
            <h1>Chating Hub</h1>
            <p className="sub">
              Входящие на русский · исходящий язык: авто или вручную в шапке диалога
            </p>
          </div>
        </div>
        <div className="top-actions">
          {me ? (
            <div
              className="user-pill"
              title={
                me.is_workspace_owner
                  ? me.email
                  : `${me.owner_email} · сотрудник «${me.member_login ?? '—'}»`
              }
            >
              <span className="user-pill-email">
                {me.is_workspace_owner ? me.email : `${me.owner_email} · ${me.member_login ?? '—'}`}
              </span>
              <span className="user-pill-meta">
                {me.credits_balance} кр. · {me.subscription_status}
              </span>
            </div>
          ) : null}
          <button type="button" className="ghost-btn" onClick={() => setAccountOpen((o) => !o)}>
            Кабинет
          </button>
          <button
            type="button"
            className="ghost-btn"
            onClick={() => {
              setToken(null)
              setAuthed(false)
              setMe(null)
              setConversations([])
              setSelectedId(null)
            }}
          >
            Выйти
          </button>
        </div>
      </header>

      {error && <div className="banner error">{error}</div>}

      {hasAnyMainSection ? (
        <nav className="section-nav" aria-label="Разделы приложения">
          {canChat ? (
            <button
              type="button"
              className={appSection === 'chat' ? 'section-tab active' : 'section-tab'}
              onClick={() => setAppSection('chat')}
            >
              Диалоги
            </button>
          ) : null}
          {canStudioAny ? (
            <button
              type="button"
              className={appSection === 'studio' ? 'section-tab active' : 'section-tab'}
              onClick={() => setAppSection('studio')}
            >
              Картинки
            </button>
          ) : null}
        </nav>
      ) : (
        <div className="banner info" style={{ margin: '0 1rem' }}>
          Нет доступа к диалогам и студии по правам аккаунта. Откройте кабинет или обратитесь к владельцу.
        </div>
      )}

      {health?.legacy_telegram_polling && health.telegram_api_reachable === false && (
        <div className="banner error">
          Нет связи с Telegram API (legacy polling). Включите VPN или задайте{' '}
          <code>TELEGRAM_PROXY</code> в <code>backend/.env</code>. Детали:{' '}
          {health.telegram_api_error ?? '—'}
        </div>
      )}

      {accountOpen && (
        <div className="account-panel">
          <div className="account-panel-header">
            <h3>Кабинет</h3>
            <button type="button" className="ghost-btn account-panel-close" onClick={() => setAccountOpen(false)}>
              Закрыть
            </button>
          </div>
          <div className="account-cabinet-tabs" role="tablist" aria-label="Разделы кабинета">
            <button
              type="button"
              role="tab"
              aria-selected={accountTab === 'integrations'}
              className={accountTab === 'integrations' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
              onClick={() => setAccountTab('integrations')}
            >
              Ключи и статусы
            </button>
            {canStudioModels ? (
              <button
                type="button"
                role="tab"
                aria-selected={accountTab === 'models'}
                className={accountTab === 'models' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                onClick={() => setAccountTab('models')}
              >
                Модели студии
              </button>
            ) : null}
            {isOwner ? (
              <button
                type="button"
                role="tab"
                aria-selected={accountTab === 'team'}
                className={accountTab === 'team' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                onClick={() => setAccountTab('team')}
              >
                Команда
              </button>
            ) : null}
          </div>

          {accountTab === 'integrations' && (
            <div className="account-cabinet-pane" role="tabpanel">
              <p className="cabinet-lead muted">
                Статусы интеграций и поля для обновления ключей. Telegram: токен BotFather и HTTPS{' '}
                <span className="mono">{health?.mode === 'saas' ? 'PUBLIC_APP_URL' : 'ваш URL'}</span> для
                webhook.
              </p>

              <div className="cabinet-status-grid">
                <div
                  className={`cabinet-status-card ${integ?.telegram_configured ? 'is-ok' : 'is-warn'}`}
                >
                  <div className="cabinet-status-title">Telegram</div>
                  <div className="cabinet-status-badge">
                    {integ?.telegram_configured ? 'Подключён' : 'Не настроен'}
                  </div>
                  {integ?.telegram_configured ? (
                    <p className="cabinet-status-detail cabinet-status-row">
                      <span className="mono">@{integ.telegram_bot_username ?? '—'}</span>
                      {integ.telegram_webhook_registered ? (
                        <span className="cabinet-status-pill ok">Webhook OK</span>
                      ) : (
                        <span className="cabinet-status-pill warn">Webhook не подтверждён</span>
                      )}
                    </p>
                  ) : (
                    <p className="cabinet-status-detail muted">Сохраните токен бота ниже.</p>
                  )}
                  {integ?.telegram_webhook_url ? (
                    <p className="mono cabinet-status-url">{integ.telegram_webhook_url}</p>
                  ) : null}
                </div>

                <div className={`cabinet-status-card ${integ?.fanvue_configured ? 'is-ok' : 'is-warn'}`}>
                  <div className="cabinet-status-title">Fanvue</div>
                  <div className="cabinet-status-badge">
                    {integ?.fanvue_configured ? 'Подключён' : 'Не настроен'}
                  </div>
                  {integ?.fanvue_creator_uuid ? (
                    <p className="cabinet-status-detail mono">Creator: {integ.fanvue_creator_uuid}</p>
                  ) : (
                    <p className="cabinet-status-detail muted">Нужны token, UUID и signing secret.</p>
                  )}
                  {integ?.fanvue_webhook_url ? (
                    <p className="mono cabinet-status-url">{integ.fanvue_webhook_url}</p>
                  ) : null}
                </div>

                <div
                  className={`cabinet-status-card ${integ?.wavespeed_configured ? 'is-ok' : 'is-warn'}`}
                >
                  <div className="cabinet-status-title">WaveSpeed</div>
                  <div className="cabinet-status-badge">
                    {integ?.wavespeed_configured ? 'Ключ сохранён' : 'Ключ не задан'}
                  </div>
                  <p className="cabinet-status-detail muted">
                    Seedream 4.5 Edit · нужен HTTPS <code className="mono">PUBLIC_APP_URL</code> для референсов.
                  </p>
                </div>

                <div
                  className={`cabinet-status-card ${health?.stripe_configured ? 'is-ok' : 'is-warn'}`}
                >
                  <div className="cabinet-status-title">Оплата (Stripe)</div>
                  <div className="cabinet-status-badge">
                    {health?.stripe_configured ? 'Готов к checkout' : 'Не настроен на сервере'}
                  </div>
                  <p className="cabinet-status-detail muted">
                    Подписка оформляется через Stripe Checkout (кнопка ниже).
                  </p>
                </div>

                <div
                  className={`cabinet-status-card ${health?.openai_studio_configured ? 'is-ok' : 'is-warn'}`}
                >
                  <div className="cabinet-status-title">Студия промпта</div>
                  <div className="cabinet-status-badge">
                    {health?.openai_studio_configured ? 'OpenAI OK' : 'Нет OPENAI_API_KEY'}
                  </div>
                  {health?.openai_studio_configured ? (
                    <p className="cabinet-status-detail muted">
                      Сборка JSON: {health.studio_prompt_credit_cost ?? '—'} кр.
                    </p>
                  ) : null}
                </div>

                <div
                  className={`cabinet-status-card ${
                    webPushState === 'on' ? 'is-ok' : 'is-warn'
                  }`}
                >
                  <div className="cabinet-status-title">Уведомления (телефон / браузер)</div>
                  <div className="cabinet-status-badge">
                    {webPushState === 'loading' || webPushState === 'unknown'
                      ? '…'
                      : webPushState === 'on'
                        ? 'Включены'
                        : webPushState === 'denied'
                          ? 'Запрещены в браузере'
                          : webPushState === 'unsupported'
                            ? 'Не поддерживается'
                            : webPushState === 'no_vapid'
                              ? 'Нет ключей на сервере'
                              : 'Выключены'}
                  </div>
                  <p className="cabinet-status-detail muted">
                    Web Push при новом входящем сообщении. На сервере: <code className="mono">VAPID_*</code>, в проде —
                    HTTPS.
                  </p>
                  {webPushState === 'denied' ? (
                    <p className="cabinet-status-detail muted">
                      Разрешите уведомления для этого сайта в настройках браузера.
                    </p>
                  ) : null}
                  {canChat && health?.web_push_configured && webPushEnvironmentOk() ? (
                    <p className="cabinet-status-detail cabinet-status-row">
                      {webPushState === 'on' ? (
                        <button
                          type="button"
                          className="ghost-btn"
                          disabled={pushBusy}
                          onClick={() => void disableWebPush()}
                        >
                          Отключить push
                        </button>
                      ) : webPushState === 'off' ? (
                        <button
                          type="button"
                          className="ghost-btn"
                          disabled={pushBusy}
                          onClick={() => void enableWebPush()}
                        >
                          Включить уведомления
                        </button>
                      ) : null}
                    </p>
                  ) : null}
                </div>
              </div>

              {integ?.integration_hint ? (
                <div className="banner info cabinet-hint-banner">{integ.integration_hint}</div>
              ) : null}

              {!canIntegrations ? (
                <p className="cabinet-lead muted">
                  Изменение ключей недоступно по правам. Статусы выше — только для просмотра.
                </p>
              ) : null}
              <h4 className="account-sub">Обновить ключи</h4>
              <div className="account-grid cabinet-keys-form">
                <label>
                  WaveSpeed API key
                  <input
                    type="password"
                    autoComplete="off"
                    value={wsApiKey}
                    onChange={(e) => setWsApiKey(e.target.value)}
                    placeholder="Ключ из личного кабинета WaveSpeed"
                    disabled={!canIntegrations}
                  />
                </label>
                <button
                  type="button"
                  className="ghost-btn"
                  disabled={!canIntegrations}
                  onClick={() => void saveWavespeed()}
                >
                  Сохранить WaveSpeed
                </button>
                <label>
                  Telegram bot token
                  <input
                    type="password"
                    autoComplete="off"
                    value={tgToken}
                    onChange={(e) => setTgToken(e.target.value)}
                    placeholder="123456:ABC…"
                    disabled={!canIntegrations}
                  />
                </label>
                <button
                  type="button"
                  className="ghost-btn"
                  disabled={!canIntegrations}
                  onClick={() => void saveTelegram()}
                >
                  Сохранить Telegram
                </button>
                <label>
                  Fanvue access token
                  <input
                    type="password"
                    value={fvToken}
                    onChange={(e) => setFvToken(e.target.value)}
                    placeholder="Bearer / access token"
                    disabled={!canIntegrations}
                  />
                </label>
                <label>
                  Fanvue creator UUID
                  <input
                    value={fvCreator}
                    onChange={(e) => setFvCreator(e.target.value)}
                    placeholder="UUID создателя"
                    disabled={!canIntegrations}
                  />
                </label>
                <label>
                  Fanvue webhook signing secret
                  <input
                    type="password"
                    value={fvSecret}
                    onChange={(e) => setFvSecret(e.target.value)}
                    placeholder="Секрет подписи вебхука"
                    disabled={!canIntegrations}
                  />
                </label>
                <button
                  type="button"
                  className="ghost-btn"
                  disabled={!canIntegrations}
                  onClick={() => void saveFanvue()}
                >
                  Сохранить Fanvue
                </button>
                {isOwner ? (
                  <button type="button" className="send-btn cabinet-checkout-btn" onClick={() => void startCheckout()}>
                    Оформить подписку (Stripe)
                  </button>
                ) : (
                  <p className="muted" style={{ gridColumn: '1 / -1' }}>
                    Оформление подписки доступно только владельцу аккаунта.
                  </p>
                )}
              </div>
            </div>
          )}

          {accountTab === 'models' && canStudioModels && (
            <div className="account-cabinet-pane" role="tabpanel">
              <p className="cabinet-lead muted">
                Модели подставляются в промпт на вкладке «Генерация картинок». До 5 фото на модель. Можно
                править название, описание, добавлять и удалять снимки.
              </p>

              <h4 className="account-sub">Новая модель</h4>
              <div className="account-grid studio-models-block cabinet-new-model">
                <label>
                  Название
                  <input
                    value={newModelName}
                    onChange={(e) => setNewModelName(e.target.value)}
                    placeholder="Например: Анна — чёрные волосы"
                  />
                </label>
                <label>
                  Описание внешности
                  <textarea
                    rows={3}
                    value={newModelProfile}
                    onChange={(e) => setNewModelProfile(e.target.value)}
                    placeholder="Волосы, возраст, типаж, кожа…"
                  />
                </label>
                <label>
                  Фото (до 5)
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    multiple
                    onChange={(e) => {
                      const list = e.target.files ? Array.from(e.target.files) : []
                      setNewModelFiles(list.slice(0, 5))
                    }}
                  />
                  {newModelFiles.length > 0 ? (
                    <span className="muted" style={{ fontSize: '0.85rem' }}>
                      Выбрано файлов: {newModelFiles.length}
                    </span>
                  ) : null}
                </label>
                <button type="button" className="send-btn" onClick={() => void createStudioModel()}>
                  Создать модель
                </button>
              </div>

              {studioModels.length === 0 ? (
                <p className="muted cabinet-empty-models">Пока нет моделей — создайте первую выше.</p>
              ) : (
                <div className="model-card-grid">
                  {studioModels.map((m) => {
                    const draft = modelDrafts[m.id] ?? { name: m.name, profile_text: m.profile_text }
                    const busy = modelSavingId === m.id
                    const imgs = m.images ?? []
                    return (
                      <article key={m.id} className="model-card">
                        <div className="model-card-head">
                          <h4 className="model-card-title">Модель #{m.id}</h4>
                          <button
                            type="button"
                            className="ghost-btn danger-text model-card-delete"
                            disabled={busy}
                            onClick={() => {
                              if (window.confirm('Удалить модель и все её фото?')) void deleteStudioModel(m.id)
                            }}
                          >
                            Удалить
                          </button>
                        </div>
                        <div className="model-card-thumbs" aria-label="Референсы">
                          {imgs.length === 0 ? (
                            <span className="model-card-no-photos muted">Нет фото</span>
                          ) : (
                            imgs.map((im) => (
                              <div key={im.id} className="model-thumb-wrap">
                                <img src={im.url} alt="" className="model-thumb" loading="lazy" />
                                <button
                                  type="button"
                                  className="model-thumb-remove"
                                  title="Удалить фото"
                                  disabled={busy}
                                  onClick={() => void deleteStudioModelImage(m.id, im.id)}
                                >
                                  ×
                                </button>
                              </div>
                            ))
                          )}
                        </div>
                        <label className="model-card-field">
                          Название
                          <input
                            value={draft.name}
                            disabled={busy}
                            onChange={(e) =>
                              setModelDrafts((prev) => ({
                                ...prev,
                                [m.id]: {
                                  ...(prev[m.id] ?? {
                                    name: m.name,
                                    profile_text: m.profile_text,
                                  }),
                                  name: e.target.value,
                                },
                              }))
                            }
                          />
                        </label>
                        <label className="model-card-field">
                          Описание
                          <textarea
                            rows={4}
                            value={draft.profile_text}
                            disabled={busy}
                            onChange={(e) =>
                              setModelDrafts((prev) => ({
                                ...prev,
                                [m.id]: {
                                  ...(prev[m.id] ?? {
                                    name: m.name,
                                    profile_text: m.profile_text,
                                  }),
                                  profile_text: e.target.value,
                                },
                              }))
                            }
                          />
                        </label>
                        <div className="model-card-actions">
                          <label className="model-card-add-files">
                            <input
                              type="file"
                              accept="image/jpeg,image/png,image/webp,image/gif"
                              multiple
                              className="sr-only-input"
                              disabled={busy || m.image_count >= 5}
                              onChange={(e) => {
                                void appendStudioModelImages(m.id, e.target.files)
                                e.target.value = ''
                              }}
                            />
                            <span className="ghost-btn model-card-add-btn">Добавить фото</span>
                          </label>
                          <button
                            type="button"
                            className="send-btn"
                            disabled={busy || !draft.name.trim()}
                            onClick={() => void patchStudioModel(m.id)}
                          >
                            {busy ? 'Сохранение…' : 'Сохранить изменения'}
                          </button>
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {accountTab === 'team' && isOwner && (
            <div className="account-cabinet-pane" role="tabpanel">
              <p className="cabinet-lead muted">
                Сотрудники входят с email владельца (ваш), отдельным логином команды и паролем. Кредиты и
                подписка — на владельце; права ниже ограничивают разделы.
              </p>
              <h4 className="account-sub">Новый участник</h4>
              <div className="account-grid cabinet-keys-form">
                <label>
                  Логин (латиница, цифры, _ · 3–32)
                  <input
                    value={newTeamLogin}
                    onChange={(e) => setNewTeamLogin(e.target.value)}
                    placeholder="например operator_1"
                    autoComplete="off"
                    disabled={teamBusy}
                  />
                </label>
                <label>
                  Пароль (мин. 8)
                  <input
                    type="password"
                    value={newTeamPassword}
                    onChange={(e) => setNewTeamPassword(e.target.value)}
                    autoComplete="new-password"
                    disabled={teamBusy}
                  />
                </label>
                <div style={{ gridColumn: '1 / -1' }} className="team-perm-grid">
                  {MEMBER_PERMISSION_LABELS.map(({ bit, label }) => (
                    <label key={bit} className="studio-label studio-check">
                      <input
                        type="checkbox"
                        checked={hasAllBits(newTeamMask, bit)}
                        disabled={teamBusy}
                        onChange={(e) => setNewTeamMask((m) => togglePermission(m, bit, e.target.checked))}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
                <button
                  type="button"
                  className="send-btn"
                  disabled={teamBusy || newTeamLogin.trim().length < 3 || newTeamPassword.length < 8}
                  onClick={() => void createWorkspaceMember()}
                >
                  {teamBusy ? 'Создание…' : 'Создать участника'}
                </button>
              </div>

              <h4 className="account-sub">Участники</h4>
              {workspaceMembers.length === 0 ? (
                <p className="muted">Пока никого нет — добавьте первого выше.</p>
              ) : (
                <ul className="team-member-list">
                  {workspaceMembers.map((row) => {
                    const mask = memberMaskEdits[row.id] ?? row.permissions_mask
                    const pwd = memberEditPassword[row.id] ?? ''
                    return (
                      <li key={row.id} className="team-member-card">
                        <div className="team-member-head">
                          <strong className="mono">{row.member_login}</strong>
                          <label className="studio-label studio-check">
                            <input
                              type="checkbox"
                              checked={row.is_active}
                              disabled={teamBusy}
                              onChange={(e) => void setWorkspaceMemberActive(row, e.target.checked)}
                            />
                            <span>Активен</span>
                          </label>
                        </div>
                        <div className="team-perm-grid">
                          {MEMBER_PERMISSION_LABELS.map(({ bit, label }) => (
                            <label key={bit} className="studio-label studio-check">
                              <input
                                type="checkbox"
                                checked={hasAllBits(mask, bit)}
                                disabled={teamBusy}
                                onChange={(e) =>
                                  setMemberMaskEdits((prev) => ({
                                    ...prev,
                                    [row.id]: togglePermission(mask, bit, e.target.checked),
                                  }))
                                }
                              />
                              <span>{label}</span>
                            </label>
                          ))}
                        </div>
                        <label>
                          Новый пароль (необязательно)
                          <input
                            type="password"
                            value={pwd}
                            autoComplete="new-password"
                            disabled={teamBusy}
                            onChange={(e) =>
                              setMemberEditPassword((p) => ({ ...p, [row.id]: e.target.value }))
                            }
                          />
                        </label>
                        <div className="team-member-actions">
                          <button
                            type="button"
                            className="ghost-btn"
                            disabled={teamBusy}
                            onClick={() => void saveWorkspaceMemberRow(row)}
                          >
                            Сохранить права и пароль
                          </button>
                          <button
                            type="button"
                            className="ghost-btn danger-text"
                            disabled={teamBusy}
                            onClick={() => void removeWorkspaceMember(row.id)}
                          >
                            Удалить
                          </button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {health && appSection !== 'studio' && (
        <div className="health-strip" title={health.database_file}>
          Режим: {health.mode ?? '—'} · всего в БД: {health.conversations_count ?? 0} диалогов,{' '}
          {health.messages_count ?? 0} сообщений
          {health.legacy_telegram_polling ? (
            <>
              {' '}
              · legacy polling Telegram:{' '}
              {health.telegram_api_reachable === true ? (
                <span className="ok">API OK @{health.telegram_bot_username ?? '?'}</span>
              ) : health.telegram_api_reachable === false ? (
                <span className="warn">API недоступен</span>
              ) : (
                <span className="muted">проверка…</span>
              )}
            </>
          ) : (
            <span className="muted"> · интеграции через личный кабинет (webhook)</span>
          )}
          {health.stripe_configured ? <span className="ok"> · Stripe</span> : (
            <span className="warn"> · Stripe не настроен</span>
          )}
          {health.telegram_proxy_configured ? <span className="ok"> · прокси TG</span> : null}
          {health.openai_studio_configured ? (
            <span className="ok">
              {' '}
              · студия промпта OpenAI ({health.studio_prompt_credit_cost ?? '—'} кр.)
            </span>
          ) : (
            <span className="warn"> · студия: нет OPENAI_API_KEY</span>
          )}
        </div>
      )}

      {hasAnyMainSection && appSection === 'studio' && canStudioAny && (
        <section className="studio-panel" aria-labelledby="studio-heading">
          <h2 id="studio-heading">Новая картинка</h2>
          {!canStudioGenerate ? (
            <div className="banner info">Генерация недоступна по правам. Попросите владельца аккаунта.</div>
          ) : null}
          <div className="studio-grid studio-grid--simple">
            <label className="studio-label">
              Формат
              <select
                value={studioOutputAspect}
                onChange={(e) => setStudioOutputAspect(e.target.value)}
              >
                {studioAspectPresets.length > 0 ? (
                  studioAspectPresets.map((p) => (
                    <option key={p.key} value={p.key}>
                      {p.label} ({p.size} px)
                    </option>
                  ))
                ) : (
                  <option value="9:16">9:16 (1080×1920)</option>
                )}
              </select>
            </label>
            <label className="studio-label">
              Модель
              <select
                value={studioSelectedModelId ?? ''}
                onChange={(e) => {
                  const v = e.target.value
                  setStudioSelectedModelId(v === '' ? null : Number(v))
                }}
              >
                <option value="">Без модели</option>
                {studioModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="studio-label">
              Референс (по желанию)
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null
                  setStudioFile(f)
                }}
              />
              {studioFile ? <span className="studio-file-name">{studioFile.name}</span> : null}
            </label>
            <label className="studio-label">
              Описание
              <textarea
                rows={5}
                placeholder="Что показать на снимке: сцена, свет, настроение…"
                value={studioDesc}
                onChange={(e) => setStudioDesc(e.target.value)}
              />
            </label>
            <div className="studio-actions">
              <button
                type="button"
                className="send-btn"
                title={
                  !health?.openai_studio_configured
                    ? 'Студия не настроена на сервере'
                    : undefined
                }
                disabled={
                  studioBusy ||
                  !canStudioGenerate ||
                  (!studioDesc.trim() && !studioFile && studioSelectedModelId == null) ||
                  !health?.openai_studio_configured
                }
                onClick={() => void refineStudioPrompt()}
              >
                {studioBusy ? 'Генерация…' : 'Сгенерировать'}
              </button>
              {canStudioGenerate && health?.openai_studio_configured ? (
                <span className="studio-credit-hint">
                  {health.studio_prompt_credit_cost ?? '—'} кр.
                </span>
              ) : !health?.openai_studio_configured && canStudioGenerate ? (
                <span className="studio-credit-hint warn">Нет доступа к студии</span>
              ) : null}
            </div>
            {studioWavespeedMsg && !studioGenImageUrl ? (
              <div className="banner info studio-status-msg">{studioWavespeedMsg}</div>
            ) : null}
            {studioGenImageUrl ? (
              <div className="studio-generated">
                <h3 className="studio-generated-title">Результат</h3>
                <div className="studio-generated-frame">
                  <img src={studioGenImageUrl} alt="Сгенерировано" className="studio-gen-img" />
                </div>
                <a
                  className="send-btn studio-download"
                  href={studioGenImageUrl}
                  target="_blank"
                  rel="noreferrer"
                  download="image.png"
                >
                  Скачать
                </a>
              </div>
            ) : null}
          </div>
        </section>
      )}

      {hasAnyMainSection && appSection === 'chat' && canChat && (
      <div className={layoutClass}>
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
                    <ConvAvatarThumb conv={c} />
                    <span className="conv-main">
                    <span className="conv-row-top">
                      <span className="plat">{platformLabel(c.platform)}</span>
                      {unread > 0 ? (
                        <span className="unread-badge" title="Непрочитанных">
                          {unread > 99 ? '99+' : unread}
                        </span>
                      ) : null}
                    </span>
                    <span className="name">{c.user_display_name ?? 'Без имени'}</span>
                    {(c.outbound_lang || c.user_lang) && (
                      <span
                        className="lang"
                        title={
                          c.outbound_lang
                            ? `Ответ: ${c.outbound_lang} (принудительно)`
                            : `Язык переписки: ${c.user_lang ?? '—'}`
                        }
                      >
                        {c.outbound_lang ? `${c.outbound_lang}*` : c.user_lang}
                      </span>
                    )}
                    {c.last_message_preview && (
                      <span className="preview">{c.last_message_preview}</span>
                    )}
                    </span>
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
                {isMobileLayout && !showThreadDock ? (
                  <button
                    type="button"
                    className="back-btn"
                    onClick={() => setSelectedId(null)}
                    aria-label="Назад к списку диалогов"
                  >
                    <span className="back-btn-icon" aria-hidden>
                      ‹
                    </span>
                  </button>
                ) : null}
                <ThreadAvatar conv={selected} />
                <div className="thread-head-main">
                  <div className="thread-head-text">
                    <h3>{selected.user_display_name ?? 'Диалог'}</h3>
                    <span className="meta">
                      {platformLabel(selected.platform)} · topic {selected.external_topic_id}
                    </span>
                  </div>
                  <div
                    className="outbound-lang-field"
                    title="На какой язык переводить ваши ответы. «Авто» — по последним входящим (поле user_lang)."
                  >
                    <label className="outbound-lang-label" htmlFor="outbound-lang-select">
                      Язык ответа
                    </label>
                    <select
                      id="outbound-lang-select"
                      className="outbound-lang-select"
                      value={selected.outbound_lang ?? ''}
                      disabled={outboundLangBusy}
                      onChange={(e) => void saveOutboundLang(selected.id, e.target.value)}
                    >
                      {OUTBOUND_LANG_OPTIONS.map((o) => (
                        <option key={o.value || 'auto'} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>
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
                            : m.pending
                              ? 'bubble out msg-enter bubble-out-pending'
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
                            <div
                              className={m.pending ? 'orig bubble-pending-meta' : 'orig'}
                              title="Ушло пользователю"
                            >
                              →{' '}
                              {m.pending
                                ? 'перевод и отправка…'
                                : m.text_translated ?? '—'}
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
                      placeholder="Сообщение на русском — уйдёт перевод на язык из «Язык ответа»"
                      title="Пишите на русском; в Telegram/Fanvue уйдёт перевод по выбранному языку"
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
      )}
    </div>
  )
}
