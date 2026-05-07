import EmojiPicker, { type EmojiClickData, Theme } from 'emoji-picker-react'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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

/** Размер страницы GET /conversations/:id/messages (синхронно с бэкендом default limit). */
const CHAT_MESSAGES_PAGE = 40

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
  yookassa_configured?: boolean
  billing_require_active_subscription?: boolean
  billing_price_managed_month_rub?: number
  billing_price_byok_month_rub?: number
  billing_credit_pack_price_rub?: number
  billing_credit_pack_credits?: number
  openai_studio_configured?: boolean
  studio_prompt_credit_cost?: number
  studio_upscale_credit_cost?: number
  studio_wan_edit_tier_switch?: boolean
  studio_allow_prompt_only?: boolean
  studio_carousel_credit_cost?: number
  web_push_configured?: boolean
}

interface UserMe {
  id: number
  email: string
  subscription_status: string
  /** managed | byok */
  billing_plan?: string
  subscription_period_end?: string | null
  operators_count?: number
  credits_balance: number
  is_workspace_owner: boolean
  is_platform_admin?: boolean
  workspace_owner_id: number
  member_login: string | null
  permissions_mask: number
  owner_email: string
  billing_require_active_subscription?: boolean
  online_payment_available?: boolean
}

interface AdminStats {
  total_users: number
  workspace_owners: number
  workspace_members: number
  total_credits_balance: number
  studio_generations_total: number
  usage_by_kind: Record<string, number>
}

interface AdminUserRow {
  id: number
  email: string
  created_at: string
  is_active: boolean
  is_platform_admin: boolean
  parent_user_id: number | null
  parent_email: string | null
  member_login: string | null
  subscription_status: string
  billing_plan: string
  subscription_period_end: string | null
  credits_balance: number
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
  llm_configured?: boolean
}

interface BillingCreditsPricing {
  min_quantity: number
  bulk_from: number
  unit_price_rub: number
  bulk_unit_price_rub: number
}

interface BillingPlanRow {
  product: 'sub_byok_month' | 'sub_managed_month' | 'credits_pack'
  title: string
  price_rub: number
  currency?: string
  credits_pricing?: BillingCreditsPricing | null
}

function creditsPurchaseTotalRub(qty: number, p: BillingCreditsPricing): number {
  const unit = qty >= p.bulk_from ? p.bulk_unit_price_rub : p.unit_price_rub
  return Math.round(qty * unit * 100) / 100
}

interface StudioModelImage {
  id: number
  url: string
  kind: string
  export_selfie?: boolean
}

type StudioModelImageKind = 'face' | 'body' | 'genitals' | 'other'

interface NewModelPhotoRow {
  file: File
  kind: StudioModelImageKind
  export_selfie: boolean
}

const STUDIO_MODEL_IMAGE_KIND_OPTIONS: { value: StudioModelImageKind; label: string }[] = [
  { value: 'face', label: 'Лицо / идентичность' },
  { value: 'body', label: 'Тело целиком' },
  { value: 'genitals', label: 'Интимная зона (реф.)' },
  { value: 'other', label: 'Общий референс' },
]

function normalizeStudioImageKind(raw: string | undefined): StudioModelImageKind {
  if (raw === 'face' || raw === 'body' || raw === 'genitals' || raw === 'other') return raw
  return 'other'
}

interface UserStudioModel {
  id: number
  name: string
  profile_text: string
  image_count: number
  images?: StudioModelImage[]
  camera_preset_id?: string | null
  export_lat?: number | null
  export_lon?: number | null
}

type StudioModelCabinetDraft = {
  name: string
  profile_text: string
  camera_preset_id: string
  export_lat: string
  export_lon: string
}

function defaultStudioModelCabinetDraft(m: UserStudioModel): StudioModelCabinetDraft {
  return {
    name: m.name,
    profile_text: m.profile_text,
    camera_preset_id: (m.camera_preset_id ?? '').trim(),
    export_lat:
      m.export_lat != null && !Number.isNaN(Number(m.export_lat)) ? String(m.export_lat) : '',
    export_lon:
      m.export_lon != null && !Number.isNaN(Number(m.export_lon)) ? String(m.export_lon) : '',
  }
}

interface StudioCameraPreset {
  id: string
  label: string
}

type AccountCabinetTab = 'overview' | 'billing' | 'integrations' | 'models' | 'team' | 'admin'

const SUBSCRIPTION_STATUS_OPTIONS = [
  'none',
  'incomplete',
  'trialing',
  'active',
  'past_due',
  'canceled',
  'unpaid',
] as const

const ADMIN_BILLING_PLAN_OPTIONS = ['managed', 'byok'] as const

function userBillingPlanLabel(plan: string | undefined): string {
  const p = (plan || 'managed').toLowerCase()
  return p === 'byok' ? 'BYOK · свои ключи' : 'Managed · платформа'
}

function userBillingPlanLong(plan: string | undefined): string {
  const p = (plan || 'managed').toLowerCase()
  return p === 'byok'
    ? 'BYOK — свои LLM и WaveSpeed, кредиты на студию не списываются'
    : 'Managed — LLM платформы и ваш ключ WaveSpeed; кредиты на студию списываются'
}

const SUBSCRIPTION_STATUS_LABELS: Record<string, string> = {
  none: 'Нет подписки',
  incomplete: 'Оформление',
  trialing: 'Пробный период',
  active: 'Активна',
  past_due: 'Просрочен платёж',
  canceled: 'Отменена',
  unpaid: 'Не оплачена',
}

const CREDIT_KIND_LABELS: Record<string, string> = {
  studio_prompt_refine: 'Студия: генерация',
  studio_image_upscale: 'Студия: апскейл',
  studio_carousel_shot: 'Студия: карусель',
  studio_model_profile_generate: 'Студия: профиль модели',
  yookassa_credits_pack: 'Пополнение баланса',
  admin_credit_adjustment: 'Изменение баланса',
}

function subscriptionStatusLabel(status: string | undefined): string {
  if (!status) return '—'
  return SUBSCRIPTION_STATUS_LABELS[status] ?? status
}

/** Соответствует серверной subscription_active: active/trialing и период не истёк. */
function subscriptionCoversStudioAccess(me: UserMe): boolean {
  const st = (me.subscription_status || '').toLowerCase()
  if (st !== 'active' && st !== 'trialing') return false
  if (me.subscription_period_end) {
    const end = new Date(me.subscription_period_end).getTime()
    if (!Number.isNaN(end) && end < Date.now()) return false
  }
  return true
}

function creditKindLabel(kind: string): string {
  return CREDIT_KIND_LABELS[kind] ?? kind
}

function formatDateTimeRu(iso: string | undefined | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return String(iso)
  }
}

/** Значение для input[type=datetime-local] из ISO UTC. */
function isoToDatetimeLocalValue(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** ISO UTC для API из локального datetime-local (или null если пусто / ошибка). */
function datetimeLocalInputToIsoUtc(local: string): string | null {
  const t = local.trim()
  if (!t) return null
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

interface StudioAspectPreset {
  key: string
  label: string
  size: string
}

interface StudioArchiveItem {
  id: number
  created_at: string
  output_aspect: string | null
  studio_model_id: number | null
  model_name: string | null
  prompt_excerpt: string | null
  image_url: string
}

interface StudioGenerationsPage {
  items: StudioArchiveItem[]
  has_more: boolean
}

/** Должен совпадать с default limit у GET /api/studio/generations */
const STUDIO_ARCHIVE_PAGE = 10

type StudioJobMode = 'model' | 'photo_edit' | 'no_face'

export default function App() {
  const navigate = useNavigate()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [hasMoreOlder, setHasMoreOlder] = useState(false)
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
  const skipNextAutoScrollRef = useRef(false)
  const loadingOlderRef = useRef(false)
  const hasMoreOlderRef = useRef(false)
  const oldestMsgIdRef = useRef<number | null>(null)

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

  const studioPaywalled = useMemo(() => {
    if (!me) return false
    if (me.is_platform_admin) return false
    const gate =
      me.billing_require_active_subscription ?? health?.billing_require_active_subscription ?? true
    if (!gate) return false
    return !subscriptionCoversStudioAccess(me)
  }, [me, health])

  const canPlatformAdmin = Boolean(me?.is_platform_admin)

  const [accountOpen, setAccountOpen] = useState(false)
  const [accountTab, setAccountTab] = useState<AccountCabinetTab>('overview')
  const [workspaceMembers, setWorkspaceMembers] = useState<WorkspaceMemberRow[]>([])
  const [teamBusy, setTeamBusy] = useState(false)
  const [newTeamLogin, setNewTeamLogin] = useState('')
  const [newTeamPassword, setNewTeamPassword] = useState('')
  const [newTeamMask, setNewTeamMask] = useState(DEFAULT_MEMBER_PERMISSIONS)
  const [memberEditPassword, setMemberEditPassword] = useState<Record<number, string>>({})
  const [memberMaskEdits, setMemberMaskEdits] = useState<Record<number, number>>({})
  const [integ, setInteg] = useState<IntegrationStatus | null>(null)
  const [modelDrafts, setModelDrafts] = useState<Record<number, StudioModelCabinetDraft>>({})
  const [studioCameraPresets, setStudioCameraPresets] = useState<StudioCameraPreset[]>([])
  const [modelSavingId, setModelSavingId] = useState<number | null>(null)
  const [tgToken, setTgToken] = useState('')
  const [fvToken, setFvToken] = useState('')
  const [fvCreator, setFvCreator] = useState('')
  const [fvSecret, setFvSecret] = useState('')

  const [appSection, setAppSection] = useState<'chat' | 'studio'>('chat')
  const [studioDesc, setStudioDesc] = useState('')
  const [studioFile, setStudioFile] = useState<File | null>(null)
  /** true = MODEL_LOCK (причёска с профиля); false = POSE_REFERENCE (с загруженного кадра). Только если есть studioFile. */
  const [studioLockModelHairstyle, setStudioLockModelHairstyle] = useState(true)
  const [studioMode, setStudioMode] = useState<StudioJobMode>('model')
  const [studioWanEditTier, setStudioWanEditTier] = useState<'standard' | 'pro'>('standard')
  const [studioWaveProfile, setStudioWaveProfile] = useState<'regular' | 'nsfw'>('nsfw')
  const [studioBusy, setStudioBusy] = useState(false)
  const [studioModels, setStudioModels] = useState<UserStudioModel[]>([])
  const [studioSelectedModelId, setStudioSelectedModelId] = useState<number | null>(null)
  const [newModelName, setNewModelName] = useState('')
  const [newModelProfile, setNewModelProfile] = useState('')
  const [newModelProfileGenBusy, setNewModelProfileGenBusy] = useState(false)
  const [newModelPhotos, setNewModelPhotos] = useState<NewModelPhotoRow[]>([])
  const [newModelCameraPresetId, setNewModelCameraPresetId] = useState('')
  const [newModelExportLat, setNewModelExportLat] = useState('')
  const [newModelExportLon, setNewModelExportLon] = useState('')
  /** Черновик файлов для «Добавить фото» на карточке модели (до загрузки на сервер). */
  const [appendModelPhotosById, setAppendModelPhotosById] = useState<
    Record<number, NewModelPhotoRow[]>
  >({})
  const [adminStats, setAdminStats] = useState<AdminStats | null>(null)
  const [adminUsers, setAdminUsers] = useState<AdminUserRow[]>([])
  const [adminUserSearch, setAdminUserSearch] = useState('')
  const [adminDataBusy, setAdminDataBusy] = useState(false)
  const [adminCreditInput, setAdminCreditInput] = useState<Record<number, string>>({})
  const [wsApiKey, setWsApiKey] = useState('')
  const [llmApiKey, setLlmApiKey] = useState('')
  const [llmBaseUrl, setLlmBaseUrl] = useState('')
  const [billingPlanRows, setBillingPlanRows] = useState<BillingPlanRow[]>([])
  const [creditsPurchaseQty, setCreditsPurchaseQty] = useState(50)
  const [yookassaPayBusy, setYookassaPayBusy] = useState<string | null>(null)
  const [creditHistoryItems, setCreditHistoryItems] = useState<
    { id: number; created_at: string; kind: string; credits_delta: number }[]
  >([])
  const [creditHistoryHasMore, setCreditHistoryHasMore] = useState(false)
  const [creditHistoryBusy, setCreditHistoryBusy] = useState(false)
  const [webPushState, setWebPushState] = useState<
    'unknown' | 'loading' | 'on' | 'off' | 'denied' | 'unsupported' | 'no_vapid'
  >('unknown')
  const [pushBusy, setPushBusy] = useState(false)
  const [studioGenImageUrl, setStudioGenImageUrl] = useState<string | null>(null)
  const [studioGenGenerationId, setStudioGenGenerationId] = useState<number | null>(null)
  const [studioUpscaleTarget, setStudioUpscaleTarget] = useState<'2k' | '4k' | '8k'>('4k')
  const [studioUpscaleBusy, setStudioUpscaleBusy] = useState(false)
  const [studioCarouselBusy, setStudioCarouselBusy] = useState(false)
  /** iOS PWA: прямой href на картинку уводит в Quick Look без «Назад» — качаем через fetch / Share. */
  const [studioDownloadBusy, setStudioDownloadBusy] = useState(false)
  const [studioWavespeedMsg, setStudioWavespeedMsg] = useState<string | null>(null)
  /** Только в dev + health.studio_allow_prompt_only: без запроса к WaveSpeed */
  const [studioDevPromptOnly, setStudioDevPromptOnly] = useState(false)
  const [studioRefinedPromptPreview, setStudioRefinedPromptPreview] = useState<string | null>(null)
  const [studioAspectPresets, setStudioAspectPresets] = useState<StudioAspectPreset[]>([])
  const [studioOutputAspect, setStudioOutputAspect] = useState('9:16')
  const [studioGenerations, setStudioGenerations] = useState<StudioArchiveItem[]>([])
  const [studioGenHasMore, setStudioGenHasMore] = useState(false)
  const [studioGenLoadingMore, setStudioGenLoadingMore] = useState(false)
  const [studioArchiveInitialLoading, setStudioArchiveInitialLoading] = useState(false)

  const studioPromptOnlyDev = useMemo(
    () =>
      import.meta.env.DEV &&
      Boolean(health?.studio_allow_prompt_only) &&
      studioDevPromptOnly,
    [health?.studio_allow_prompt_only, studioDevPromptOnly],
  )

  useEffect(() => {
    if (!studioFile) setStudioLockModelHairstyle(true)
  }, [studioFile])

  const studioGenerationsRef = useRef<StudioArchiveItem[]>([])

  useEffect(() => {
    studioGenerationsRef.current = studioGenerations
  }, [studioGenerations])

  useEffect(() => {
    selectedIdRef.current = selectedId
  }, [selectedId])

  useEffect(() => {
    hasMoreOlderRef.current = hasMoreOlder
  }, [hasMoreOlder])

  useEffect(() => {
    loadingOlderRef.current = loadingOlder
  }, [loadingOlder])

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

  const refreshBillingPlans = useCallback(async () => {
    const r = await apiFetch('/api/billing/plans')
    if (r.ok) {
      const data = (await r.json()) as { items: BillingPlanRow[] }
      setBillingPlanRows(Array.isArray(data.items) ? data.items : [])
    }
  }, [])

  useEffect(() => {
    const p = billingPlanRows.find((r) => r.product === 'credits_pack')?.credits_pricing
    if (!p) return
    setCreditsPurchaseQty((prev) => (prev < p.min_quantity ? p.min_quantity : prev))
  }, [billingPlanRows])

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

  const loadStudioCameraPresets = useCallback(async () => {
    const r = await apiFetch('/api/studio/camera-presets')
    if (r.ok) setStudioCameraPresets((await r.json()) as StudioCameraPreset[])
  }, [])

  const fetchStudioArchivePage = useCallback(async (skip: number) => {
    const p = new URLSearchParams()
    p.set('limit', String(STUDIO_ARCHIVE_PAGE))
    p.set('skip', String(skip))
    const r = await apiFetch(`/api/studio/generations?${p}`)
    if (!r.ok) throw new Error('Не удалось загрузить архив студии')
    return (await r.json()) as StudioGenerationsPage
  }, [])

  const loadStudioGenerationsReset = useCallback(async () => {
    const page = await fetchStudioArchivePage(0)
    setStudioGenerations(page.items)
    setStudioGenHasMore(page.has_more)
  }, [fetchStudioArchivePage])

  const loadMoreStudioGenerations = useCallback(async () => {
    if (studioGenLoadingMore || !studioGenHasMore) return
    setStudioGenLoadingMore(true)
    setError(null)
    try {
      const skip = studioGenerationsRef.current.length
      const page = await fetchStudioArchivePage(skip)
      setStudioGenerations((prev) => {
        const seen = new Set(prev.map((x) => x.id))
        const add = page.items.filter((x) => !seen.has(x.id))
        return [...prev, ...add]
      })
      setStudioGenHasMore(page.has_more)
    } catch (e) {
      setError(String(e))
    } finally {
      setStudioGenLoadingMore(false)
    }
  }, [fetchStudioArchivePage, studioGenLoadingMore, studioGenHasMore])

  const loadAdminStats = useCallback(async () => {
    const r = await apiFetch('/api/admin/stats')
    if (r.ok) setAdminStats((await r.json()) as AdminStats)
  }, [])

  const fetchAdminUsers = useCallback(async (search: string) => {
    const q = new URLSearchParams()
    q.set('limit', '150')
    if (search.trim()) q.set('q', search.trim())
    const r = await apiFetch(`/api/admin/users?${q}`)
    if (r.ok) setAdminUsers((await r.json()) as AdminUserRow[])
  }, [])

  useEffect(() => {
    if (!accountOpen || accountTab !== 'admin' || !canPlatformAdmin) return
    setAdminDataBusy(true)
    void Promise.all([loadAdminStats(), fetchAdminUsers('')]).finally(() => setAdminDataBusy(false))
  }, [accountOpen, accountTab, canPlatformAdmin, loadAdminStats, fetchAdminUsers])

  useEffect(() => {
    setModelDrafts(
      Object.fromEntries(studioModels.map((m) => [m.id, defaultStudioModelCabinetDraft(m)])),
    )
  }, [studioModels])

  useEffect(() => {
    if (!me || !accountOpen) return
    if (accountTab === 'admin' && !canPlatformAdmin) setAccountTab('overview')
    if (accountTab === 'models' && !canStudioModels) setAccountTab('overview')
    if (accountTab === 'team' && !isOwner) setAccountTab('overview')
    if (accountTab === 'billing' && !isOwner) setAccountTab('overview')
  }, [me, accountOpen, accountTab, canPlatformAdmin, canStudioModels, isOwner])

  useEffect(() => {
    if (!me) return
    if (appSection === 'chat' && !canChat && canStudioAny) setAppSection('studio')
    if (appSection === 'studio' && !canStudioAny && canChat) setAppSection('chat')
  }, [me?.id, appSection, canChat, canStudioAny])

  useEffect(() => {
    if (authed && accountOpen) void refreshIntegrations()
  }, [authed, accountOpen, refreshIntegrations])

  useEffect(() => {
    if (!authed || !accountOpen || accountTab !== 'billing') return
    void refreshBillingPlans()
  }, [authed, accountOpen, accountTab, refreshBillingPlans])

  useEffect(() => {
    if (!authed || !accountOpen || accountTab !== 'billing' || !isOwner) return
    let cancelled = false
    setCreditHistoryBusy(true)
    void apiFetch('/api/workspace/credit-history?limit=40&skip=0')
      .then(async (r) => {
        if (!r.ok || cancelled) return
        const d = (await r.json()) as {
          items: { id: number; created_at: string; kind: string; credits_delta: number }[]
          has_more: boolean
        }
        if (!cancelled) {
          setCreditHistoryItems(Array.isArray(d.items) ? d.items : [])
          setCreditHistoryHasMore(Boolean(d.has_more))
        }
      })
      .finally(() => {
        if (!cancelled) setCreditHistoryBusy(false)
      })
    return () => {
      cancelled = true
    }
  }, [authed, accountOpen, accountTab, isOwner])

  useEffect(() => {
    if (!authed) return
    const needModels =
      (appSection === 'studio' && canStudioAny) ||
      (accountOpen && accountTab === 'models' && canStudioModels)
    if (needModels) {
      void loadStudioModels()
      void loadStudioCameraPresets()
    }
  }, [
    authed,
    accountOpen,
    accountTab,
    appSection,
    canStudioAny,
    canStudioModels,
    loadStudioModels,
    loadStudioCameraPresets,
  ])

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

  useEffect(() => {
    if (!authed || appSection !== 'studio' || !canStudioGenerate) return
    setStudioArchiveInitialLoading(true)
    setError(null)
    void loadStudioGenerationsReset()
      .catch((e) => setError(String(e)))
      .finally(() => setStudioArchiveInitialLoading(false))
  }, [authed, appSection, canStudioGenerate, loadStudioGenerationsReset])

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

  const fetchMessagesPage = useCallback(async (id: number, before?: number) => {
    const p = new URLSearchParams()
    p.set('limit', String(CHAT_MESSAGES_PAGE))
    if (before != null) p.set('before', String(before))
    const r = await apiFetch(`/api/conversations/${id}/messages?${p}`)
    if (!r.ok) throw new Error('Не удалось загрузить сообщения')
    return (await r.json()) as ChatMessage[]
  }, [])

  const loadMessages = useCallback(
    async (id: number) => {
      const data = await fetchMessagesPage(id)
      setMessages(data)
      setHasMoreOlder(data.length >= CHAT_MESSAGES_PAGE)
    },
    [fetchMessagesPage],
  )

  const loadOlderMessages = useCallback(async () => {
    const sid = selectedIdRef.current
    if (sid == null || loadingOlderRef.current || !hasMoreOlderRef.current) return
    const beforeId = oldestMsgIdRef.current
    if (beforeId == null) return
    loadingOlderRef.current = true
    setLoadingOlder(true)
    const el = messagesContainerRef.current
    const prevH = el?.scrollHeight ?? 0
    const prevT = el?.scrollTop ?? 0
    try {
      const chunk = await fetchMessagesPage(sid, beforeId)
      if (chunk.length === 0) {
        setHasMoreOlder(false)
        return
      }
      if (chunk.length < CHAT_MESSAGES_PAGE) setHasMoreOlder(false)
      skipNextAutoScrollRef.current = true
      setMessages((prev) => {
        const seen = new Set<number>()
        const merged: ChatMessage[] = []
        for (const m of chunk) {
          const mid = Number(m.id)
          if (!Number.isFinite(mid) || seen.has(mid)) continue
          seen.add(mid)
          merged.push(m)
        }
        for (const m of prev) {
          const mid = Number(m.id)
          if (!Number.isFinite(mid) || seen.has(mid)) continue
          seen.add(mid)
          merged.push(m)
        }
        return merged.sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
        )
      })
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const el2 = messagesContainerRef.current
          if (el2) el2.scrollTop = prevT + (el2.scrollHeight - prevH)
        })
      })
    } catch (e) {
      setError(String(e))
    } finally {
      loadingOlderRef.current = false
      setLoadingOlder(false)
    }
  }, [fetchMessagesPage])

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
      setHasMoreOlder(false)
      return
    }
    setMessages([])
    setHasMoreOlder(false)
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

  /** Мгновенный скролл вниз; несколько попыток — после открытия чата высота ленты на мобильных/PWA дорисовывается с задержкой. */
  const scrollToBottomInstant = useCallback(() => {
    const el = messagesContainerRef.current
    if (!el) return
    const apply = () => {
      const top = Math.max(0, el.scrollHeight - el.clientHeight)
      el.scrollTop = top
    }
    apply()
    requestAnimationFrame(apply)
    requestAnimationFrame(() => {
      requestAnimationFrame(apply)
    })
    window.setTimeout(apply, 0)
    window.setTimeout(apply, 50)
    window.setTimeout(apply, 120)
    window.setTimeout(apply, 280)
    window.setTimeout(apply, 450)
  }, [])

  const scrollToBottom = useCallback((smooth: boolean) => {
    const el = messagesContainerRef.current
    if (!el) return
    const top = Math.max(0, el.scrollHeight - el.clientHeight)
    if (smooth) {
      el.scrollTo({ top, behavior: 'smooth' })
    } else {
      scrollToBottomInstant()
    }
    setShowJumpDown(false)
  }, [scrollToBottomInstant])

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

  useEffect(() => {
    if (displayMessages.length === 0) oldestMsgIdRef.current = null
    else oldestMsgIdRef.current = Number(displayMessages[0].id)
  }, [displayMessages])

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

    if (skipNextAutoScrollRef.current) {
      skipNextAutoScrollRef.current = false
      prevMsgLenRef.current = len
      return
    }

    // Первая загрузка истории — вниз без анимации (несколько проходов из-за отложенной вёрстки)
    if (prev === 0 && len > 0) {
      prevMsgLenRef.current = len
      scrollToBottomInstant()
      return
    }

    if (len > prev) {
      const dist =
        container.scrollHeight - container.scrollTop - container.clientHeight
      if (dist < 96) {
        requestAnimationFrame(() => scrollToBottom(true))
      }
    }

    prevMsgLenRef.current = len
  }, [displayMessages, loading, selectedId, scrollToBottom, scrollToBottomInstant])

  /** «К последним»: по видимости хвоста ленты (надёжнее метрик scrollTop в PWA / iOS). */
  useEffect(() => {
    const root = messagesContainerRef.current
    if (!root || loading || selectedId == null) return
    const end = root.querySelector('.messages-end')
    if (!(end instanceof HTMLElement)) {
      setShowJumpDown(false)
      return
    }
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries[0]?.isIntersecting ?? true
        setShowJumpDown(!hit)
      },
      { root, rootMargin: '0px 0px 64px 0px', threshold: 0.02 },
    )
    io.observe(end)
    return () => io.disconnect()
  }, [selectedId, loading, displayMessages.length])

  /** У верхней границы — подгрузка истории. */
  useEffect(() => {
    const el = messagesContainerRef.current
    if (!el || loading || selectedId == null) return
    const sync = () => {
      if (
        el.scrollTop < 120 &&
        hasMoreOlderRef.current &&
        !loadingOlderRef.current &&
        !loading
      ) {
        void loadOlderMessages()
      }
    }
    el.addEventListener('scroll', sync, { passive: true })
    sync()
    return () => el.removeEventListener('scroll', sync)
  }, [selectedId, loading, loadOlderMessages])

  /** Догоняем низ после смены диалога / окончания загрузки (без displayMessages в deps — иначе при каждом новом пузыре сбивали бы скролл). */
  useEffect(() => {
    if (loading || selectedId == null) return
    const t = window.setTimeout(() => {
      const el = messagesContainerRef.current
      if (!el) return
      const dist = el.scrollHeight - el.scrollTop - el.clientHeight
      if (dist > 100) {
        scrollToBottomInstant()
      }
    }, 500)
    return () => window.clearTimeout(t)
  }, [selectedId, loading, scrollToBottomInstant])

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

  const deleteStudioGeneration = async (id: number, imageUrl: string) => {
    setError(null)
    const r = await apiFetch(`/api/studio/generations/${id}`, { method: 'DELETE' })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    setStudioGenImageUrl((prev) => (prev === imageUrl ? null : prev))
    setStudioGenGenerationId((prev) => (prev === id ? null : prev))
    void loadStudioGenerationsReset()
  }

  const downloadStudioResultImage = async () => {
    const url = studioGenImageUrl
    if (!url) return
    setStudioDownloadBusy(true)
    setError(null)
    try {
      const res = await fetch(url)
      if (!res.ok) {
        setError('Не удалось загрузить изображение.')
        return
      }
      const blob = await res.blob()
      const filename = 'image.png'
      const file = new File([blob], filename, { type: blob.type || 'image/png' })

      if (typeof navigator.share === 'function' && typeof navigator.canShare === 'function') {
        try {
          if (navigator.canShare({ files: [file] })) {
            await navigator.share({ files: [file], title: 'Изображение' })
            return
          }
        } catch (err: unknown) {
          if (err instanceof Error && err.name === 'AbortError') return
        }
      }

      const objectUrl = URL.createObjectURL(blob)
      try {
        const a = document.createElement('a')
        a.href = objectUrl
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
      } finally {
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
      }
    } catch {
      setError(
        'Не удалось скачать. На iPhone откройте меню «Поделиться» или удерживайте превью выше → «Сохранить в Фото».',
      )
    } finally {
      setStudioDownloadBusy(false)
    }
  }

  const refineStudioPrompt = async () => {
    setError(null)
    if (!studioDesc.trim() && !studioFile && studioSelectedModelId == null) {
      setError('Добавьте описание, референс и/или выберите сохранённую модель.')
      return
    }
    if (studioMode === 'photo_edit' && !studioFile) {
      setError('В режиме «Доработать фото» загрузите изображение.')
      return
    }
    if (studioMode === 'no_face' && studioSelectedModelId == null && !studioFile) {
      setError('В режиме «Без лица» выберите модель или загрузите референс.')
      return
    }
    setStudioBusy(true)
    setStudioGenImageUrl(null)
    setStudioGenGenerationId(null)
    setStudioWavespeedMsg(null)
    setStudioRefinedPromptPreview(null)
    try {
      const promptOnlyActive =
        import.meta.env.DEV &&
        Boolean(health?.studio_allow_prompt_only) &&
        studioDevPromptOnly
      const fd = new FormData()
      fd.append('description', studioDesc.trim())
      if (studioSelectedModelId != null) fd.append('model_id', String(studioSelectedModelId))
      if (studioFile) fd.append('image', studioFile)
      fd.append('output_aspect', studioOutputAspect)
      fd.append('studio_mode', studioMode)
      fd.append('wan_edit_tier', studioWanEditTier)
      fd.append('studio_wave_profile', studioWaveProfile)
      fd.append('generate_wavespeed', promptOnlyActive ? '0' : '1')
      fd.append('wavespeed_single_reference', '1')
      fd.append('lock_model_hairstyle', studioLockModelHairstyle ? '1' : '0')
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
        generation_id?: number | null
      }
      setStudioGenImageUrl(data.generated_image_url?.trim() || null)
      setStudioGenGenerationId(
        typeof data.generation_id === 'number' ? data.generation_id : null,
      )
      setStudioWavespeedMsg(data.wavespeed_message?.trim() || null)
      setStudioRefinedPromptPreview((data.refined_prompt ?? '').trim() || null)
      void refreshMe()
      void loadStudioGenerationsReset()
    } catch (e) {
      setError(e instanceof TypeError && e.message === 'Failed to fetch' ? 'Сеть: не удалось связаться с сервером (проверьте, что бэкенд запущен и порт / proxy).' : (e instanceof Error ? e.message : 'Неизвестная ошибка запроса'))
    } finally {
      setStudioBusy(false)
    }
  }

  const upscaleStudioGeneration = async () => {
    if (studioGenGenerationId == null) {
      setError('Откройте картинку из блока «Сохранённые» или сгенерируйте заново — нужна запись архива.')
      return
    }
    setError(null)
    setStudioWavespeedMsg(null)
    setStudioUpscaleBusy(true)
    try {
      const r = await apiFetch(`/api/studio/generations/${studioGenGenerationId}/upscale`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_resolution: studioUpscaleTarget }),
      })
      const data = (await r.json().catch(() => ({}))) as {
        generated_image_url?: string | null
        generation_id?: number | null
        message?: string | null
        target_resolution?: string
      }
      if (!r.ok) {
        setError(formatApiErrorDetail(data) || r.statusText)
        return
      }
      const url = data.generated_image_url?.trim()
      if (url) {
        setStudioGenImageUrl(url)
        if (typeof data.generation_id === 'number') {
          setStudioGenGenerationId(data.generation_id)
        }
      } else {
        setStudioWavespeedMsg(data.message?.trim() || 'Апскейл не выполнен.')
      }
      void refreshMe()
      void loadStudioGenerationsReset()
    } catch (e) {
      setError(
        e instanceof TypeError && e.message === 'Failed to fetch'
          ? 'Сеть: не удалось связаться с сервером.'
          : e instanceof Error
            ? e.message
            : 'Ошибка запроса',
      )
    } finally {
      setStudioUpscaleBusy(false)
    }
  }

  const runStudioCarousel = async (count: number) => {
    if (studioGenGenerationId == null) {
      setError('Сначала сгенерируйте или откройте снимок в «Результат», чтобы был сохранённый кадр.')
      return
    }
    setError(null)
    setStudioWavespeedMsg(null)
    setStudioCarouselBusy(true)
    try {
      const r = await apiFetch(`/api/studio/generations/${studioGenGenerationId}/carousel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          count,
          studio_wave_profile: studioWaveProfile,
          wan_edit_tier: studioWanEditTier,
        }),
      })
      const data = (await r.json().catch(() => ({}))) as {
        items?: { generation_id: number; image_url: string }[]
        message?: string | null
      }
      if (!r.ok) {
        setError(formatApiErrorDetail(data) || r.statusText)
        return
      }
      const items = data.items ?? []
      const note = (data.message ?? '').trim()
      if (items.length > 0 && note) {
        setStudioWavespeedMsg(`Сохранено кадров: ${items.length}. ${note}`)
      } else if (items.length > 0) {
        setStudioWavespeedMsg(
          `Карусель: добавлено ${items.length} кадров — откройте «Сохранённые». Учитываются текущие «Тип» и WAN.`,
        )
      } else if (note) {
        setStudioWavespeedMsg(note)
      }
      void refreshMe()
      void loadStudioGenerationsReset()
    } catch (e) {
      setError(
        e instanceof TypeError && e.message === 'Failed to fetch'
          ? 'Сеть: не удалось связаться с сервером.'
          : e instanceof Error
            ? e.message
            : 'Ошибка запроса',
      )
    } finally {
      setStudioCarouselBusy(false)
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

  const saveLlm = async () => {
    setError(null)
    const k = llmApiKey.trim()
    if (k.length < 8) {
      setError('Вставьте API-ключ LLM (OpenAI-совместимый, для тарифа BYOK).')
      return
    }
    const bu = llmBaseUrl.trim()
    const r = await apiFetch('/api/integrations/llm', {
      method: 'PUT',
      body: JSON.stringify({ api_key: k, base_url: bu || null }),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    setLlmApiKey('')
    setLlmBaseUrl('')
    setInteg((await r.json()) as IntegrationStatus)
  }

  const generateModelProfileFromPhotos = async () => {
    setError(null)
    if (newModelPhotos.length === 0) {
      setError('Сначала выберите фото модели (до 5 файлов).')
      return
    }
    setNewModelProfileGenBusy(true)
    try {
      const fd = new FormData()
      for (const row of newModelPhotos) fd.append('images', row.file)
      const r = await apiFetch('/api/studio/models/generate-profile', { method: 'POST', body: fd })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      const data = (await r.json()) as { profile_text: string }
      setNewModelProfile(data.profile_text)
      void refreshMe()
    } catch (e) {
      setError(
        e instanceof TypeError && e.message === 'Failed to fetch'
          ? 'Сеть: не удалось связаться с сервером.'
          : e instanceof Error
            ? e.message
            : 'Ошибка запроса',
      )
    } finally {
      setNewModelProfileGenBusy(false)
    }
  }

  const createStudioModel = async () => {
    setError(null)
    const name = newModelName.trim()
    if (!name) {
      setError('Укажите название модели.')
      return
    }
    const lt = newModelExportLat.trim()
    const ln = newModelExportLon.trim()
    if ((lt && !ln) || (!lt && ln)) {
      setError('Укажите и широту, и долготу для ГЕО, или оставьте оба поля пустыми.')
      return
    }
    const fd = new FormData()
    fd.append('name', name)
    fd.append('profile_text', newModelProfile.trim())
    for (const row of newModelPhotos) fd.append('images', row.file)
    fd.append(
      'image_kinds',
      JSON.stringify(newModelPhotos.map((r) => r.kind)),
    )
    fd.append(
      'image_export_selfies',
      JSON.stringify(newModelPhotos.map((r) => r.export_selfie)),
    )
    fd.append('camera_preset_id', newModelCameraPresetId.trim())
    fd.append('export_lat', lt)
    fd.append('export_lon', ln)
    const r = await apiFetch('/api/studio/models', { method: 'POST', body: fd })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    setNewModelName('')
    setNewModelProfile('')
    setNewModelPhotos([])
    setNewModelCameraPresetId('')
    setNewModelExportLat('')
    setNewModelExportLon('')
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
    setAppendModelPhotosById((prev) => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    void loadStudioModels()
  }

  const adminApplyCredits = async (userId: number) => {
    setError(null)
    const raw = adminCreditInput[userId] ?? ''
    const delta = parseInt(raw, 10)
    if (Number.isNaN(delta) || delta === 0) {
      setError('Укажите целое число кредитов (не 0) для начисления или списания.')
      return
    }
    setAdminDataBusy(true)
    try {
      const r = await apiFetch(`/api/admin/users/${userId}/credits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delta, note: 'admin panel' }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      setAdminCreditInput((prev) => {
        const n = { ...prev }
        delete n[userId]
        return n
      })
      void refreshMe()
      void loadAdminStats()
      void fetchAdminUsers(adminUserSearch)
    } finally {
      setAdminDataBusy(false)
    }
  }

  const adminPatchSubscription = async (
    userId: number,
    patch: { status?: string; billing_plan?: string; current_period_end?: string | null },
  ) => {
    setError(null)
    setAdminDataBusy(true)
    try {
      const body: Record<string, string | null> = {}
      if (patch.status !== undefined) body.status = patch.status
      if (patch.billing_plan !== undefined) body.billing_plan = patch.billing_plan
      if (patch.current_period_end !== undefined) body.current_period_end = patch.current_period_end
      const r = await apiFetch(`/api/admin/users/${userId}/subscription`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      void fetchAdminUsers(adminUserSearch)
      void refreshMe()
    } finally {
      setAdminDataBusy(false)
    }
  }

  const adminSetUserActive = async (userId: number, isActive: boolean) => {
    setError(null)
    const r = await apiFetch(`/api/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: isActive }),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    void fetchAdminUsers(adminUserSearch)
  }

  const adminSetPlatformAdmin = async (userId: number, v: boolean) => {
    setError(null)
    const r = await apiFetch(`/api/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_platform_admin: v }),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatApiErrorDetail(j) || r.statusText)
      return
    }
    void fetchAdminUsers(adminUserSearch)
    void refreshMe()
  }

  const patchStudioModel = async (id: number) => {
    const d = modelDrafts[id]
    if (!d) return
    setError(null)
    const lt = d.export_lat.trim()
    const ln = d.export_lon.trim()
    if ((lt && !ln) || (!lt && ln)) {
      setError('Укажите и широту, и долготу для ГЕО, или оставьте оба поля пустыми.')
      return
    }
    let export_lat: number | null = null
    let export_lon: number | null = null
    if (lt && ln) {
      export_lat = parseFloat(lt.replace(',', '.'))
      export_lon = parseFloat(ln.replace(',', '.'))
      if (Number.isNaN(export_lat) || Number.isNaN(export_lon)) {
        setError('Широта и долгота должны быть числами (например 55.7558 и 37.6173).')
        return
      }
    }
    setModelSavingId(id)
    try {
      const r = await apiFetch(`/api/studio/models/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: d.name.trim(),
          profile_text: d.profile_text,
          camera_preset_id: d.camera_preset_id.trim() || null,
          export_lat,
          export_lon,
        }),
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

  const uploadAppendStudioModelImages = async (id: number, rows: NewModelPhotoRow[]) => {
    if (!rows.length) return
    setError(null)
    setModelSavingId(id)
    try {
      const fd = new FormData()
      for (const row of rows) fd.append('images', row.file)
      fd.append(
        'image_kinds',
        JSON.stringify(rows.map((r) => r.kind)),
      )
      fd.append(
        'image_export_selfies',
        JSON.stringify(rows.map((r) => r.export_selfie)),
      )
      const r = await apiFetch(`/api/studio/models/${id}/images`, { method: 'POST', body: fd })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      setAppendModelPhotosById((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      void loadStudioModels()
    } finally {
      setModelSavingId(null)
    }
  }

  const patchStudioModelImage = async (
    modelId: number,
    imageId: number,
    patch: { kind?: StudioModelImageKind; export_selfie?: boolean },
  ) => {
    setError(null)
    setModelSavingId(modelId)
    try {
      const r = await apiFetch(`/api/studio/models/${modelId}/images/${imageId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
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

  const startYookassaPayment = async (
    product: BillingPlanRow['product'],
    creditsQuantity?: number,
  ) => {
    setError(null)
    setYookassaPayBusy(product)
    try {
      const body =
        product === 'credits_pack'
          ? { product, credits_quantity: creditsQuantity }
          : { product }
      const r = await apiFetch('/api/billing/yookassa/payment', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatApiErrorDetail(j) || r.statusText)
        return
      }
      const data = (await r.json()) as { confirmation_url: string }
      window.location.href = data.confirmation_url
    } finally {
      setYookassaPayBusy(null)
    }
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
            <img src="/brand-icon.svg" alt="" className="brand-mark" width={40} height={40} aria-hidden />
            <div>
              <h1>ModelMate</h1>
              <p className="sub">
                Студия ведения AI-моделей: регистрация, чат с переводом и подключение каналов
              </p>
            </div>
          </div>
        </header>
        <nav
          aria-label="Справочные страницы"
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '0.5rem',
            flexWrap: 'wrap',
            margin: '-0.35rem 0 0.5rem',
            fontSize: '0.8125rem',
          }}
        >
          <Link to="/" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            Главная сайта
          </Link>
          <Link to="/pricing" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            Тарифы
          </Link>
          <Link to="/faq" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            FAQ
          </Link>
          <Link to="/privacy" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            Конфиденциальность
          </Link>
          <Link to="/terms" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            Соглашение
          </Link>
          <Link to="/login" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            Отдельная страница входа
          </Link>
        </nav>
        <main className="auth-page">
          <AuthPanel
            onSuccess={async (fromRegister?: boolean) => {
              const r = await apiFetch('/api/auth/me')
              if (r.ok) setMe((await r.json()) as UserMe)
              setAuthed(true)
              if (fromRegister) {
                setAccountTab('overview')
                setAccountOpen(true)
              }
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
    isMobileLayout && selectedId != null && appSection === 'chat' && canChat
      ? 'mobile-chat-open'
      : '',
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
          <img src="/brand-icon.svg" alt="" className="brand-mark" width={40} height={40} aria-hidden />
          <div>
            <h1>ModelMate</h1>
            <p className="sub">
              Студия ведения AI-моделей — диалоги, интеграции и генерация изображений
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
                {me.credits_balance} кр. · {userBillingPlanLabel(me.billing_plan)} ·{' '}
                {subscriptionStatusLabel(me.subscription_status)}
              </span>
            </div>
          ) : null}
          <button type="button" className="ghost-btn" onClick={() => setAccountOpen((o) => !o)}>
            Личный кабинет
          </button>
          <Link to="/" className="ghost-btn">
            О сервисе
          </Link>
          <button
            type="button"
            className="ghost-btn"
            onClick={() => {
              setToken(null)
              setAuthed(false)
              setMe(null)
              setConversations([])
              setSelectedId(null)
              navigate('/', { replace: true })
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
        <div className="banner error">Нет связи с Telegram. Обратитесь к администратору сервиса.</div>
      )}

      {accountOpen && (
        <div className="account-panel">
          <div className="account-panel-header">
            <h3>Личный кабинет</h3>
            <button type="button" className="ghost-btn account-panel-close" onClick={() => setAccountOpen(false)}>
              Закрыть
            </button>
          </div>
          <div className="account-cabinet-tabs" role="tablist" aria-label="Разделы кабинета">
            <button
              type="button"
              role="tab"
              aria-selected={accountTab === 'overview'}
              className={accountTab === 'overview' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
              onClick={() => setAccountTab('overview')}
            >
              Обзор
            </button>
            {isOwner ? (
              <button
                type="button"
                role="tab"
                aria-selected={accountTab === 'billing'}
                className={accountTab === 'billing' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                onClick={() => setAccountTab('billing')}
              >
                Тариф и баланс
              </button>
            ) : null}
            <button
              type="button"
              role="tab"
              aria-selected={accountTab === 'integrations'}
              className={accountTab === 'integrations' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
              onClick={() => setAccountTab('integrations')}
            >
              Подключения
            </button>
            {canStudioModels ? (
              <button
                type="button"
                role="tab"
                aria-selected={accountTab === 'models'}
                className={accountTab === 'models' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                onClick={() => setAccountTab('models')}
              >
                Модели
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
            {canPlatformAdmin ? (
              <button
                type="button"
                role="tab"
                aria-selected={accountTab === 'admin'}
                className={accountTab === 'admin' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                onClick={() => setAccountTab('admin')}
              >
                Админ
              </button>
            ) : null}
          </div>

          {accountTab === 'overview' && (
            <div className="account-cabinet-pane cabinet-overview" role="tabpanel">
              <p className="cabinet-lead muted">
                Сводка по аккаунту. Тариф, оплата и история кредитов — в разделе «Тариф и баланс» (владелец).
              </p>
              <div className="cabinet-dashboard-grid">
                <div className="cabinet-dash-card">
                  <div className="cabinet-dash-label">Баланс кредитов</div>
                  <div className="cabinet-dash-value">{me?.credits_balance ?? '—'}</div>
                  <p className="cabinet-dash-hint muted">Общий для пространства</p>
                </div>
                <div className="cabinet-dash-card">
                  <div className="cabinet-dash-label">Тариф</div>
                  <div className="cabinet-dash-value">{userBillingPlanLabel(me?.billing_plan)}</div>
                  <p className="cabinet-dash-hint muted">{userBillingPlanLong(me?.billing_plan)}</p>
                </div>
                <div className="cabinet-dash-card">
                  <div className="cabinet-dash-label">Операторов</div>
                  <div className="cabinet-dash-value">{me?.operators_count ?? 0}</div>
                  <p className="cabinet-dash-hint muted">Сотрудники без учёта владельца</p>
                </div>
                <div className="cabinet-dash-card">
                  <div className="cabinet-dash-label">Подписка</div>
                  <div className="cabinet-dash-value">{subscriptionStatusLabel(me?.subscription_status)}</div>
                  <p className="cabinet-dash-hint muted">
                    {me?.subscription_period_end
                      ? `До ${formatDateTimeRu(me.subscription_period_end)}`
                      : 'Оформите тариф при необходимости'}
                  </p>
                </div>
              </div>
              {me?.billing_require_active_subscription ? (
                <div className="banner info" style={{ marginTop: '1rem' }}>
                  Для студии нужна активная подписка. Сейчас:{' '}
                  <strong>{subscriptionStatusLabel(me?.subscription_status)}</strong>.
                </div>
              ) : null}
              <div className="cabinet-overview-actions">
                {isOwner ? (
                  <button type="button" className="ghost-btn" onClick={() => setAccountTab('billing')}>
                    Тариф и баланс
                  </button>
                ) : null}
                <button type="button" className="ghost-btn" onClick={() => setAccountTab('integrations')}>
                  Подключения
                </button>
                {isOwner ? (
                  <button type="button" className="ghost-btn" onClick={() => setAccountTab('team')}>
                    Команда
                  </button>
                ) : null}
              </div>
            </div>
          )}

          {accountTab === 'billing' && isOwner && (
            <div className="account-cabinet-pane" role="tabpanel">
              <p className="cabinet-lead muted">
                <strong>Здесь выбираете тариф</strong> (Managed или BYOK) <strong>и оплачиваете</strong> подписку или
                пакет кредитов. При неактивной подписке студия может быть недоступна.
              </p>
              <p className="cabinet-lead muted">
                <strong>Managed</strong> — студия списывает кредиты. <strong>BYOK</strong> — ваши ключи к AI и
                WaveSpeed, кредиты на студию не списываются.
              </p>
              <div className="cabinet-module cabinet-module--highlight">
                <div className="cabinet-module-head">
                  <span className="cabinet-module-title">Текущее состояние</span>
                  <span
                    className={`cabinet-module-badge ${me?.subscription_status === 'active' ? 'is-ok' : 'is-warn'}`}
                  >
                    {subscriptionStatusLabel(me?.subscription_status)}
                  </span>
                </div>
                <p className="cabinet-module-body">{userBillingPlanLong(me?.billing_plan)}</p>
                <p className="muted cabinet-module-meta">
                  {me?.subscription_period_end
                    ? `Период до ${formatDateTimeRu(me.subscription_period_end)}`
                    : 'Дата окончания появится после оплаты'}
                  {' · '}Баланс: <strong>{me?.credits_balance ?? 0}</strong> кр.
                </p>
              </div>
              <h4 className="account-sub">Тариф и пополнение</h4>
              {me?.online_payment_available ? (
                <>
                  <p className="muted" style={{ marginBottom: '0.75rem' }}>
                    Оплата банковской картой. После успешной оплаты вернитесь в кабинет.
                  </p>
                  <div className="cabinet-yookassa-rows">
                    {billingPlanRows.map((row) => {
                      if (row.product === 'credits_pack' && row.credits_pricing) {
                        const p = row.credits_pricing
                        const q = Math.floor(creditsPurchaseQty)
                        const valid =
                          Number.isFinite(q) && Number.isInteger(q) && q >= p.min_quantity
                        const totalRub = valid ? creditsPurchaseTotalRub(q, p) : null
                        return (
                          <div key={row.product} className="cabinet-yookassa-row">
                            <div>
                              <div className="cabinet-offer-title">{row.title}</div>
                              <p className="muted small" style={{ margin: '0.35rem 0 0.25rem' }}>
                                От {p.min_quantity} шт. —{' '}
                                {p.unit_price_rub.toLocaleString('ru-RU', {
                                  minimumFractionDigits: 0,
                                  maximumFractionDigits: 2,
                                })}{' '}
                                ₽/кредит; от {p.bulk_from} шт. —{' '}
                                {p.bulk_unit_price_rub.toLocaleString('ru-RU', {
                                  minimumFractionDigits: 0,
                                  maximumFractionDigits: 2,
                                })}{' '}
                                ₽/кредит.
                              </p>
                              <label
                                className="muted small"
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  flexWrap: 'wrap',
                                  gap: '0.5rem',
                                  marginTop: '0.35rem',
                                }}
                              >
                                Количество кредитов:
                                <input
                                  type="number"
                                  min={p.min_quantity}
                                  step={1}
                                  value={creditsPurchaseQty}
                                  style={{
                                    width: '6.5rem',
                                    padding: '0.35rem 0.5rem',
                                    borderRadius: 8,
                                    border: '1px solid var(--border, rgba(255,255,255,0.18))',
                                    background: 'var(--bg-subtle, rgba(255,255,255,0.06))',
                                    color: 'inherit',
                                  }}
                                  onChange={(e) => {
                                    const v = e.target.valueAsNumber
                                    if (Number.isNaN(v)) setCreditsPurchaseQty(p.min_quantity)
                                    else setCreditsPurchaseQty(Math.floor(v))
                                  }}
                                />
                              </label>
                              <div className="cabinet-offer-price" style={{ marginTop: '0.35rem' }}>
                                {totalRub != null
                                  ? `${totalRub.toLocaleString('ru-RU', {
                                      minimumFractionDigits: 0,
                                      maximumFractionDigits: 2,
                                    })} ₽`
                                  : '—'}
                              </div>
                            </div>
                            <button
                              type="button"
                              className="send-btn"
                              disabled={yookassaPayBusy !== null || !valid}
                              onClick={() => void startYookassaPayment('credits_pack', q)}
                            >
                              {yookassaPayBusy === row.product ? '…' : 'Оплатить'}
                            </button>
                          </div>
                        )
                      }
                      return (
                        <div key={row.product} className="cabinet-yookassa-row">
                          <div>
                            <div className="cabinet-offer-title">{row.title}</div>
                            <div className="cabinet-offer-price">
                              {row.price_rub}{' '}
                              {row.currency === 'RUB' || !row.currency ? '₽' : row.currency}
                            </div>
                          </div>
                          <button
                            type="button"
                            className="send-btn"
                            disabled={yookassaPayBusy !== null}
                            onClick={() => void startYookassaPayment(row.product)}
                          >
                            {yookassaPayBusy === row.product ? '…' : 'Оплатить'}
                          </button>
                        </div>
                      )
                    })}
                  </div>
                </>
              ) : (
                <p className="muted">Онлайн-оплата не подключена. Обратитесь к администратору сервиса.</p>
              )}
              <h4 className="account-sub">История операций</h4>
              {creditHistoryBusy ? (
                <p className="muted">Загрузка…</p>
              ) : creditHistoryItems.length === 0 ? (
                <p className="muted">Записей пока нет.</p>
              ) : (
                <div className="cabinet-table-wrap">
                  <table className="cabinet-table">
                    <thead>
                      <tr>
                        <th>Дата</th>
                        <th>Операция</th>
                        <th>Кредиты</th>
                      </tr>
                    </thead>
                    <tbody>
                      {creditHistoryItems.map((row) => (
                        <tr key={row.id}>
                          <td className="mono small">{formatDateTimeRu(row.created_at)}</td>
                          <td>{creditKindLabel(row.kind)}</td>
                          <td
                            className={`mono ${row.credits_delta >= 0 ? 'cabinet-credit-plus' : 'cabinet-credit-minus'}`}
                          >
                            {row.credits_delta > 0 ? `+${row.credits_delta}` : row.credits_delta}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {creditHistoryHasMore ? (
                <p className="muted small">Показаны последние операции.</p>
              ) : null}
            </div>
          )}

          {accountTab === 'integrations' && (
            <div className="account-cabinet-pane cabinet-connections" role="tabpanel">
              <p className="cabinet-lead muted">
                Подключите каналы и API. Поля редактирования зависят от прав: при необходимости попросите владельца
                выдать доступ к интеграциям.
              </p>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">Telegram</h4>
                  <span
                    className={`cabinet-module-badge ${integ?.telegram_configured ? 'is-ok' : 'is-warn'}`}
                  >
                    {integ?.telegram_configured ? 'Подключено' : 'Не подключено'}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  Токен от BotFather. Сайт должен работать по <strong>HTTPS</strong> — иначе Telegram не примет
                  webhook (для локальной отладки используйте туннель).
                </p>
                {integ?.telegram_configured ? (
                  <p className="small mono">
                    @{integ.telegram_bot_username ?? '—'}
                    {integ.telegram_webhook_registered ? ' · webhook активен' : ' · webhook не подтверждён'}
                  </p>
                ) : null}
                <div className="cabinet-module-form">
                  <label>
                    Токен бота
                    <input
                      type="password"
                      autoComplete="off"
                      value={tgToken}
                      onChange={(e) => setTgToken(e.target.value)}
                      placeholder="Вставьте токен"
                      disabled={!canIntegrations}
                    />
                  </label>
                  <button
                    type="button"
                    className="send-btn"
                    disabled={!canIntegrations}
                    onClick={() => void saveTelegram()}
                  >
                    Сохранить
                  </button>
                </div>
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">Fanvue</h4>
                  <span className={`cabinet-module-badge ${integ?.fanvue_configured ? 'is-ok' : 'is-warn'}`}>
                    {integ?.fanvue_configured ? 'Подключено' : 'Не подключено'}
                  </span>
                </div>
                <p className="muted cabinet-module-body">API и вебхуки платформы Fanvue.</p>
                <div className="cabinet-module-form cabinet-module-form--grid">
                  <label>
                    Access token
                    <input
                      type="password"
                      value={fvToken}
                      onChange={(e) => setFvToken(e.target.value)}
                      disabled={!canIntegrations}
                    />
                  </label>
                  <label>
                    Creator UUID
                    <input value={fvCreator} onChange={(e) => setFvCreator(e.target.value)} disabled={!canIntegrations} />
                  </label>
                  <label className="cabinet-field-span2">
                    Webhook signing secret
                    <input
                      type="password"
                      value={fvSecret}
                      onChange={(e) => setFvSecret(e.target.value)}
                      disabled={!canIntegrations}
                    />
                  </label>
                  <button
                    type="button"
                    className="send-btn"
                    disabled={!canIntegrations}
                    onClick={() => void saveFanvue()}
                  >
                    Сохранить
                  </button>
                </div>
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">WaveSpeed</h4>
                  <span className={`cabinet-module-badge ${integ?.wavespeed_configured ? 'is-ok' : 'is-warn'}`}>
                    {integ?.wavespeed_configured ? 'Ключ сохранён' : 'Нет ключа'}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  Генерация и апскейл в студии через WaveSpeed возможны только с вашим ключом из этого поля
                  (любой тариф). Без сохранённого ключа запросы к WaveSpeed не выполняются.
                </p>
                <div className="cabinet-module-form">
                  <label>
                    API-ключ
                    <input
                      type="password"
                      autoComplete="off"
                      value={wsApiKey}
                      onChange={(e) => setWsApiKey(e.target.value)}
                      disabled={!canIntegrations}
                    />
                  </label>
                  <button
                    type="button"
                    className="send-btn"
                    disabled={!canIntegrations}
                    onClick={() => void saveWavespeed()}
                  >
                    Сохранить
                  </button>
                </div>
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">Текстовая модель (BYOK)</h4>
                  <span className={`cabinet-module-badge ${integ?.llm_configured ? 'is-ok' : 'is-warn'}`}>
                    {integ?.llm_configured ? 'Есть ключ' : 'Не настроено'}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  OpenAI-совместимый API только для тарифа <strong>BYOK</strong>. На Managed текст обрабатывается на
                  сервисе.
                </p>
                <div className="cabinet-module-form cabinet-module-form--grid">
                  <label>
                    API-ключ
                    <input
                      type="password"
                      autoComplete="off"
                      value={llmApiKey}
                      onChange={(e) => setLlmApiKey(e.target.value)}
                      disabled={!canIntegrations}
                    />
                  </label>
                  <label>
                    Базовый URL (по желанию)
                    <input
                      type="text"
                      autoComplete="off"
                      value={llmBaseUrl}
                      onChange={(e) => setLlmBaseUrl(e.target.value)}
                      placeholder="https://api.openai.com/v1"
                      disabled={!canIntegrations}
                    />
                  </label>
                  <button
                    type="button"
                    className="send-btn"
                    disabled={!canIntegrations}
                    onClick={() => void saveLlm()}
                  >
                    Сохранить
                  </button>
                </div>
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">Уведомления</h4>
                  <span className={`cabinet-module-badge ${webPushState === 'on' ? 'is-ok' : 'is-warn'}`}>
                    {webPushState === 'loading' || webPushState === 'unknown'
                      ? '…'
                      : webPushState === 'on'
                        ? 'Вкл.'
                        : 'Выкл.'}
                  </span>
                </div>
                <p className="muted cabinet-module-body">Браузерные уведомления о новых сообщениях в чате.</p>
                {webPushState === 'denied' ? (
                  <p className="muted small">Разрешите уведомления для сайта в настройках браузера.</p>
                ) : null}
                {canChat && health?.web_push_configured && webPushEnvironmentOk() ? (
                  <div className="cabinet-module-form">
                    {webPushState === 'on' ? (
                      <button
                        type="button"
                        className="ghost-btn"
                        disabled={pushBusy}
                        onClick={() => void disableWebPush()}
                      >
                        Отключить
                      </button>
                    ) : webPushState === 'off' ? (
                      <button
                        type="button"
                        className="send-btn"
                        disabled={pushBusy}
                        onClick={() => void enableWebPush()}
                      >
                        Включить уведомления
                      </button>
                    ) : null}
                  </div>
                ) : !health?.web_push_configured ? (
                  <p className="muted small">На сервере не включены push-уведомления.</p>
                ) : null}
              </section>

              {integ?.integration_hint ? (
                <div className="banner info cabinet-hint-banner">{integ.integration_hint}</div>
              ) : null}
              {!canIntegrations ? (
                <p className="muted" style={{ marginTop: '1rem' }}>
                  Редактирование подключений недоступно по правам аккаунта.
                </p>
              ) : null}
            </div>
          )}

          {accountTab === 'models' && canStudioModels && (
            <div className="account-cabinet-pane" role="tabpanel">
              {studioPaywalled ? (
                <div className="banner info" style={{ marginBottom: '1rem' }}>
                  Редактирование моделей недоступно без активной подписки владельца.{' '}
                  {isOwner ? (
                    <button
                      type="button"
                      className="ghost-btn"
                      style={{ marginLeft: '0.5rem' }}
                      onClick={() => setAccountTab('billing')}
                    >
                      Тариф и баланс
                    </button>
                  ) : (
                    <> Попросите владельца оформить тариф в кабинете.</>
                  )}
                </div>
              ) : null}
              <p className="cabinet-lead muted">
                Модели подставляются в промпт на вкладке «Генерация картинок». До 5 фото на модель. Для
                каждого снимка укажите тип: лицо, тело, интимный референс или общий — от этого зависит
                порядок в запросе к image-edit и текст для LLM.
              </p>

              <h4 className="account-sub">Новая модель</h4>
              <div className="account-grid studio-models-block cabinet-new-model">
                <label>
                  Название
                  <input
                    value={newModelName}
                    onChange={(e) => setNewModelName(e.target.value)}
                    placeholder="Например: Анна — чёрные волосы"
                    disabled={studioPaywalled}
                  />
                </label>
                <label>
                  Фото модели (до 5)
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    multiple
                    disabled={studioPaywalled}
                    onChange={(e) => {
                      const list = e.target.files ? Array.from(e.target.files) : []
                      setNewModelPhotos(
                        list.slice(0, 5).map((file, i) => ({
                          file,
                          kind: (i === 0 ? 'face' : 'other') as StudioModelImageKind,
                          export_selfie: i === 0,
                        })),
                      )
                    }}
                  />
                  {newModelPhotos.length > 0 ? (
                    <ul className="studio-new-model-photo-kinds">
                      {newModelPhotos.map((row, idx) => (
                        <li key={`${row.file.name}-${idx}`} className="studio-model-photo-kind-row">
                          <span className="muted small studio-model-photo-filename">
                            {row.file.name}
                          </span>
                          <select
                            className="studio-model-kind-select"
                            value={row.kind}
                            disabled={studioPaywalled}
                            onChange={(e) => {
                              const v = e.target.value as StudioModelImageKind
                              setNewModelPhotos((prev) =>
                                prev.map((p, i) => (i === idx ? { ...p, kind: v } : p)),
                              )
                            }}
                          >
                            {STUDIO_MODEL_IMAGE_KIND_OPTIONS.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                          <label className="studio-label studio-check studio-model-selfie-inline">
                            <input
                              type="checkbox"
                              checked={row.export_selfie}
                              disabled={studioPaywalled}
                              onChange={(e) => {
                                const v = e.target.checked
                                setNewModelPhotos((prev) =>
                                  prev.map((p, i) => (i === idx ? { ...p, export_selfie: v } : p)),
                                )
                              }}
                            />
                            <span>Селфи (EXIF)</span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </label>
                <label className="studio-new-model-profile-label">
                  Описание внешности (JSON, можно вставить вручную)
                  <textarea
                    rows={6}
                    value={newModelProfile}
                    onChange={(e) => setNewModelProfile(e.target.value)}
                    placeholder='{"model_profile": { … }} — или нажмите кнопку ниже'
                    className="studio-model-profile-textarea"
                    disabled={studioPaywalled}
                  />
                  <button
                    type="button"
                    className="ghost-btn studio-gen-profile-btn"
                    disabled={studioPaywalled || newModelProfileGenBusy || newModelPhotos.length === 0}
                    title={newModelPhotos.length === 0 ? 'Сначала выберите фото' : undefined}
                    onClick={() => void generateModelProfileFromPhotos()}
                  >
                    {newModelProfileGenBusy ? 'Генерация…' : 'Сгенерировать из фото'}
                  </button>
                </label>
                <div className="studio-model-export-block account-grid" style={{ gridColumn: '1 / -1' }}>
                  <h4 className="account-sub" style={{ margin: 0 }}>
                    Экспорт «как с телефона»
                  </h4>
                  <p className="muted small" style={{ margin: 0 }}>
                    На сохранённый снимок студии: лёгкий шум, JPEG и EXIF по пресету. Пустой пресет — без
                    этой обработки. Тип камеры (селфи / основная) задаётся отдельно для каждого фото модели
                    ниже; в файл попадает настройка кадра «лицо», иначе — первого по порядку.
                  </p>
                  <label>
                    Пресет камеры
                    <select
                      value={newModelCameraPresetId}
                      disabled={studioPaywalled}
                      onChange={(e) => setNewModelCameraPresetId(e.target.value)}
                    >
                      <option value="">— не применять —</option>
                      {studioCameraPresets.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Широта (ГЕО)
                    <input
                      value={newModelExportLat}
                      onChange={(e) => setNewModelExportLat(e.target.value)}
                      placeholder="55.7558"
                      inputMode="decimal"
                      disabled={studioPaywalled}
                    />
                  </label>
                  <label>
                    Долгота (ГЕО)
                    <input
                      value={newModelExportLon}
                      onChange={(e) => setNewModelExportLon(e.target.value)}
                      placeholder="37.6173"
                      inputMode="decimal"
                      disabled={studioPaywalled}
                    />
                  </label>
                </div>
                <button
                  type="button"
                  className="send-btn"
                  disabled={studioPaywalled}
                  onClick={() => void createStudioModel()}
                >
                  Создать модель
                </button>
              </div>

              {studioModels.length === 0 ? (
                <p className="muted cabinet-empty-models">Пока нет моделей — создайте первую выше.</p>
              ) : (
                <div className="model-card-grid">
                  {studioModels.map((m) => {
                    const draft = modelDrafts[m.id] ?? defaultStudioModelCabinetDraft(m)
                    const busy = modelSavingId === m.id
                    const imgs = m.images ?? []
                    const pendingAppend = appendModelPhotosById[m.id] ?? []
                    const modelPhotoSlotsFull = m.image_count + pendingAppend.length >= 5
                    return (
                      <article key={m.id} className="model-card">
                        <div className="model-card-head">
                          <h4 className="model-card-title">Модель #{m.id}</h4>
                          <button
                            type="button"
                            className="ghost-btn danger-text model-card-delete"
                            disabled={busy || studioPaywalled}
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
                                <div className="model-thumb-frame">
                                  <img src={im.url} alt="" className="model-thumb" loading="lazy" />
                                  <button
                                    type="button"
                                    className="model-thumb-remove"
                                    title="Удалить фото"
                                    disabled={busy || studioPaywalled}
                                    onClick={() => void deleteStudioModelImage(m.id, im.id)}
                                  >
                                    ×
                                  </button>
                                </div>
                                <select
                                  className="studio-model-kind-select"
                                  aria-label="Тип референса"
                                  value={normalizeStudioImageKind(im.kind)}
                                  disabled={busy || studioPaywalled}
                                  onChange={(e) => {
                                    const v = e.target.value as StudioModelImageKind
                                    void patchStudioModelImage(m.id, im.id, { kind: v })
                                  }}
                                >
                                  {STUDIO_MODEL_IMAGE_KIND_OPTIONS.map((o) => (
                                    <option key={o.value} value={o.value}>
                                      {o.label}
                                    </option>
                                  ))}
                                </select>
                                <label className="studio-label studio-check model-thumb-selfie-check">
                                  <input
                                    type="checkbox"
                                    checked={!!im.export_selfie}
                                    disabled={busy || studioPaywalled}
                                    onChange={(e) =>
                                      void patchStudioModelImage(m.id, im.id, {
                                        export_selfie: e.target.checked,
                                      })
                                    }
                                  />
                                  <span>Селфи EXIF</span>
                                </label>
                              </div>
                            ))
                          )}
                        </div>
                        {pendingAppend.length > 0 ? (
                          <div className="model-card-append-draft">
                            <p className="muted small model-card-append-hint">
                              К загрузке: укажите тип кадра для каждого файла.
                            </p>
                            <ul className="studio-new-model-photo-kinds">
                              {pendingAppend.map((row, idx) => (
                                <li
                                  key={`${row.file.name}-${idx}`}
                                  className="studio-model-photo-kind-row"
                                >
                                  <span className="muted small studio-model-photo-filename">
                                    {row.file.name}
                                  </span>
                                  <select
                                    className="studio-model-kind-select"
                                    value={row.kind}
                                    disabled={busy || studioPaywalled}
                                    onChange={(e) => {
                                      const v = e.target.value as StudioModelImageKind
                                      setAppendModelPhotosById((prev) => {
                                        const cur = prev[m.id] ?? []
                                        const nextRows = cur.map((p, i) =>
                                          i === idx ? { ...p, kind: v } : p,
                                        )
                                        return { ...prev, [m.id]: nextRows }
                                      })
                                    }}
                                  >
                                    {STUDIO_MODEL_IMAGE_KIND_OPTIONS.map((o) => (
                                      <option key={o.value} value={o.value}>
                                        {o.label}
                                      </option>
                                    ))}
                                  </select>
                                  <label className="studio-label studio-check studio-model-selfie-inline">
                                    <input
                                      type="checkbox"
                                      checked={row.export_selfie}
                                      disabled={busy || studioPaywalled}
                                      onChange={(e) => {
                                        const v = e.target.checked
                                        setAppendModelPhotosById((prev) => {
                                          const cur = prev[m.id] ?? []
                                          const nextRows = cur.map((p, i) =>
                                            i === idx ? { ...p, export_selfie: v } : p,
                                          )
                                          return { ...prev, [m.id]: nextRows }
                                        })
                                      }}
                                    />
                                    <span>Селфи (EXIF)</span>
                                  </label>
                                  <button
                                    type="button"
                                    className="ghost-btn danger-text"
                                    disabled={busy || studioPaywalled}
                                    title="Убрать из списка"
                                    onClick={() =>
                                      setAppendModelPhotosById((prev) => {
                                        const cur = prev[m.id] ?? []
                                        const nextRows = cur.filter((_, i) => i !== idx)
                                        const next = { ...prev }
                                        if (nextRows.length) next[m.id] = nextRows
                                        else delete next[m.id]
                                        return next
                                      })
                                    }
                                  >
                                    ×
                                  </button>
                                </li>
                              ))}
                            </ul>
                            <div className="model-card-append-draft-actions">
                              <button
                                type="button"
                                className="ghost-btn"
                                disabled={busy || studioPaywalled}
                                onClick={() =>
                                  setAppendModelPhotosById((prev) => {
                                    const next = { ...prev }
                                    delete next[m.id]
                                    return next
                                  })
                                }
                              >
                                Отменить
                              </button>
                              <button
                                type="button"
                                className="send-btn"
                                disabled={busy || studioPaywalled}
                                onClick={() => void uploadAppendStudioModelImages(m.id, pendingAppend)}
                              >
                                Загрузить ({pendingAppend.length})
                              </button>
                            </div>
                          </div>
                        ) : null}
                        <label className="model-card-field">
                          Название
                          <input
                            value={draft.name}
                            disabled={busy || studioPaywalled}
                            onChange={(e) =>
                              setModelDrafts((prev) => ({
                                ...prev,
                                [m.id]: {
                                  ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
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
                            disabled={busy || studioPaywalled}
                            onChange={(e) =>
                              setModelDrafts((prev) => ({
                                ...prev,
                                [m.id]: {
                                  ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                  profile_text: e.target.value,
                                },
                              }))
                            }
                          />
                        </label>
                        <div className="studio-model-export-block account-grid" style={{ gridColumn: '1 / -1' }}>
                          <h4 className="account-sub" style={{ margin: 0 }}>
                            Экспорт «как с телефона»
                          </h4>
                          <p className="muted small" style={{ margin: 0 }}>
                            Дата/время в EXIF — момент сохранения кадра. ГЕО — опционально (оба поля). Селфи
                            / основная камера в EXIF — у каждого фото в блоке референсов выше.
                          </p>
                          <label>
                            Пресет камеры
                            <select
                              value={draft.camera_preset_id}
                              disabled={busy || studioPaywalled}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    camera_preset_id: e.target.value,
                                  },
                                }))
                              }
                            >
                              <option value="">— не применять —</option>
                              {studioCameraPresets.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Широта
                            <input
                              value={draft.export_lat}
                              disabled={busy || studioPaywalled}
                              placeholder="55.7558"
                              inputMode="decimal"
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    export_lat: e.target.value,
                                  },
                                }))
                              }
                            />
                          </label>
                          <label>
                            Долгота
                            <input
                              value={draft.export_lon}
                              disabled={busy || studioPaywalled}
                              placeholder="37.6173"
                              inputMode="decimal"
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    export_lon: e.target.value,
                                  },
                                }))
                              }
                            />
                          </label>
                        </div>
                        <div className="model-card-actions">
                          <label className="model-card-add-files">
                            <input
                              type="file"
                              accept="image/jpeg,image/png,image/webp,image/gif"
                              multiple
                              className="sr-only-input"
                              disabled={busy || studioPaywalled || modelPhotoSlotsFull}
                              onChange={(e) => {
                                const list = e.target.files ? Array.from(e.target.files) : []
                                const slots = Math.max(0, 5 - m.image_count - pendingAppend.length)
                                const slice = list.slice(0, slots)
                                if (slice.length > 0) {
                                  const priorCount = m.image_count + pendingAppend.length
                                  setAppendModelPhotosById((prev) => ({
                                    ...prev,
                                    [m.id]: [
                                      ...(prev[m.id] ?? []),
                                      ...slice.map((file, j) => {
                                        const isFirstEver = priorCount + j === 0
                                        return {
                                          file,
                                          kind: (isFirstEver
                                            ? 'face'
                                            : 'other') as StudioModelImageKind,
                                          export_selfie: isFirstEver,
                                        }
                                      }),
                                    ],
                                  }))
                                }
                                e.target.value = ''
                              }}
                            />
                            <span className="ghost-btn model-card-add-btn">Добавить фото</span>
                          </label>
                          <button
                            type="button"
                            className="send-btn"
                            disabled={busy || studioPaywalled || !draft.name.trim()}
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

          {accountTab === 'admin' && canPlatformAdmin && (
            <div className="account-cabinet-pane admin-cabinet-pane" role="tabpanel">
              <p className="cabinet-lead muted">
                Платформа: пользователи, кредиты, подписка (статус, тариф Managed/BYOK, дата окончания
                периода), события usage. Счёт и подписка всегда у <strong>владельца</strong> пространства;
                у участников отображаются те же значения. Доступ к этой вкладке выдаёт владелец платформы.
              </p>
              {adminDataBusy && !adminStats ? <p className="muted">Загрузка…</p> : null}
              {adminStats ? (
                <div className="admin-stat-grid">
                  <div className="admin-stat-card">
                    <div className="admin-stat-label">Пользователей</div>
                    <div className="admin-stat-value">{adminStats.total_users}</div>
                    <div className="admin-stat-hint">
                      владельцев: {adminStats.workspace_owners} · в команде: {adminStats.workspace_members}
                    </div>
                  </div>
                  <div className="admin-stat-card">
                    <div className="admin-stat-label">Кредитов (сумма балансов)</div>
                    <div className="admin-stat-value">{adminStats.total_credits_balance}</div>
                  </div>
                  <div className="admin-stat-card">
                    <div className="admin-stat-label">Архив генераций студии</div>
                    <div className="admin-stat-value">{adminStats.studio_generations_total}</div>
                  </div>
                </div>
              ) : null}
              {adminStats && Object.keys(adminStats.usage_by_kind).length > 0 ? (
                <div className="admin-usage-block">
                  <h4 className="account-sub">Usage по типам (события)</h4>
                  <ul className="admin-usage-list">
                    {Object.entries(adminStats.usage_by_kind)
                      .sort((a, b) => a[0].localeCompare(b[0]))
                      .map(([k, c]) => (
                        <li key={k}>
                          <span className="mono">{k || '—'}</span> — {c}
                        </li>
                      ))}
                  </ul>
                </div>
              ) : null}

              <h4 className="account-sub">Пользователи</h4>
              <div className="admin-user-toolbar">
                <input
                  type="search"
                  placeholder="Поиск по email"
                  value={adminUserSearch}
                  onChange={(e) => setAdminUserSearch(e.target.value)}
                  className="admin-user-search"
                />
                <button
                  type="button"
                  className="ghost-btn"
                  disabled={adminDataBusy}
                  onClick={() => void fetchAdminUsers(adminUserSearch)}
                >
                  Найти
                </button>
                <button
                  type="button"
                  className="ghost-btn"
                  disabled={adminDataBusy}
                  onClick={() => {
                    setAdminUserSearch('')
                    void fetchAdminUsers('')
                  }}
                >
                  Сброс
                </button>
              </div>

              <div className="admin-user-table-wrap">
                <table className="admin-user-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Email / роль</th>
                      <th>Статус</th>
                      <th>Тариф</th>
                      <th>Действует до</th>
                      <th>Кр. счёта</th>
                      <th>Активен</th>
                      <th>Админ</th>
                      <th>Кредиты ±</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adminUsers.map((u) => {
                      const isOwnerRow = u.parent_user_id == null
                      return (
                        <tr key={u.id}>
                          <td className="mono">{u.id}</td>
                          <td>
                            <div>{u.email}</div>
                            {!isOwnerRow ? (
                              <div className="muted small">
                                участник: {u.member_login ?? '—'} · владелец:{' '}
                                {u.parent_email ?? String(u.parent_user_id)}
                              </div>
                            ) : (
                              <div className="muted small">владелец</div>
                            )}
                          </td>
                          <td>
                            <select
                              value={u.subscription_status}
                              onChange={(e) => {
                                const v = e.target.value
                                if (v !== u.subscription_status) void adminPatchSubscription(u.id, { status: v })
                              }}
                              className="admin-sub-select"
                              disabled={adminDataBusy}
                            >
                              {SUBSCRIPTION_STATUS_OPTIONS.map((s) => (
                                <option key={s} value={s}>
                                  {SUBSCRIPTION_STATUS_LABELS[s] ?? s}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <select
                              value={(u.billing_plan || 'managed').toLowerCase()}
                              onChange={(e) => {
                                const v = e.target.value
                                if (v !== (u.billing_plan || 'managed').toLowerCase()) {
                                  void adminPatchSubscription(u.id, { billing_plan: v })
                                }
                              }}
                              className="admin-sub-select"
                              disabled={adminDataBusy}
                              title="План владельца пространства; у участников — как у владельца"
                            >
                              {ADMIN_BILLING_PLAN_OPTIONS.map((p) => (
                                <option key={p} value={p}>
                                  {userBillingPlanLabel(p)}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="admin-period-cell">
                            <div className="mono small" title={u.subscription_period_end ?? undefined}>
                              {formatDateTimeRu(u.subscription_period_end)}
                            </div>
                            <div className="admin-period-edit">
                              <input
                                type="datetime-local"
                                className="admin-period-inp"
                                defaultValue={isoToDatetimeLocalValue(u.subscription_period_end)}
                                key={`pe-${u.id}-${u.subscription_period_end ?? 'none'}`}
                                id={`admin-period-${u.id}`}
                                disabled={adminDataBusy}
                              />
                              <button
                                type="button"
                                className="ghost-btn small"
                                disabled={adminDataBusy}
                                onClick={() => {
                                  const el = document.getElementById(
                                    `admin-period-${u.id}`,
                                  ) as HTMLInputElement | null
                                  const raw = el?.value ?? ''
                                  void adminPatchSubscription(u.id, {
                                    current_period_end: raw
                                      ? datetimeLocalInputToIsoUtc(raw)
                                      : null,
                                  })
                                }}
                              >
                                ОК
                              </button>
                              <button
                                type="button"
                                className="ghost-btn small"
                                disabled={adminDataBusy}
                                onClick={() => void adminPatchSubscription(u.id, { current_period_end: null })}
                              >
                                Сброс
                              </button>
                            </div>
                            <p className="muted small admin-sub-hint">Дата окончания периода подписки (UTC).</p>
                          </td>
                          <td>{u.credits_balance}</td>
                          <td>
                            <input
                              type="checkbox"
                              checked={u.is_active}
                              onChange={(e) => void adminSetUserActive(u.id, e.target.checked)}
                            />
                          </td>
                          <td>
                            {isOwnerRow ? (
                              <input
                                type="checkbox"
                                checked={u.is_platform_admin}
                                onChange={(e) => void adminSetPlatformAdmin(u.id, e.target.checked)}
                              />
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                          <td>
                            <div className="admin-credit-row">
                              <input
                                type="text"
                                inputMode="numeric"
                                className="admin-credit-inp"
                                placeholder="+/-"
                                value={adminCreditInput[u.id] ?? ''}
                                onChange={(e) =>
                                  setAdminCreditInput((prev) => ({ ...prev, [u.id]: e.target.value }))
                                }
                              />
                              <button
                                type="button"
                                className="ghost-btn small"
                                disabled={adminDataBusy}
                                onClick={() => void adminApplyCredits(u.id)}
                              >
                                OK
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {import.meta.env.DEV && health && appSection !== 'studio' && (
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
          {health.telegram_proxy_configured ? <span className="ok"> · прокси TG</span> : null}
          {health.openai_studio_configured ? (
            <span className="ok">
              {' '}
              · студия: промпт ({health.studio_prompt_credit_cost ?? '—'} кр.)
            </span>
          ) : (
            <span className="warn"> · студия: текстовая модель на сервере недоступна</span>
          )}
        </div>
      )}

      {hasAnyMainSection && appSection === 'studio' && canStudioAny && (
        <>
        <section className="studio-panel" aria-labelledby="studio-heading">
          <h2 id="studio-heading">Новая картинка</h2>
          {studioPaywalled ? (
            <div className="studio-paywall cabinet-module cabinet-module--highlight" role="status">
              <p className="cabinet-module-body" style={{ marginBottom: '0.75rem' }}>
                Чтобы генерировать картинки, сначала оформите тариф: активная подписка Managed или BYOK.
              </p>
              <p className="muted small" style={{ marginBottom: '1rem' }}>
                {isOwner ? (
                  <>
                    Откройте личный кабинет → вкладка <strong>«Тариф и баланс»</strong>, выберите план и нажмите
                    «Оплатить».
                  </>
                ) : (
                  <>
                    Оформить подписку может владелец аккаунта ({me?.owner_email ?? 'email владельца'}) в кабинете →
                    «Тариф и баланс».
                  </>
                )}
              </p>
              {isOwner ? (
                <button
                  type="button"
                  className="send-btn"
                  onClick={() => {
                    setAccountOpen(true)
                    setAccountTab('billing')
                  }}
                >
                  Перейти к тарифу и оплате
                </button>
              ) : (
                <button type="button" className="ghost-btn" onClick={() => setAccountOpen(true)}>
                  Открыть кабинет
                </button>
              )}
            </div>
          ) : (
            <>
              {!canStudioGenerate ? (
                <div className="banner info">Генерация недоступна по правам. Попросите владельца аккаунта.</div>
              ) : null}
              <div className="studio-grid studio-grid--simple">
            <div className="studio-mode-row" role="group" aria-label="Режим студии">
              <span className="studio-mode-label">Режим</span>
              <div className="studio-mode-segment">
                {(
                  [
                    { id: 'model' as const, label: 'Модель' },
                    { id: 'photo_edit' as const, label: 'Доработать фото' },
                    { id: 'no_face' as const, label: 'Без лица' },
                  ] as const
                ).map(({ id, label }) => (
                  <button
                    key={id}
                    type="button"
                    className={`studio-mode-btn${studioMode === id ? ' is-active' : ''}`}
                    onClick={() => setStudioMode(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <p className="studio-mode-hint">
              {studioMode === 'model'
                ? 'Как раньше: выбранная модель, опционально референс позы и описание.'
                : studioMode === 'photo_edit'
                  ? 'Обязательно загрузите фото; промпт описывает правки. Модель по желанию (подсказка по телу/коже).'
                  : 'Кадр без лица/головы; нужна модель с фото или свой референс.'}
            </p>
            <div className="studio-mode-row" role="group" aria-label="Тип генерации WaveSpeed">
              <span className="studio-mode-label">Тип</span>
              <div className="studio-mode-segment">
                <button
                  type="button"
                  className={`studio-mode-btn${studioWaveProfile === 'regular' ? ' is-active' : ''}`}
                  onClick={() => setStudioWaveProfile('regular')}
                >
                  Обычные фотографии
                </button>
                <button
                  type="button"
                  className={`studio-mode-btn${studioWaveProfile === 'nsfw' ? ' is-active' : ''}`}
                  onClick={() => setStudioWaveProfile('nsfw')}
                >
                  NSFW
                </button>
              </div>
            </div>
            <p className="studio-mode-hint">
              {studioWaveProfile === 'regular'
                ? 'Google Nano Banana Pro: выше качество для обычных снимков; действуют ограничения безопасности Google.'
                : 'Редактор изображений по правилам этой кнопки (настраивается на стороне сервиса).'}
            </p>
            {import.meta.env.DEV && health?.studio_allow_prompt_only ? (
              <>
                <div className="studio-mode-row" role="group" aria-label="Режим вывода студии (отладка)">
                  <span className="studio-mode-label">Вывод</span>
                  <div className="studio-mode-segment">
                    <button
                      type="button"
                      className={`studio-mode-btn${!studioDevPromptOnly ? ' is-active' : ''}`}
                      onClick={() => {
                        setStudioDevPromptOnly(false)
                        setStudioRefinedPromptPreview(null)
                      }}
                    >
                      Картинка
                    </button>
                    <button
                      type="button"
                      className={`studio-mode-btn${studioDevPromptOnly ? ' is-active' : ''}`}
                      onClick={() => {
                        setStudioDevPromptOnly(true)
                        setStudioRefinedPromptPreview(null)
                      }}
                    >
                      Только промпт
                    </button>
                  </div>
                </div>
                <p className="studio-mode-hint">
                  Только dev-сборка Vite +{' '}
                  <span className="mono">STUDIO_ALLOW_PROMPT_ONLY=true</span> на сервере: WaveSpeed не
                  вызывается, внизу показывается итоговый JSON-промпт.
                </p>
              </>
            ) : null}
            {health?.studio_wan_edit_tier_switch && studioWaveProfile === 'nsfw' ? (
              <>
                <div className="studio-mode-row" role="group" aria-label="Редактор WaveSpeed WAN 2.7">
                  <span className="studio-mode-label">WAN 2.7</span>
                  <div className="studio-mode-segment">
                    <button
                      type="button"
                      className={`studio-mode-btn${studioWanEditTier === 'standard' ? ' is-active' : ''}`}
                      onClick={() => setStudioWanEditTier('standard')}
                    >
                      Обычный
                    </button>
                    <button
                      type="button"
                      className={`studio-mode-btn${studioWanEditTier === 'pro' ? ' is-active' : ''}`}
                      onClick={() => setStudioWanEditTier('pro')}
                    >
                      Pro
                    </button>
                  </div>
                </div>
                <p className="studio-mode-hint">
                  Версия Pro на стороне WaveSpeed обычно дороже обычной WAN 2.7.
                </p>
              </>
            ) : null}
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
              {studioMode === 'photo_edit' ? 'Фото для доработки' : 'Референс (по желанию)'}
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
            <label
              className="studio-label studio-check"
              style={!studioFile ? { opacity: 0.55 } : undefined}
            >
              <input
                type="checkbox"
                checked={studioLockModelHairstyle}
                disabled={!studioFile}
                onChange={(e) => setStudioLockModelHairstyle(e.target.checked)}
              />
              <span>
                Причёска как у модели. Снимите галочку, чтобы взять укладку с загруженного фото (лицо,
                фигура и цвет волос по-прежнему из профиля модели).
              </span>
            </label>
            <label className="studio-label">
              Описание
              <textarea
                rows={5}
                placeholder={
                  studioMode === 'photo_edit'
                    ? 'Что изменить: свет, фон, детали…'
                    : 'Что показать на снимке: сцена, свет, настроение…'
                }
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
                    : !studioPromptOnlyDev && !integ?.wavespeed_configured
                      ? 'Сохраните ключ WaveSpeed в разделе «Подключения»'
                      : undefined
                }
                disabled={
                  studioBusy ||
                  !canStudioGenerate ||
                  (!studioDesc.trim() && !studioFile && studioSelectedModelId == null) ||
                  (studioMode === 'photo_edit' && !studioFile) ||
                  (studioMode === 'no_face' && studioSelectedModelId == null && !studioFile) ||
                  !health?.openai_studio_configured ||
                  (!studioPromptOnlyDev && !integ?.wavespeed_configured)
                }
                onClick={() => void refineStudioPrompt()}
              >
                {studioBusy
                  ? 'Генерация…'
                  : studioPromptOnlyDev
                    ? 'Собрать промпт'
                    : 'Сгенерировать'}
              </button>
              {canStudioGenerate && health?.openai_studio_configured ? (
                studioPromptOnlyDev || integ?.wavespeed_configured ? (
                  <span className="studio-credit-hint">
                    {health.studio_prompt_credit_cost ?? '—'} кр.
                  </span>
                ) : (
                  <span className="studio-credit-hint warn">Нужен ключ WaveSpeed в кабинете</span>
                )
              ) : !health?.openai_studio_configured && canStudioGenerate ? (
                <span className="studio-credit-hint warn">Нет доступа к студии</span>
              ) : null}
            </div>
            {import.meta.env.DEV &&
            health?.studio_allow_prompt_only &&
            studioDevPromptOnly &&
            studioRefinedPromptPreview ? (
              <label className="studio-label">
                Итоговый промпт (WaveSpeed не вызывался)
                <textarea
                  className="mono"
                  rows={16}
                  readOnly
                  spellCheck={false}
                  value={studioRefinedPromptPreview}
                />
              </label>
            ) : null}
            {studioWavespeedMsg ? (
              <div className="banner info studio-status-msg">{studioWavespeedMsg}</div>
            ) : null}
            {studioGenImageUrl ? (
              <div className="studio-generated">
                <h3 className="studio-generated-title">Результат</h3>
                <div className="studio-generated-frame">
                  <img src={studioGenImageUrl} alt="Сгенерировано" className="studio-gen-img" />
                </div>
                <div className="studio-upscale-row">
                  <label className="studio-upscale-control">
                    <span className="studio-upscale-control-label">Апскейл</span>
                    <select
                      value={studioUpscaleTarget}
                      onChange={(e) =>
                        setStudioUpscaleTarget(e.target.value as '2k' | '4k' | '8k')
                      }
                      disabled={studioUpscaleBusy}
                    >
                      <option value="2k">2K</option>
                      <option value="4k">4K</option>
                      <option value="8k">8K</option>
                    </select>
                  </label>
                  <button
                    type="button"
                    className="ghost-btn studio-upscale-btn"
                    disabled={
                      studioUpscaleBusy ||
                      !canStudioGenerate ||
                      studioGenGenerationId == null ||
                      !integ?.wavespeed_configured
                    }
                    title={
                      !integ?.wavespeed_configured
                        ? 'Сохраните ключ WaveSpeed в кабинете'
                        : studioGenGenerationId == null
                          ? 'Выберите снимок из «Сохранённые» или сгенерируйте снова'
                          : undefined
                    }
                    onClick={() => void upscaleStudioGeneration()}
                  >
                    {studioUpscaleBusy ? 'Апскейл…' : 'Апскейл'}
                  </button>
                  {canStudioGenerate && health?.studio_upscale_credit_cost != null ? (
                    <span className="studio-credit-hint">
                      {health.studio_upscale_credit_cost} кр.
                    </span>
                  ) : null}
                </div>
                <div className="studio-upscale-row studio-carousel-row">
                  <button
                    type="button"
                    className="ghost-btn studio-carousel-btn"
                    disabled={
                      studioCarouselBusy ||
                      studioUpscaleBusy ||
                      !canStudioGenerate ||
                      studioGenGenerationId == null ||
                      !integ?.wavespeed_configured
                    }
                    title={
                      !integ?.wavespeed_configured
                        ? 'Сохраните ключ WaveSpeed в кабинете'
                        : 'Тот же сценарий и образ, другие ракурсы'
                    }
                    onClick={() => void runStudioCarousel(3)}
                  >
                    {studioCarouselBusy ? 'Карусель…' : 'Карусель ×3'}
                  </button>
                  <button
                    type="button"
                    className="ghost-btn studio-carousel-btn"
                    disabled={
                      studioCarouselBusy ||
                      studioUpscaleBusy ||
                      !canStudioGenerate ||
                      studioGenGenerationId == null ||
                      !integ?.wavespeed_configured
                    }
                    title={
                      !integ?.wavespeed_configured
                        ? 'Сохраните ключ WaveSpeed в кабинете'
                        : 'Четыре кадра для ленты — окружение и образ как на этом снимке'
                    }
                    onClick={() => void runStudioCarousel(4)}
                  >
                    {studioCarouselBusy ? 'Карусель…' : 'Карусель ×4'}
                  </button>
                  {canStudioGenerate && health?.studio_carousel_credit_cost != null ? (
                    <span className="studio-credit-hint">
                      {health.studio_carousel_credit_cost} кр./кадр
                    </span>
                  ) : null}
                </div>
                <button
                  type="button"
                  className="send-btn studio-download"
                  disabled={studioDownloadBusy}
                  title="На iPhone откроется меню «Поделиться» — сохраните в Фото без выхода из приложения"
                  onClick={() => void downloadStudioResultImage()}
                >
                  {studioDownloadBusy ? 'Сохранение…' : 'Скачать'}
                </button>
              </div>
            ) : null}
          </div>
            </>
          )}
        </section>
        {canStudioGenerate ? (
          <section className="studio-panel studio-archive-section" aria-labelledby="studio-archive-heading">
            <h2 id="studio-archive-heading">Сохранённые</h2>
            <p className="muted studio-archive-lead">
              Картинки с WaveSpeed сохраняются на сервере — их можно открыть позже.
            </p>
            {studioArchiveInitialLoading ? (
              <p className="muted">Загрузка архива…</p>
            ) : studioGenerations.length === 0 ? (
              <p className="muted empty-hint">Пока нет сохранённых генераций.</p>
            ) : (
              <>
                <ul className="studio-archive-grid">
                  {studioGenerations.map((g) => (
                    <li key={g.id} className="studio-archive-item">
                      <button
                        type="button"
                        className="studio-archive-thumb-btn"
                        title={g.prompt_excerpt?.trim() || 'Открыть в «Результат»'}
                        onClick={() => {
                          setStudioGenGenerationId(g.id)
                          setStudioGenImageUrl(g.image_url)
                        }}
                      >
                        <img src={g.image_url} alt="" className="studio-archive-thumb" loading="lazy" />
                      </button>
                      <button
                        type="button"
                        className="studio-archive-del"
                        aria-label="Удалить из архива"
                        onClick={(e) => {
                          e.stopPropagation()
                          void deleteStudioGeneration(g.id, g.image_url)
                        }}
                      >
                        ×
                      </button>
                      <span className="studio-archive-meta" title={g.created_at}>
                        {g.model_name ?? '—'}
                      </span>
                    </li>
                  ))}
                </ul>
                {studioGenHasMore ? (
                  <div className="studio-archive-more-wrap">
                    <button
                      type="button"
                      className="send-btn studio-archive-more-btn"
                      disabled={studioGenLoadingMore}
                      onClick={() => void loadMoreStudioGenerations()}
                    >
                      {studioGenLoadingMore ? 'Загрузка…' : `Ещё ${STUDIO_ARCHIVE_PAGE}`}
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </section>
        ) : null}
        </>
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
                <div
                  className="messages-scroll"
                  ref={messagesContainerRef}
                  role="log"
                  aria-live="polite"
                  aria-relevant="additions"
                >
                  {loading ? (
                    <div className="messages-loading">
                      <span className="skeleton-line" />
                      <span className="skeleton-line short" />
                    </div>
                  ) : (
                    <>
                      {loadingOlder ? (
                        <div className="messages-older-loading" role="status">
                          <span className="muted">Загрузка истории…</span>
                        </div>
                      ) : null}
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
                    </>
                  )}
                </div>

                {showJumpDown && !loading && (
                  <button
                    type="button"
                    className="jump-down"
                    onClick={() => scrollToBottom(true)}
                  >
                    К последним ↓
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
