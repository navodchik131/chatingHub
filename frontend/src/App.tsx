import EmojiPicker, { type EmojiClickData, Theme } from 'emoji-picker-react'
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch, getToken, setToken } from './api'
import {
  getPushSubscriptionState,
  subscribeWebPush,
  unsubscribeWebPush,
  webPushEnvironmentOk,
} from './webPush'
import { billingReturnCopy } from './billingReturnCopy'
import { creditUnitFromHealth } from './billing/credits'
import { subscriptionCostCredits } from './billing/referral'
import { formatClientFetchError, formatHttpApiError } from './apiErrors'
import { postStudioJobAndWait, postStudioJobStart } from './studioJobs'
import {
  computeMotionVideoCreditCost,
  mergeMotionVideoPricing,
} from './studioMotionPricing'
import {
  fetchStudioArchivePage,
  fetchStudioArchivePending,
  isMotionRenderArchiveId,
  mergeStudioArchiveItems,
  mergeVideoArchiveWithMotionRenders,
  studioArchiveIsPending,
  studioArchiveThumbUrl,
  type StudioArchiveItem,
  type StudioArchiveMediaKind,
} from './studioArchive'
import './components/studio/studio-ui.css'
import { StudioArchiveThumbPicker } from './components/studio/StudioArchiveThumbPicker'
import { StudioGenerationGallery } from './components/studio/StudioGenerationGallery'
import { StudioMediaSlot } from './components/studio/StudioMediaSlot'
import { StudioModelBootstrapPanel } from './components/studio/StudioModelBootstrapPanel'
import { StudioPillField } from './components/studio/StudioPillField'
import { IconModel, IconSpark } from './components/studio/studioIcons'
import { AuthPanel } from './AuthPanel'
import { AppShell, type WorkspaceSection } from './components/AppShell'
import { WorkspaceOverview } from './components/WorkspaceOverview'
import {
  SetupTour,
  dismissSetupTour,
  markSetupTourHadGeneration,
  readSetupTourDismissed,
  readSetupTourHadGeneration,
  resolveSetupTourPhase,
} from './components/SetupTour'
import { studioImageGenerateBlockReason } from './studio/studioGenerateGate'
import {
  WavespeedSetupBanner,
  needsUserWavespeedKey,
} from './components/WavespeedSetupBanner'
import './App.css'
import { StudioInpaintMaskPainter, type StudioInpaintMaskPainterRef } from './StudioInpaintMaskPainter'
import {
  DEFAULT_MEMBER_PERMISSIONS,
  MEMBER_PERMISSION_LABELS,
  PERM_INTEGRATIONS,
  PERM_STUDIO_GENERATE,
  PERM_STUDIO_MODELS,
  hasAllBits,
  togglePermission,
} from './workspacePermissions'
import { WAVESPEED_REF_URL } from './billing/planCatalog'

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
  /** Модель студии для доступа операторов (назначает владелец). */
  studio_model_id?: number | null
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

interface ChatMessageAttachment {
  id: number
  kind: string
  url: string
  mime_type: string
}

interface ChatMessage {
  id: number
  direction: 'inbound' | 'outbound'
  text_original: string
  text_translated: string | null
  created_at: string
  attachments?: ChatMessageAttachment[]
  /** Локальный превью до ответа сервера. */
  localPreviewUrl?: string
  /** Локальный черновик до ответа сервера (перевод ещё готовится). */
  pending?: boolean
}

/** Размер страницы GET /conversations/:id/messages (синхронно с бэкендом default limit). */
const CHAT_MESSAGES_PAGE = 40

/**
 * Web Share API с передачей File на десктопе (Chrome/Edge) даёт системное окно «Поделиться»
 * вместо нормального скачивания. Оставляем share для установленной PWA и типичных тач-сценариев.
 */
function preferNativeShareOnMobile(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const nav = window.navigator as Navigator & { standalone?: boolean }
    if (window.matchMedia('(display-mode: standalone)').matches) return true
    if (nav.standalone === true) return true
    if (window.matchMedia('(pointer: coarse)').matches) return true
    return false
  } catch {
    return false
  }
}

function platformLabel(p: Platform): string {
  if (p === 'telegram') return 'Telegram'
  return 'Fanvue'
}

function studioIntegrationsHint(): string {
  return 'Добавьте API-ключ WaveSpeed: кабинет → Подключения → блок WaveSpeed.'
}

const WS_ONBOARDING_LS = 'modelmate_ws_onboarding_v1'

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
  studio_inpaint_credit_cost?: number
  studio_upscale_credit_cost?: number
  studio_wan_edit_tier_switch?: boolean
  studio_allow_prompt_only?: boolean
  /** true: маска студии → кроп + WAN/Nano + серверная склейка; false на сервере = Z-Image inpaint */
  studio_regional_masked_edit?: boolean
  studio_carousel_credit_cost?: number
  /** 0 или отсутствует = без автоудаления (см. бэкенд). */
  studio_generations_retention_days?: number
  studio_generations_retention_interval_hours?: number
  studio_motion_control_credit_cost?: number
  studio_motion_video_pricing?: import('./studioMotionPricing').StudioMotionVideoPricing
  /** Всегда seedance_t2v (Seedance 2.0 Text-to-Video). */
  studio_motion_video_provider?: string
  studio_seedance_t2v_duration_default?: number
  studio_seedance_t2v_duration_min?: number
  studio_seedance_t2v_duration_max?: number
  studio_seedance_t2v_prompt_max_chars?: number
  studio_grok_motion_timeline_enabled?: boolean
  studio_grok_motion_configured?: boolean
  studio_grok_scene_compose_configured?: boolean
  studio_seedance_i2v_duration_default?: number
  studio_seedance_i2v_duration_min?: number
  studio_seedance_i2v_duration_max?: number
  web_push_configured?: boolean
}

function studioArchiveRetentionLead(health: HealthInfo | null, kind: 'image' | 'video' = 'image'): ReactNode {
  const days = health?.studio_generations_retention_days
  if (typeof days === 'number' && days > 0) {
    const n100 = days % 100
    const n10 = days % 10
    const word =
      n10 === 1 && n100 !== 11
        ? 'день'
        : n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)
          ? 'дня'
          : 'дней'
    if (kind === 'video') {
      return (
        <>
          Ролики доступны по ссылке провайдера примерно <strong>{days}</strong> {word}. Сохраните
          важное на устройство заранее.
        </>
      )
    }
    return (
      <>
        Картинки с WaveSpeed хранятся на сервере примерно <strong>{days}</strong> {word}, затем
        удаляются автоматически. Сохраните важное на устройство заранее.
      </>
    )
  }
  if (kind === 'video') {
    return <>Готовые ролики можно открыть и скачать из истории.</>
  }
  return <>Картинки с WaveSpeed сохраняются на сервере — их можно открыть позже.</>
}

interface PlanLimitsMe {
  max_users: number
  max_models: number
  max_dialogs_per_month: number | null
  max_grok_per_month: number | null
}

interface PlanUsageMe {
  users: number
  models: number
  dialogs_this_month: number
  grok_this_month: number
  limits: PlanLimitsMe
}

interface UserMe {
  id: number
  email: string
  subscription_status: string
  /** managed | byok */
  billing_plan?: string
  plan_tier?: string
  plan_display_name?: string
  plan_usage?: PlanUsageMe | null
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
  signup_bonus_credits?: number
}

interface ReferralMe {
  referral_code: string
  referral_link: string
  invited_count: number
  credits_earned: number
  friend_referral_credits: number
  signup_base_credits: number
  referrer_payment_percent: number
  credit_unit_price_rub: number
  referrer_reward_summary: string
}

interface WorkspaceMemberRow {
  id: number
  member_login: string
  permissions_mask: number
  is_active: boolean
  allowed_studio_model_ids: number[]
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
  wavespeed_managed_by_platform?: boolean
  llm_configured?: boolean
}

interface BillingCreditsPricing {
  min_quantity: number
  bulk_from: number
  unit_price_rub: number
  bulk_unit_price_rub: number
}

interface BillingPlanRow {
  product: string
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
}

type StudioModelImageKind = 'face' | 'body' | 'genitals' | 'turnaround' | 'other'
type StudioExifCamera = 'selfie' | 'main'

interface NewModelPhotoRow {
  file: File
  kind: StudioModelImageKind
}

const STUDIO_MODEL_MAX_IMAGES = 8

const STUDIO_MODEL_IMAGE_KIND_OPTIONS: { value: StudioModelImageKind; label: string }[] = [
  { value: 'turnaround', label: 'Развёртка / character sheet' },
  { value: 'face', label: 'Лицо / идентичность' },
  { value: 'body', label: 'Тело целиком' },
  { value: 'genitals', label: 'Интимная зона (реф.)' },
  { value: 'other', label: 'Общий референс' },
]

function normalizeStudioImageKind(raw: string | undefined): StudioModelImageKind {
  if (
    raw === 'face' ||
    raw === 'body' ||
    raw === 'genitals' ||
    raw === 'turnaround' ||
    raw === 'other'
  )
    return raw
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
  phone_exif_selfie_ready?: boolean
  phone_exif_main_ready?: boolean
  phone_exif_selfie_summary?: string | null
  phone_exif_main_summary?: string | null
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

type AccountCabinetTab = 'overview' | 'billing' | 'integrations' | 'models' | 'team'

function userBillingPlanLabel(me: UserMe | null | undefined): string {
  if (me?.plan_display_name) return me.plan_display_name
  const p = (me?.billing_plan || 'managed').toLowerCase()
  return p === 'byok' ? 'BYOK Solo' : 'Managed Solo'
}

function userBillingPlanLong(me: UserMe | null | undefined): string {
  const p = (me?.billing_plan || 'managed').toLowerCase()
  const tier = (me?.plan_tier || 'solo').toLowerCase()
  const base =
    p === 'byok'
      ? 'BYOK — свой WaveSpeed; GROK и текст студии на сервере; кредиты на студию не списываются'
      : 'Managed — ключ WaveSpeed платформы после оплаты; операции студии списывают кредиты'
  return `${base} · тариф ${tier.toUpperCase()}`
}

function canPurchaseStudioCreditPack(me: UserMe | undefined): boolean {
  if (!me?.online_payment_available) return false
  const st = (me.subscription_status || '').toLowerCase()
  if (st !== 'active') return false
  const p = (me.billing_plan || 'managed').toLowerCase()
  return p === 'managed'
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
  yookassa_managed_subscription_bonus: 'Подписка Managed: бонус кредитов',
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

interface StudioAspectPreset {
  key: string
  label: string
  size: string
}

interface StudioMotionRenderItem {
  id: number
  created_at: string
  studio_generation_id: number | null
  studio_model_id?: number | null
  video_url: string
  frame_image_url: string
}

interface StudioMotionRendersPage {
  items: StudioMotionRenderItem[]
  has_more: boolean
}

/** Должен совпадать с default limit у GET /api/studio/generations */
const STUDIO_ARCHIVE_PAGE = 10

function studioGalleryMediaKind(section: WorkspaceSection): StudioArchiveMediaKind | undefined {
  if (section === 'studio' || section === 'studio_bootstrap') return 'image'
  if (section === 'studio_video') return 'video'
  return undefined
}

type StudioJobMode =
  | 'model_scene'
  | 'model'
  | 'photo_edit'
  | 'no_face'
  | 'face_swap'
  | 'grok_compose'

/** Только текст в промпт, без референса даже для Grok. */
const STUDIO_TEXT_ONLY_MODES: StudioJobMode[] = ['model']

function studioModeUsesTextOnlyPrompt(mode: StudioJobMode): boolean {
  return STUDIO_TEXT_ONLY_MODES.includes(mode)
}

const STUDIO_IMAGE_MODE_OPTIONS: { id: StudioJobMode; label: string }[] = [
  { id: 'model_scene', label: 'Основная' },
  { id: 'grok_compose', label: 'Face swap' },
  { id: 'model', label: 'По промту' },
  { id: 'photo_edit', label: 'Доработать фото' },
  { id: 'no_face', label: 'Без лица' },
]

export default function App() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const billingBannerCopy = useMemo(
    () => billingReturnCopy(searchParams.get('billing')),
    [searchParams],
  )
  const clearBillingQuery = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('billing')
        return next
      },
      { replace: true },
    )
  }, [setSearchParams])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [chatReplyFile, setChatReplyFile] = useState<File | null>(null)
  const [chatReplyArchiveId, setChatReplyArchiveId] = useState<number | null>(null)
  const [chatArchivePickerOpen, setChatArchivePickerOpen] = useState(false)
  const chatReplyFileInputRef = useRef<HTMLInputElement | null>(null)
  const chatReplyFilePreview = useMemo(
    () => (chatReplyFile ? URL.createObjectURL(chatReplyFile) : null),
    [chatReplyFile],
  )
  useEffect(() => {
    return () => {
      if (chatReplyFilePreview) URL.revokeObjectURL(chatReplyFilePreview)
    }
  }, [chatReplyFilePreview])
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

  const unreadTotal = useMemo(
    () => conversations.reduce((sum, c) => sum + (c.unread_count ?? 0), 0),
    [conversations],
  )

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
  const [newTeamModelIds, setNewTeamModelIds] = useState<number[]>([])
  const [memberEditPassword, setMemberEditPassword] = useState<Record<number, string>>({})
  const [memberMaskEdits, setMemberMaskEdits] = useState<Record<number, number>>({})
  const [memberModelEdits, setMemberModelEdits] = useState<Record<number, number[]>>({})
  const [convModelBusy, setConvModelBusy] = useState(false)
  const [integ, setInteg] = useState<IntegrationStatus | null>(null)
  const studioNeedsUserWsKey = useMemo(() => needsUserWavespeedKey(integ), [integ])
  const [modelDrafts, setModelDrafts] = useState<Record<number, StudioModelCabinetDraft>>({})
  const [studioCameraPresets, setStudioCameraPresets] = useState<StudioCameraPreset[]>([])
  const [modelSavingId, setModelSavingId] = useState<number | null>(null)
  const [tgToken, setTgToken] = useState('')
  const [fvToken, setFvToken] = useState('')
  const [fvCreator, setFvCreator] = useState('')
  const [fvSecret, setFvSecret] = useState('')

  const [appSection, setAppSection] = useState<WorkspaceSection>('overview')
  const [studioDesc, setStudioDesc] = useState('')
  const [studioFile, setStudioFile] = useState<File | null>(null)
  /** Маска (белое = зона замены): Multi-URL в Nano/WAN при STUDIO_REGIONAL_MASKED_EDIT=true или Z-Inpaint если false. */
  const [studioInpaintMaskFile, setStudioInpaintMaskFile] = useState<File | null>(null)
  /** Режим маски: рисуем белым по превью референса. */
  const [studioPaintInpaintMask, setStudioPaintInpaintMask] = useState(false)
  const [studioMaskBrushPreset, setStudioMaskBrushPreset] = useState<'s' | 'm' | 'l'>('m')
  const [studioReferenceObjectUrl, setStudioReferenceObjectUrl] = useState<string | null>(null)
  const studioMaskPainterRef = useRef<StudioInpaintMaskPainterRef | null>(null)
  /** Снимок из архива как база для режима «Доработать фото» (альтернатива файлу). */
  const [studioPhotoEditArchiveId, setStudioPhotoEditArchiveId] = useState<number | null>(null)
  /** true = MODEL_LOCK (причёска с профиля); false = POSE_REFERENCE (с загруженного кадра). Только если есть studioFile. */
  const [studioLockModelHairstyle, setStudioLockModelHairstyle] = useState(true)
  const [studioSendPoseRefToWavespeed, setStudioSendPoseRefToWavespeed] = useState(true)
  const [studioMode, setStudioMode] = useState<StudioJobMode>('model_scene')
  const [studioWanEditTier, setStudioWanEditTier] = useState<'standard' | 'pro'>('standard')
  const [studioWaveProfile, setStudioWaveProfile] = useState<'regular' | 'nsfw'>('nsfw')
  const [studioBusy, setStudioBusy] = useState(false)
  const [studioModels, setStudioModels] = useState<UserStudioModel[]>([])
  const [studioSelectedModelId, setStudioSelectedModelId] = useState<number | null>(null)
  /** EXIF при сохранении кадра: фронталка или основная камера (эталоны на модели). */
  const [studioExifCamera, setStudioExifCamera] = useState<StudioExifCamera>('main')
  const [newModelName, setNewModelName] = useState('')
  const [newModelProfile, setNewModelProfile] = useState('')
  const [newModelProfileGenBusy, setNewModelProfileGenBusy] = useState(false)
  const [newModelPhotos, setNewModelPhotos] = useState<NewModelPhotoRow[]>([])
  const [newModelCameraPresetId, setNewModelCameraPresetId] = useState('')
  const [newModelExportLat, setNewModelExportLat] = useState('')
  const [newModelExportLon, setNewModelExportLon] = useState('')
  const [newModelPhoneExifSelfie, setNewModelPhoneExifSelfie] = useState<File | null>(null)
  const [newModelPhoneExifMain, setNewModelPhoneExifMain] = useState<File | null>(null)
  const [modelPhoneExifBusy, setModelPhoneExifBusy] = useState<string | null>(null)
  /** Черновик файлов для «Добавить фото» на карточке модели (до загрузки на сервер). */
  const [appendModelPhotosById, setAppendModelPhotosById] = useState<
    Record<number, NewModelPhotoRow[]>
  >({})
  const [wsApiKey, setWsApiKey] = useState('')
  const [wsSetupPulse, setWsSetupPulse] = useState(false)
  const [setupTourDismissed, setSetupTourDismissed] = useState(readSetupTourDismissed)
  const [setupTourHadGen, setSetupTourHadGen] = useState(readSetupTourHadGeneration)
  const [studioArchiveReady, setStudioArchiveReady] = useState(false)
  const [llmApiKey, setLlmApiKey] = useState('')
  const [llmBaseUrl, setLlmBaseUrl] = useState('')
  const [billingPlanRows, setBillingPlanRows] = useState<BillingPlanRow[]>([])
  const [billingPayMode, setBillingPayMode] = useState<'byok' | 'managed'>('byok')
  const [billingPayPeriod, setBillingPayPeriod] = useState<'month' | 'year'>('month')
  const [referralInfo, setReferralInfo] = useState<ReferralMe | null>(null)
  const [creditsPurchaseQty, setCreditsPurchaseQty] = useState(50)
  const [yookassaPayBusy, setYookassaPayBusy] = useState<string | null>(null)
  const [billingCreditUnitRub, setBillingCreditUnitRub] = useState(3.7)
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
  /** Временная ссылка CDN, если архив после генерации сохранить не удалось — кнопка «Сохранить в архив». */
  const [studioPendingExternalImageUrl, setStudioPendingExternalImageUrl] = useState<string | null>(
    null,
  )
  const [studioImportArchiveBusy, setStudioImportArchiveBusy] = useState(false)
  /** Только в dev + health.studio_allow_prompt_only: без запроса к WaveSpeed */
  const [studioDevPromptOnly, setStudioDevPromptOnly] = useState(false)
  const [studioRefinedPromptPreview, setStudioRefinedPromptPreview] = useState<string | null>(null)
  const [studioAspectPresets, setStudioAspectPresets] = useState<StudioAspectPreset[]>([])
  const [studioOutputAspect, setStudioOutputAspect] = useState('9:16')
  const [studioGenerations, setStudioGenerations] = useState<StudioArchiveItem[]>([])
  /** Картинки архива для пикеров на странице видео (галерея там — только video). */
  const [studioImagePickerArchive, setStudioImagePickerArchive] = useState<StudioArchiveItem[]>([])
  const findStudioArchiveItem = useCallback(
    (id: number): StudioArchiveItem | undefined =>
      studioGenerations.find((x) => x.id === id) ??
      studioImagePickerArchive.find((x) => x.id === id),
    [studioGenerations, studioImagePickerArchive],
  )
  const [studioGenHasMore, setStudioGenHasMore] = useState(false)
  const [studioGenLoadingMore, setStudioGenLoadingMore] = useState(false)
  const [studioArchiveInitialLoading, setStudioArchiveInitialLoading] = useState(false)

  const [motionFrameArchiveId, setMotionFrameArchiveId] = useState<number | null>(null)
  const [motionOutfitArchiveId, setMotionOutfitArchiveId] = useState<number | null>(null)
  const [motionFrameNotes, setMotionFrameNotes] = useState('')
  const [motionGrokTimeline, setMotionGrokTimeline] = useState<string | null>(null)
  const [motionFirstFrameFile, setMotionFirstFrameFile] = useState<File | null>(null)
  const [motionVideoFile, setMotionVideoFile] = useState<File | null>(null)
  const [motionDesc, setMotionDesc] = useState('')
  const [motionAutoPrompt, setMotionAutoPrompt] = useState(true)
  const [motionLockHairstyle, setMotionLockHairstyle] = useState(true)
  const [motionVideoNegPrompt, setMotionVideoNegPrompt] = useState('')
  const [motionKeepSound, setMotionKeepSound] = useState(true)
  /** Только для провайдера Seedance I2V (сек., диапазон с health). */
  const [motionSeedanceDuration, setMotionSeedanceDuration] = useState(5)
  const motionSeedanceDurationInitRef = useRef(false)
  const [motionBusyFrame, setMotionBusyFrame] = useState(false)
  const [motionBusyCompose, setMotionBusyCompose] = useState(false)
  const [motionBusyVideo, setMotionBusyVideo] = useState(false)
  const [motionVideoFileId, setMotionVideoFileId] = useState<string | null>(null)
  const [motionPreviewUrl, setMotionPreviewUrl] = useState<string | null>(null)
  const [motionPreviewGenId, setMotionPreviewGenId] = useState<number | null>(null)
  const [motionResultVideoUrl, setMotionResultVideoUrl] = useState<string | null>(null)
  const [motionMsg, setMotionMsg] = useState<string | null>(null)
  /** Анализ шага 1 (vision/Grok) — не финальный Seedance-промпт. */
  const [motionStep1Preview, setMotionStep1Preview] = useState<string | null>(null)
  /** Финальный промпт T2V после шага 2 (с @Image на сервере). */
  const [motionAutoTextPreview, setMotionAutoTextPreview] = useState<string | null>(null)
  const [motionRenders, setMotionRenders] = useState<StudioMotionRenderItem[]>([])
  const [motionDrivingUploadBusy, setMotionDrivingUploadBusy] = useState(false)
  const [motionUseStillFinal, setMotionUseStillFinal] = useState(false)
  const [motionVideoDownloadBusy, setMotionVideoDownloadBusy] = useState(false)
  /** Первый кадр видео: regular = Nano Banana; nsfw = WAN 2.7 как тип «NSFW» на вкладке картинок. */
  const [motionFirstFrameWaveProfile, setMotionFirstFrameWaveProfile] = useState<'regular' | 'nsfw'>(
    'regular',
  )
  /** Локальный превью загруженного кадра (пока нет записи архива на сервере). */
  const [motionStillBlobUrl, setMotionStillBlobUrl] = useState<string | null>(null)
  /** CDN-URL кадра, если сервер не сохранил файл (можно «Сохранить в архив» без повторной генерации). */
  const [motionPendingExternalStillUrl, setMotionPendingExternalStillUrl] = useState<string | null>(
    null,
  )

  const studioPromptOnlyDev = useMemo(
    () =>
      import.meta.env.DEV &&
      Boolean(health?.studio_allow_prompt_only) &&
      studioDevPromptOnly,
    [health?.studio_allow_prompt_only, studioDevPromptOnly],
  )

  const seedanceDurationMin =
    health?.studio_seedance_t2v_duration_min ?? health?.studio_seedance_i2v_duration_min ?? 4
  const seedanceDurationMax =
    health?.studio_seedance_t2v_duration_max ?? health?.studio_seedance_i2v_duration_max ?? 15

  /** Реф выбран или уже загружен — сразу тариф «с реф-видео» на кнопке. */
  const motionHasReferenceVideo = Boolean(motionVideoFileId || motionVideoFile)

  const motionVideoPricing = mergeMotionVideoPricing(health?.studio_motion_video_pricing)

  const motionVideoCreditCost = computeMotionVideoCreditCost(
    motionSeedanceDuration,
    motionHasReferenceVideo,
    motionVideoPricing,
  )

  useEffect(() => {
    if (motionSeedanceDurationInitRef.current || !health) return
    const d =
      health.studio_seedance_t2v_duration_default ?? health.studio_seedance_i2v_duration_default
    const mn =
      health.studio_seedance_t2v_duration_min ?? health.studio_seedance_i2v_duration_min ?? 4
    const mx =
      health.studio_seedance_t2v_duration_max ?? health.studio_seedance_i2v_duration_max ?? 15
    if (typeof d === 'number' && Number.isFinite(d)) {
      setMotionSeedanceDuration(Math.max(mn, Math.min(mx, Math.round(d))))
    } else {
      setMotionSeedanceDuration(Math.max(mn, Math.min(mx, 5)))
    }
    motionSeedanceDurationInitRef.current = true
  }, [health])

  useEffect(() => {
    setMotionSeedanceDuration((prev) =>
      Math.max(seedanceDurationMin, Math.min(seedanceDurationMax, prev)),
    )
  }, [seedanceDurationMin, seedanceDurationMax])

  useEffect(() => {
    if (!studioFile) setStudioLockModelHairstyle(true)
  }, [studioFile])

  useEffect(() => {
    if (!studioFile) {
      setStudioReferenceObjectUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return null
      })
      return
    }
    const url = URL.createObjectURL(studioFile)
    setStudioReferenceObjectUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return url
    })
  }, [studioFile])

  /** Превью референса для маски: локальный файл или снимок из архива («Доработать фото»). */
  const studioInpaintBaseImageSrc =
    studioReferenceObjectUrl ??
    (studioMode === 'photo_edit' && studioPhotoEditArchiveId != null
      ? findStudioArchiveItem(studioPhotoEditArchiveId)?.image_url ?? null
      : null)

  useEffect(() => {
    const hasBaseImage =
      studioFile != null ||
      (studioMode === 'photo_edit' && studioPhotoEditArchiveId != null)
    if (!hasBaseImage) {
      setStudioInpaintMaskFile(null)
      setStudioPaintInpaintMask(false)
    }
  }, [studioFile, studioMode, studioPhotoEditArchiveId])

  useEffect(() => {
    if (!studioInpaintBaseImageSrc) setStudioPaintInpaintMask(false)
  }, [studioInpaintBaseImageSrc])

  useEffect(() => {
    if (studioPaintInpaintMask) setStudioInpaintMaskFile(null)
  }, [studioPaintInpaintMask])

  useEffect(() => {
    if (studioInpaintMaskFile) setStudioPaintInpaintMask(false)
  }, [studioInpaintMaskFile])

  useEffect(() => {
    if (studioModeUsesTextOnlyPrompt(studioMode)) {
      setStudioFile(null)
      setStudioPhotoEditArchiveId(null)
      setStudioPaintInpaintMask(false)
      setStudioInpaintMaskFile(null)
      setStudioSendPoseRefToWavespeed(false)
    }
    if (studioMode !== 'photo_edit') {
      setStudioPhotoEditArchiveId(null)
    }
    if (studioMode === 'photo_edit') {
      setStudioSelectedModelId(null)
    }
  }, [studioMode])

  const studioGenerationsRef = useRef<StudioArchiveItem[]>([])
  const studioImageGenInFlightRef = useRef(false)

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
    const [r, h] = await Promise.all([apiFetch('/api/billing/plans'), apiFetch('/api/health')])
    if (h.ok) {
      const health = (await h.json()) as Parameters<typeof creditUnitFromHealth>[0]
      setBillingCreditUnitRub(creditUnitFromHealth(health))
    }
    if (r.ok) {
      const data = (await r.json()) as { items: BillingPlanRow[] }
      setBillingPlanRows(Array.isArray(data.items) ? data.items : [])
    }
  }, [])

  const refreshReferral = useCallback(async () => {
    const r = await apiFetch('/api/referral/me')
    if (r.ok) setReferralInfo((await r.json()) as ReferralMe)
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

  const loadStudioImagePickerArchive = useCallback(async () => {
    const page = await fetchStudioArchivePage(0, STUDIO_ARCHIVE_PAGE, 'image')
    setStudioImagePickerArchive(page.items)
  }, [])

  const refreshMotionRenders = useCallback(async () => {
    const r = await apiFetch('/api/studio/motion/renders?limit=40&skip=0')
    if (!r.ok) return
    const data = (await r.json()) as StudioMotionRendersPage
    setMotionRenders(Array.isArray(data.items) ? data.items : [])
  }, [])

  const loadStudioGenerationsReset = useCallback(async () => {
    const kind = studioGalleryMediaKind(appSection)
    const page = await fetchStudioArchivePage(0, STUDIO_ARCHIVE_PAGE, kind)
    let merged = page.items
    try {
      const pending = await fetchStudioArchivePending(kind)
      merged = mergeStudioArchiveItems(page.items, pending.items)
    } catch {
      /* pending опционален */
    }
    setStudioGenerations(merged)
    setStudioGenHasMore(page.has_more)
    if (appSection === 'studio' || appSection === 'studio_bootstrap') {
      setStudioImagePickerArchive(page.items)
    } else if (appSection === 'studio_video') {
      await loadStudioImagePickerArchive()
      await refreshMotionRenders()
    }
  }, [appSection, loadStudioImagePickerArchive, refreshMotionRenders])

  const syncStudioArchivePending = useCallback(async () => {
    try {
      const kind = studioGalleryMediaKind(appSection)
      const pending = await fetchStudioArchivePending(kind)
      if (pending.items.length) {
        setStudioGenerations((prev) => mergeStudioArchiveItems(prev, pending.items))
      }
      if (appSection === 'studio_video') {
        const imgPending = await fetchStudioArchivePending('image')
        if (imgPending.items.length) {
          setStudioImagePickerArchive((prev) => mergeStudioArchiveItems(prev, imgPending.items))
        }
      }
    } catch {
      /* тихий опрос */
    }
  }, [appSection])

  const loadMoreStudioGenerations = useCallback(async () => {
    if (studioGenLoadingMore || !studioGenHasMore) return
    setStudioGenLoadingMore(true)
    setError(null)
    try {
      const skip = studioGenerationsRef.current.length
      const kind = studioGalleryMediaKind(appSection)
      const page = await fetchStudioArchivePage(skip, STUDIO_ARCHIVE_PAGE, kind)
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
  }, [appSection, studioGenLoadingMore, studioGenHasMore])

  const studioVideoGalleryItems = useMemo(
    () => mergeVideoArchiveWithMotionRenders(studioGenerations, motionRenders),
    [studioGenerations, motionRenders],
  )

  const studioArchiveHasPending = useMemo(() => {
    if (studioGenerations.some(studioArchiveIsPending)) return true
    if (appSection === 'studio_video') {
      return studioImagePickerArchive.some(studioArchiveIsPending)
    }
    return false
  }, [studioGenerations, studioImagePickerArchive, appSection])

  useEffect(() => {
    if (!authed || !canStudioGenerate || !studioArchiveHasPending) return
    let cancelled = false
    const tick = () => {
      if (!cancelled) void syncStudioArchivePending()
    }
    tick()
    const id = window.setInterval(tick, 12_000)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [authed, canStudioGenerate, studioArchiveHasPending, syncStudioArchivePending])

  const uploadMotionDrivingVideo = useCallback(async (file: File) => {
    setMotionDrivingUploadBusy(true)
    setMotionMsg(null)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('video', file)
      const r = await apiFetch('/api/studio/motion/upload-driving-video', {
        method: 'POST',
        body: fd,
        timeoutMs: 120_000,
      })
      const data = (await r.json().catch(() => ({}))) as {
        motion_video_file_id?: string
        detail?: unknown
      }
      if (!r.ok) {
        setError(formatHttpApiError(r, data))
        setMotionVideoFileId(null)
        return
      }
      const id = typeof data.motion_video_file_id === 'string' ? data.motion_video_file_id.trim() : ''
      setMotionVideoFileId(id || null)
    } catch (e) {
      setMotionVideoFileId(null)
      setError(
        e instanceof TypeError && e.message === 'Failed to fetch'
          ? 'Сеть: не удалось загрузить видео на сервер.'
          : e instanceof Error
            ? e.message
            : 'Ошибка загрузки видео',
      )
    } finally {
      setMotionDrivingUploadBusy(false)
    }
  }, [])

  useEffect(() => {
    setModelDrafts(
      Object.fromEntries(studioModels.map((m) => [m.id, defaultStudioModelCabinetDraft(m)])),
    )
  }, [studioModels])

  useEffect(() => {
    if (!me || !accountOpen) return
    if (accountTab === 'models' && !canStudioModels) setAccountTab('overview')
    if (accountTab === 'team' && !isOwner) setAccountTab('overview')
    if (accountTab === 'billing' && !isOwner) setAccountTab('overview')
  }, [me, accountOpen, accountTab, canPlatformAdmin, canStudioModels, isOwner])

  const openWavespeedIntegrations = useCallback(() => {
    setAccountOpen(true)
    setAccountTab('integrations')
    setWsSetupPulse(true)
    window.setTimeout(() => {
      document.getElementById('cabinet-wavespeed-key')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 120)
  }, [])

  useEffect(() => {
    if (!studioNeedsUserWsKey) setWsSetupPulse(false)
  }, [studioNeedsUserWsKey])

  useEffect(() => {
    if (!authed || !isOwner || !integ) return
    if (!studioNeedsUserWsKey) return
    try {
      if (localStorage.getItem(WS_ONBOARDING_LS)) return
      localStorage.setItem(WS_ONBOARDING_LS, '1')
    } catch {
      /* private mode */
    }
    setAccountOpen(true)
    setAccountTab('integrations')
    setWsSetupPulse(true)
  }, [authed, isOwner, integ, studioNeedsUserWsKey])

  useEffect(() => {
    if (!me) return
    if (appSection === 'chat' && !canChat) setAppSection('overview')
    if (
      (appSection === 'studio' ||
        appSection === 'studio_bootstrap' ||
        appSection === 'studio_video') &&
      !canStudioAny &&
      canChat
    )
      setAppSection('chat')
    if (
      (appSection === 'studio' ||
        appSection === 'studio_bootstrap' ||
        appSection === 'studio_video') &&
      !canStudioAny &&
      !canChat
    )
      setAppSection('overview')
  }, [me?.id, appSection, canChat, canStudioAny])

  useEffect(() => {
    if (authed && accountOpen) void refreshIntegrations()
  }, [authed, accountOpen, refreshIntegrations])

  useEffect(() => {
    if (!authed || !accountOpen || accountTab !== 'billing') return
    void refreshBillingPlans()
    if (isOwner) void refreshReferral()
  }, [authed, accountOpen, accountTab, refreshBillingPlans, refreshReferral, isOwner])

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
      ((appSection === 'overview' ||
        appSection === 'studio' ||
        appSection === 'studio_bootstrap' ||
        appSection === 'studio_video') &&
        canStudioAny) ||
      (appSection === 'chat' && isOwner) ||
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
    isOwner,
    loadStudioModels,
    loadStudioCameraPresets,
  ])

  useEffect(() => {
    if (authed && accountOpen && accountTab === 'team' && isOwner) {
      void refreshWorkspaceMembers()
      void loadStudioModels()
    }
  }, [authed, accountOpen, accountTab, isOwner, refreshWorkspaceMembers, loadStudioModels])

  useEffect(() => {
    setMemberMaskEdits(Object.fromEntries(workspaceMembers.map((x) => [x.id, x.permissions_mask])))
    setMemberModelEdits(
      Object.fromEntries(workspaceMembers.map((x) => [x.id, x.allowed_studio_model_ids ?? []])),
    )
  }, [workspaceMembers])

  useEffect(() => {
    if (
      authed &&
      (appSection === 'overview' ||
        appSection === 'studio' ||
        appSection === 'studio_bootstrap' ||
        appSection === 'studio_video')
    )
      void refreshIntegrations()
  }, [authed, appSection, refreshIntegrations])

  useEffect(() => {
    if (
      !authed ||
      (appSection !== 'overview' &&
        appSection !== 'studio' &&
        appSection !== 'studio_bootstrap' &&
        appSection !== 'studio_video')
    )
      return
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
    if (
      !authed ||
      (appSection !== 'overview' &&
        appSection !== 'studio' &&
        appSection !== 'studio_bootstrap' &&
        appSection !== 'studio_video') ||
      !canStudioGenerate
    )
      return
    setStudioArchiveInitialLoading(true)
    setError(null)
    void loadStudioGenerationsReset()
      .catch((e) => setError(String(e)))
      .finally(() => {
        setStudioArchiveInitialLoading(false)
        setStudioArchiveReady(true)
      })
  }, [authed, appSection, canStudioGenerate, loadStudioGenerationsReset])

  useEffect(() => {
    if (!authed || (appSection !== 'overview' && appSection !== 'studio_video')) return
    void refreshMotionRenders()
  }, [authed, appSection, refreshMotionRenders])

  useEffect(() => {
    if (appSection !== 'studio_video') return
    if (motionFrameArchiveId == null) return
    const g = findStudioArchiveItem(motionFrameArchiveId)
    if (g) {
      const thumb = studioArchiveThumbUrl(g) || g.image_url
      if (thumb) setMotionPreviewUrl(thumb)
      setMotionPreviewGenId(g.id)
      setMotionPendingExternalStillUrl(null)
    }
  }, [appSection, motionFrameArchiveId, findStudioArchiveItem])

  useEffect(() => {
    if (motionPreviewGenId == null) return
    const g = findStudioArchiveItem(motionPreviewGenId)
    if (!g || g.status === 'failed') return
    const thumb = studioArchiveThumbUrl(g) || g.image_url
    if (thumb && g.status === 'ready') {
      setMotionPreviewUrl(thumb)
      setMotionPendingExternalStillUrl(null)
    }
  }, [findStudioArchiveItem, motionPreviewGenId])

  useEffect(() => {
    if (studioGenGenerationId == null) return
    const g = findStudioArchiveItem(studioGenGenerationId)
    if (!g) return
    if (g.status === 'failed') return
    if (g.media_kind === 'video' && (g.video_url || '').trim()) {
      setMotionResultVideoUrl(g.video_url!.trim())
      return
    }
    const url = (g.image_url || '').trim()
    if (url && (g.status === 'ready' || g.status === 'provider_ready')) {
      setStudioGenImageUrl(url)
      setStudioPendingExternalImageUrl(
        url.includes('/api/studio/public-generation-image') ? null : url,
      )
    }
  }, [findStudioArchiveItem, studioGenGenerationId])

  useEffect(() => {
    if (!motionFirstFrameFile) {
      setMotionStillBlobUrl(null)
      return
    }
    const objUrl = URL.createObjectURL(motionFirstFrameFile)
    setMotionStillBlobUrl(objUrl)
    return () => {
      URL.revokeObjectURL(objUrl)
    }
  }, [motionFirstFrameFile])

  const studioMotionStillDisplayUrl = useMemo(() => {
    const u = motionPreviewUrl?.trim()
    if (u) return u
    return motionStillBlobUrl
  }, [motionPreviewUrl, motionStillBlobUrl])

  const motionHasFirstFrame = motionPreviewGenId != null
  const motionCanComposePrompt =
    motionVideoFileId != null &&
    studioSelectedModelId != null &&
    (motionHasFirstFrame || motionFrameArchiveId != null || motionFirstFrameFile != null)

  const motionVideoBtnBlockReason = useMemo((): string | null => {
    if (motionBusyVideo) return null
    if (studioNeedsUserWsKey) return studioIntegrationsHint()
    if (studioSelectedModelId == null) return 'Выберите модель вверху страницы.'
    if (!motionHasFirstFrame) {
      return 'Нужен первый кадр: архив, свой файл (и «Промпт по видео») или «Сгенерировать кадр».'
    }
    if (!motionDesc.trim()) {
      return 'Заполните краткий бриф для видео — хотя бы одной фразой.'
    }
    return null
  }, [
    motionBusyVideo,
    studioNeedsUserWsKey,
    studioSelectedModelId,
    motionHasFirstFrame,
    motionDesc,
  ])

  const studioImageBtnBlockReason = useMemo(
    () =>
      studioImageGenerateBlockReason({
        studioBusy,
        canStudioGenerate,
        studioMode,
        studioDesc,
        studioFile,
        studioPhotoEditArchiveId,
        studioSelectedModelId,
        studioSendPoseRefToWavespeed,
        studioPaintInpaintMask,
        studioInpaintMaskFile,
        grokSceneConfigured: health?.studio_grok_scene_compose_configured !== false,
        openaiStudioConfigured: health?.openai_studio_configured === true,
        wavespeedConfigured: integ?.wavespeed_configured === true,
        studioPromptOnlyDev,
        studioNeedsUserWsKey,
      }),
    [
      studioBusy,
      canStudioGenerate,
      studioMode,
      studioDesc,
      studioFile,
      studioPhotoEditArchiveId,
      studioSelectedModelId,
      studioSendPoseRefToWavespeed,
      studioPaintInpaintMask,
      studioInpaintMaskFile,
      health?.studio_grok_scene_compose_configured,
      health?.openai_studio_configured,
      integ?.wavespeed_configured,
      studioPromptOnlyDev,
      studioNeedsUserWsKey,
    ],
  )

  const setupTourGenerationsCount = useMemo(
    () =>
      studioGenerations.filter((g) => (g.status || '').trim() !== 'failed').length,
    [studioGenerations],
  )

  const setupTourPhase = useMemo(
    () =>
      me && authed && canStudioAny && !studioPaywalled
        ? resolveSetupTourPhase({
            dismissed: setupTourDismissed,
            hadGeneration: setupTourHadGen,
            archiveReady: studioArchiveReady,
            wavespeedReady: !studioNeedsUserWsKey,
            modelsCount: studioModels.length,
            generationsCount: setupTourGenerationsCount,
          })
        : null,
    [
      me,
      authed,
      canStudioAny,
      studioPaywalled,
      setupTourDismissed,
      setupTourHadGen,
      studioArchiveReady,
      studioNeedsUserWsKey,
      studioModels.length,
      setupTourGenerationsCount,
    ],
  )

  const showSetupTour =
    Boolean(setupTourPhase) &&
    setupTourPhase !== 'done' &&
    !studioArchiveInitialLoading &&
    studioArchiveReady

  useEffect(() => {
    if (setupTourGenerationsCount < 1) return
    if (setupTourHadGen) return
    markSetupTourHadGeneration()
    setSetupTourHadGen(true)
    setSetupTourDismissed(true)
  }, [setupTourGenerationsCount, setupTourHadGen])

  const dismissSetupTourUi = useCallback(() => {
    dismissSetupTour()
    setSetupTourDismissed(true)
  }, [])

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
    if (appSection === 'studio_video' && authed) {
      void loadHealth()
    }
  }, [appSection, authed, loadHealth])

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
          conversation_id?: number
          message?: ChatMessage
          status?: string
        }
        if (payload.type === 'studio_generation') {
          void syncStudioArchivePending()
          return
        }
        if (payload.type === 'studio_job') {
          void syncStudioArchivePending()
          if (payload.status === 'completed' || payload.status === 'failed') {
            void refreshMotionRenders()
            void loadStudioGenerationsReset()
            void refreshMe()
          }
          return
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
  }, [
    loadConversations,
    loadHealth,
    authed,
    refreshMotionRenders,
    loadStudioGenerationsReset,
    syncStudioArchivePending,
    refreshMe,
  ])

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

  const saveConversationStudioModel = async (convId: number, raw: string) => {
    let studioModelId: number | null = null
    if (raw !== '') {
      const n = Number(raw)
      if (!Number.isFinite(n) || n <= 0) return
      studioModelId = n
    }
    setError(null)
    setConvModelBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ studio_model_id: studioModelId }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        return
      }
      const updated = (await r.json()) as Conversation
      setConversations((prev) => prev.map((c) => (c.id === convId ? { ...c, ...updated } : c)))
    } catch {
      setError('Не удалось назначить модель диалогу')
    } finally {
      setConvModelBusy(false)
    }
  }

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
        setError(formatHttpApiError(r, err))
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

  const clearChatReplyAttachment = useCallback(() => {
    setChatReplyFile(null)
    setChatReplyArchiveId(null)
    if (chatReplyFileInputRef.current) chatReplyFileInputRef.current.value = ''
  }, [])

  useEffect(() => {
    setChatArchivePickerOpen(false)
    clearChatReplyAttachment()
  }, [selectedId, clearChatReplyAttachment])

  const chatReplyHasAttachment = Boolean(chatReplyFile || chatReplyArchiveId)

  const sendReply = async () => {
    if (selectedId == null) return
    const text = draft.trim()
    if (!text && !chatReplyHasAttachment) return
    const convId = selectedId
    const fileToSend = chatReplyFile
    const archiveIdToSend = chatReplyArchiveId
    let localPreviewUrl: string | undefined
    if (fileToSend) {
      localPreviewUrl = URL.createObjectURL(fileToSend)
    } else if (archiveIdToSend != null) {
      const g = findStudioArchiveItem(archiveIdToSend)
      const thumb = g ? studioArchiveThumbUrl(g) || g.image_url : null
      if (thumb) localPreviewUrl = thumb
    }
    pendingOutboundIdRef.current -= 1
    const tempId = pendingOutboundIdRef.current
    const optimistic: ChatMessage = {
      id: tempId,
      direction: 'outbound',
      text_original: text,
      text_translated: null,
      created_at: new Date().toISOString(),
      pending: true,
      localPreviewUrl,
    }
    setError(null)
    setDraft('')
    setEmojiOpen(false)
    clearChatReplyAttachment()
    setChatArchivePickerOpen(false)
    setMessages((prev) => [...prev, optimistic])
    requestAnimationFrame(() => scrollToBottom(true))
    try {
      let r: Response
      if (fileToSend || archiveIdToSend != null) {
        const fd = new FormData()
        if (text) fd.append('text', text)
        if (fileToSend) fd.append('image', fileToSend, fileToSend.name || 'image.jpg')
        if (archiveIdToSend != null && !fileToSend) {
          fd.append('studio_generation_id', String(archiveIdToSend))
        }
        r = await apiFetch(`/api/conversations/${convId}/reply`, {
          method: 'POST',
          body: fd,
        })
      } else {
        r = await apiFetch(`/api/conversations/${convId}/reply`, {
          method: 'POST',
          body: JSON.stringify({ text }),
        })
      }
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        setMessages((prev) => {
          if (selectedIdRef.current !== convId) return prev
          return prev.filter((m) => m.id !== tempId)
        })
        setDraft((d) => (d.trim() ? `${text}\n\n${d}` : text))
        if (fileToSend) setChatReplyFile(fileToSend)
        if (archiveIdToSend != null) setChatReplyArchiveId(archiveIdToSend)
        if (localPreviewUrl && fileToSend) URL.revokeObjectURL(localPreviewUrl)
        return
      }
      const msg: ChatMessage = await r.json()
      if (localPreviewUrl && fileToSend) URL.revokeObjectURL(localPreviewUrl)
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
      if (localPreviewUrl && fileToSend) URL.revokeObjectURL(localPreviewUrl)
      setMessages((prev) => {
        if (selectedIdRef.current !== convId) return prev
        return prev.filter((m) => m.id !== tempId)
      })
      setDraft((d) => (d.trim() ? `${text}\n\n${d}` : text))
      if (fileToSend) setChatReplyFile(fileToSend)
      if (archiveIdToSend != null) setChatReplyArchiveId(archiveIdToSend)
      setError('Не удалось отправить сообщение')
    }
  }

  const deleteStudioGeneration = async (id: number, imageUrl: string) => {
    setError(null)
    const r = await apiFetch(`/api/studio/generations/${id}`, { method: 'DELETE' })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatHttpApiError(r, j))
      return
    }
    setStudioGenImageUrl((prev) => (prev === imageUrl ? null : prev))
    setStudioGenGenerationId((prev) => (prev === id ? null : prev))
    void loadStudioGenerationsReset()
    void refreshMotionRenders()
  }

  const deleteStudioVideoArchiveItem = (g: StudioArchiveItem) => {
    if (isMotionRenderArchiveId(g.id)) {
      const rid = -g.id
      setMotionRenders((prev) => prev.filter((r) => r.id !== rid))
      return
    }
    void deleteStudioGeneration(g.id, g.image_url || g.video_url || '')
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

      if (
        preferNativeShareOnMobile() &&
        typeof navigator.share === 'function' &&
        typeof navigator.canShare === 'function'
      ) {
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

  /** Повторно скачивает картинку с CDN провайдера в архив студии (если при генерации файл не сохранился). */
  const retryImportStudioImageToArchive = async (scope: 'studio_photo' | 'motion_still') => {
    const pendingRaw =
      scope === 'studio_photo' ? studioPendingExternalImageUrl : motionPendingExternalStillUrl
    const u = pendingRaw?.trim()
    if (!u?.startsWith('https://')) return
    setStudioImportArchiveBusy(true)
    setError(null)
    try {
      const rp =
        scope === 'studio_photo'
          ? (studioRefinedPromptPreview ?? '').trim()
          : (motionFrameNotes ?? '').trim()
      const r = await apiFetch('/api/studio/import-archive-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_url: u,
          generation_id:
            scope === 'studio_photo'
              ? (studioGenGenerationId ?? undefined)
              : (motionPreviewGenId ?? undefined),
          refined_prompt: rp || (scope === 'studio_photo' ? '[import фото]' : '[import кадр для видео]'),
          output_aspect: studioOutputAspect,
          studio_model_id: studioSelectedModelId ?? undefined,
          exif_camera: studioExifCamera,
        }),
        timeoutMs: 300_000,
      })
      const data = (await r.json().catch(() => ({}))) as {
        generated_image_url?: string | null
        generation_id?: number | null
        message?: string | null
        detail?: unknown
      }
      if (!r.ok) {
        setError(formatHttpApiError(r, data))
        if (data.message?.trim()) setStudioWavespeedMsg(data.message.trim())
        return
      }
      const nu = data.generated_image_url?.trim()
      if (typeof data.generation_id === 'number') {
        if (scope === 'studio_photo') {
          if (nu) setStudioGenImageUrl(nu)
          setStudioGenGenerationId(data.generation_id)
          setStudioPendingExternalImageUrl(null)
          setStudioWavespeedMsg(null)
        } else {
          if (nu) setMotionPreviewUrl(nu)
          setMotionPreviewGenId(data.generation_id)
          setMotionPendingExternalStillUrl(null)
          setMotionMsg(null)
        }
        void refreshMe()
        void loadStudioGenerationsReset()
      } else {
        const m = data.message?.trim()
        if (scope === 'studio_photo') {
          if (nu) setStudioGenImageUrl(nu)
          if (m) setStudioWavespeedMsg(m)
        } else if (m) {
          setMotionMsg(m)
        }
      }
    } catch (e) {
      setError(formatClientFetchError(e, true))
    } finally {
      setStudioImportArchiveBusy(false)
    }
  }

  const downloadMotionResultVideo = async (urlRaw: string | null | undefined) => {
    const url = urlRaw?.trim()
    if (!url) return
    setMotionVideoDownloadBusy(true)
    setError(null)
    try {
      const tryShareUrl = async (): Promise<boolean> => {
        if (!preferNativeShareOnMobile() || typeof navigator.share !== 'function') return false
        try {
          await navigator.share({ title: 'Видео ModelMate', url })
          return true
        } catch (err: unknown) {
          if (err instanceof Error && err.name === 'AbortError') return true
          return false
        }
      }

      let blob: Blob | null = null
      try {
        const res = await fetch(url)
        if (res.ok) blob = await res.blob()
      } catch {
        blob = null
      }

      if (blob) {
        const name = `modelmate-motion-${Date.now()}.mp4`
        const file = new File([blob], name, { type: blob.type || 'video/mp4' })
        if (
          preferNativeShareOnMobile() &&
          typeof navigator.share === 'function' &&
          typeof navigator.canShare === 'function' &&
          navigator.canShare({ files: [file] })
        ) {
          try {
            await navigator.share({ files: [file], title: 'Видео ModelMate' })
            return
          } catch (err: unknown) {
            if (err instanceof Error && err.name === 'AbortError') return
          }
        }
        const objectUrl = URL.createObjectURL(blob)
        try {
          const a = document.createElement('a')
          a.href = objectUrl
          a.download = name
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
        } finally {
          window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
        }
        return
      }

      if (await tryShareUrl()) return
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch {
      setError(
        'Не удалось сохранить ролик. На iPhone: кнопка «Поделиться» или меню⋯ на плеере → «Сохранить видео».',
      )
    } finally {
      setMotionVideoDownloadBusy(false)
    }
  }

  const refineStudioPrompt = async () => {
    if (studioImageGenInFlightRef.current || studioBusy) return
    setError(null)
    if (studioMode === 'photo_edit') {
      if (!studioFile && studioPhotoEditArchiveId == null) {
        setError('В режиме «Доработать фото» загрузите изображение или выберите снимок из архива «Картинки».')
        return
      }
      if (!studioDesc.trim()) {
        setError('Опишите, что изменить или исправить на фото.')
        return
      }
    } else if (studioMode === 'model_scene') {
      if (health?.studio_grok_scene_compose_configured === false) {
        setError('Режим «Основная» использует Grok — на сервере нужен GROK_API_KEY.')
        return
      }
      if (studioSelectedModelId == null) {
        setError('В режиме «Основная» выберите модель с развёрткой и профилем.')
        return
      }
      if (!studioFile) {
        setError('Загрузите референс сцены — Grok возьмёт позу, свет и кадр; в генерацию уйдут только фото модели.')
        return
      }
    } else if (studioMode === 'model') {
      if (health?.studio_grok_scene_compose_configured === false) {
        setError('Режим «По промту» использует Grok — на сервере нужен GROK_API_KEY.')
        return
      }
      if (studioSelectedModelId == null) {
        setError('В режиме «По промту» выберите модель с фото «Тело целиком» в кабинете.')
        return
      }
      if (!studioDesc.trim()) {
        setError('В режиме «По промту» опишите сцену в поле промпта.')
        return
      }
    } else if (
      studioMode !== 'face_swap' &&
      studioMode !== 'grok_compose' &&
      !studioDesc.trim() &&
      !studioFile &&
      studioSelectedModelId == null
    ) {
      setError('Добавьте описание, референс и/или выберите сохранённую модель.')
      return
    }
    if (studioMode === 'face_swap') {
      if (studioSelectedModelId == null) {
        setError('В режиме Face swap выберите модель студии (эталон внешности).')
        return
      }
      if (!studioFile) {
        setError('Загрузите исходное фото (сцена + человека, которого заменить на вашу модель).')
        return
      }
    }
    if (studioMode === 'no_face' && studioSelectedModelId == null && !studioFile) {
      setError('В режиме «Без лица» выберите модель или загрузите референс.')
      return
    }
    if (studioMode === 'grok_compose') {
      if (health?.studio_grok_scene_compose_configured === false) {
        setError('Grok не настроен на сервере (нужен GROK_API_KEY в .env).')
        return
      }
      if (studioSelectedModelId == null) {
        setError('В режиме «Face swap» выберите модель с листами и JSON-профилем.')
        return
      }
      if (!studioFile) {
        setError('Загрузите референс сцены (поза, свет, кадр).')
        return
      }
    }
    const hasStudioBaseImage =
      studioFile != null ||
      (studioMode === 'photo_edit' && studioPhotoEditArchiveId != null)
    const wantsInpaint =
      !studioModeUsesTextOnlyPrompt(studioMode) &&
      studioMode !== 'model_scene' &&
      (studioPaintInpaintMask || studioInpaintMaskFile != null)
    if (wantsInpaint && !hasStudioBaseImage) {
      setError(
        'Для маски загрузите изображение или выберите снимок из архива (режим «Доработать фото»).',
      )
      return
    }
    let inpaintAttach: File | null = null
    if (studioPaintInpaintMask) {
      inpaintAttach = (await studioMaskPainterRef.current?.getMaskFile()) ?? null
      if (!inpaintAttach) {
        setError(
          'Включено «нарисовать маску»: закрасьте кистью область замены или снимите галочку.',
        )
        return
      }
    } else if (studioInpaintMaskFile) {
      inpaintAttach = studioInpaintMaskFile
    }
    studioImageGenInFlightRef.current = true
    setStudioBusy(true)
    setStudioGenImageUrl(null)
    setStudioGenGenerationId(null)
    setStudioWavespeedMsg(null)
    setStudioPendingExternalImageUrl(null)
    setStudioRefinedPromptPreview(null)
    try {
      const promptOnlyActive =
        import.meta.env.DEV &&
        Boolean(health?.studio_allow_prompt_only) &&
        studioDevPromptOnly
      const fd = new FormData()
      fd.append('description', studioDesc.trim())
      if (studioSelectedModelId != null) {
        fd.append('model_id', String(studioSelectedModelId))
      }
      if (studioFile) fd.append('image', studioFile)
      if (inpaintAttach) fd.append('inpaint_mask', inpaintAttach)
      if (
        studioMode === 'photo_edit' &&
        studioPhotoEditArchiveId != null &&
        !studioFile
      ) {
        fd.append('existing_generation_id', String(studioPhotoEditArchiveId))
      }
      fd.append('output_aspect', studioOutputAspect)
      fd.append('studio_mode', studioMode)
      fd.append('wan_edit_tier', studioWanEditTier)
      fd.append('studio_wave_profile', studioWaveProfile)
      fd.append('generate_wavespeed', promptOnlyActive ? '0' : '1')
      fd.append('wavespeed_single_reference', '1')
      fd.append(
        'send_pose_reference_to_wavespeed',
        studioSendPoseRefToWavespeed ? '1' : '0',
      )
      fd.append('lock_model_hairstyle', studioLockModelHairstyle ? '1' : '0')
      fd.append('exif_camera', studioExifCamera)
      const accepted = await postStudioJobStart('/api/studio/refine-prompt', {
        method: 'POST',
        body: fd,
      })
      const gid =
        typeof accepted.generation_id === 'number' ? accepted.generation_id : null
      if (gid != null) {
        setStudioGenGenerationId(gid)
        setStudioGenImageUrl(null)
        setStudioPendingExternalImageUrl(null)
      }
      setStudioWavespeedMsg(
        'Генерация запущена — смотрите прогресс в «Сохранённые». Результат подставится автоматически.',
      )
      void refreshMe()
      void loadStudioGenerationsReset()
    } catch (e) {
      setError(formatClientFetchError(e, true))
    } finally {
      studioImageGenInFlightRef.current = false
      setStudioBusy(false)
    }
  }

  type MotionFirstFrameApiData = {
    refined_prompt?: string
    reference_scene_description?: string | null
    motion_video_prompt_auto?: string | null
    generated_image_url?: string | null
    wavespeed_message?: string | null
    generation_id?: number | null
    motion_video_file_id?: string
    detail?: unknown
  }

  const applyMotionFirstFrameResponse = (data: MotionFirstFrameApiData) => {
    setMotionVideoFileId((prev) => {
      const fromApi =
        typeof data.motion_video_file_id === 'string' ? data.motion_video_file_id.trim() : ''
      return fromApi || prev || null
    })
    const gUrl = data.generated_image_url?.trim() || null
    const gId = typeof data.generation_id === 'number' ? data.generation_id : null
    setMotionPreviewUrl(gUrl)
    setMotionPreviewGenId(gId)
    setMotionPendingExternalStillUrl(
      gId != null ||
        !gUrl ||
        !gUrl.startsWith('https://') ||
        gUrl.includes('/api/studio/public-generation-image')
        ? null
        : gUrl,
    )
    setMotionMsg(data.wavespeed_message?.trim() || null)
    {
      const scene = (data.reference_scene_description ?? '').trim()
      const motion = (data.motion_video_prompt_auto ?? '').trim()
      setMotionGrokTimeline(motion || null)
      const parts: string[] = []
      if (scene)
        parts.push(
          'Первый кадр (сцена для вашей модели, без внешности из видео):\n' + scene,
        )
      if (motion) parts.push('Движение по ролику (Grok timeline):\n' + motion)
      setMotionStep1Preview(parts.length > 0 ? parts.join('\n\n—\n\n') : null)
    }
    setMotionDesc((prev) => {
      if (prev.trim()) return prev
      const notes = motionFrameNotes.trim()
      if (notes) return notes
      return 'Движение как в реф-видео. Сохранить сцену, одежду и свет с первого кадра.'
    })
  }

  const callMotionFirstFrameApi = async (
    useStillFinalEffective: boolean,
  ): Promise<
    | { ok: true; data: MotionFirstFrameApiData }
    | { ok: false; data: MotionFirstFrameApiData; response: Response }
  > => {
    const fd = new FormData()
    if (motionFrameArchiveId != null) {
      fd.append('existing_generation_id', String(motionFrameArchiveId))
    }
    if (motionFirstFrameFile) {
      fd.append('first_frame_image', motionFirstFrameFile)
    }
    if (motionVideoFile) {
      fd.append('video', motionVideoFile)
    }
    fd.append('model_id', String(studioSelectedModelId ?? ''))
    fd.append('description', motionFrameNotes.trim())
    fd.append('output_aspect', studioOutputAspect)
    fd.append(
      'wan_edit_tier',
      motionFirstFrameWaveProfile === 'nsfw' ? studioWanEditTier : 'standard',
    )
    fd.append('studio_wave_profile', motionFirstFrameWaveProfile)
    fd.append('auto_motion_prompt', motionAutoPrompt ? '1' : '0')
    fd.append('lock_model_hairstyle', motionLockHairstyle ? '1' : '0')
    fd.append('use_still_as_final', useStillFinalEffective && motionFirstFrameFile ? '1' : '0')
    fd.append('exif_camera', studioExifCamera)
    try {
      const accepted = await postStudioJobStart('/api/studio/motion/first-frame', {
        method: 'POST',
        body: fd,
      })
      return {
        ok: true as const,
        data: {
          generation_id: accepted.generation_id ?? null,
          wavespeed_message:
            'Кадр генерируется — смотрите прогресс в «Сохранённые».',
        },
      }
    } catch (e) {
      const msg = formatClientFetchError(e, true)
      return {
        ok: false as const,
        data: { detail: msg } as MotionFirstFrameApiData,
        response: new Response(null, { status: 500, statusText: 'Error' }),
      }
    }
  }

  const applyMotionComposeResponse = (data: {
    motion_video_prompt_auto?: string
    reference_scene_description?: string | null
    generation_id?: number | null
    motion_video_file_id?: string | null
  }) => {
    const timeline = (data.motion_video_prompt_auto ?? '').trim()
    if (timeline) setMotionGrokTimeline(timeline)
    const scene = (data.reference_scene_description ?? '').trim()
    const parts: string[] = []
    if (scene) parts.push('Кадр для модели:\n' + scene)
    if (timeline) parts.push('Движение (Grok timeline):\n' + timeline)
    setMotionStep1Preview(parts.length > 0 ? parts.join('\n\n—\n\n') : null)
    const gId = typeof data.generation_id === 'number' ? data.generation_id : null
    if (gId != null) {
      setMotionPreviewGenId(gId)
      const g = findStudioArchiveItem(gId)
      if (g?.image_url) setMotionPreviewUrl(g.image_url)
    }
    if (data.motion_video_file_id) setMotionVideoFileId(data.motion_video_file_id)
    setMotionDesc((prev) => {
      if (prev.trim()) return prev
      return 'Движение как в реф-видео. Сохранить сцену и свет с первого кадра.'
    })
  }

  const runMotionComposeVideoPrompt = async () => {
    setError(null)
    if (!motionVideoFileId) {
      setError('Сначала загрузите референс-видео.')
      return
    }
    if (studioSelectedModelId == null) {
      setError('Выберите модель.')
      return
    }
    if (
      motionPreviewGenId == null &&
      motionFrameArchiveId == null &&
      !motionFirstFrameFile
    ) {
      setError('Нужен кадр: архив, свой файл или сгенерированный кадр.')
      return
    }
    setMotionBusyCompose(true)
    setMotionMsg(null)
    try {
      const fd = new FormData()
      fd.append('motion_video_file_id', motionVideoFileId)
      fd.append('model_id', String(studioSelectedModelId))
      fd.append('description', motionFrameNotes.trim())
      fd.append('lock_model_hairstyle', motionLockHairstyle ? '1' : '0')
      if (motionFrameArchiveId != null && motionPreviewGenId == null) {
        fd.append('existing_generation_id', String(motionFrameArchiveId))
      } else if (motionPreviewGenId != null) {
        fd.append('existing_generation_id', String(motionPreviewGenId))
      }
      if (motionFirstFrameFile) {
        fd.append('first_frame_image', motionFirstFrameFile)
      }
      const data = await postStudioJobAndWait<{
        motion_video_prompt_auto: string
        reference_scene_description?: string | null
        generation_id?: number | null
        motion_video_file_id?: string | null
      }>('/api/studio/motion/compose-video-prompt', { method: 'POST', body: fd })
      applyMotionComposeResponse(data)
      void refreshMe()
      void loadStudioGenerationsReset()
    } catch (e) {
      setError(formatClientFetchError(e, true))
    } finally {
      setMotionBusyCompose(false)
    }
  }

  const runMotionFirstFrame = async () => {
    setError(null)
    const hasStill =
      motionFrameArchiveId != null || motionFirstFrameFile != null || motionVideoFile != null
    if (!hasStill) {
      setError('Загрузите референс-видео, файл первого кадра или выберите снимок из архива.')
      return
    }
    if (motionAutoPrompt && !motionVideoFile) {
      setError(
        'Для авто-описания движения по ролику загрузите референс-видео (или отключите опцию).',
      )
      return
    }
    if (studioSelectedModelId == null) {
      setError('Выберите модель.')
      return
    }
    setMotionBusyFrame(true)
    setMotionMsg(null)
    setMotionResultVideoUrl(null)
    setMotionAutoTextPreview(null)
    setMotionStep1Preview(null)
    setMotionGrokTimeline(null)
    setMotionPendingExternalStillUrl(null)
    try {
      const res = await callMotionFirstFrameApi(
        !!(motionUseStillFinal && motionFirstFrameFile),
      )
      if (!res.ok) {
        setError(formatHttpApiError(res.response, res.data))
        return
      }
      applyMotionFirstFrameResponse(res.data)
      void refreshMe()
      void loadStudioGenerationsReset()
    } catch (e) {
      setError(formatClientFetchError(e, true))
    } finally {
      setMotionBusyFrame(false)
    }
  }

  const runMotionRenderVideo = async () => {
    setError(null)
    if (studioSelectedModelId == null) {
      setError('Выберите модель с фото (лучше — развёртка / character sheet).')
      return
    }
    if (!motionDesc.trim()) {
      setError('Опишите сцену, движение и при необходимости одежду. Можно использовать @Image1 в тексте.')
      return
    }
    if (motionPreviewGenId == null) {
      setError('Нужен первый кадр: выберите из архива, загрузите файл или сгенерируйте кадр.')
      return
    }

    setMotionBusyVideo(true)
    setMotionResultVideoUrl(null)
    try {
      const fd = new FormData()
      fd.append('model_id', String(studioSelectedModelId))
      fd.append('prompt', motionDesc.trim())
      fd.append('output_aspect', studioOutputAspect)
      fd.append('negative_prompt', motionVideoNegPrompt.trim())
      fd.append('generate_audio', motionKeepSound ? '1' : '0')
      fd.append('duration_seconds', String(motionSeedanceDuration))
      fd.append('auto_motion_prompt', motionAutoPrompt ? '1' : '0')
      if (motionPreviewGenId != null) {
        fd.append('first_frame_generation_id', String(motionPreviewGenId))
      }
      if (motionGrokTimeline?.trim()) {
        fd.append('motion_timeline', motionGrokTimeline.trim())
      }
      if (motionVideoFileId) {
        fd.append('motion_video_file_id', motionVideoFileId)
      } else {
        fd.append('motion_video_file_id', '')
      }
      if (motionOutfitArchiveId != null) {
        fd.append('outfit_generation_id', String(motionOutfitArchiveId))
      } else {
        fd.append('outfit_generation_id', '')
      }
      await postStudioJobStart('/api/studio/motion/render-video', {
        method: 'POST',
        body: fd,
      })
      setMotionResultVideoUrl(null)
      setMotionMsg(
        'Видео генерируется — заглушка в «Сохранённые», обычно 10–40 мин. Обновление по готовности автоматически.',
      )
      void refreshMe()
      void loadStudioGenerationsReset()
      void refreshMotionRenders()
    } catch (e) {
      setError(formatClientFetchError(e, true))
      void refreshMotionRenders()
    } finally {
      setMotionBusyVideo(false)
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
      const data = await postStudioJobAndWait<{
        generated_image_url?: string | null
        generation_id?: number | null
        message?: string | null
        target_resolution?: string
      }>(`/api/studio/generations/${studioGenGenerationId}/upscale`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_resolution: studioUpscaleTarget }),
      })
      const url = data.generated_image_url?.trim()
      const gid =
        typeof data.generation_id === 'number' && Number.isFinite(data.generation_id)
          ? data.generation_id
          : null
      if (url) {
        setStudioGenImageUrl(url)
        if (gid != null) {
          setStudioGenGenerationId(gid)
          setStudioPendingExternalImageUrl(null)
        } else if (
          url.startsWith('https://') &&
          !url.includes('/api/studio/public-generation-image')
        ) {
          setStudioPendingExternalImageUrl(url)
        } else {
          setStudioPendingExternalImageUrl(null)
        }
      } else {
        setStudioPendingExternalImageUrl(null)
        setStudioWavespeedMsg(data.message?.trim() || 'Апскейл не выполнен.')
      }
      void refreshMe()
      void loadStudioGenerationsReset()
    } catch (e) {
      setError(formatClientFetchError(e, true))
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
      const data = await postStudioJobAndWait<{
        items?: { generation_id: number; image_url: string }[]
        message?: string | null
      }>(`/api/studio/generations/${studioGenGenerationId}/carousel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          count,
          studio_wave_profile: studioWaveProfile,
          wan_edit_tier: studioWanEditTier,
        }),
      })
      const items = data.items ?? []
      const note = (data.message ?? '').trim()
      if (items.length > 0 && note) {
        setStudioWavespeedMsg(`Сохранено кадров: ${items.length}. ${note}`)
      } else if (items.length > 0) {
        setStudioWavespeedMsg(
          `Карусель: добавлено ${items.length} кадров — смотрите в «Сохранённые».`,
        )
      } else if (note) {
        setStudioWavespeedMsg(note)
      }
      void refreshMe()
      void loadStudioGenerationsReset()
    } catch (e) {
      setError(formatClientFetchError(e, true))
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
      setError(formatHttpApiError(r, j))
      return
    }
    setWsApiKey('')
    setWsSetupPulse(false)
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
      setError(formatHttpApiError(r, j))
      return
    }
    setLlmApiKey('')
    setLlmBaseUrl('')
    setInteg((await r.json()) as IntegrationStatus)
  }

  const generateModelProfileFromPhotos = async () => {
    setError(null)
    if (newModelPhotos.length === 0) {
      setError(`Сначала выберите фото модели (до ${STUDIO_MODEL_MAX_IMAGES} файлов).`)
      return
    }
    setNewModelProfileGenBusy(true)
    try {
      const fd = new FormData()
      for (const row of newModelPhotos) fd.append('images', row.file)
      const r = await apiFetch('/api/studio/models/generate-profile', { method: 'POST', body: fd })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      const data = (await r.json()) as { profile_text: string }
      setNewModelProfile(data.profile_text)
      void refreshMe()
    } catch (e) {
      setError(formatClientFetchError(e, true))
    } finally {
      setNewModelProfileGenBusy(false)
    }
  }

  const uploadModelPhoneExifRef = async (
    modelId: number,
    role: 'selfie' | 'main',
    file: File,
  ): Promise<boolean> => {
    const fd = new FormData()
    fd.append('role', role)
    fd.append('image', file)
    const r = await apiFetch(`/api/studio/models/${modelId}/phone-exif-reference`, {
      method: 'POST',
      body: fd,
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatHttpApiError(r, j))
      return false
    }
    return true
  }

  const clearModelPhoneExifRef = async (modelId: number, role: 'selfie' | 'main') => {
    setError(null)
    setModelPhoneExifBusy(`${modelId}-${role}`)
    try {
      const r = await apiFetch(
        `/api/studio/models/${modelId}/phone-exif-reference?role=${encodeURIComponent(role)}`,
        { method: 'DELETE' },
      )
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      void loadStudioModels()
    } finally {
      setModelPhoneExifBusy(null)
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
    fd.append('camera_preset_id', newModelCameraPresetId.trim())
    fd.append('export_lat', lt)
    fd.append('export_lon', ln)
    const r = await apiFetch('/api/studio/models', { method: 'POST', body: fd })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatHttpApiError(r, j))
      return
    }
    const created = (await r.json()) as UserStudioModel
    if (newModelPhoneExifSelfie) {
      await uploadModelPhoneExifRef(created.id, 'selfie', newModelPhoneExifSelfie)
    }
    if (newModelPhoneExifMain) {
      await uploadModelPhoneExifRef(created.id, 'main', newModelPhoneExifMain)
    }
    setNewModelName('')
    setNewModelProfile('')
    setNewModelPhotos([])
    setNewModelCameraPresetId('')
    setNewModelExportLat('')
    setNewModelExportLon('')
    setNewModelPhoneExifSelfie(null)
    setNewModelPhoneExifMain(null)
    void loadStudioModels()
  }

  const deleteStudioModel = async (id: number) => {
    setError(null)
    const r = await apiFetch(`/api/studio/models/${id}`, { method: 'DELETE' })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatHttpApiError(r, j))
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
        setError(formatHttpApiError(r, j))
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
      const r = await apiFetch(`/api/studio/models/${id}/images`, { method: 'POST', body: fd })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
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
    patch: { kind?: StudioModelImageKind },
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
        setError(formatHttpApiError(r, j))
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
      setError(formatHttpApiError(r, j))
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
      setError(formatHttpApiError(r, j))
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
      setError(formatHttpApiError(r, j))
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
          allowed_studio_model_ids: newTeamModelIds,
        }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      setNewTeamLogin('')
      setNewTeamPassword('')
      setNewTeamMask(DEFAULT_MEMBER_PERMISSIONS)
      setNewTeamModelIds([])
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
      const modelIds = memberModelEdits[row.id] ?? row.allowed_studio_model_ids ?? []
      const body: {
        permissions_mask: number
        password?: string
        allowed_studio_model_ids: number[]
      } = { permissions_mask: mask, allowed_studio_model_ids: modelIds }
      if (pwd.length >= 8) body.password = pwd
      const r = await apiFetch(`/api/workspace/members/${row.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
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
      setError(formatHttpApiError(r, j))
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
      setError(formatHttpApiError(r, j))
      return
    }
    void refreshWorkspaceMembers()
  }

  const paySubscriptionWithCredits = async (product: BillingPlanRow['product']) => {
    setError(null)
    setYookassaPayBusy(product)
    try {
      const r = await apiFetch('/api/billing/subscribe-with-credits', {
        method: 'POST',
        body: JSON.stringify({ product }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      void refreshMe()
      void refreshBillingPlans()
    } finally {
      setYookassaPayBusy(null)
    }
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
        setError(formatHttpApiError(r, j))
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
                setAccountTab('integrations')
                setAccountOpen(true)
                setWsSetupPulse(true)
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
    hasAnyMainSection ? 'app--shell' : '',
    isMobileLayout && selectedId != null && appSection === 'chat' && canChat
      ? 'mobile-chat-open'
      : '',
    showThreadDock ? 'with-thread-dock' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const handleLogout = () => {
    setToken(null)
    setAuthed(false)
    setMe(null)
    setConversations([])
    setSelectedId(null)
    navigate('/', { replace: true })
  }

  const openWorkspaceChat = (convId?: number) => {
    if (convId != null) setSelectedId(convId)
    setAppSection('chat')
  }

  return (
    <div className={appClass}>
      <div className="app-bg" aria-hidden />
      {billingBannerCopy ? (
        <div
          className={`billing-return-banner billing-return-banner--${billingBannerCopy.variant}`}
          role="status"
        >
          <div className="billing-return-banner__text">
            <h2 className="billing-return-banner__title">{billingBannerCopy.title}</h2>
            <p className="billing-return-banner__body">{billingBannerCopy.body}</p>
          </div>
          <div className="billing-return-banner__actions">
            {isOwner ? (
              <button
                type="button"
                className="send-btn"
                onClick={() => {
                  setAccountTab('billing')
                  setAccountOpen(true)
                  clearBillingQuery()
                }}
              >
                Тариф и пополнение
              </button>
            ) : null}
            <button type="button" className="ghost-btn" onClick={clearBillingQuery}>
              Закрыть
            </button>
          </div>
        </div>
      ) : null}
      {showThreadDock ? (
        <header
          className={
            hasAnyMainSection ? 'thread-mobile-dock thread-mobile-dock--shell' : 'thread-mobile-dock'
          }
        >
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
      {error && <div className="banner error">{error}</div>}

      {!hasAnyMainSection ? (
        <div className="banner info" style={{ margin: '0 1rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <span>
            Нет доступа к диалогам и студии по правам аккаунта. Откройте кабинет или обратитесь к владельцу.
          </span>
          <button type="button" className="ghost-btn" onClick={() => setAccountOpen(true)}>
            Личный кабинет
          </button>
        </div>
      ) : null}

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
                  <div className="cabinet-dash-value">{userBillingPlanLabel(me)}</div>
                  <p className="cabinet-dash-hint muted">{userBillingPlanLong(me)}</p>
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
              {me?.billing_require_active_subscription && me.subscription_status === 'trialing' ? (
                <div className="banner info" style={{ marginTop: '1rem' }}>
                  <strong>Пробный доступ:</strong> студия доступна, пока есть бонусные кредиты. Подключите свой ключ
                  WaveSpeed в разделе «Подключения». После нулевого баланса оформите подписку Managed или BYOK — иначе
                  студия заблокируется.
                </div>
              ) : me?.billing_require_active_subscription && !subscriptionCoversStudioAccess(me) ? (
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
                {canPlatformAdmin ? (
                  <Link to="/admin" className="ghost-btn cabinet-admin-link">
                    Админ-панель
                  </Link>
                ) : null}
              </div>
            </div>
          )}

          {accountTab === 'billing' && isOwner && (
            <div className="account-cabinet-pane" role="tabpanel">
              <p className="cabinet-lead muted">
                <strong>Здесь выбираете тариф</strong> (Managed или BYOK) <strong>и оплачиваете</strong> подписку. Пакет
                кредитов — только после оплаченного Managed.
              </p>
              <p className="cabinet-lead muted">
                <strong>Managed</strong> — кредиты на студию; картинки до оплаты через ваш WaveSpeed, после оплаты через
                ключ платформы. <strong>BYOK</strong> — всегда ваш WaveSpeed; кредиты на студию не списываются. Текст и
                vision студии всегда обрабатываются на сервере.
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
                <p className="cabinet-module-body">{userBillingPlanLong(me)}</p>
                <p className="muted cabinet-module-meta">
                  {me?.subscription_period_end
                    ? `Период до ${formatDateTimeRu(me.subscription_period_end)}`
                    : 'Дата окончания появится после оплаты'}
                  {' · '}Баланс: <strong>{me?.credits_balance ?? 0}</strong> кр.
                </p>
                {me?.plan_usage ? (
                  <ul className="muted small" style={{ margin: '0.75rem 0 0', paddingLeft: '1.1rem' }}>
                    <li>
                      Пользователи: {me.plan_usage.users} / {me.plan_usage.limits.max_users}
                    </li>
                    <li>
                      Модели: {me.plan_usage.models} / {me.plan_usage.limits.max_models}
                    </li>
                    <li>
                      Диалоги в месяце: {me.plan_usage.dialogs_this_month}
                      {me.plan_usage.limits.max_dialogs_per_month != null
                        ? ` / ${me.plan_usage.limits.max_dialogs_per_month}`
                        : ' · без лимита'}
                    </li>
                    <li>
                      GROK в месяце: {me.plan_usage.grok_this_month}
                      {me.plan_usage.limits.max_grok_per_month != null
                        ? ` / ${me.plan_usage.limits.max_grok_per_month}`
                        : ''}
                    </li>
                  </ul>
                ) : null}
              </div>
              {referralInfo ? (
                <div className="cabinet-module" style={{ marginBottom: '1rem' }}>
                  <div className="cabinet-module-head">
                    <span className="cabinet-module-title">Реферальная программа</span>
                  </div>
                  <p className="cabinet-module-body muted small">
                    Друг по ссылке: +{referralInfo.friend_referral_credits} кр. (плюс триал{' '}
                    {referralInfo.signup_base_credits} кр.). С каждой оплаты приглашённого:{' '}
                    <strong>{referralInfo.referrer_reward_summary}</strong>
                    {referralInfo.credits_earned > 0
                      ? ` Уже начислено: ${referralInfo.credits_earned} кр.`
                      : null}
                    . Подписку можно оплатить кредитами (1 кр. = {referralInfo.credit_unit_price_rub} ₽).
                  </p>
                  <p className="mono small" style={{ wordBreak: 'break-all' }}>
                    {referralInfo.referral_link}
                  </p>
                  <p className="muted small">
                    Приглашено: {referralInfo.invited_count} · Заработано: {referralInfo.credits_earned} кр.
                  </p>
                </div>
              ) : null}
              <h4 className="account-sub">Тариф и пополнение</h4>
              {me?.online_payment_available ? (
                <>
                  <p className="muted" style={{ marginBottom: '0.75rem' }}>
                    Оплата банковской картой. После успешной оплаты вернитесь в кабинет.
                  </p>
                  <div className="mkt-pricing-toggles" style={{ marginBottom: '0.75rem' }}>
                    <button
                      type="button"
                      className={billingPayMode === 'byok' ? 'mkt-toggle active' : 'mkt-toggle'}
                      onClick={() => setBillingPayMode('byok')}
                    >
                      BYOK
                    </button>
                    <button
                      type="button"
                      className={billingPayMode === 'managed' ? 'mkt-toggle active' : 'mkt-toggle'}
                      onClick={() => setBillingPayMode('managed')}
                    >
                      Managed
                    </button>
                    <button
                      type="button"
                      className={billingPayPeriod === 'month' ? 'mkt-toggle active' : 'mkt-toggle'}
                      onClick={() => setBillingPayPeriod('month')}
                    >
                      Месяц
                    </button>
                    <button
                      type="button"
                      className={billingPayPeriod === 'year' ? 'mkt-toggle active' : 'mkt-toggle'}
                      onClick={() => setBillingPayPeriod('year')}
                    >
                      Год
                    </button>
                  </div>
                  <div className="cabinet-yookassa-rows">
                    {billingPlanRows
                      .filter((row) => {
                        if (row.product === 'credits_pack') return true
                        const m = row.product.match(/^sub_(byok|managed)_(solo|pro|studio)_(month|year)$/)
                        if (!m) return false
                        return m[1] === billingPayMode && m[3] === billingPayPeriod
                      })
                      .map((row) => {
                      if (row.product === 'credits_pack' && row.credits_pricing) {
                        const packOk = canPurchaseStudioCreditPack(me)
                        if (!packOk) {
                          return (
                            <div key={row.product} className="cabinet-yookassa-row">
                              <div>
                                <div className="cabinet-offer-title">{row.title}</div>
                                <p className="muted small" style={{ margin: '0.35rem 0 0' }}>
                                  Покупка кредитов открывается после оплаты подписки Managed (статус «Активна», не пробный
                                  период).
                                </p>
                              </div>
                              <button type="button" className="send-btn" disabled>
                                Недоступно
                              </button>
                            </div>
                          )
                        }
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
                      const subCredits = subscriptionCostCredits(row.price_rub, billingCreditUnitRub)
                      const balance = me?.credits_balance ?? 0
                      const canPayCredits = balance >= subCredits
                      return (
                        <div key={row.product} className="cabinet-yookassa-row">
                          <div>
                            <div className="cabinet-offer-title">{row.title}</div>
                            <div className="cabinet-offer-price">
                              {row.price_rub}{' '}
                              {row.currency === 'RUB' || !row.currency ? '₽' : row.currency}
                            </div>
                            <p className="muted small" style={{ margin: '0.35rem 0 0' }}>
                              или {subCredits} кр. ({billingCreditUnitRub} ₽/кр.) · на балансе {balance} кр.
                            </p>
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
                            <button
                              type="button"
                              className="ghost-btn"
                              disabled={yookassaPayBusy !== null || !canPayCredits}
                              title={
                                canPayCredits
                                  ? undefined
                                  : `Нужно ${subCredits} кр., на балансе ${balance}`
                              }
                              onClick={() => void paySubscriptionWithCredits(row.product)}
                            >
                              {yookassaPayBusy === row.product ? '…' : 'Кредитами'}
                            </button>
                            <button
                              type="button"
                              className="send-btn"
                              disabled={yookassaPayBusy !== null}
                              onClick={() => void startYookassaPayment(row.product)}
                            >
                              {yookassaPayBusy === row.product ? '…' : 'Картой'}
                            </button>
                          </div>
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

              {studioNeedsUserWsKey && isOwner ? (
                <WavespeedSetupBanner
                  variant="integrations"
                  isTrialing={(me?.subscription_status || '').toLowerCase() === 'trialing'}
                  canConnect={canIntegrations}
                  onOpenIntegrations={openWavespeedIntegrations}
                />
              ) : null}

              <section
                id="cabinet-wavespeed-key"
                className={`cabinet-module${studioNeedsUserWsKey ? ' cabinet-module--highlight' : ''}${wsSetupPulse ? ' cabinet-module--pulse' : ''}`}
              >
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">WaveSpeed</h4>
                  <span className={`cabinet-module-badge ${integ?.wavespeed_configured ? 'is-ok' : 'is-warn'}`}>
                    {integ?.wavespeed_managed_by_platform
                      ? 'Ключ платформы (Managed)'
                      : integ?.wavespeed_configured
                        ? 'Ключ сохранён'
                        : 'Нет ключа'}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  <strong>Пробный Managed:</strong> сохраните свой API-ключ — студия ходит в WaveSpeed только с ним, пока не
                  оформлена оплата.
                  <br />
                  <strong>Оплаченный Managed:</strong> картинки через ключ платформы (<code>WAVESPEED_PLATFORM_API_KEY</code>
                  ). Поле ниже не обязательно.
                  <br />
                  <strong>Тариф BYOK:</strong> всегда ваш ключ — без него генерация недоступна.
                  <br />
                  <strong>Ключ:</strong>{' '}
                  <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                    зарегистрируйтесь на wavespeed.ai
                  </a>{' '}
                  (реферальная ссылка ModelMate) и скопируйте API-ключ в поле ниже.
                </p>
                <div className="cabinet-module-form">
                  <label>
                    API-ключ
                    <input
                      type="password"
                      autoComplete="off"
                      value={wsApiKey}
                      onChange={(e) => setWsApiKey(e.target.value)}
                      placeholder="Вставьте ключ из wavespeed.ai"
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

              {canPlatformAdmin ? (
              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">Текстовая модель (студия)</h4>
                  <span className={`cabinet-module-badge ${integ?.llm_configured ? 'is-ok' : 'is-warn'}`}>
                    {integ?.llm_configured ? 'Ключ на сервере' : 'Сервер не настроен'}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  Промпты и vision в студии всегда идут через AI-ключ, заданный администратором на сервере (
                  <code>OPENAI_API_KEY</code> / совместимая база). Поля ниже не используются студией и оставлены на будущее.
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
              ) : null}

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
                Модели подставляются в промпт на вкладке «Генерация картинок». До {STUDIO_MODEL_MAX_IMAGES}{' '}
                фото на модель. Для
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
                  Фото модели (до {STUDIO_MODEL_MAX_IMAGES})
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    multiple
                    disabled={studioPaywalled}
                    onChange={(e) => {
                      const list = e.target.files ? Array.from(e.target.files) : []
                      setNewModelPhotos(
                        list.slice(0, STUDIO_MODEL_MAX_IMAGES).map((file, i) => ({
                          file,
                          kind: (i === 0 ? 'face' : 'other') as StudioModelImageKind,
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
                    На сохранённые кадры студии: шум, JPEG и EXIF. Сначала эталоны с телефона (ниже), иначе
                    пресет из списка. Фронталка или основная камера выбирается при каждой генерации на
                    странице «Картинки».
                  </p>
                  <div className="studio-phone-exif-refs">
                    <p className="studio-phone-exif-refs__title">Эталоны EXIF с телефона</p>
                    <label className="studio-phone-exif-refs__slot">
                      <span>Фронтальная камера</span>
                      <input
                        type="file"
                        accept="image/jpeg,image/jpg"
                        disabled={studioPaywalled}
                        onChange={(e) =>
                          setNewModelPhoneExifSelfie(e.target.files?.[0] ?? null)
                        }
                      />
                      {newModelPhoneExifSelfie ? (
                        <span className="muted small">{newModelPhoneExifSelfie.name}</span>
                      ) : (
                        <span className="muted small">JPEG из галереи (не из мессенджера)</span>
                      )}
                    </label>
                    <label className="studio-phone-exif-refs__slot">
                      <span>Основная камера</span>
                      <input
                        type="file"
                        accept="image/jpeg,image/jpg"
                        disabled={studioPaywalled}
                        onChange={(e) => setNewModelPhoneExifMain(e.target.files?.[0] ?? null)}
                      />
                      {newModelPhoneExifMain ? (
                        <span className="muted small">{newModelPhoneExifMain.name}</span>
                      ) : (
                        <span className="muted small">Обычное фото с задней камеры</span>
                      )}
                    </label>
                  </div>
                  <label>
                    Пресет камеры (запасной)
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
                    const modelPhotoSlotsFull =
                      m.image_count + pendingAppend.length >= STUDIO_MODEL_MAX_IMAGES
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
                            Эталоны с телефона важнее пресета. Дата в EXIF — при сохранении кадра. ГЕО —
                            опционально. Фронталка или основная — переключатель на странице «Картинки» при
                            генерации.
                          </p>
                          <div className="studio-phone-exif-refs">
                            <p className="studio-phone-exif-refs__title">Эталоны EXIF с телефона</p>
                            <div className="studio-phone-exif-refs__slot">
                              <span>Фронтальная камера</span>
                              {m.phone_exif_selfie_ready && m.phone_exif_selfie_summary ? (
                                <p className="muted small studio-phone-exif-refs__ok">
                                  ✓ {m.phone_exif_selfie_summary}
                                </p>
                              ) : (
                                <p className="muted small">Не загружен</p>
                              )}
                              <label className="model-card-add-files">
                                <input
                                  type="file"
                                  accept="image/jpeg,image/jpg"
                                  className="sr-only-input"
                                  disabled={busy || studioPaywalled}
                                  onChange={(e) => {
                                    const f = e.target.files?.[0]
                                    if (!f) return
                                    void (async () => {
                                      setModelPhoneExifBusy(`${m.id}-selfie`)
                                      await uploadModelPhoneExifRef(m.id, 'selfie', f)
                                      setModelPhoneExifBusy(null)
                                      void loadStudioModels()
                                    })()
                                    e.target.value = ''
                                  }}
                                />
                                <span className="ghost-btn">
                                  {modelPhoneExifBusy === `${m.id}-selfie`
                                    ? 'Чтение…'
                                    : m.phone_exif_selfie_ready
                                      ? 'Заменить'
                                      : 'Загрузить'}
                                </span>
                              </label>
                              {m.phone_exif_selfie_ready ? (
                                <button
                                  type="button"
                                  className="ghost-btn small"
                                  disabled={busy || studioPaywalled}
                                  onClick={() => void clearModelPhoneExifRef(m.id, 'selfie')}
                                >
                                  Сбросить
                                </button>
                              ) : null}
                            </div>
                            <div className="studio-phone-exif-refs__slot">
                              <span>Основная камера</span>
                              {m.phone_exif_main_ready && m.phone_exif_main_summary ? (
                                <p className="muted small studio-phone-exif-refs__ok">
                                  ✓ {m.phone_exif_main_summary}
                                </p>
                              ) : (
                                <p className="muted small">Не загружен</p>
                              )}
                              <label className="model-card-add-files">
                                <input
                                  type="file"
                                  accept="image/jpeg,image/jpg"
                                  className="sr-only-input"
                                  disabled={busy || studioPaywalled}
                                  onChange={(e) => {
                                    const f = e.target.files?.[0]
                                    if (!f) return
                                    void (async () => {
                                      setModelPhoneExifBusy(`${m.id}-main`)
                                      await uploadModelPhoneExifRef(m.id, 'main', f)
                                      setModelPhoneExifBusy(null)
                                      void loadStudioModels()
                                    })()
                                    e.target.value = ''
                                  }}
                                />
                                <span className="ghost-btn">
                                  {modelPhoneExifBusy === `${m.id}-main`
                                    ? 'Чтение…'
                                    : m.phone_exif_main_ready
                                      ? 'Заменить'
                                      : 'Загрузить'}
                                </span>
                              </label>
                              {m.phone_exif_main_ready ? (
                                <button
                                  type="button"
                                  className="ghost-btn small"
                                  disabled={busy || studioPaywalled}
                                  onClick={() => void clearModelPhoneExifRef(m.id, 'main')}
                                >
                                  Сбросить
                                </button>
                              ) : null}
                            </div>
                          </div>
                          <label>
                            Пресет камеры (запасной)
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
                                const slots = Math.max(
                                  0,
                                  STUDIO_MODEL_MAX_IMAGES - m.image_count - pendingAppend.length,
                                )
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
                подписка — на владельце; права ниже ограничивают разделы. Модели студии и чаты назначаются
                вручную — без галочки участник их не видит.
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
                {studioModels.length > 0 ? (
                  <div style={{ gridColumn: '1 / -1' }} className="team-model-grid">
                    <span className="account-sub" style={{ margin: 0 }}>
                      Модели студии
                    </span>
                    {studioModels.map((m) => (
                      <label key={m.id} className="studio-label studio-check">
                        <input
                          type="checkbox"
                          checked={newTeamModelIds.includes(m.id)}
                          disabled={teamBusy}
                          onChange={(e) => {
                            const on = e.target.checked
                            setNewTeamModelIds((prev) => {
                              const s = new Set(prev)
                              if (on) s.add(m.id)
                              else s.delete(m.id)
                              return [...s].sort((a, b) => a - b)
                            })
                          }}
                        />
                        <span>{m.name}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="muted" style={{ gridColumn: '1 / -1' }}>
                    Сначала создайте модели в студии — затем назначьте их участникам.
                  </p>
                )}
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
                    const modelIds = memberModelEdits[row.id] ?? row.allowed_studio_model_ids ?? []
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
                        {studioModels.length > 0 ? (
                          <div className="team-model-grid">
                            <span className="account-sub" style={{ margin: 0 }}>
                              Модели студии
                            </span>
                            {studioModels.map((m) => (
                              <label key={m.id} className="studio-label studio-check">
                                <input
                                  type="checkbox"
                                  checked={modelIds.includes(m.id)}
                                  disabled={teamBusy}
                                  onChange={(e) => {
                                    const on = e.target.checked
                                    setMemberModelEdits((prev) => {
                                      const cur = prev[row.id] ?? modelIds
                                      const s = new Set(cur)
                                      if (on) s.add(m.id)
                                      else s.delete(m.id)
                                      return { ...prev, [row.id]: [...s].sort((a, b) => a - b) }
                                    })
                                  }}
                                />
                                <span>{m.name}</span>
                              </label>
                            ))}
                          </div>
                        ) : null}
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
                            Сохранить права, модели и пароль
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

      {hasAnyMainSection ? (
        <AppShell
          appSection={appSection}
          onSectionChange={setAppSection}
          canChat={canChat}
          canStudioAny={canStudioAny}
          unreadTotal={unreadTotal}
          creditsBalance={me?.credits_balance ?? null}
          billingPlanLabel={userBillingPlanLabel(me)}
          userTitle={
            me?.is_workspace_owner
              ? me.email
              : `${me?.owner_email ?? ''}${me?.member_login ? ` · ${me.member_login}` : ''}`
          }
          userMeta={`${me?.credits_balance ?? 0} кр. · ${userBillingPlanLabel(me)}`}
          onAccountOpen={() => setAccountOpen(true)}
          onLogout={handleLogout}
        >
          {health?.legacy_telegram_polling && health.telegram_api_reachable === false && (
            <div className="banner error">
              Нет связи с Telegram. Обратитесь к администратору сервиса.
            </div>
          )}

          {appSection === 'overview' && me ? (
            <>
            {showSetupTour ? (
              <SetupTour
                phase={setupTourPhase}
                isOwner={isOwner}
                canStudioModels={canStudioModels}
                onOpenIntegrations={openWavespeedIntegrations}
                onOpenModels={() => {
                  setAccountOpen(true)
                  setAccountTab('models')
                }}
                onGoStudio={() => setAppSection('studio')}
                onDismiss={dismissSetupTourUi}
              />
            ) : null}
            <WorkspaceOverview
              creditsBalance={me.credits_balance}
              billingPlanLabel={userBillingPlanLabel(me)}
              subscriptionLabel={subscriptionStatusLabel(me.subscription_status)}
              unreadTotal={unreadTotal}
              conversationsTotal={conversations.length}
              generationsTotal={studioGenerations.length}
              canChat={canChat}
              canStudioAny={canStudioAny}
              conversations={conversations}
              generations={studioGenerations}
              motionRenders={motionRenders}
              onOpenChat={openWorkspaceChat}
              onOpenStudio={() => setAppSection('studio')}
              onOpenVideo={() => setAppSection('studio_video')}
              onOpenAccount={() => setAccountOpen(true)}
            />
            </>
          ) : null}

      {import.meta.env.DEV &&
        health &&
        appSection !== 'studio' &&
        appSection !== 'studio_bootstrap' &&
        appSection !== 'studio_video' && (
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
        <section className="studio-panel studio-workspace-page" aria-labelledby="studio-heading">
          <div className="studio-workspace">
            <div className="studio-workspace__composer" aria-labelledby="studio-heading">
              <header className="studio-workspace__composer-head">
                <h2 id="studio-heading">Картинки</h2>
                <p className="studio-workspace__tagline">Модель, референс и описание — результат в истории справа.</p>
              </header>
              {!studioPaywalled && studioNeedsUserWsKey ? (
                <WavespeedSetupBanner
                  variant="studio"
                  isTrialing={(me?.subscription_status || '').toLowerCase() === 'trialing'}
                  canConnect={isOwner && canIntegrations}
                  onOpenIntegrations={openWavespeedIntegrations}
                />
              ) : null}
              {!studioPaywalled && showSetupTour ? (
                <SetupTour
                  phase={setupTourPhase}
                  isOwner={isOwner}
                  canStudioModels={canStudioModels}
                  onOpenIntegrations={openWavespeedIntegrations}
                  onOpenModels={() => {
                    setAccountOpen(true)
                    setAccountTab('models')
                  }}
                  onGoStudio={() => setAppSection('studio')}
                  onDismiss={dismissSetupTourUi}
                />
              ) : null}
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
              <div className="studio-slot-grid studio-slot-grid--composer">
            <div className="studio-mode-row studio-mode-compact" role="group" aria-label="Режим студии">
              <span className="studio-mode-label">Режим</span>
              <div className="studio-mode-segment">
                {STUDIO_IMAGE_MODE_OPTIONS.map(({ id, label }) => (
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
            {studioMode === 'grok_compose' &&
            health?.studio_grok_scene_compose_configured === false ? (
              <div className="banner warn">
                Grok не настроен: на сервере нужен <span className="mono">GROK_API_KEY</span> (или
                OpenAI-совместимый ключ с vision).
              </div>
            ) : null}
            <div className="studio-mode-row" role="group" aria-label="Тип снимка">
              <span className="studio-mode-label">Стиль</span>
              <div className="studio-mode-segment">
                <button
                  type="button"
                  className={`studio-mode-btn${studioWaveProfile === 'regular' ? ' is-active' : ''}`}
                  onClick={() => setStudioWaveProfile('regular')}
                >
                  Обычные
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
                <div className="studio-mode-row" role="group" aria-label="Детализация редактора">
                  <span className="studio-mode-label">Качество</span>
                  <div className="studio-mode-segment">
                    <button
                      type="button"
                      className={`studio-mode-btn${studioWanEditTier === 'standard' ? ' is-active' : ''}`}
                      onClick={() => setStudioWanEditTier('standard')}
                    >
                      Стандарт
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
                <p className="studio-mode-hint">Pro — выше детализация, обычно дороже по кредитам.</p>
              </>
            ) : null}
            <StudioPillField
              label="Формат"
              hint="Стороны кадра"
              scrollRow
              options={
                studioAspectPresets.length > 0
                  ? studioAspectPresets.map((p) => ({
                      value: p.key,
                      label: p.key,
                      title: p.label,
                    }))
                  : [{ value: '9:16', label: '9:16', title: '9:16' }]
              }
              value={studioOutputAspect}
              onChange={(v) => v != null && setStudioOutputAspect(String(v))}
            />
            <StudioPillField
              label="Модель"
              hint={
                studioMode === 'model_scene'
                  ? 'Внешность в WaveSpeed; сцена — из референса через Grok'
                  : studioModeUsesTextOnlyPrompt(studioMode)
                    ? 'Обязательна — только её фото в генерацию'
                    : studioMode === 'face_swap'
                      ? 'Обязательна вместе с фото'
                      : 'Листы для лица и тела'
              }
              icon={<IconModel className="studio-slot__icon-svg" />}
              scrollRow={studioModels.length > 4}
              options={studioModels.map((m) => ({ value: m.id, label: m.name }))}
              value={studioSelectedModelId}
              onChange={(v) => setStudioSelectedModelId(v)}
              allowEmpty={studioMode !== 'model_scene' && !studioModeUsesTextOnlyPrompt(studioMode)}
              emptyLabel="Без модели"
            />
            {studioMode === 'photo_edit' ? (
              <StudioArchiveThumbPicker
                label="Кадр из архива"
                hint="Вместо загрузки с устройства"
                items={studioGenerations}
                value={studioPhotoEditArchiveId}
                onChange={(id) => {
                  setStudioPhotoEditArchiveId(id)
                  if (id != null) setStudioFile(null)
                }}
              />
            ) : null}
            {!studioModeUsesTextOnlyPrompt(studioMode) ? (
              <StudioMediaSlot
                label={
                  studioMode === 'photo_edit'
                    ? 'Фото'
                    : studioMode === 'face_swap'
                      ? 'Исходное фото'
                      : 'Референс'
                }
                hint={
                  studioMode === 'photo_edit'
                    ? 'Или выберите миниатюру выше'
                    : studioMode === 'model_scene'
                      ? 'Для Grok: поза, свет, кадр (не уходит в WaveSpeed)'
                      : 'Поза и сцена'
                }
                icon="image"
                previewUrl={studioReferenceObjectUrl}
                accept="image/jpeg,image/png,image/webp,image/gif"
                onFile={(f) => {
                  setStudioFile(f)
                  if (f) setStudioPhotoEditArchiveId(null)
                }}
                onClear={() => setStudioFile(null)}
                emptyLabel="JPG, PNG, WebP"
              />
            ) : (
              <p className="studio-mode-hint">
                Режим «По промту»: сцена только из текста промпта, без референс-фото.
              </p>
            )}
            {studioMode === 'model_scene' ? (
              <p className="studio-mode-hint">
                Референс читает Grok и попадает в текстовый промпт без отсылок к «реф-фото». В
                WaveSpeed — только снимки модели (развёртка, тело, лицо).
              </p>
            ) : null}
            {!studioModeUsesTextOnlyPrompt(studioMode) && studioMode !== 'model_scene' ? (
            <label
              className="studio-label studio-check"
              style={!studioInpaintBaseImageSrc ? { opacity: 0.55 } : undefined}
            >
              <input
                type="checkbox"
                checked={studioPaintInpaintMask}
                disabled={!studioInpaintBaseImageSrc}
                onChange={(e) => {
                  const on = e.target.checked
                  setStudioPaintInpaintMask(on)
                }}
              />
              <span>Нарисовать маску кистью — белым отметьте, что нужно изменить на снимке.</span>
            </label>
            ) : null}
            {!studioModeUsesTextOnlyPrompt(studioMode) &&
            studioMode !== 'model_scene' &&
            studioPaintInpaintMask &&
            studioInpaintBaseImageSrc ? (
              <div className="studio-mask-painter-controls">
                <div className="studio-mask-painter-row">
                  <label className="studio-mask-brush-label">
                    Кисть
                    <select
                      value={studioMaskBrushPreset}
                      onChange={(e) =>
                        setStudioMaskBrushPreset(e.target.value as 's' | 'm' | 'l')
                      }
                    >
                      <option value="s">Тонкая</option>
                      <option value="m">Средняя</option>
                      <option value="l">Толщина</option>
                    </select>
                  </label>
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => studioMaskPainterRef.current?.clearMask()}
                  >
                    Очистить маску
                  </button>
                </div>
                <StudioInpaintMaskPainter
                  ref={studioMaskPainterRef}
                  imageSrc={studioInpaintBaseImageSrc}
                  enabled={studioPaintInpaintMask}
                  brushSize={studioMaskBrushPreset}
                />
              </div>
            ) : null}
            {!studioModeUsesTextOnlyPrompt(studioMode) && studioMode !== 'model_scene' ? (
            <label
              className="studio-label"
              style={
                !studioInpaintBaseImageSrc || studioPaintInpaintMask
                  ? { opacity: 0.55 }
                  : undefined
              }
            >
              Файл маски (белое — что менять){' '}
              <span className="muted studio-file-name">альтернатива кисти</span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={!studioInpaintBaseImageSrc || studioPaintInpaintMask}
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null
                  setStudioInpaintMaskFile(f)
                }}
              />
              {!studioPaintInpaintMask && studioInpaintMaskFile ? (
                <span className="studio-file-name">{studioInpaintMaskFile.name}</span>
              ) : !studioPaintInpaintMask ? (
                <span
                  className="muted"
                  style={{ display: 'block', marginTop: '0.35rem', fontSize: '0.85rem' }}
                >
                  Альтернатива кисти: полностью подготовленная маска во внешнем редакторе.
                </span>
              ) : null}
            </label>
            ) : null}
            {studioSelectedModelId != null ? (
              <div className="studio-mode-row" role="group" aria-label="Камера для EXIF при сохранении">
                <span className="studio-mode-label">EXIF</span>
                <div className="studio-mode-segment">
                  <button
                    type="button"
                    className={`studio-mode-btn${studioExifCamera === 'selfie' ? ' is-active' : ''}`}
                    onClick={() => setStudioExifCamera('selfie')}
                  >
                    Фронталка
                  </button>
                  <button
                    type="button"
                    className={`studio-mode-btn${studioExifCamera === 'main' ? ' is-active' : ''}`}
                    onClick={() => setStudioExifCamera('main')}
                  >
                    Основная
                  </button>
                </div>
              </div>
            ) : null}
            {studioSelectedModelId != null ? (
              <p className="studio-mode-hint">
                При сохранении кадра в архив подставляются эталоны EXIF модели (фронталка или основная
                камера) или пресет «как с телефона».
              </p>
            ) : null}
            <div className="studio-toggles">
            {studioMode !== 'photo_edit' &&
            !studioModeUsesTextOnlyPrompt(studioMode) &&
            studioMode !== 'model_scene' ? (
              <label
                className="studio-toggle-row"
                style={!studioFile ? { opacity: 0.55 } : undefined}
              >
                <span>Причёска с модели</span>
                <input
                  type="checkbox"
                  checked={studioLockModelHairstyle}
                  disabled={!studioFile}
                  onChange={(e) => setStudioLockModelHairstyle(e.target.checked)}
                />
              </label>
            ) : null}
            {studioMode === 'no_face' ? (
              <label
                className="studio-toggle-row"
                style={!studioFile ? { opacity: 0.55 } : undefined}
              >
                <span>Референс позы в WaveSpeed</span>
                <input
                  type="checkbox"
                  checked={studioSendPoseRefToWavespeed}
                  disabled={
                    !studioFile ||
                    studioPaintInpaintMask ||
                    studioInpaintMaskFile != null
                  }
                  onChange={(e) => setStudioSendPoseRefToWavespeed(e.target.checked)}
                />
              </label>
            ) : null}
            </div>
            <div className="studio-prompt-box studio-slot--wide">
              <div className="studio-slot__head">
                <span className="studio-slot__icon-wrap">
                  <svg className="studio-slot__icon-svg" width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden>
                    <path d="M4 6h16M4 12h10M4 18h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </span>
                <div className="studio-slot__titles">
                  <span className="studio-slot__label">Промпт</span>
                  <span className="studio-slot__hint">
                    {studioMode === 'model_scene'
                      ? 'Уточнения к сцене (опционально)'
                      : studioModeUsesTextOnlyPrompt(studioMode)
                        ? 'Поза, место, одежда, свет — подробно'
                        : 'Сцена, свет, настроение'}
                  </span>
                </div>
              </div>
              <textarea
                rows={4}
                placeholder={
                  studioMode === 'model_scene'
                    ? 'По желанию: уточнить одежду, настроение, детали…'
                    : studioModeUsesTextOnlyPrompt(studioMode)
                      ? 'Например: спальня, стоит у окна, красное платье, мягкий дневной свет…'
                      : 'Опишите кадр…'
                }
                value={studioDesc}
                onChange={(e) => setStudioDesc(e.target.value)}
              />
            </div>
            <div className="studio-generate-footer">
              {studioImageBtnBlockReason ? (
                <p className="studio-generate-block-hint" role="status">
                  {studioImageBtnBlockReason}
                </p>
              ) : null}
              <div className="studio-workspace__actions">
              <button
                type="button"
                className="studio-magic-btn"
                title={studioImageBtnBlockReason ?? undefined}
                disabled={studioBusy || studioImageBtnBlockReason != null}
                onClick={() => void refineStudioPrompt()}
              >
                {studioBusy
                  ? 'Генерация…'
                  : studioPromptOnlyDev
                    ? 'Собрать промпт'
                    : 'Сгенерировать'}
                {canStudioGenerate &&
                (studioPromptOnlyDev || integ?.wavespeed_configured) ? (
                  <span className="studio-magic-btn__cost">
                    <IconSpark className="studio-slot__icon-svg" />
                    {(studioInpaintMaskFile != null || studioPaintInpaintMask
                      ? health?.studio_inpaint_credit_cost
                      : health?.studio_prompt_credit_cost) ?? '—'}
                  </span>
                ) : null}
              </button>
              </div>
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
            {studioPendingExternalImageUrl ? (
              <div className="studio-pending-archive studio-upscale-row" style={{ marginTop: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <p className="muted" style={{ margin: 0, flex: '1 1 12rem' }}>
                  Картинка готова, но не попала в «Сохранённые». Можно сохранить в архив без повторной генерации.
                </p>
                <button
                  type="button"
                  className="ghost-btn"
                  disabled={studioImportArchiveBusy || !canStudioGenerate}
                  onClick={() => void retryImportStudioImageToArchive('studio_photo')}
                >
                  {studioImportArchiveBusy ? 'Сохраняем в архив…' : 'Сохранить в архив'}
                </button>
              </div>
            ) : null}
            {studioGenImageUrl ? (
              <div className="studio-result-panel studio-generated">
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
                        ? studioIntegrationsHint()
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
                        ? studioIntegrationsHint()
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
                        ? studioIntegrationsHint()
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
                <div className="studio-upscale-row">
                  <button
                    type="button"
                    className="ghost-btn studio-video-from-img-btn"
                    disabled={studioGenGenerationId == null || !canStudioGenerate}
                    title="Открыть вкладку «Видео» с этим кадром"
                    onClick={() => {
                      if (studioGenGenerationId == null) return
                      const g = findStudioArchiveItem(studioGenGenerationId)
                      setMotionFrameArchiveId(studioGenGenerationId)
                      if (g?.studio_model_id != null) setStudioSelectedModelId(g.studio_model_id)
                      setMotionFirstFrameFile(null)
                      setAppSection('studio_video')
                    }}
                  >
                    Видео из этого кадра
                  </button>
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
            </div>
            {canStudioGenerate ? (
              <StudioGenerationGallery
                title="История"
                lead={studioArchiveRetentionLead(health)}
                items={studioGenerations}
                loading={studioArchiveInitialLoading}
                hasMore={studioGenHasMore}
                loadingMore={studioGenLoadingMore}
                onLoadMore={() => void loadMoreStudioGenerations()}
                loadMoreLabel={`Ещё ${STUDIO_ARCHIVE_PAGE}`}
                onDelete={(g) =>
                  void deleteStudioGeneration(g.id, g.image_url || g.video_url || '')
                }
                onVideoFromImage={(g) => {
                  setMotionFrameArchiveId(g.id)
                  if (g.studio_model_id != null) setStudioSelectedModelId(g.studio_model_id)
                  setMotionFirstFrameFile(null)
                  setAppSection('studio_video')
                }}
              />
            ) : null}
          </div>
        </section>
      )}

      {hasAnyMainSection && appSection === 'studio_bootstrap' && canStudioAny && (
        <section
          className="studio-panel studio-workspace-page"
          aria-labelledby="studio-bootstrap-heading"
        >
          <div className="studio-workspace">
            <div className="studio-workspace__composer">
              <header className="studio-workspace__composer-head">
                <h2 id="studio-bootstrap-heading">База модели</h2>
                <p className="studio-workspace__tagline">
                  Развёртка 16:9 из своего фото или архива; опционально — слияние двух референсов.
                </p>
              </header>
              {!canStudioGenerate ? (
                <div className="banner info">Генерация недоступна по правам.</div>
              ) : studioPaywalled ? (
                <div className="banner info">
                  Оформите подписку в кабинете → «Тариф и баланс».
                </div>
              ) : (
                <StudioModelBootstrapPanel
                  canGenerate={canStudioGenerate}
                  studioPaywalled={studioPaywalled}
                  studioNeedsUserWsKey={studioNeedsUserWsKey}
                  isTrialing={(me?.subscription_status || '').toLowerCase() === 'trialing'}
                  canConnectIntegrations={isOwner && canIntegrations}
                  onOpenIntegrations={openWavespeedIntegrations}
                  aspectOptions={
                    studioAspectPresets.length > 0
                      ? studioAspectPresets.map((p) => ({
                          value: p.key,
                          label: p.key,
                          title: p.label,
                        }))
                      : [{ value: '9:16', label: '9:16', title: '9:16' }]
                  }
                  defaultAspect={studioOutputAspect}
                  archiveItems={studioGenerations}
                  onArchiveRefresh={() => {
                    void loadStudioGenerationsReset()
                    void loadStudioImagePickerArchive()
                  }}
                  onError={setError}
                />
              )}
            </div>
            {canStudioGenerate ? (
              <StudioGenerationGallery
                title="История"
                lead={studioArchiveRetentionLead(health)}
                items={studioGenerations}
                loading={studioArchiveInitialLoading}
                hasMore={studioGenHasMore}
                loadingMore={studioGenLoadingMore}
                onLoadMore={() => void loadMoreStudioGenerations()}
                loadMoreLabel={`Ещё ${STUDIO_ARCHIVE_PAGE}`}
                onDelete={(g) =>
                  void deleteStudioGeneration(g.id, g.image_url || g.video_url || '')
                }
                onVideoFromImage={(g) => {
                  setMotionFrameArchiveId(g.id)
                  if (g.studio_model_id != null) setStudioSelectedModelId(g.studio_model_id)
                  setMotionFirstFrameFile(null)
                  setAppSection('studio_video')
                }}
              />
            ) : null}
          </div>
        </section>
      )}

      {hasAnyMainSection && appSection === 'studio_video' && canStudioAny && (
          <section className="studio-panel studio-workspace-page studio-video-page" aria-labelledby="studio-motion-heading">
            <div className="studio-workspace">
            <div className="studio-workspace__composer">
              <header className="studio-workspace__composer-head">
                <h2 id="studio-motion-heading">Видео</h2>
                <p className="studio-workspace__tagline">
                  Реф-ролик, первый кадр и бриф — готовые ролики в истории справа.
                </p>
              </header>
              {!studioPaywalled && studioNeedsUserWsKey ? (
                <WavespeedSetupBanner
                  variant="video"
                  isTrialing={(me?.subscription_status || '').toLowerCase() === 'trialing'}
                  canConnect={isOwner && canIntegrations}
                  onOpenIntegrations={openWavespeedIntegrations}
                />
              ) : null}
            {!canStudioGenerate ? (
              <div className="banner info" role="status">
                Нет прав на генерацию. Обратитесь к владельцу аккаунта.
              </div>
            ) : studioPaywalled ? (
              <div className="banner info" role="status">
                Оформите подписку в кабинете → «Тариф и баланс».
              </div>
            ) : (
              <div className="studio-slot-grid studio-slot-grid--composer">
                <StudioPillField
                  label="Формат"
                  scrollRow
                  options={
                    studioAspectPresets.length > 0
                      ? studioAspectPresets.map((p) => ({
                          value: p.key,
                          label: p.key,
                          title: p.label,
                        }))
                      : [{ value: '9:16', label: '9:16', title: '9:16' }]
                  }
                  value={studioOutputAspect}
                  onChange={(v) => v != null && setStudioOutputAspect(String(v))}
                />
                <StudioPillField
                  label="Модель"
                  icon={<IconModel className="studio-slot__icon-svg" />}
                  options={studioModels.map((m) => ({ value: m.id, label: m.name }))}
                  value={studioSelectedModelId}
                  onChange={(v) => setStudioSelectedModelId(v)}
                  allowEmpty
                  emptyLabel="Выберите"
                />
                {health?.studio_grok_motion_configured === false ? (
                  <div className="banner warn">
                    Grok не настроен на сервере.
                  </div>
                ) : null}

                <div className="studio-video-step-card">
                  <h3>Кадр и движение</h3>
                  <div className="studio-slot-grid">
                    <StudioMediaSlot
                      label="Реф. видео"
                      hint="Движение · MP4"
                      icon="video"
                      busy={motionDrivingUploadBusy}
                      emptyLabel={motionVideoFile?.name || 'Загрузить'}
                      accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
                      onFile={(f) => {
                        setMotionVideoFile(f)
                        setMotionVideoFileId(null)
                        setMotionPreviewGenId(null)
                        setMotionPreviewUrl(null)
                        setMotionGrokTimeline(null)
                        setMotionResultVideoUrl(null)
                        if (f) void uploadMotionDrivingVideo(f)
                      }}
                      onClear={() => {
                        setMotionVideoFile(null)
                        setMotionVideoFileId(null)
                      }}
                    />
                    <StudioMediaSlot
                      label="Первый кадр"
                      hint="JPG, PNG"
                      icon="image"
                      previewUrl={studioMotionStillDisplayUrl}
                      accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                      onFile={(f) => {
                        setMotionFirstFrameFile(f)
                        setMotionPreviewGenId(null)
                        setMotionPreviewUrl(null)
                        setMotionFrameArchiveId(null)
                      }}
                      onClear={() => {
                        setMotionFirstFrameFile(null)
                        setMotionPreviewUrl(null)
                      }}
                    />
                  </div>
                  <StudioArchiveThumbPicker
                    label="Кадр из архива"
                    hint="Вместо загрузки файла"
                    items={studioImagePickerArchive}
                    value={motionFrameArchiveId}
                    onChange={(id, item) => {
                      setMotionFrameArchiveId(id)
                      if (id != null) {
                        setMotionFirstFrameFile(null)
                        if (item?.studio_model_id != null) {
                          setStudioSelectedModelId(item.studio_model_id)
                        }
                      }
                    }}
                  />
                  <StudioPillField
                    label="Стиль кадра"
                    options={[
                      { value: 'regular', label: 'Обычный' },
                      { value: 'nsfw', label: 'NSFW' },
                    ]}
                    value={motionFirstFrameWaveProfile}
                    onChange={(v) =>
                      v != null &&
                      setMotionFirstFrameWaveProfile(v as 'regular' | 'nsfw')
                    }
                  />
                  {studioSelectedModelId != null ? (
                    <div className="studio-mode-row" role="group" aria-label="Камера для EXIF при сохранении кадра">
                      <span className="studio-mode-label">EXIF</span>
                      <div className="studio-mode-segment">
                        <button
                          type="button"
                          className={`studio-mode-btn${studioExifCamera === 'selfie' ? ' is-active' : ''}`}
                          onClick={() => setStudioExifCamera('selfie')}
                        >
                          Фронталка
                        </button>
                        <button
                          type="button"
                          className={`studio-mode-btn${studioExifCamera === 'main' ? ' is-active' : ''}`}
                          onClick={() => setStudioExifCamera('main')}
                        >
                          Основная
                        </button>
                      </div>
                    </div>
                  ) : null}
                  <div className="studio-toggles">
                    <label className="studio-toggle-row">
                      <span>Timeline по ролику</span>
                      <input
                        type="checkbox"
                        checked={motionAutoPrompt}
                        onChange={(e) => setMotionAutoPrompt(e.target.checked)}
                      />
                    </label>
                    <label className="studio-toggle-row">
                      <span>Причёска модели</span>
                      <input
                        type="checkbox"
                        checked={motionLockHairstyle}
                        onChange={(e) => setMotionLockHairstyle(e.target.checked)}
                      />
                    </label>
                    <label className="studio-toggle-row">
                      <span>Кадр без WaveSpeed</span>
                      <input
                        type="checkbox"
                        checked={motionUseStillFinal}
                        onChange={(e) => setMotionUseStillFinal(e.target.checked)}
                      />
                    </label>
                  </div>
                  <textarea
                    className="studio-field-textarea"
                    rows={2}
                    placeholder="Уточнения к кадру (по желанию)"
                    value={motionFrameNotes}
                    onChange={(e) => setMotionFrameNotes(e.target.value)}
                  />
                  {motionStep1Preview ? (
                    <details className="studio-video-auto-block">
                      <summary>Grok: сцена и движение</summary>
                      <div className="studio-motion-auto-preview">{motionStep1Preview}</div>
                    </details>
                  ) : null}
                  <div className="studio-workspace__actions">
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={
                        motionBusyCompose ||
                        !motionCanComposePrompt ||
                        health?.studio_grok_scene_compose_configured === false
                      }
                      onClick={() => void runMotionComposeVideoPrompt()}
                    >
                      {motionBusyCompose ? 'Grok…' : 'Промпт по видео'}
                    </button>
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={
                        motionBusyFrame ||
                        !integ?.wavespeed_configured ||
                        studioSelectedModelId == null ||
                        (!motionVideoFile &&
                          !motionFirstFrameFile &&
                          motionFrameArchiveId == null)
                      }
                      onClick={() => void runMotionFirstFrame()}
                    >
                      {motionBusyFrame ? 'Кадр…' : 'Сгенерировать кадр'}
                    </button>
                  </div>
                </div>

                <div className="studio-video-step-card">
                  <h3>Seedance</h3>
                  <StudioArchiveThumbPicker
                    label="Наряд (опционально)"
                    hint="По умолчанию одежда с первого кадра (@Image1). Укажите другой снимок — только если нужен иной наряд"
                    items={studioImagePickerArchive}
                    value={motionOutfitArchiveId}
                    onChange={(id) => setMotionOutfitArchiveId(id)}
                  />
                  <div className="studio-prompt-box">
                    <div className="studio-slot__head">
                      <span className="studio-slot__icon-wrap">
                        <svg className="studio-slot__icon-svg" width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden>
                          <path d="M4 6h16M4 12h10M4 18h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                      </span>
                      <div className="studio-slot__titles">
                        <span className="studio-slot__label">Бриф</span>
                        <span className="studio-slot__hint">Сцена и движение</span>
                      </div>
                    </div>
                    <textarea
                      rows={4}
                      placeholder="Опишите ролик…"
                      value={motionDesc}
                      onChange={(e) => setMotionDesc(e.target.value)}
                    />
                  </div>
                  <StudioPillField
                    label="Длительность"
                    options={Array.from(
                      { length: Math.max(0, seedanceDurationMax - seedanceDurationMin + 1) },
                      (_, i) => {
                        const sec = seedanceDurationMin + i
                        const cost = computeMotionVideoCreditCost(
                          sec,
                          motionHasReferenceVideo,
                          motionVideoPricing,
                        )
                        const costSuffix = ` · ${cost} кр.`
                        return { value: sec, label: `${sec} с${costSuffix}` }
                      },
                    )}
                    value={motionSeedanceDuration}
                    onChange={(v) => v != null && setMotionSeedanceDuration(Number(v))}
                  />
                  <p className="muted studio-field-hint">
                    Стоимость:{' '}
                    {motionHasReferenceVideo
                      ? `$${motionVideoPricing.usd_per_sec_with_reference_video}/с`
                      : `$${motionVideoPricing.usd_per_sec_without_reference_video}/с`}{' '}
                    (≈{' '}
                    {computeMotionVideoCreditCost(1, motionHasReferenceVideo, motionVideoPricing)}{' '}
                    кр./с, курс {motionVideoPricing.rub_per_usd} ₽/$,{' '}
                    {motionVideoPricing.rub_per_credit} ₽/кредит). С реф-видео дороже.
                  </p>
                  <label className="studio-field-optional">
                    Негатив (по желанию)
                    <textarea
                      rows={2}
                      placeholder="Чего избегать"
                      value={motionVideoNegPrompt}
                      onChange={(e) => setMotionVideoNegPrompt(e.target.value)}
                    />
                  </label>
                  <div className="studio-toggles">
                    <label className="studio-toggle-row">
                      <span>Звук</span>
                      <input
                        type="checkbox"
                        checked={motionKeepSound}
                        onChange={(e) => setMotionKeepSound(e.target.checked)}
                      />
                    </label>
                  </div>
                  {motionAutoTextPreview ? (
                    <details className="studio-video-auto-block">
                      <summary>Промпт Seedance</summary>
                      <div className="studio-motion-auto-preview">{motionAutoTextPreview}</div>
                    </details>
                  ) : null}
                  {motionMsg ? (
                    <p className="muted studio-inline-msg">{motionMsg}</p>
                  ) : null}
                  <div className="studio-generate-footer">
                    {motionVideoBtnBlockReason ? (
                      <p className="studio-video-block-hint" role="status">
                        {motionVideoBtnBlockReason}
                      </p>
                    ) : null}
                    <div className="studio-workspace__actions">
                    <button
                      type="button"
                      className="studio-magic-btn"
                      disabled={motionBusyVideo || motionVideoBtnBlockReason != null}
                      title={motionVideoBtnBlockReason ?? undefined}
                      onClick={() => void runMotionRenderVideo()}
                    >
                      {motionBusyVideo ? 'Видео…' : 'Сгенерировать видео'}
                      <span
                        className="studio-magic-btn__cost"
                        key={`${motionSeedanceDuration}-${motionHasReferenceVideo ? 1 : 0}`}
                      >
                        <IconSpark className="studio-slot__icon-svg" />
                        {motionVideoCreditCost}
                      </span>
                    </button>
                    </div>
                  </div>
                  {motionResultVideoUrl ? (
                    <div className="studio-result-panel">
                      <video
                        src={motionResultVideoUrl}
                        controls
                        playsInline
                        className="studio-gen-img studio-video-player"
                      />
                      <div className="studio-workspace__actions">
                        <button
                          type="button"
                          className="ghost-btn"
                          disabled={motionVideoDownloadBusy}
                          onClick={() => void downloadMotionResultVideo(motionResultVideoUrl)}
                        >
                          {motionVideoDownloadBusy ? 'Сохранение…' : 'Скачать'}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            )}
            </div>
            {canStudioGenerate ? (
              <StudioGenerationGallery
                title="История"
                lead={studioArchiveRetentionLead(health, 'video')}
                items={studioVideoGalleryItems}
                loading={studioArchiveInitialLoading}
                hasMore={studioGenHasMore}
                loadingMore={studioGenLoadingMore}
                onLoadMore={() => void loadMoreStudioGenerations()}
                loadMoreLabel={`Ещё ${STUDIO_ARCHIVE_PAGE}`}
                emptyText="Здесь появятся ваши ролики после «Сделать видео»"
                onDelete={(g) => deleteStudioVideoArchiveItem(g)}
              />
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
                    {c.studio_model_id != null ? (
                      <span className="lang" title="Модель для операторов">
                        {studioModels.find((m) => m.id === c.studio_model_id)?.name ??
                          `модель #${c.studio_model_id}`}
                      </span>
                    ) : isOwner ? (
                      <span className="lang muted" title="Только владелец видит диалог без модели">
                        без модели
                      </span>
                    ) : null}
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
                  {isOwner && studioModels.length > 0 ? (
                    <div
                      className="outbound-lang-field"
                      title="Операторы с доступом к этой модели увидят диалог в списке чатов."
                    >
                      <label className="outbound-lang-label" htmlFor="conv-studio-model-select">
                        Модель (чат)
                      </label>
                      <select
                        id="conv-studio-model-select"
                        className="outbound-lang-select"
                        value={
                          selected.studio_model_id != null ? String(selected.studio_model_id) : ''
                        }
                        disabled={convModelBusy}
                        onChange={(e) =>
                          void saveConversationStudioModel(selected.id, e.target.value)
                        }
                      >
                        <option value="">Не назначена (только владелец)</option>
                        {studioModels.map((m) => (
                          <option key={m.id} value={String(m.id)}>
                            {m.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}
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
                      {displayMessages.map((m) => {
                        const hasMedia =
                          Boolean(m.localPreviewUrl) ||
                          Boolean(m.attachments && m.attachments.length > 0)
                        const hasText = Boolean(
                          (m.direction === 'inbound'
                            ? m.text_translated ?? m.text_original
                            : m.text_original
                          )?.trim(),
                        )
                        return (
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
                        {hasMedia ? (
                          <div className="bubble-media">
                            {m.localPreviewUrl ? (
                              <img
                                src={m.localPreviewUrl}
                                alt=""
                                className="bubble-media__img"
                              />
                            ) : null}
                            {(m.attachments ?? []).map((a) => (
                              <img
                                key={a.id}
                                src={a.url}
                                alt=""
                                className="bubble-media__img"
                                loading="lazy"
                              />
                            ))}
                          </div>
                        ) : null}
                        {hasText && m.direction === 'inbound' ? (
                          <>
                            <div className="ru">{m.text_translated ?? m.text_original}</div>
                            <div className="orig" title="Оригинал">
                              {m.text_original}
                            </div>
                          </>
                        ) : hasText ? (
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
                        ) : null}
                        <time>
                          {new Date(m.created_at).toLocaleString('ru-RU', {
                            day: '2-digit',
                            month: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </time>
                      </article>
                        )
                      })}
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
                    {(chatReplyFile || chatReplyArchiveId != null) && (
                      <div className="chat-composer-attach-preview">
                        {chatReplyFile && chatReplyFilePreview ? (
                          <img
                            src={chatReplyFilePreview}
                            alt=""
                            className="chat-composer-attach-preview__img"
                          />
                        ) : chatReplyArchiveId != null ? (
                          (() => {
                            const g = findStudioArchiveItem(chatReplyArchiveId)
                            const src = g
                              ? studioArchiveThumbUrl(g) || g.image_url
                              : null
                            return src ? (
                              <img src={src} alt="" className="chat-composer-attach-preview__img" />
                            ) : (
                              <span className="muted">Архив #{chatReplyArchiveId}</span>
                            )
                          })()
                        ) : null}
                        <button
                          type="button"
                          className="chat-composer-attach-preview__clear"
                          onClick={clearChatReplyAttachment}
                          title="Убрать вложение"
                        >
                          ×
                        </button>
                      </div>
                    )}
                    {chatArchivePickerOpen ? (
                      <div className="chat-composer-archive">
                        <StudioArchiveThumbPicker
                          label="Из архива студии"
                          hint="Готовое изображение уйдёт в чат"
                          items={studioImagePickerArchive}
                          value={chatReplyArchiveId}
                          onChange={(id) => {
                            setChatReplyArchiveId(id)
                            if (id != null) setChatReplyFile(null)
                            if (chatReplyFileInputRef.current) {
                              chatReplyFileInputRef.current.value = ''
                            }
                          }}
                        />
                      </div>
                    ) : null}
                    <div className="composer-toolbar">
                      <input
                        ref={chatReplyFileInputRef}
                        type="file"
                        accept="image/jpeg,image/png,image/webp,image/gif"
                        className="chat-composer-file-input"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          if (!f) return
                          setChatReplyFile(f)
                          setChatReplyArchiveId(null)
                        }}
                      />
                      <button
                        type="button"
                        className="icon-btn"
                        title="Фото с устройства"
                        onClick={() => chatReplyFileInputRef.current?.click()}
                      >
                        <span aria-hidden>📎</span>
                      </button>
                      <button
                        type="button"
                        className="icon-btn"
                        title="Из архива студии"
                        aria-expanded={chatArchivePickerOpen}
                        onClick={() => {
                          setChatArchivePickerOpen((o) => {
                            const next = !o
                            if (next) void loadStudioImagePickerArchive()
                            return next
                          })
                        }}
                      >
                        <span aria-hidden>🖼</span>
                      </button>
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
                        disabled={!draft.trim() && !chatReplyHasAttachment}
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
        </AppShell>
      ) : null}
    </div>
  )
}
