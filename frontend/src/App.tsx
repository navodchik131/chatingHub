import EmojiPicker, { type EmojiClickData, Theme } from 'emoji-picker-react'
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation, Trans } from 'react-i18next'
import { apiFetch, getToken, setToken } from './api'
import {
  getPushSubscriptionState,
  subscribeWebPush,
  unsubscribeWebPush,
  webPushEnvironmentOk,
} from './webPush'
import { billingReturnCopy } from './billingReturnCopy'
import { openPaymentUrl } from './billing/openPaymentUrl'
import { creditUnitFromHealth } from './billing/credits'
import { subscriptionCostCredits } from './billing/referral'
import { formatClientFetchError, formatHttpApiError } from './apiErrors'
import { postStudioJobAndWait, postStudioJobStart } from './studioJobs'
import {
  computeMotionVideoCreditCost,
  mergeMotionVideoPricing,
  motionVideoUsdPerSec,
  type SeedanceT2vResolution,
  type SeedanceT2vVariant,
} from './studioMotionPricing'
import {
  createOptimisticStudioArchiveItem,
  fetchStudioArchivePage,
  fetchStudioArchivePending,
  isMotionRenderArchiveId,
  isOptimisticStudioArchiveId,
  mergeStudioArchiveItems,
  mergeVideoArchiveWithMotionRenders,
  prependOptimisticStudioArchive,
  removeOptimisticStudioArchive,
  replaceOptimisticStudioArchiveId,
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
import { OwnerEmailCompleteForm, TelegramLoginButton } from './auth/TelegramAuth'
import { AppShell, type WorkspaceSection } from './components/AppShell'
import { AppLanguageSwitcher } from './i18n/AppLanguageSwitcher'
import { formatAppNumber } from './i18n'
import {
  conversationNoteKindLabel,
  formatSlaSeconds,
  outboundLangOptions,
  studioArchiveRetentionLead,
} from './i18n/appLabels'
import { formatAppCurrency, formatDateTimeApp, formatNoteUpdatedAtApp } from './i18n/appFormat'
import {
  companionModeLabel,
  creditKindLabel,
  memberPermissionLabel,
  subscriptionStatusLabel,
} from './i18n/cabinetLabels'
import { WorkspaceOverview } from './components/WorkspaceOverview'
import { CreatorDonationsPanel } from './components/CreatorDonationsPanel'
import { CreatorDonationAlertBanner } from './components/CreatorDonationAlertBanner'
import {
  type CreatorDonationOverview,
  type CreatorDonationOverviewEvent,
  formatDonationOverviewHint,
  formatDonationTotalsLabel,
  readDonationLastSeenEventId,
  writeDonationLastSeenEventId,
} from './utils/creatorDonationOverview'
import { ConversationPlatformTabs } from './components/ConversationPlatformTabs'
import { ConversationCategoryTabs } from './components/ConversationCategoryTabs'
import {
  conversationCategoryBadgeLabel,
  conversationCategoryLabel,
  manualCategoryLabel,
} from './i18n/chatLabels'
import {
  STUDIO_IMAGE_MODE_IDS,
  STUDIO_MODEL_IMAGE_KIND_VALUES,
  studioImageModeLabel,
  studioModelImageKindLabel,
  type StudioModelImageKind,
} from './i18n/studioLabels'
import {
  type ConversationCategory,
  MANUAL_CATEGORY_VALUES,
  matchesConversationCategory,
  sortConversationsForInbox,
} from './conversationCategories'
import {
  chatPlatformLabel,
  type ChatPlatform,
  visibleChatPlatforms,
} from './chatPlatforms'
import {
  SetupTour,
  dismissSetupTour,
  markSetupTourHadGeneration,
  readSetupTourDismissed,
  readSetupTourHadGeneration,
  resolveSetupTourPhase,
} from './components/SetupTour'
import { studioImageGenerateBlockReason, studioDemoModelHint, studioIntegrationsHint } from './studio/studioGenerateGate'
import {
  buildAndStartFaceSwapScenario,
  buildAndStartPhotoEditScenario,
  buildAndStartPoRefuScenario,
  buildAndStartPromptOnlyScenario,
} from './studio/runStudioScenario'
import type { StudioScenarioGenOptions } from './studio/studioScenarioPresets'
import {
  aspectsForModel,
  defaultUiModelForNsfw,
  fetchGenerationModelOptions,
  modelsForNsfwMode,
  normalizeWaveModelSelection,
  pickValidAspect,
  pickValidModelId,
  type GenerationModelDefinition,
} from './workflow/wavespeedModels'
import {
  WavespeedSetupBanner,
  needsUserWavespeedKey,
} from './components/WavespeedSetupBanner'
import { FirstGenWizard } from './components/onboarding/FirstGenWizard'
import {
  clearFirstGenWizardPending,
  hasFirstGenWizardPending,
  markFirstGenWizardDoneForUser,
  markFirstGenWizardPending,
  readFirstGenWizardDoneForUser,
  trackFunnelEvent,
} from './analytics/funnel'
import './App.css'
import './styles/chat-ui.css'
import { StudioInpaintMaskPainter, type StudioInpaintMaskPainterRef } from './StudioInpaintMaskPainter'
import {
  DEFAULT_MEMBER_PERMISSIONS,
  MEMBER_PERMISSION_ITEMS,
  PERM_CHAT,
  PERM_INTEGRATIONS,
  PERM_STUDIO_GENERATE,
  PERM_STUDIO_MODELS,
  hasAllBits,
  togglePermission,
} from './workspacePermissions'
import { WAVESPEED_REF_URL } from './billing/planCatalog'
import {
  canPurchaseCredits,
  chatAllowedForPlan,
  normalizeBillingPlan,
  planDisplayLong,
  planDisplayShort,
  studioAccessAllowed,
} from './billing/planLabels'
import {
  formatStudioImageCostLabel,
  quoteStudioImageCredits,
  studioGenerationUsesDemo,
} from './studioImagePricing'

type Platform = ChatPlatform

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
  /** Не переводить входящие/исходящие — только оригинальный текст. */
  auto_translate_disabled?: boolean
  /** NULL = с подключения; off/draft/semi_auto/auto — переопределение в диалоге. */
  companion_mode_override?: string | null
  /** Фактический режим с учётом подключения. */
  effective_companion_mode?: string | null
  manual_category?: 'vip' | 'bomzh' | null
  is_blocked?: boolean
  peer_unavailable?: boolean
  is_hidden?: boolean
  assigned_user_id?: number | null
  assigned_member_login?: string | null
  is_no_response?: boolean
  is_new?: boolean
  updated_at: string
  last_message_preview: string | null
  unread_count?: number
  has_avatar?: boolean
}

interface ConversationNote {
  id: number
  kind: 'manual' | 'ai_profile' | 'ai_daily' | 'ai_insight'
  content: string
  is_pinned: boolean
  author_user_id: number | null
  author_label: string
  created_at: string
  updated_at: string
}

const CHAT_REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🔥'] as const

interface MessageReaction {
  emoji: string
  actor: 'owner' | 'peer'
}

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
  reply_to_message_id?: number | null
  reply_preview?: string | null
  reactions?: MessageReaction[]
  companion_bot?: boolean
  bot_response_event_id?: number | null
  operator_rating?: number | null
  platform_sync_ok?: boolean | null
}

interface CompanionDraft {
  id: number
  conversation_id: number
  trigger_message_id: number
  draft_text: string
  target_lang: string | null
  created_at: string
}

const COMPANION_MODE_VALUES = ['off', 'draft', 'semi_auto', 'auto'] as const
const COMPANION_CONVERSATION_MODE_VALUES = ['', 'off', 'draft', 'semi_auto', 'auto'] as const

function resolveEffectiveCompanionMode(conv: Conversation): string | null {
  if (conv.effective_companion_mode) return conv.effective_companion_mode
  const override = (conv.companion_mode_override ?? '').trim()
  return override || null
}

function isCompanionManualDraftMode(mode: string | null | undefined): boolean {
  return mode === 'draft'
}

interface CompanionFeedbackReport {
  id: number
  report_date: string
  content: string
  stats: Record<string, number>
  created_at: string
  updated_at: string
}

/** Размер страницы GET /conversations/:id/messages (синхронно с бэкендом default limit). */
const CHAT_MESSAGES_PAGE = 40

/** Instagram Direct: скрыть админ-инструкции и отключить OAuth до релиза интеграции. */
const INSTAGRAM_INTEGRATION_IN_DEVELOPMENT = true

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
  return chatPlatformLabel(p)
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
  const { t: tc } = useTranslation('chat')
  const url = useConversationAvatarBlob(conv.id, Boolean(conv.has_avatar))
  const letter = (conv.user_display_name ?? '?').slice(0, 1).toUpperCase()
  const unread = conv.unread_count ?? 0
  return (
    <button
      type="button"
      className={`chat-strip-item ${active ? 'is-active' : ''}`}
      onClick={onSelect}
      title={conv.user_display_name ?? tc('strip.dialogFallback')}
      aria-label={conv.user_display_name ?? tc('strip.dialogFallback')}
      aria-current={active ? 'true' : undefined}
    >
      <span className="chat-strip-item-inner">
        {url ? <img src={url} alt="" /> : <span className="chat-strip-letter">{letter}</span>}
        {unread > 0 && !active ? (
          <span className="chat-strip-unread" aria-label={tc('strip.unreadAria')} />
        ) : null}
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
  telegram_login_configured?: boolean
  telegram_login_bot_username?: string | null
  tribute_billing_configured?: boolean
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
  studio_seedance_t2v_default_resolution?: string
  studio_seedance_t2v_resolutions?: string[]
  studio_seedance_t2v_variants?: string[]
  studio_grok_motion_timeline_enabled?: boolean
  studio_grok_motion_configured?: boolean
  studio_grok_scene_compose_configured?: boolean
  studio_seedance_i2v_duration_default?: number
  studio_seedance_i2v_duration_min?: number
  studio_seedance_i2v_duration_max?: number
  web_push_configured?: boolean
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
  demo_generations_remaining?: number
  demo_generations_grant?: number
  workflow_demo_limited?: boolean
  chat_allowed?: boolean
  telegram_linked?: boolean
  telegram_username?: string | null
  email_setup_required?: boolean
  public_email?: string | null
  telegram_login_available?: boolean
  tribute_billing_available?: boolean
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
  tribute_share_percent: number
}

interface PlatformConnection {
  id: number
  platform: 'telegram' | 'fanvue' | 'instagram' | 'tribute'
  label: string | null
  studio_model_id: number | null
  bot_username?: string | null
  webhook_registered?: boolean
  creator_uuid?: string | null
  instagram_user_id?: string | null
  instagram_username?: string | null
  oauth_connected?: boolean
  webhook_url?: string | null
  is_active?: boolean
  companion_mode?: string
  companion_delay_min_sec?: number
  companion_delay_max_sec?: number
  companion_max_replies_per_hour?: number
}

interface IntegrationStatus {
  telegram_configured: boolean
  telegram_bot_username: string | null
  fanvue_configured: boolean
  fanvue_creator_uuid: string | null
  fanvue_webhook_url: string | null
  fanvue_oauth_available?: boolean
  fanvue_oauth_connected?: boolean
  instagram_configured?: boolean
  instagram_oauth_available?: boolean
  instagram_webhook_url?: string | null
  telegram_webhook_url: string | null
  telegram_webhook_registered?: boolean
  integration_hint?: string | null
  wavespeed_configured?: boolean
  wavespeed_managed_by_platform?: boolean
  llm_configured?: boolean
  telegram_connections?: PlatformConnection[]
  fanvue_connections?: PlatformConnection[]
  instagram_connections?: PlatformConnection[]
  tribute_configured?: boolean
  tribute_connections?: PlatformConnection[]
  max_connections_per_platform?: number
}

interface TributeEarningsSummary {
  from_date: string
  to_date: string
  is_owner: boolean
  chatter_share_percent: number
  gross_minor: number
  display_minor: number
  currency: string
  by_currency: Record<string, number>
  event_count: number
}

interface ChatterStatsRow {
  user_id: number
  member_login: string
  is_active: boolean
  outbound_messages: number
  conversations_replied: number
  companion_ratings_positive: number
  companion_ratings_negative: number
  median_reply_seconds?: number | null
  avg_first_response_seconds?: number | null
  tribute_display_minor: number
  tribute_gross_minor: number
  tribute_currency: string
  tribute_share_percent: number
  tribute_event_count: number
}

interface ChatterStatsSummary {
  from_date: string
  to_date: string
  is_owner: boolean
  self: ChatterStatsRow
  members: ChatterStatsRow[] | null
}

interface CompanionHealth {
  active: boolean
  effective_mode: string | null
  status: string
  reasons: string[]
  pending_jobs: number
  pending_drafts: number
  relationship_score: number | null
  mood: string | null
}

interface ChatterSnippet {
  id: number
  title: string
  body: string
  lang: string | null
  sort_order: number
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

type StudioExifCamera = 'selfie' | 'main'

interface NewModelPhotoRow {
  file: File
  kind: StudioModelImageKind
}

const STUDIO_MODEL_MAX_IMAGES = 8

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

interface CompanionPersona {
  age?: string | null
  city?: string | null
  country?: string | null
  timezone?: string | null
  personality?: string | null
  hobbies?: string | null
  interests?: string | null
  lifestyle?: string | null
  speaking_style?: string | null
  backstory?: string | null
}

interface UserStudioModel {
  id: number
  name: string
  profile_text: string
  companion_persona?: CompanionPersona
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
  companion_persona: CompanionPersona
  camera_preset_id: string
  export_lat: string
  export_lon: string
}

function companionPersonaFromModel(m: UserStudioModel): CompanionPersona {
  const p = m.companion_persona ?? {}
  return {
    age: p.age ?? '',
    city: p.city ?? '',
    country: p.country ?? '',
    timezone: p.timezone ?? '',
    personality: p.personality ?? '',
    hobbies: p.hobbies ?? '',
    interests: p.interests ?? '',
    lifestyle: p.lifestyle ?? '',
    speaking_style: p.speaking_style ?? '',
    backstory: p.backstory ?? '',
  }
}

function companionPersonaToApi(p: CompanionPersona): CompanionPersona {
  const trim = (v?: string | null) => (v ?? '').trim()
  const out: CompanionPersona = {
    age: trim(p.age) || null,
    city: trim(p.city) || null,
    country: trim(p.country) || null,
    timezone: trim(p.timezone) || null,
    personality: trim(p.personality) || null,
    hobbies: trim(p.hobbies) || null,
    interests: trim(p.interests) || null,
    lifestyle: trim(p.lifestyle) || null,
    speaking_style: trim(p.speaking_style) || null,
    backstory: trim(p.backstory) || null,
  }
  const hasAny = Object.values(out).some((v) => v != null && v !== '')
  return hasAny ? out : {}
}

function defaultStudioModelCabinetDraft(m: UserStudioModel): StudioModelCabinetDraft {
  return {
    name: m.name,
    profile_text: m.profile_text,
    companion_persona: companionPersonaFromModel(m),
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

type AccountCabinetTab = 'overview' | 'billing' | 'donations' | 'integrations' | 'models' | 'team'

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

interface StudioReferenceAnalysisResponse {
  analysis: Record<string, unknown>
  summary_ru: string
  effective_studio_mode: string
  visibility: {
    include_face?: boolean
    include_hair?: boolean
    crop_locked_no_face?: boolean
    allowed_image_kinds?: string[]
  }
}

const STUDIO_REFERENCE_ANALYSIS_MODES: StudioJobMode[] = ['model', 'no_face']

export default function App() {
  const { t } = useTranslation('workspace')
  const { t: tAuth } = useTranslation('auth')
  const { t: ts } = useTranslation('studio')
  const { t: tc } = useTranslation('chat')
  const { t: tCommon } = useTranslation('common')
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
  const [chatPlatformTab, setChatPlatformTab] = useState<ChatPlatform>('telegram')
  const [chatCategoryTab, setChatCategoryTab] = useState<ConversationCategory>('all')
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
  const [autoTranslateBusy, setAutoTranslateBusy] = useState(false)
  const [replyToMessage, setReplyToMessage] = useState<ChatMessage | null>(null)
  const [reactionBusyKey, setReactionBusyKey] = useState<string | null>(null)
  const [convNotesOpen, setConvNotesOpen] = useState(false)
  const [convNotes, setConvNotes] = useState<ConversationNote[]>([])
  const [convNotesLoading, setConvNotesLoading] = useState(false)
  const [convNoteDraft, setConvNoteDraft] = useState('')
  const [convNoteComposeOpen, setConvNoteComposeOpen] = useState(false)
  const convNoteDraftRef = useRef<HTMLTextAreaElement>(null)
  const [convNotesBusy, setConvNotesBusy] = useState(false)
  const [convNotesAnalyzeBusy, setConvNotesAnalyzeBusy] = useState(false)
  const [threadSettingsOpen, setThreadSettingsOpen] = useState(false)
  const [companionDrafts, setCompanionDrafts] = useState<CompanionDraft[]>([])
  const [companionDraftBusy, setCompanionDraftBusy] = useState<number | null>(null)
  const [companionRatingBusy, setCompanionRatingBusy] = useState<number | null>(null)
  const [companionRatingSavedId, setCompanionRatingSavedId] = useState<number | null>(null)
  const [companionModeBusy, setCompanionModeBusy] = useState(false)
  const [companionHealth, setCompanionHealth] = useState<CompanionHealth | null>(null)
  const [assigneeBusy, setAssigneeBusy] = useState(false)
  const [chatterSnippets, setChatterSnippets] = useState<ChatterSnippet[]>([])
  const [newSnippetTitle, setNewSnippetTitle] = useState('')
  const [newSnippetBody, setNewSnippetBody] = useState('')
  const [snippetBusy, setSnippetBusy] = useState(false)
  const [convCategoryBusy, setConvCategoryBusy] = useState(false)
  const [convBlockedBusy, setConvBlockedBusy] = useState(false)
  const [convHideBusy, setConvHideBusy] = useState(false)
  const [companionFeedbackReports, setCompanionFeedbackReports] = useState<
    CompanionFeedbackReport[]
  >([])
  const [companionFeedbackLoading, setCompanionFeedbackLoading] = useState(false)

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
    const chatPerm = owner || hasAllBits(m, PERM_CHAT)
    const gen = owner || hasAllBits(m, PERM_STUDIO_GENERATE)
    const models = owner || hasAllBits(m, PERM_STUDIO_MODELS)
    const integ = owner || hasAllBits(m, PERM_INTEGRATIONS)
    const studioAny = owner || !!(m & (PERM_STUDIO_GENERATE | PERM_STUDIO_MODELS))
    return {
      isOwner: owner,
      canChat: chatPerm && chatAllowedForPlan(me),
      canStudioGenerate: gen,
      canStudioModels: models,
      canIntegrations: integ,
      canStudioAny: studioAny,
      hasAnyMainSection: chatPerm && chatAllowedForPlan(me) || studioAny,
    }
  }, [me])

  const unreadTotal = useMemo(
    () => conversations.reduce((sum, c) => sum + (c.unread_count ?? 0), 0),
    [conversations],
  )

  const studioPaywalled = useMemo(() => {
    if (!me) return false
    const gate =
      me.billing_require_active_subscription ?? health?.billing_require_active_subscription ?? true
    if (!gate) return false
    return !studioAccessAllowed(me)
  }, [me, health])

  const cabinetAccountMeta = useMemo(() => {
    if (!me) return { emailLine: '', roleLine: '', initial: '?' }
    const owner = me.is_workspace_owner
    const emailLine = owner
      ? me.email
      : `${me.owner_email}${me.member_login ? ` · ${me.member_login}` : ''}`
    const roleLine = owner
      ? t('cabinet.roleOwner')
      : me.member_login
        ? t('cabinet.roleOperatorLogin', { login: me.member_login })
        : t('cabinet.roleOperator')
    const seed = (owner ? me.email : me.member_login || me.email) || '?'
    return { emailLine, roleLine, initial: seed.charAt(0).toUpperCase() }
  }, [me, t])

  const canPlatformAdmin = Boolean(me?.is_platform_admin)

  const [accountOpen, setAccountOpen] = useState(false)
  const [firstGenWizardOpen, setFirstGenWizardOpen] = useState(false)
  const [accountTab, setAccountTab] = useState<AccountCabinetTab>('overview')
  const [workspaceMembers, setWorkspaceMembers] = useState<WorkspaceMemberRow[]>([])
  const [teamBusy, setTeamBusy] = useState(false)
  const [newTeamLogin, setNewTeamLogin] = useState('')
  const [newTeamPassword, setNewTeamPassword] = useState('')
  const [newTeamMask, setNewTeamMask] = useState(DEFAULT_MEMBER_PERMISSIONS)
  const [newTeamModelIds, setNewTeamModelIds] = useState<number[]>([])
  const [newTeamTributeShare, setNewTeamTributeShare] = useState('20')
  const [memberEditPassword, setMemberEditPassword] = useState<Record<number, string>>({})
  const [memberMaskEdits, setMemberMaskEdits] = useState<Record<number, number>>({})
  const [memberModelEdits, setMemberModelEdits] = useState<Record<number, number[]>>({})
  const [memberTributeEdits, setMemberTributeEdits] = useState<Record<number, string>>({})
  const [integ, setInteg] = useState<IntegrationStatus | null>(null)
  const studioNeedsUserWsKey = useMemo(() => needsUserWavespeedKey(integ), [integ])

  const chatVisiblePlatforms = useMemo(
    () => visibleChatPlatforms(conversations, integ),
    [conversations, integ],
  )

  const platformFilteredConversations = useMemo(
    () => conversations.filter((c) => c.platform === chatPlatformTab),
    [conversations, chatPlatformTab],
  )

  const filteredConversations = useMemo(
    () =>
      sortConversationsForInbox(
        platformFilteredConversations.filter((c) =>
          matchesConversationCategory(c, chatCategoryTab),
        ),
      ),
    [platformFilteredConversations, chatCategoryTab],
  )
  const [modelDrafts, setModelDrafts] = useState<Record<number, StudioModelCabinetDraft>>({})
  const [studioCameraPresets, setStudioCameraPresets] = useState<StudioCameraPreset[]>([])
  const [modelSavingId, setModelSavingId] = useState<number | null>(null)
  const [tgToken, setTgToken] = useState('')
  const [tgDraftLabel, setTgDraftLabel] = useState('')
  const [tgDraftModelId, setTgDraftModelId] = useState<number | ''>('')
  const [tgEditConnectionId, setTgEditConnectionId] = useState<number | null>(null)
  const [fvDraftModelId, setFvDraftModelId] = useState<number | ''>('')
  const [fvBusy, setFvBusy] = useState(false)
  const [fvSyncNote, setFvSyncNote] = useState<string | null>(null)
  const [igDraftModelId, setIgDraftModelId] = useState<number | ''>('')
  const [igBusy, setIgBusy] = useState(false)
  const [tributeApiKey, setTributeApiKey] = useState('')
  const [tributeDraftLabel, setTributeDraftLabel] = useState('')
  const [tributeDraftModelId, setTributeDraftModelId] = useState<number | ''>('')
  const [tributeEditConnectionId, setTributeEditConnectionId] = useState<number | null>(null)
  const [tributeEarnings, setTributeEarnings] = useState<TributeEarningsSummary | null>(null)
  const [creatorDonationOverview, setCreatorDonationOverview] = useState<CreatorDonationOverview | null>(null)
  const [creatorDonationAlert, setCreatorDonationAlert] = useState<CreatorDonationOverviewEvent | null>(null)
  const [chatterStats, setChatterStats] = useState<ChatterStatsSummary | null>(null)

  const tributeEarningsDisplay = useMemo(() => {
    if (!tributeEarnings) {
      if (integ?.tribute_configured) {
        return {
          label: '—',
          hint: t('tribute.donationsHint'),
        }
      }
      return { label: null as string | null, hint: null as string | null }
    }
    const cur = tributeEarnings.currency || 'USD'
    const label = formatAppCurrency(tributeEarnings.display_minor, cur)
    const from = tributeEarnings.from_date
    const to = tributeEarnings.to_date
    const period = from === to ? from : `${from} — ${to}`
    if (tributeEarnings.event_count === 0) {
      return {
        label,
        hint: t('tribute.noEvents', { period }),
      }
    }
    const hint = tributeEarnings.is_owner
      ? t('tribute.ownerHint', { period, eventsPart: tributeEarnings.event_count ? t('tribute.ownerEvents', { count: tributeEarnings.event_count }) : '' })
      : t('tribute.chatterHint', { percent: tributeEarnings.chatter_share_percent, period })
    return { label, hint }
  }, [tributeEarnings, integ?.tribute_configured, t])

  const platformDonationsDisplay = useMemo(() => {
    if (!creatorDonationOverview) {
      return {
        visible: false,
        label: null as string | null,
        hint: null as string | null,
        recent: [] as CreatorDonationOverview['recent_events'],
      }
    }
    const ov = creatorDonationOverview
    const visible =
      ov.has_donation_setup || ov.donations_count > 0 || ov.active_links > 0
    const label = formatDonationTotalsLabel(ov.totals_by_currency)
    const hint = formatDonationOverviewHint(ov, t)
    return {
      visible,
      label,
      hint,
      recent: ov.recent_events.slice(0, 5),
    }
  }, [creatorDonationOverview, t])

  const chatterStatsDisplay = useMemo(() => {
    if (!chatterStats) {
      return {
        outbound: null as number | null,
        conversations: null as number | null,
        ratingsHint: null as string | null,
        period: null as string | null,
      }
    }
    const from = chatterStats.from_date
    const to = chatterStats.to_date
    const period = from === to ? from : `${from} — ${to}`
    let outbound = chatterStats.self.outbound_messages
    let conversations = chatterStats.self.conversations_replied
    let pos = chatterStats.self.companion_ratings_positive
    let neg = chatterStats.self.companion_ratings_negative
    if (chatterStats.is_owner && chatterStats.members && chatterStats.members.length > 0) {
      outbound = chatterStats.members.reduce((s, m) => s + m.outbound_messages, 0)
      conversations = chatterStats.members.reduce((s, m) => s + m.conversations_replied, 0)
      pos = chatterStats.members.reduce((s, m) => s + m.companion_ratings_positive, 0)
      neg = chatterStats.members.reduce((s, m) => s + m.companion_ratings_negative, 0)
    }
    const ratingsHint =
      pos + neg > 0 ? `${pos} / ${neg}` : null
    return { outbound, conversations, ratingsHint, period }
  }, [chatterStats])

  const [appSection, setAppSection] = useState<WorkspaceSection>('overview')
  const [studioDesc, setStudioDesc] = useState('')
  const [studioFile, setStudioFile] = useState<File | null>(null)
  /** Face swap без модели из кабинета — фото identity (как в workflow «Смена модели»). */
  const [studioIdentityFile, setStudioIdentityFile] = useState<File | null>(null)
  /** Маска (белое = зона замены): Multi-URL в Nano/WAN при STUDIO_REGIONAL_MASKED_EDIT=true или Z-Inpaint если false. */
  const [studioInpaintMaskFile, setStudioInpaintMaskFile] = useState<File | null>(null)
  /** Режим маски: рисуем белым по превью референса. */
  const [studioPaintInpaintMask, setStudioPaintInpaintMask] = useState(false)
  const [studioMaskBrushPreset, setStudioMaskBrushPreset] = useState<'s' | 'm' | 'l'>('m')
  const [studioReferenceObjectUrl, setStudioReferenceObjectUrl] = useState<string | null>(null)
  const [studioIdentityObjectUrl, setStudioIdentityObjectUrl] = useState<string | null>(null)
  const [studioReferenceAnalysis, setStudioReferenceAnalysis] =
    useState<StudioReferenceAnalysisResponse | null>(null)
  const [studioReferenceAnalyzing, setStudioReferenceAnalyzing] = useState(false)
  const studioMaskPainterRef = useRef<StudioInpaintMaskPainterRef | null>(null)
  /** Снимок из архива как база для режима «Доработать фото» (альтернатива файлу). */
  const [studioPhotoEditArchiveId, setStudioPhotoEditArchiveId] = useState<number | null>(null)
  /** true = MODEL_LOCK (причёска с профиля); false = POSE_REFERENCE (с загруженного кадра). Только если есть studioFile. */
  const [studioLockModelHairstyle, setStudioLockModelHairstyle] = useState(true)
  const [studioSendPoseRefToWavespeed, setStudioSendPoseRefToWavespeed] = useState(true)
  const [studioMode, setStudioMode] = useState<StudioJobMode>('model_scene')
  const [studioWanEditTier, setStudioWanEditTier] = useState<'standard' | 'pro'>('standard')
  const [studioWaveProfile, setStudioWaveProfile] = useState<'regular' | 'nsfw'>('nsfw')
  const [studioWaveModelId, setStudioWaveModelId] = useState<string>(() =>
    defaultUiModelForNsfw(true),
  )
  const [studioGenModels, setStudioGenModels] = useState<GenerationModelDefinition[]>([])

  const studioAvailableGenModels = useMemo(
    () => modelsForNsfwMode(studioGenModels, studioWaveProfile === 'nsfw'),
    [studioGenModels, studioWaveProfile],
  )

  const studioEffectiveWanTier = useMemo((): 'standard' | 'pro' => {
    if (studioWaveModelId === 'wan-2.7-pro') return 'pro'
    if (studioWaveModelId === 'wan-2.7') return studioWanEditTier
    return 'standard'
  }, [studioWaveModelId, studioWanEditTier])

  const studioImageCreditQuote = useMemo(() => {
    const plan = normalizeBillingPlan(me?.billing_plan)
    if (plan === 'pro') {
      return { label: 'Pro', useDemo: false }
    }
    const credits = quoteStudioImageCredits({
      waveProfile: studioWaveProfile,
      waveModelId: studioWaveModelId,
      wanEditTier: studioEffectiveWanTier,
      studioMode,
      workflow: true,
    })
    const useDemo = studioGenerationUsesDemo({
      billingPlan: me?.billing_plan,
      demoRemaining: me?.demo_generations_remaining ?? 0,
      creditsBalance: me?.credits_balance ?? 0,
      waveProfile: studioWaveProfile,
      waveModelId: studioWaveModelId,
      wanEditTier: studioEffectiveWanTier,
      studioMode,
      workflow: true,
    })
    return {
      credits,
      label: formatStudioImageCostLabel(credits, {
        demoRemaining: me?.demo_generations_remaining ?? 0,
        useDemo,
      }),
      useDemo,
    }
  }, [
    me?.billing_plan,
    me?.credits_balance,
    me?.demo_generations_remaining,
    studioMode,
    studioWaveProfile,
    studioWaveModelId,
    studioEffectiveWanTier,
    studioWanEditTier,
  ])

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
  const [billingPayMode, setBillingPayMode] = useState<'standard' | 'pro'>('pro')
  const [billingPayPeriod, setBillingPayPeriod] = useState<'month' | 'year'>('month')
  const [referralInfo, setReferralInfo] = useState<ReferralMe | null>(null)
  const [creditsPurchaseQty, setCreditsPurchaseQty] = useState(50)
  const [yookassaPayBusy, setYookassaPayBusy] = useState<string | null>(null)
  const [tributePayBusy, setTributePayBusy] = useState<string | null>(null)
  const anyBillingPayBusy = yookassaPayBusy !== null || tributePayBusy !== null
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
  const [motionSeedanceVariant, setMotionSeedanceVariant] = useState<SeedanceT2vVariant>('standard')
  const [motionVideoResolution, setMotionVideoResolution] = useState<SeedanceT2vResolution>('720p')
  const motionSeedanceDurationInitRef = useRef(false)
  const motionVideoUploadSeqRef = useRef(0)
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
    { variant: motionSeedanceVariant, resolution: motionVideoResolution },
  )

  const motionVideoUsdPerSecDisplay = motionVideoUsdPerSec(
    motionSeedanceVariant,
    motionVideoResolution,
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
    const res = health.studio_seedance_t2v_default_resolution
    if (res === '480p' || res === '720p' || res === '1080p') {
      setMotionVideoResolution(res)
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

  useEffect(() => {
    if (!studioIdentityFile) {
      setStudioIdentityObjectUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return null
      })
      return
    }
    const url = URL.createObjectURL(studioIdentityFile)
    setStudioIdentityObjectUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return url
    })
  }, [studioIdentityFile])

  useEffect(() => {
    setStudioReferenceAnalysis(null)
  }, [studioFile, studioMode, studioSelectedModelId])

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

  useEffect(() => {
    if (!authed || !isOwner) return
    trackFunnelEvent('workspace_opened')
  }, [authed, isOwner])

  useEffect(() => {
    if (!authed || !me || !isOwner || !canStudioGenerate) return
    if (readFirstGenWizardDoneForUser(me.id)) return
    if (!hasFirstGenWizardPending()) return
    if (studioPaywalled) return
    clearFirstGenWizardPending()
    setFirstGenWizardOpen(true)
  }, [authed, me, isOwner, canStudioGenerate, studioPaywalled])

  useEffect(() => {
    if (firstGenWizardOpen) setAccountOpen(false)
  }, [firstGenWizardOpen])

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

  const refreshTributeEarnings = useCallback(async () => {
    const r = await apiFetch('/api/tribute/earnings/summary')
    if (r.ok) {
      setTributeEarnings((await r.json()) as TributeEarningsSummary)
    } else {
      setTributeEarnings(null)
    }
  }, [])

  const refreshCreatorDonationOverview = useCallback(async () => {
    if (!isOwner) return
    const r = await apiFetch('/api/creator-donations/overview')
    if (!r.ok) {
      setCreatorDonationOverview(null)
      return
    }
    const data = (await r.json()) as CreatorDonationOverview
    setCreatorDonationOverview(data)
    const ownerId = me?.id
    const latestId = data.latest_event_id
    if (!ownerId || !latestId) {
      setCreatorDonationAlert(null)
      return
    }
    const seenId = readDonationLastSeenEventId(ownerId)
    if (seenId === 0) {
      writeDonationLastSeenEventId(ownerId, latestId)
      setCreatorDonationAlert(null)
      return
    }
    if (latestId > seenId && data.latest_event) {
      setCreatorDonationAlert(data.latest_event)
      if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
        const amount = formatAppCurrency(
          data.latest_event.amount_minor,
          data.latest_event.currency,
        )
        try {
          new Notification(t('platformDonations.alertTitle'), {
            body: t('platformDonations.alertBody', { amount }),
            tag: `creator-donation-${latestId}`,
          })
        } catch {
          /* ignore */
        }
      }
    } else {
      setCreatorDonationAlert(null)
    }
  }, [isOwner, me?.id, t])

  const openCreatorDonations = useCallback(() => {
    if (me?.id && creatorDonationOverview?.latest_event_id) {
      writeDonationLastSeenEventId(me.id, creatorDonationOverview.latest_event_id)
    }
    setCreatorDonationAlert(null)
    setAccountOpen(true)
    setAccountTab('donations')
  }, [me?.id, creatorDonationOverview?.latest_event_id])

  const dismissCreatorDonationAlert = useCallback(() => {
    if (me?.id && creatorDonationOverview?.latest_event_id) {
      writeDonationLastSeenEventId(me.id, creatorDonationOverview.latest_event_id)
    }
    setCreatorDonationAlert(null)
  }, [me?.id, creatorDonationOverview?.latest_event_id])

  const refreshChatterStats = useCallback(async () => {
    const r = await apiFetch('/api/workspace/chatter-stats/summary')
    if (r.ok) {
      setChatterStats((await r.json()) as ChatterStatsSummary)
    } else {
      setChatterStats(null)
    }
  }, [])

  const refreshChatterSnippets = useCallback(async () => {
    const r = await apiFetch('/api/workspace/snippets')
    if (r.ok) {
      setChatterSnippets((await r.json()) as ChatterSnippet[])
    }
  }, [])

  const refreshCompanionHealth = useCallback(async (convId: number) => {
    const r = await apiFetch(`/api/conversations/${convId}/companion-health`)
    if (r.ok) {
      setCompanionHealth((await r.json()) as CompanionHealth)
    } else {
      setCompanionHealth(null)
    }
  }, [])

  const refreshCompanionFeedback = useCallback(async () => {
    setCompanionFeedbackLoading(true)
    try {
      const r = await apiFetch('/api/integrations/companion-feedback?limit=7')
      if (r.ok) {
        setCompanionFeedbackReports((await r.json()) as CompanionFeedbackReport[])
      }
    } finally {
      setCompanionFeedbackLoading(false)
    }
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

  const studioArchiveOptimisticOpts = useCallback(
    (mediaKind: StudioArchiveMediaKind, promptExcerpt?: string | null) => {
      const model =
        studioSelectedModelId != null
          ? studioModels.find((m) => m.id === studioSelectedModelId)
          : undefined
      return createOptimisticStudioArchiveItem({
        mediaKind,
        promptExcerpt,
        studioModelId: studioSelectedModelId,
        modelName: model?.name ?? null,
        outputAspect: studioOutputAspect,
      })
    },
    [studioModels, studioOutputAspect, studioSelectedModelId],
  )

  const pushOptimisticStudioGeneration = useCallback((item: StudioArchiveItem) => {
    setStudioGenerations((prev) => prependOptimisticStudioArchive(prev, item))
  }, [])

  const resolveOptimisticStudioGeneration = useCallback(
    (tempId: number, realId: number | null) => {
      setStudioGenerations((prev) => {
        if (realId == null) return removeOptimisticStudioArchive(prev, tempId)
        return replaceOptimisticStudioArchiveId(prev, tempId, realId)
      })
    },
    [],
  )

  const loadStudioGenerationsReset = useCallback(async () => {
    const kind = studioGalleryMediaKind(appSection)
    const page = await fetchStudioArchivePage(0, STUDIO_ARCHIVE_PAGE, kind)
    setStudioGenerations((prev) => {
      const optimistic = prev.filter((g) => isOptimisticStudioArchiveId(g.id))
      return mergeStudioArchiveItems(page.items, optimistic)
    })
    setStudioGenHasMore(page.has_more)
    if (appSection === 'studio' || appSection === 'studio_bootstrap') {
      setStudioImagePickerArchive(page.items)
    } else if (appSection === 'studio_video') {
      void loadStudioImagePickerArchive()
      void refreshMotionRenders()
    }
    void fetchStudioArchivePending(kind)
      .then((pending) => {
        if (!pending.items.length) return
        setStudioGenerations((prev) => mergeStudioArchiveItems(prev, pending.items))
      })
      .catch(() => {
        /* pending опционален */
      })
  }, [appSection, loadStudioImagePickerArchive, refreshMotionRenders])

  const syncStudioArchivePending = useCallback(async () => {
    try {
      const kind = studioGalleryMediaKind(appSection)
      const pendingPromise = fetchStudioArchivePending(kind)
      const imagePendingPromise =
        appSection === 'studio_video'
          ? fetchStudioArchivePending('image')
          : Promise.resolve({ items: [] as StudioArchiveItem[], poll_after_seconds: 12 })
      const [pending, imgPending] = await Promise.all([pendingPromise, imagePendingPromise])
      if (pending.items.length) {
        setStudioGenerations((prev) => mergeStudioArchiveItems(prev, pending.items))
      }
      if (imgPending.items.length) {
        setStudioImagePickerArchive((prev) => mergeStudioArchiveItems(prev, imgPending.items))
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

  const resetMotionVideoWorkflow = useCallback(() => {
    setMotionPreviewGenId(null)
    setMotionPreviewUrl(null)
    setMotionFrameArchiveId(null)
    setMotionFirstFrameFile(null)
    setMotionGrokTimeline(null)
    setMotionStep1Preview(null)
    setMotionResultVideoUrl(null)
    setMotionPendingExternalStillUrl(null)
    setMotionAutoTextPreview(null)
  }, [])

  const uploadMotionDrivingVideo = useCallback(async (file: File) => {
    const uploadSeq = ++motionVideoUploadSeqRef.current
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
      if (uploadSeq !== motionVideoUploadSeqRef.current) return
      if (!r.ok) {
        setError(formatHttpApiError(r, data))
        setMotionVideoFileId(null)
        return
      }
      const id = typeof data.motion_video_file_id === 'string' ? data.motion_video_file_id.trim() : ''
      setMotionVideoFileId(id || null)
    } catch (e) {
      if (uploadSeq !== motionVideoUploadSeqRef.current) return
      setMotionVideoFileId(null)
      setError(
        e instanceof TypeError && e.message === 'Failed to fetch'
          ? ts('runtime.videoUploadNetwork')
          : e instanceof Error
            ? e.message
            : ts('runtime.videoUploadFailed'),
      )
    } finally {
      if (uploadSeq === motionVideoUploadSeqRef.current) {
        setMotionDrivingUploadBusy(false)
      }
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
    if (accountTab === 'donations' && !isOwner) setAccountTab('overview')
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
    if (!authed || !isOwner || !integ || !me) return
    if (!studioNeedsUserWsKey) return
    if (firstGenWizardOpen || hasFirstGenWizardPending()) return
    if (!readFirstGenWizardDoneForUser(me.id)) return
    try {
      if (localStorage.getItem(WS_ONBOARDING_LS)) return
      localStorage.setItem(WS_ONBOARDING_LS, '1')
    } catch {
      /* private mode */
    }
    setAccountOpen(true)
    setAccountTab('integrations')
    setWsSetupPulse(true)
  }, [authed, isOwner, integ, studioNeedsUserWsKey, firstGenWizardOpen, me])

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
    if (!authed || !canChat) return
    if (appSection !== 'overview') return
    const refresh = () => {
      void refreshTributeEarnings()
      void refreshChatterStats()
    }
    refresh()
    const onVis = () => {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVis)
    const timer = window.setInterval(refresh, 60_000)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      window.clearInterval(timer)
    }
  }, [authed, canChat, appSection, refreshTributeEarnings, refreshChatterStats])

  useEffect(() => {
    if (!authed || !canChat || appSection !== 'overview') return
    if (!integ?.tribute_configured) return
    void refreshTributeEarnings()
  }, [authed, canChat, appSection, integ?.tribute_configured, refreshTributeEarnings])

  useEffect(() => {
    if (!authed || !isOwner) return
    void refreshCreatorDonationOverview()
    const timer = window.setInterval(() => void refreshCreatorDonationOverview(), 60_000)
    return () => window.clearInterval(timer)
  }, [authed, isOwner, refreshCreatorDonationOverview])

  useEffect(() => {
    if (authed && accountOpen && accountTab === 'donations' && isOwner) {
      void refreshCreatorDonationOverview()
    }
  }, [authed, accountOpen, accountTab, isOwner, refreshCreatorDonationOverview])

  useEffect(() => {
    if (authed && accountOpen && accountTab === 'team' && isOwner) {
      void refreshChatterStats()
      void refreshChatterSnippets()
    }
  }, [authed, accountOpen, accountTab, isOwner, refreshChatterStats, refreshChatterSnippets])

  useEffect(() => {
    if (!authed) return
    const account = searchParams.get('account')
    const fanvue = searchParams.get('fanvue')
    const instagram = searchParams.get('instagram')
    if (account === 'integrations' || fanvue || instagram) {
      setAccountOpen(true)
      setAccountTab('integrations')
    }
    if (fanvue === 'connected') {
      void refreshIntegrations()
    } else if (fanvue === 'error') {
      setError(tc('errors.fanvueConnect'))
    }
    if (instagram === 'connected') {
      void refreshIntegrations()
    } else if (instagram === 'error') {
      setError(tc('errors.instagramConnect'))
    }
    if (account || fanvue || instagram) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.delete('account')
          next.delete('fanvue')
          next.delete('instagram')
          next.delete('reason')
          return next
        },
        { replace: true },
      )
    }
  }, [authed, searchParams, refreshIntegrations, setSearchParams])

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
    void fetchGenerationModelOptions().then(setStudioGenModels)
  }, [authed, appSection])

  useEffect(() => {
    if (!studioGenModels.length) return
    setStudioWaveModelId((prev) =>
      pickValidModelId(studioGenModels, studioWaveProfile === 'nsfw', prev),
    )
  }, [studioGenModels, studioWaveProfile])

  useEffect(() => {
    if (!studioGenModels.length) return
    const aspects = aspectsForModel(studioGenModels, studioWaveModelId)
    setStudioOutputAspect((prev) => pickValidAspect(aspects, prev))
  }, [studioGenModels, studioWaveModelId])

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
    if (studioSelectedModelId == null) return ts('runtime.selectModelTop')
    if (!motionHasFirstFrame) {
      return ts('runtime.needFirstFrame')
    }
    if (!motionDesc.trim()) {
      return ts('runtime.needVideoBrief')
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
        studioIdentityFile,
        studioWaveModelId,
        studioWaveProfile,
        studioWanEditTier,
        creditsBalance: me?.credits_balance ?? 0,
        demoRemaining: me?.demo_generations_remaining ?? 0,
        billingPlan: me?.billing_plan,
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
      studioIdentityFile,
      studioWaveModelId,
      studioWaveProfile,
      studioWanEditTier,
      me?.billing_plan,
      me?.credits_balance,
      me?.demo_generations_remaining,
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
    if (r.status === 403) {
      setConversations([])
      return
    }
    if (!r.ok) throw new Error(tc('errors.loadConversations'))
    const data: Conversation[] = await r.json()
    setConversations(data)
  }, [])

  const markConversationRead = useCallback(
    async (convId: number) => {
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, unread_count: 0 } : c)),
      )
      try {
        const r = await apiFetch(`/api/conversations/${convId}/read`, { method: 'POST' })
        if (!r.ok) void loadConversations()
      } catch {
        void loadConversations()
      }
    },
    [loadConversations],
  )

  const selectConversation = useCallback(
    (convId: number) => {
      setSelectedId(convId)
      void markConversationRead(convId)
    },
    [markConversationRead],
  )

  const fetchMessagesPage = useCallback(async (id: number, before?: number) => {
    const p = new URLSearchParams()
    p.set('limit', String(CHAT_MESSAGES_PAGE))
    if (before != null) p.set('before', String(before))
    const r = await apiFetch(`/api/conversations/${id}/messages?${p}`)
    if (!r.ok) throw new Error(tc('errors.loadMessages'))
    return (await r.json()) as ChatMessage[]
  }, [])

  const loadMessages = useCallback(
    async (id: number) => {
      const data = await fetchMessagesPage(id)
      setMessages(data)
      setHasMoreOlder(data.length >= CHAT_MESSAGES_PAGE)
      const dr = await apiFetch(`/api/conversations/${id}/companion-drafts`)
      if (dr.ok) {
        setCompanionDrafts((await dr.json()) as CompanionDraft[])
      } else {
        setCompanionDrafts([])
      }
    },
    [fetchMessagesPage],
  )

  const approveCompanionDraft = async (draft: CompanionDraft, text?: string) => {
    if (selectedId == null) return
    setCompanionDraftBusy(draft.id)
    setError(null)
    try {
      const r = await apiFetch(
        `/api/conversations/${selectedId}/companion-drafts/${draft.id}/approve`,
        {
          method: 'POST',
          body: JSON.stringify(text != null ? { text } : {}),
        },
      )
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      const msg = (await r.json()) as ChatMessage
      setCompanionDrafts((prev) => prev.filter((d) => d.id !== draft.id))
      setMessages((prev) => {
        if (prev.some((m) => Number(m.id) === Number(msg.id))) return prev
        return [...prev, msg]
      })
    } finally {
      setCompanionDraftBusy(null)
    }
  }

  const rejectCompanionDraft = async (draftId: number) => {
    if (selectedId == null) return
    setCompanionDraftBusy(draftId)
    setError(null)
    try {
      const r = await apiFetch(
        `/api/conversations/${selectedId}/companion-drafts/${draftId}/reject`,
        { method: 'POST' },
      )
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      setCompanionDrafts((prev) => prev.filter((d) => d.id !== draftId))
    } finally {
      setCompanionDraftBusy(null)
    }
  }

  const rateCompanionMessage = async (messageId: number, rating: -1 | 1) => {
    if (selectedId == null) return
    const snapshot = messages.find((m) => Number(m.id) === Number(messageId))
    const current = snapshot?.operator_rating
    const nextRating: -1 | 0 | 1 = current === rating ? 0 : rating
    const optimisticRating = nextRating === 0 ? null : nextRating

    setCompanionRatingBusy(messageId)
    setCompanionRatingSavedId(null)
    setError(null)
    setMessages((prev) =>
      prev.map((m) =>
        Number(m.id) === Number(messageId) ? { ...m, operator_rating: optimisticRating } : m,
      ),
    )

    try {
      const r = await apiFetch(
        `/api/conversations/${selectedId}/messages/${messageId}/companion-rating`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rating: nextRating }),
        },
      )
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        if (snapshot) {
          setMessages((prev) =>
            prev.map((m) =>
              Number(m.id) === Number(messageId)
                ? { ...m, operator_rating: snapshot.operator_rating ?? null }
                : m,
            ),
          )
        }
        return
      }
      const msg = (await r.json()) as ChatMessage
      setMessages((prev) =>
        prev.map((m) => (Number(m.id) === Number(msg.id) ? { ...m, ...msg } : m)),
      )
      if (nextRating !== 0) {
        setCompanionRatingSavedId(messageId)
        window.setTimeout(() => {
          setCompanionRatingSavedId((id) => (id === messageId ? null : id))
        }, 2500)
      }
    } finally {
      setCompanionRatingBusy(null)
    }
  }

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
    const conv = conversations.find((c) => c.id === id)
    if (conv) {
      setChatPlatformTab(conv.platform)
      selectConversation(id)
    }
  }, [conversations, selectConversation])

  useEffect(() => {
    if (chatVisiblePlatforms.length === 0) return
    if (!chatVisiblePlatforms.includes(chatPlatformTab)) {
      setChatPlatformTab(chatVisiblePlatforms[0])
    }
  }, [chatVisiblePlatforms, chatPlatformTab])

  useEffect(() => {
    if (selectedId == null) return
    if (!filteredConversations.some((c) => c.id === selectedId)) {
      setSelectedId(null)
    }
  }, [filteredConversations, selectedId])

  useEffect(() => {
    if (selectedId == null) {
      setCompanionHealth(null)
      return
    }
    void refreshCompanionHealth(selectedId)
  }, [selectedId, refreshCompanionHealth])

  useEffect(() => {
    if (!authed || !canChat) return
    void refreshChatterSnippets()
  }, [authed, canChat, refreshChatterSnippets])

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
    if (!accountOpen || accountTab !== 'integrations' || !authed) return
    void refreshCompanionFeedback()
  }, [accountOpen, accountTab, authed, refreshCompanionFeedback])

  useEffect(() => {
    prevMsgLenRef.current = 0
    setShowJumpDown(false)
    setConvNotesOpen(false)
    setConvNoteDraft('')
    setThreadSettingsOpen(false)
  }, [selectedId])

  const loadConvNotes = useCallback(async (convId: number) => {
    setConvNotesLoading(true)
    try {
      const r = await apiFetch(`/api/conversations/${convId}/notes`)
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      setConvNotes((await r.json()) as ConversationNote[])
    } catch (e) {
      setError(String(e))
    } finally {
      setConvNotesLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedId == null) return
    if (isMobileLayout && !convNotesOpen) return
    void loadConvNotes(selectedId)
  }, [convNotesOpen, selectedId, isMobileLayout, loadConvNotes])

  useEffect(() => {
    setConvNoteComposeOpen(false)
    setConvNoteDraft('')
  }, [selectedId])

  useEffect(() => {
    if (!convNoteComposeOpen) return
    const id = window.requestAnimationFrame(() => convNoteDraftRef.current?.focus())
    return () => window.cancelAnimationFrame(id)
  }, [convNoteComposeOpen])

  const convNotesPinned = useMemo(
    () =>
      convNotes.filter(
        (n) => n.kind === 'ai_profile' || n.kind === 'ai_daily' || n.is_pinned,
      ),
    [convNotes],
  )
  const convNotesScroll = useMemo(
    () =>
      convNotes.filter(
        (n) => n.kind !== 'ai_profile' && n.kind !== 'ai_daily' && !n.is_pinned,
      ),
    [convNotes],
  )

  useEffect(() => {
    if (selectedId == null) {
      setMessages([])
      setHasMoreOlder(false)
      setCompanionRatingSavedId(null)
      return
    }
    setMessages([])
    setHasMoreOlder(false)
    setCompanionRatingSavedId(null)
    let cancelled = false
    setLoading(true)
    setError(null)
    loadMessages(selectedId)
      .catch((e) => setError(String(e)))
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedId, loadMessages])

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
        if (payload.type === 'companion_draft') {
          const sid = selectedIdRef.current
          const raw = payload as {
            conversation_id?: number
            event?: CompanionDraft
          }
          if (sid != null && sid === raw.conversation_id && raw.event?.id) {
            const ev = raw.event
            setCompanionDrafts((prev) => {
              if (prev.some((d) => d.id === ev.id)) return prev
              return [...prev, ev]
            })
          }
          return
        }
        if (payload.type === 'new_message') {
          void loadHealth()
          const sid = selectedIdRef.current
          const convId = payload.conversation_id
          if (sid != null && sid === convId && payload.message) {
            const mid = Number(payload.message.id)
            const incoming = payload.message as ChatMessage
            if (
              incoming.direction === 'outbound' &&
              incoming.bot_response_event_id != null
            ) {
              const eventId = Number(incoming.bot_response_event_id)
              setCompanionDrafts((prev) => prev.filter((d) => d.id !== eventId))
            }
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
            void (async () => {
              await markConversationRead(sid)
              void loadConvNotes(sid)
              void loadConversations()
            })()
          } else {
            void loadConversations()
          }
          return
        }
        if (payload.type === 'message_updated') {
          const sid = selectedIdRef.current
          if (sid != null && sid === payload.conversation_id && payload.message) {
            const incoming = payload.message as ChatMessage
            const mid = Number(incoming.id)
            setMessages((prev) =>
              prev.map((m) => (Number(m.id) === mid ? { ...m, ...incoming } : m)),
            )
          }
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
    loadConvNotes,
    markConversationRead,
    loadHealth,
    authed,
    refreshMotionRenders,
    loadStudioGenerationsReset,
    syncStudioArchivePending,
    refreshMe,
  ])

  useEffect(() => {
    if (!emojiOpen) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (emojiWrapRef.current?.contains(t)) return
      setEmojiOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [emojiOpen])

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
    setEmojiOpen(false)
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
        setError(formatHttpApiError(r, err))
        return
      }
      const updated = (await r.json()) as Conversation
      setConversations((prev) => prev.map((c) => (c.id === convId ? { ...c, ...updated } : c)))
    } catch {
      setError(tc('errors.saveReplyLang'))
    } finally {
      setOutboundLangBusy(false)
    }
  }

  const addConvNote = async () => {
    if (selectedId == null) return
    const text = convNoteDraft.trim()
    if (!text) return
    setConvNotesBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/conversations/${selectedId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      setConvNoteDraft('')
      setConvNoteComposeOpen(false)
      await loadConvNotes(selectedId)
    } finally {
      setConvNotesBusy(false)
    }
  }

  const openConvNoteCompose = () => {
    setConvNoteComposeOpen(true)
  }

  const closeConvNoteCompose = () => {
    setConvNoteComposeOpen(false)
    setConvNoteDraft('')
  }

  const analyzeConvNotes = async () => {
    if (selectedId == null) return
    setConvNotesAnalyzeBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/conversations/${selectedId}/notes/analyze`, { method: 'POST' })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      setConvNotes((await r.json()) as ConversationNote[])
    } finally {
      setConvNotesAnalyzeBusy(false)
    }
  }

  const deleteConvNote = async (noteId: number) => {
    if (selectedId == null) return
    setConvNotesBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${selectedId}/notes/${noteId}`, {
        method: 'DELETE',
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      await loadConvNotes(selectedId)
    } finally {
      setConvNotesBusy(false)
    }
  }

  const toggleConvNotePin = async (note: ConversationNote) => {
    if (selectedId == null || note.kind !== 'manual') return
    setConvNotesBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${selectedId}/notes/${note.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_pinned: !note.is_pinned }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      await loadConvNotes(selectedId)
    } finally {
      setConvNotesBusy(false)
    }
  }

  const saveAutoTranslateDisabled = async (convId: number, disabled: boolean) => {
    setError(null)
    setAutoTranslateBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_translate_disabled: disabled }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        return
      }
      const updated = (await r.json()) as Conversation
      setConversations((prev) => prev.map((c) => (c.id === convId ? { ...c, ...updated } : c)))
    } catch {
      setError(tc('errors.saveTranslate'))
    } finally {
      setAutoTranslateBusy(false)
    }
  }

  const saveCompanionModeOverride = async (convId: number, raw: string) => {
    const v = raw === '' ? null : raw
    setError(null)
    setCompanionModeBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ companion_mode_override: v }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        return
      }
      const updated = (await r.json()) as Conversation
      setConversations((prev) => prev.map((c) => (c.id === convId ? { ...c, ...updated } : c)))
      void refreshCompanionHealth(convId)
    } catch {
      setError(tc('errors.saveCompanion'))
    } finally {
      setCompanionModeBusy(false)
    }
  }

  const saveAssignedUser = async (convId: number, raw: string) => {
    const v = raw === '' ? null : parseInt(raw, 10)
    setAssigneeBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assigned_user_id: v }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        return
      }
      const updated = (await r.json()) as Conversation
      setConversations((prev) => prev.map((c) => (c.id === convId ? { ...c, ...updated } : c)))
    } catch {
      setError(tc('errors.assignChatter'))
    } finally {
      setAssigneeBusy(false)
    }
  }

  const insertChatterSnippet = (body: string) => {
    setDraft((prev) => (prev.trim() ? `${prev.trim()}\n${body}` : body))
  }

  const createChatterSnippet = async () => {
    const title = newSnippetTitle.trim()
    const body = newSnippetBody.trim()
    if (!title || !body) return
    setSnippetBusy(true)
    try {
      const r = await apiFetch('/api/workspace/snippets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, body }),
      })
      if (!r.ok) {
        setError(tc('errors.createTemplate'))
        return
      }
      setNewSnippetTitle('')
      setNewSnippetBody('')
      await refreshChatterSnippets()
    } finally {
      setSnippetBusy(false)
    }
  }

  const deleteChatterSnippet = async (id: number) => {
    setSnippetBusy(true)
    try {
      await apiFetch(`/api/workspace/snippets/${id}`, { method: 'DELETE' })
      await refreshChatterSnippets()
    } finally {
      setSnippetBusy(false)
    }
  }

  const saveManualCategory = async (convId: number, raw: string) => {
    const v = raw === '' ? null : raw
    setError(null)
    setConvCategoryBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manual_category: v }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        return
      }
      const updated = (await r.json()) as Conversation
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? {
                ...c,
                ...updated,
                last_message_preview: c.last_message_preview,
                unread_count: c.unread_count,
                is_no_response: c.is_no_response,
                is_new: c.is_new,
              }
            : c,
        ),
      )
    } catch {
      setError(tc('errors.saveCategory'))
    } finally {
      setConvCategoryBusy(false)
    }
  }

  const saveConversationBlocked = async (convId: number, blocked: boolean) => {
    setError(null)
    setConvBlockedBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${convId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_blocked: blocked }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        return
      }
      const updated = (await r.json()) as Conversation
      setConversations((prev) =>
        prev.map((c) =>
          c.id === convId
            ? {
                ...c,
                ...updated,
                last_message_preview: c.last_message_preview,
                unread_count: c.unread_count,
                is_no_response: c.is_no_response,
                is_new: c.is_new,
              }
            : c,
        ),
      )
    } catch {
      setError(tc('errors.saveBlock'))
    } finally {
      setConvBlockedBusy(false)
    }
  }

  const hideConversation = async (convId: number) => {
    if (!window.confirm(tc('errors.hideConfirm'))) {
      return
    }
    setError(null)
    setConvHideBusy(true)
    try {
      const r = await apiFetch(`/api/conversations/${convId}`, { method: 'DELETE' })
      if (!r.ok && r.status !== 204) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        return
      }
      setConversations((prev) => prev.filter((c) => c.id !== convId))
      if (selectedId === convId) {
        setSelectedId(null)
        setMessages([])
      }
    } catch {
      setError(tc('errors.hideFailed'))
    } finally {
      setConvHideBusy(false)
    }
  }

  const scrollToMessage = useCallback((messageId: number | null | undefined) => {
    if (!messageId) return
    const el = messagesContainerRef.current?.querySelector(
      `[data-msg-id="${messageId}"]`,
    )
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [])

  const toggleReaction = async (msg: ChatMessage, emoji: string) => {
    if (selectedId == null || msg.pending) return
    const key = `${msg.id}:${emoji}`
    setReactionBusyKey(key)
    setError(null)
    try {
      const r = await apiFetch(
        `/api/conversations/${selectedId}/messages/${msg.id}/reactions`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ emoji }),
        },
      )
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        return
      }
      const updated = (await r.json()) as ChatMessage
      setMessages((prev) =>
        prev.map((m) => (Number(m.id) === Number(updated.id) ? { ...m, ...updated } : m)),
      )
      if (updated.platform_sync_ok === false) {
        setError(tc('errors.reactionTelegram'))
      }
    } catch {
      setError(tc('errors.reactionFailed'))
    } finally {
      setReactionBusyKey(null)
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
    setReplyToMessage(null)
  }, [selectedId, clearChatReplyAttachment])

  const chatReplyHasAttachment = Boolean(chatReplyFile || chatReplyArchiveId)

  const sendReply = async () => {
    if (selectedId == null) return
    if (selected?.peer_unavailable) return
    const text = draft.trim()
    if (!text && !chatReplyHasAttachment) return
    const convId = selectedId
    const replyTarget = replyToMessage
    const replyToId =
      replyTarget && !replyTarget.pending && replyTarget.id > 0 ? replyTarget.id : null
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
      reply_to_message_id: replyToId,
      reply_preview: replyTarget
        ? (
            replyTarget.text_original ||
            replyTarget.text_translated ||
            tc('composer.messageFallback')
          ).slice(0, 160)
        : null,
    }
    setError(null)
    setDraft('')
    setEmojiOpen(false)
    setReplyToMessage(null)
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
        if (replyToId != null) fd.append('reply_to_message_id', String(replyToId))
        r = await apiFetch(`/api/conversations/${convId}/reply`, {
          method: 'POST',
          body: fd,
        })
      } else {
        r = await apiFetch(`/api/conversations/${convId}/reply`, {
          method: 'POST',
          body: JSON.stringify({
            text,
            reply_to_message_id: replyToId,
          }),
        })
      }
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, err))
        if (r.status === 410) {
          setConversations((prev) =>
            prev.map((c) => (c.id === convId ? { ...c, peer_unavailable: true } : c)),
          )
        }
        setMessages((prev) => {
          if (selectedIdRef.current !== convId) return prev
          return prev.filter((m) => m.id !== tempId)
        })
        setDraft((d) => (d.trim() ? `${text}\n\n${d}` : text))
        if (replyTarget) setReplyToMessage(replyTarget)
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
      if (replyTarget) setReplyToMessage(replyTarget)
      if (fileToSend) setChatReplyFile(fileToSend)
      if (archiveIdToSend != null) setChatReplyArchiveId(archiveIdToSend)
      setError(tc('errors.sendFailed'))
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
    if (isOptimisticStudioArchiveId(g.id)) {
      setStudioGenerations((prev) => removeOptimisticStudioArchive(prev, g.id))
      return
    }
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
        setError(tc('errors.imageLoadFailed'))
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
            await navigator.share({ files: [file], title: tc('errors.shareImageTitle') })
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
        tc('errors.imageDownloadFailed'),
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
          await navigator.share({ title: ts('runtime.shareVideoTitle'), url })
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
            await navigator.share({ files: [file], title: ts('runtime.shareVideoTitle') })
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
        ts('runtime.videoDownloadFailed'),
      )
    } finally {
      setMotionVideoDownloadBusy(false)
    }
  }

  const analyzeStudioReference = async () => {
    if (!studioFile) return
    setStudioReferenceAnalyzing(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('image', studioFile)
      fd.append('studio_mode', studioMode)
      fd.append('studio_wave_profile', studioWaveProfile)
      if (studioSelectedModelId != null) {
        fd.append('model_id', String(studioSelectedModelId))
      }
      const r = await apiFetch('/api/studio/reference/analyze', { method: 'POST', body: fd })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      const data = (await r.json()) as StudioReferenceAnalysisResponse
      setStudioReferenceAnalysis(data)
      if (
        data.effective_studio_mode === 'no_face' &&
        (studioMode === 'model' || studioMode === 'no_face')
      ) {
        setStudioMode('no_face')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setStudioReferenceAnalyzing(false)
    }
  }

  const refineStudioPrompt = async () => {
    if (studioImageGenInFlightRef.current || studioBusy) return
    setError(null)
    if (studioMode === 'photo_edit') {
      if (!studioFile && studioPhotoEditArchiveId == null) {
        setError(ts('runtime.photoEditNeedImage'))
        return
      }
      if (!studioDesc.trim()) {
        setError(ts('runtime.photoEditNeedPrompt'))
        return
      }
    } else if (studioMode === 'model_scene') {
      if (health?.studio_grok_scene_compose_configured === false) {
        setError(ts('runtime.mainNeedsGrok'))
        return
      }
      if (studioSelectedModelId == null) {
        setError(ts('runtime.mainNeedModel'))
        return
      }
      if (!studioFile) {
        setError(ts('runtime.mainNeedRef'))
        return
      }
    } else if (studioMode === 'model') {
      if (health?.studio_grok_scene_compose_configured === false) {
        setError(ts('runtime.promptNeedsGrok'))
        return
      }
      if (studioSelectedModelId == null) {
        setError(ts('runtime.promptNeedModel'))
        return
      }
      if (!studioDesc.trim()) {
        setError(ts('runtime.promptNeedText'))
        return
      }
    } else if (
      studioMode !== 'face_swap' &&
      studioMode !== 'grok_compose' &&
      !studioDesc.trim() &&
      !studioFile &&
      studioSelectedModelId == null
    ) {
      setError(ts('runtime.needInput'))
      return
    }
    if (studioMode === 'no_face' && studioSelectedModelId == null && !studioFile) {
      setError(ts('runtime.noFaceNeedInput'))
      return
    }
    if (studioMode === 'grok_compose' || studioMode === 'face_swap') {
      if (health?.studio_grok_scene_compose_configured === false) {
        setError(ts('runtime.grokNotConfigured'))
        return
      }
      if (!studioFile) {
        setError(ts('runtime.needSceneRef'))
        return
      }
      if (studioSelectedModelId == null && !studioIdentityFile) {
        setError(
          ts('gate.grokComposeNoIdentity'),
        )
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
        ts('runtime.maskNeedImage'),
      )
      return
    }
    let inpaintAttach: File | null = null
    if (studioPaintInpaintMask) {
      inpaintAttach = (await studioMaskPainterRef.current?.getMaskFile()) ?? null
      if (!inpaintAttach) {
        setError(
          ts('runtime.maskNeedPaint'),
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
    const { item: optimisticItem, tempId: optimisticTempId } = studioArchiveOptimisticOpts(
      'image',
      studioDesc.trim(),
    )
    pushOptimisticStudioGeneration(optimisticItem)
    try {
      const promptOnlyActive =
        import.meta.env.DEV &&
        Boolean(health?.studio_allow_prompt_only) &&
        studioDevPromptOnly
      const workflowDemoLimited = Boolean(me?.workflow_demo_limited)
      const genOptions: StudioScenarioGenOptions = {
        outputAspect: studioOutputAspect,
        waveProfile: studioWaveProfile,
        waveModelId: studioWaveModelId,
        wanEditTier: studioEffectiveWanTier,
        exifCamera: studioExifCamera,
        realismEnabled: true,
        userPrompt: studioDesc.trim(),
      }
      const useWorkflowPath =
        !promptOnlyActive &&
        (studioMode === 'model_scene' ||
          studioMode === 'grok_compose' ||
          studioMode === 'face_swap' ||
          studioMode === 'model' ||
          (studioMode === 'photo_edit' &&
            studioFile != null &&
            !inpaintAttach &&
            studioPhotoEditArchiveId == null))

      let accepted: Awaited<ReturnType<typeof postStudioJobStart>>
      if (useWorkflowPath) {
        if (studioMode === 'model_scene') {
          if (studioSelectedModelId == null || !studioFile) {
            throw new Error(ts('runtime.workflowMainNeedInputs'))
          }
          ;({ accepted } = await buildAndStartPoRefuScenario({
            modelId: studioSelectedModelId,
            sceneFile: studioFile,
            genOptions,
            workflowDemoLimited,
          }))
        } else if (studioMode === 'grok_compose' || studioMode === 'face_swap') {
          if (!studioFile) {
            throw new Error(ts('runtime.workflowFaceSwapNoScene'))
          }
          ;({ accepted } = await buildAndStartFaceSwapScenario({
            sceneFile: studioFile,
            identityFile: studioIdentityFile,
            modelId: studioSelectedModelId,
            genOptions,
            workflowDemoLimited,
          }))
        } else if (studioMode === 'model') {
          if (studioSelectedModelId == null) {
            throw new Error(ts('runtime.workflowPromptNoModel'))
          }
          ;({ accepted } = await buildAndStartPromptOnlyScenario({
            modelId: studioSelectedModelId,
            genOptions,
            workflowDemoLimited,
          }))
        } else if (studioMode === 'photo_edit') {
          if (!studioFile) {
            throw new Error(ts('runtime.workflowPhotoEditNoImage'))
          }
          ;({ accepted } = await buildAndStartPhotoEditScenario({
            sceneFile: studioFile,
            userPrompt: studioDesc.trim(),
            genOptions,
            workflowDemoLimited,
          }))
        } else {
          throw new Error(ts('runtime.workflowModeUnsupported'))
        }
      } else {
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
        fd.append('wan_edit_tier', studioEffectiveWanTier)
        fd.append('studio_wave_profile', studioWaveProfile)
        const waveSel = normalizeWaveModelSelection(studioWaveModelId)
        fd.append('workflow_wave_model', waveSel.apiWaveModelId)
        fd.append('generate_wavespeed', promptOnlyActive ? '0' : '1')
        fd.append('wavespeed_single_reference', '1')
        fd.append(
          'send_pose_reference_to_wavespeed',
          studioSendPoseRefToWavespeed ? '1' : '0',
        )
        fd.append('lock_model_hairstyle', studioLockModelHairstyle ? '1' : '0')
        fd.append('exif_camera', studioExifCamera)
        if (studioReferenceAnalysis?.analysis) {
          fd.append('reference_analysis_json', JSON.stringify(studioReferenceAnalysis.analysis))
        }
        accepted = await postStudioJobStart('/api/studio/refine-prompt', {
          method: 'POST',
          body: fd,
        })
      }
      const gid =
        typeof accepted.generation_id === 'number' ? accepted.generation_id : null
      resolveOptimisticStudioGeneration(optimisticTempId, gid)
      if (gid != null) {
        setStudioGenGenerationId(gid)
        setStudioGenImageUrl(null)
        setStudioPendingExternalImageUrl(null)
      }
      setStudioWavespeedMsg(
        ts('runtime.genStarted'),
      )
      void refreshMe()
      void syncStudioArchivePending()
    } catch (e) {
      resolveOptimisticStudioGeneration(optimisticTempId, null)
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
          ts('videoUi.grokSceneLine', { scene }),
        )
      if (motion) parts.push(ts('videoUi.grokMotionLine', { motion }))
      setMotionStep1Preview(parts.length > 0 ? parts.join('\n\n—\n\n') : null)
    }
    setMotionDesc((prev) => {
      if (prev.trim()) return prev
      const notes = motionFrameNotes.trim()
      if (notes) return notes
      return ts('runtime.motionRefHint')
    })
  }

  const callMotionFirstFrameApi = async (
    useStillFinalEffective: boolean,
  ): Promise<
    | { ok: true; data: MotionFirstFrameApiData }
    | { ok: false; data: MotionFirstFrameApiData; response: Response }
  > => {
    const fd = new FormData()
    const sendArchiveStill =
      motionFrameArchiveId != null && !motionVideoFile && !motionFirstFrameFile
    if (sendArchiveStill) {
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
            ts('runtime.frameGenerating'),
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
    if (scene) parts.push(ts('videoUi.grokFrameLine', { scene }))
    if (timeline) parts.push(ts('videoUi.grokMotionLine', { motion: timeline }))
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
      return ts('runtime.motionRefHintShort')
    })
  }

  const runMotionComposeVideoPrompt = async () => {
    setError(null)
    if (!motionVideoFileId) {
      setError(ts('runtime.needRefVideo'))
      return
    }
    if (studioSelectedModelId == null) {
      setError(ts('runtime.selectModel'))
      return
    }
    if (
      motionPreviewGenId == null &&
      motionFrameArchiveId == null &&
      !motionFirstFrameFile
    ) {
      setError(ts('runtime.needFrame'))
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
      setError(ts('runtime.needVideoOrFrame'))
      return
    }
    if (motionAutoPrompt && !motionVideoFile) {
      setError(
        ts('runtime.needVideoForMotion'),
      )
      return
    }
    if (studioSelectedModelId == null) {
      setError(ts('runtime.selectModel'))
      return
    }
    setMotionBusyFrame(true)
    setMotionMsg(null)
    setMotionResultVideoUrl(null)
    setMotionAutoTextPreview(null)
    setMotionStep1Preview(null)
    setMotionGrokTimeline(null)
    setMotionPendingExternalStillUrl(null)
    const { item: optimisticFrame, tempId: optimisticFrameTempId } = studioArchiveOptimisticOpts(
      'image',
      motionFrameNotes.trim() || ts('videoUi.frameBusy'),
    )
    pushOptimisticStudioGeneration(optimisticFrame)
    try {
      const res = await callMotionFirstFrameApi(
        !!(motionUseStillFinal && motionFirstFrameFile),
      )
      if (!res.ok) {
        resolveOptimisticStudioGeneration(optimisticFrameTempId, null)
        setError(formatHttpApiError(res.response, res.data))
        return
      }
      const frameGid =
        typeof res.data.generation_id === 'number' ? res.data.generation_id : null
      resolveOptimisticStudioGeneration(optimisticFrameTempId, frameGid)
      applyMotionFirstFrameResponse(res.data)
      void refreshMe()
      void syncStudioArchivePending()
    } catch (e) {
      resolveOptimisticStudioGeneration(optimisticFrameTempId, null)
      setError(formatClientFetchError(e, true))
    } finally {
      setMotionBusyFrame(false)
    }
  }

  const runMotionRenderVideo = async () => {
    setError(null)
    if (studioSelectedModelId == null) {
      setError(ts('runtime.needModelWithPhotos'))
      return
    }
    if (!motionDesc.trim()) {
      setError(ts('runtime.needT2vPrompt'))
      return
    }
    if (motionPreviewGenId == null) {
      setError(ts('runtime.needFirstFramePick'))
      return
    }

    setMotionBusyVideo(true)
    setMotionResultVideoUrl(null)
    const { item: optimisticVideo, tempId: optimisticVideoTempId } = studioArchiveOptimisticOpts(
      'video',
      motionDesc.trim(),
    )
    pushOptimisticStudioGeneration(optimisticVideo)
    try {
      const fd = new FormData()
      fd.append('model_id', String(studioSelectedModelId))
      fd.append('prompt', motionDesc.trim())
      fd.append('output_aspect', studioOutputAspect)
      fd.append('negative_prompt', motionVideoNegPrompt.trim())
      fd.append('generate_audio', motionKeepSound ? '1' : '0')
      fd.append('duration_seconds', String(motionSeedanceDuration))
      fd.append('seedance_variant', motionSeedanceVariant)
      fd.append('video_resolution', motionVideoResolution)
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
      const accepted = await postStudioJobStart('/api/studio/motion/render-video', {
        method: 'POST',
        body: fd,
      })
      const videoGid =
        typeof accepted.generation_id === 'number' ? accepted.generation_id : null
      resolveOptimisticStudioGeneration(optimisticVideoTempId, videoGid)
      setMotionResultVideoUrl(null)
      setMotionMsg(
        ts('runtime.videoGenerating'),
      )
      void refreshMe()
      void syncStudioArchivePending()
      void refreshMotionRenders()
    } catch (e) {
      resolveOptimisticStudioGeneration(optimisticVideoTempId, null)
      setError(formatClientFetchError(e, true))
      void refreshMotionRenders()
    } finally {
      setMotionBusyVideo(false)
    }
  }

  const upscaleStudioGeneration = async () => {
    if (studioGenGenerationId == null) {
      setError(ts('runtime.openFromArchive'))
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
        setStudioWavespeedMsg(data.message?.trim() || ts('runtime.upscaleFailed'))
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
      setError(ts('runtime.needResultFrame'))
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
        setStudioWavespeedMsg(ts('runtime.carouselSaved', { count: items.length, note }))
      } else if (items.length > 0) {
        setStudioWavespeedMsg(
          ts('runtime.carouselAdded', { count: items.length }),
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
      setError(ts('runtime.wsKeyPersonal'))
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
      setError(ts('runtime.wsKeyPro'))
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
      setError(ts('runtime.needModelPhotos', { max: STUDIO_MODEL_MAX_IMAGES }))
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
      setError(ts('runtime.needModelName'))
      return
    }
    const lt = newModelExportLat.trim()
    const ln = newModelExportLon.trim()
    if ((lt && !ln) || (!lt && ln)) {
      setError(ts('runtime.geoBothOrNone'))
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
      setError(ts('runtime.geoBothOrNone'))
      return
    }
    let export_lat: number | null = null
    let export_lon: number | null = null
    if (lt && ln) {
      export_lat = parseFloat(lt.replace(',', '.'))
      export_lon = parseFloat(ln.replace(',', '.'))
      if (Number.isNaN(export_lat) || Number.isNaN(export_lon)) {
        setError(ts('runtime.geoInvalid'))
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
          companion_persona: companionPersonaToApi(d.companion_persona),
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

  const patchPlatformConnection = async (
    platform: 'telegram' | 'fanvue' | 'instagram' | 'tribute',
    connectionId: number,
    patch: {
      label?: string | null
      studio_model_id?: number | null
      companion_mode?: string
      companion_delay_min_sec?: number
      companion_delay_max_sec?: number
      companion_max_replies_per_hour?: number
    },
  ) => {
    setError(null)
    const r = await apiFetch(`/api/integrations/${platform}/${connectionId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatHttpApiError(r, j))
      return false
    }
    setInteg((await r.json()) as IntegrationStatus)
    return true
  }

  const saveTelegram = async (connectionId?: number | null) => {
    setError(null)
    const tok = tgToken.trim()
    if (tok.length < 15) {
      setError(ts('runtime.tgTokenShort'))
      return
    }
    const body: Record<string, unknown> = { bot_token: tok }
    const cid = connectionId ?? tgEditConnectionId
    if (cid != null) body.connection_id = cid
    const label = tgDraftLabel.trim()
    if (label) body.label = label
    if (tgDraftModelId !== '') body.studio_model_id = tgDraftModelId
    const r = await apiFetch('/api/integrations/telegram', {
      method: 'PUT',
      body: JSON.stringify(body),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatHttpApiError(r, j))
      return
    }
    setTgToken('')
    setTgDraftLabel('')
    setTgDraftModelId('')
    setTgEditConnectionId(null)
    setInteg((await r.json()) as IntegrationStatus)
    void refreshMe()
  }

  const connectFanvueOAuth = async (connectionId?: number | null) => {
    setError(null)
    setFvBusy(true)
    try {
      const body: Record<string, unknown> = {}
      if (connectionId != null) body.connection_id = connectionId
      if (fvDraftModelId !== '') body.studio_model_id = fvDraftModelId
      const r = await apiFetch('/api/integrations/fanvue/oauth/start', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      const j = (await r.json()) as { authorize_url?: string }
      if (!j.authorize_url) {
        setError(ts('runtime.fanvueEmptyAuth'))
        return
      }
      window.location.href = j.authorize_url
    } finally {
      setFvBusy(false)
    }
  }

  const disconnectFanvue = async (connectionId: number) => {
    setError(null)
    setFvSyncNote(null)
    setFvBusy(true)
    try {
      const r = await apiFetch(`/api/integrations/fanvue?connection_id=${connectionId}`, {
        method: 'DELETE',
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      setInteg((await r.json()) as IntegrationStatus)
      void refreshMe()
    } finally {
      setFvBusy(false)
    }
  }

  const syncFanvueHistory = async (connectionId: number) => {
    setError(null)
    setFvSyncNote(null)
    setFvBusy(true)
    try {
      const r = await apiFetch(`/api/integrations/fanvue/sync?connection_id=${connectionId}`, {
        method: 'POST',
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      const j = (await r.json()) as {
        chats_processed?: number
        messages_imported?: number
        messages_skipped?: number
        errors?: string[]
      }
      const imported = j.messages_imported ?? 0
      const chats = j.chats_processed ?? 0
      const skipped = j.messages_skipped ?? 0
      setFvSyncNote(
        tc('import.historyLoaded', {
          imported,
          chats,
          skipped: skipped ? tc('import.skipped', { count: skipped }) : '',
          warnings: j.errors?.length ? tc('import.warnings', { count: j.errors.length }) : '',
        }),
      )
    } finally {
      setFvBusy(false)
    }
  }

  const copyFanvueWebhookUrl = async () => {
    const url = integ?.fanvue_webhook_url
    if (!url) return
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      setError(ts('runtime.webhookCopyFailed'))
    }
  }

  const connectInstagramOAuth = async (connectionId?: number | null) => {
    setError(null)
    setIgBusy(true)
    try {
      const body: Record<string, unknown> = {}
      if (connectionId != null) body.connection_id = connectionId
      if (igDraftModelId !== '') body.studio_model_id = igDraftModelId
      const r = await apiFetch('/api/integrations/instagram/oauth/start', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      const j = (await r.json()) as { authorize_url?: string }
      if (!j.authorize_url) {
        setError(ts('runtime.igEmptyAuth'))
        return
      }
      window.location.href = j.authorize_url
    } finally {
      setIgBusy(false)
    }
  }

  const disconnectInstagram = async (connectionId: number) => {
    setError(null)
    setIgBusy(true)
    try {
      const r = await apiFetch(`/api/integrations/instagram?connection_id=${connectionId}`, {
        method: 'DELETE',
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      setInteg((await r.json()) as IntegrationStatus)
      void refreshMe()
    } finally {
      setIgBusy(false)
    }
  }

  const saveTribute = async (connectionId?: number | null) => {
    setError(null)
    const key = tributeApiKey.trim()
    if (key.length < 8) {
      setError(ts('runtime.tributeKey'))
      return
    }
    const body: Record<string, unknown> = { api_key: key }
    const cid = connectionId ?? tributeEditConnectionId
    if (cid != null) body.connection_id = cid
    const label = tributeDraftLabel.trim()
    if (label) body.label = label
    if (tributeDraftModelId !== '') body.studio_model_id = tributeDraftModelId
    const r = await apiFetch('/api/integrations/tribute', {
      method: 'PUT',
      body: JSON.stringify(body),
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatHttpApiError(r, j))
      return
    }
    setTributeApiKey('')
    setTributeDraftLabel('')
    setTributeDraftModelId('')
    setTributeEditConnectionId(null)
    setInteg((await r.json()) as IntegrationStatus)
    void refreshTributeEarnings()
  }

  const disconnectTribute = async (connectionId: number) => {
    setError(null)
    const r = await apiFetch(`/api/integrations/tribute?connection_id=${connectionId}`, {
      method: 'DELETE',
    })
    if (!r.ok) {
      const j = await r.json().catch(() => ({}))
      setError(formatHttpApiError(r, j))
      return
    }
    setInteg((await r.json()) as IntegrationStatus)
    void refreshTributeEarnings()
  }

  const copyTributeWebhookUrl = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      setError(ts('runtime.webhookCopyFailed'))
    }
  }

  const createWorkspaceMember = async () => {
    setError(null)
    const login = newTeamLogin.trim().toLowerCase()
    if (login.length < 3) {
      setError(ts('runtime.memberLoginShort'))
      return
    }
    if (newTeamPassword.length < 8) {
      setError(ts('runtime.memberPasswordShort'))
      return
    }
    setTeamBusy(true)
    try {
      const shareRaw = newTeamTributeShare.trim()
      let tributeSharePercent: number | undefined
      if (shareRaw !== '') {
        const n = Number(shareRaw)
        if (!Number.isFinite(n) || n < 0 || n > 100) {
          setError(ts('runtime.tributeShareInvalid'))
          return
        }
        tributeSharePercent = Math.round(n)
      }
      const r = await apiFetch('/api/workspace/members', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          member_login: login,
          password: newTeamPassword,
          permissions_mask: newTeamMask,
          allowed_studio_model_ids: newTeamModelIds,
          ...(tributeSharePercent !== undefined ? { tribute_share_percent: tributeSharePercent } : {}),
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
      setNewTeamTributeShare('20')
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
      setError(ts('runtime.memberPasswordNew'))
      return
    }
    setTeamBusy(true)
    try {
      const modelIds = memberModelEdits[row.id] ?? row.allowed_studio_model_ids ?? []
      const shareRaw = (memberTributeEdits[row.id] ?? String(row.tribute_share_percent)).trim()
      const n = Number(shareRaw)
      if (!Number.isFinite(n) || n < 0 || n > 100) {
        setError(ts('runtime.tributeShareInvalid'))
        return
      }
      const body: {
        permissions_mask: number
        password?: string
        allowed_studio_model_ids: number[]
        tribute_share_percent: number
      } = {
        permissions_mask: mask,
        allowed_studio_model_ids: modelIds,
        tribute_share_percent: Math.round(n),
      }
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
    if (!window.confirm(ts('runtime.deleteMemberConfirm'))) return
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

  const startTributePayment = async (
    product: BillingPlanRow['product'],
    creditsQuantity?: number,
  ) => {
    setError(null)
    setTributePayBusy(product)
    try {
      const body =
        product === 'credits_pack'
          ? { product, credits_quantity: creditsQuantity }
          : { product }
      const r = await apiFetch('/api/billing/tribute/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return
      }
      const data = (await r.json()) as {
        payment_url: string
        telegram_deep_link?: string | null
      }
      openPaymentUrl(data.payment_url, { telegramDeepLink: data.telegram_deep_link })
    } finally {
      setTributePayBusy(null)
    }
  }

  if (!authReady) {
    return (
      <div className="app">
        <div className="app-bg" aria-hidden />
        <p className="muted" style={{ padding: '2rem' }}>
          {tAuth('loading')}
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
              <p className="sub">{tAuth('appTagline')}</p>
            </div>
          </div>
          <AppLanguageSwitcher />
        </header>
        <nav
          aria-label={tAuth('helpNavAria')}
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
            {tAuth('home')}
          </Link>
          <Link to="/pricing" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            {tAuth('pricing')}
          </Link>
          <Link to="/faq" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            {tAuth('faq')}
          </Link>
          <Link to="/privacy" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            {tAuth('privacy')}
          </Link>
          <Link to="/terms" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            {tAuth('terms')}
          </Link>
          <Link to="/login" className="ghost-btn" style={{ padding: '0.35rem 0.75rem', fontSize: 'inherit' }}>
            {tAuth('loginPageLink')}
          </Link>
        </nav>
        <main className="auth-page">
          <AuthPanel
            onSuccess={async (fromRegister?: boolean) => {
              const r = await apiFetch('/api/auth/me')
              let user: UserMe | null = null
              if (r.ok) {
                user = (await r.json()) as UserMe
                setMe(user)
              }
              setAuthed(true)
              if (fromRegister) {
                markFirstGenWizardPending()
                const paywalled =
                  user != null &&
                  (user.billing_require_active_subscription ?? true) &&
                  !studioAccessAllowed(user) &&
                  !user.is_platform_admin
                if (!paywalled) {
                  clearFirstGenWizardPending()
                  setFirstGenWizardOpen(true)
                }
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
    'layout--chat',
    isMobileLayout ? 'mobile' : '',
    isMobileLayout && selectedId != null ? 'thread-focus' : '',
    selected && !isMobileLayout ? 'layout--chat-with-notes' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const appClass = [
    'app',
    hasAnyMainSection ? 'app--shell' : '',
    appSection === 'chat' && canChat ? 'app--chat' : '',
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
    if (convId != null) selectConversation(convId)
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
                {t('billingReturn.goBilling')}
              </button>
            ) : null}
            <button type="button" className="ghost-btn" onClick={clearBillingQuery}>
              {tCommon('close')}
            </button>
          </div>
        </div>
      ) : null}
      {creatorDonationAlert && isOwner ? (
        <CreatorDonationAlertBanner
          event={creatorDonationAlert}
          onOpen={openCreatorDonations}
          onDismiss={dismissCreatorDonationAlert}
        />
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
              aria-label={tc('dock.backAria')}
            >
              <span aria-hidden>‹</span>
            </button>
            <div
              className="thread-mobile-dock-scroll"
              role="tablist"
              aria-label={tc('dock.otherDialogsAria')}
            >
              {filteredConversations.map((c) => (
                <ChatStripItem
                  key={c.id}
                  conv={c}
                  active={c.id === selectedId}
                  onSelect={() => selectConversation(c.id)}
                />
              ))}
            </div>
          </div>
        </header>
      ) : null}
      {error && !accountOpen && !firstGenWizardOpen ? (
        <div className="banner error" role="alert">
          {error}
        </div>
      ) : null}

      <FirstGenWizard
        open={firstGenWizardOpen}
        ownerId={me?.id ?? 0}
        studioNeedsUserWsKey={studioNeedsUserWsKey}
        workflowDemoLimited={Boolean(me?.workflow_demo_limited)}
        onClose={() => setFirstGenWizardOpen(false)}
        onOpenIntegrations={() => {
          setAccountTab('integrations')
          setAccountOpen(true)
          trackFunnelEvent('integrations_opened')
        }}
        onComplete={() => {
          if (me) markFirstGenWizardDoneForUser(me.id)
          markSetupTourHadGeneration()
          setSetupTourHadGen(true)
          setAppSection('studio')
          trackFunnelEvent('studio_opened')
          void loadStudioModels()
          void loadStudioGenerationsReset()
          void refreshMe()
        }}
        onModelSaved={() => {
          void loadStudioModels()
        }}
      />

      {!hasAnyMainSection ? (
        <div className="banner info" style={{ margin: '0 1rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <span>{t('cabinet.noAccessBanner')}</span>
          <button type="button" className="ghost-btn" onClick={() => setAccountOpen(true)}>
            {t('accessDenied.openCabinet')}
          </button>
        </div>
      ) : null}

      {accountOpen && (
        <div className="account-panel account-panel--mm">
          <header className="mm-cabinet-header">
            <button
              type="button"
              className="mm-cabinet-header-back"
              onClick={() => setAccountOpen(false)}
              aria-label={t('cabinet.closeAria')}
            >
              ‹
            </button>
            <div className="mm-cabinet-header-brand">
              <div className="mm-cabinet-header-logo" aria-hidden>
                M
              </div>
              <div>
                <div className="mm-cabinet-header-title">{t('cabinet.title')}</div>
                <div className="mm-cabinet-header-meta">
                  {cabinetAccountMeta.emailLine} · {cabinetAccountMeta.roleLine}
                </div>
              </div>
            </div>
            <div className="mm-cabinet-header-spacer" />
            <div className="mm-cabinet-header-credits">
              <span className="mm-cabinet-header-credits-icon" aria-hidden>
                ◆
              </span>
              <span className="mm-cabinet-header-credits-value">
                {formatAppNumber(me?.credits_balance ?? 0)}
              </span>
              <span className="mm-cabinet-header-credits-unit">{t('cabinet.creditsUnit')}</span>
            </div>
            <AppLanguageSwitcher className="mm-lang-switch mm-lang-switch--compact mm-cabinet-lang" />
            <div className="mm-cabinet-header-avatar" aria-hidden>
              {cabinetAccountMeta.initial}
            </div>
          </header>

          <div className="mm-cabinet-body">
            <div className="mm-cabinet-page-head">
              <div className="mm-cabinet-page-kicker">{t('cabinet.kicker')}</div>
              <h1 className="mm-cabinet-page-title">{t('cabinet.title')}</h1>
            </div>

            {error ? (
              <div className="account-panel-error banner error" role="alert">
                {error}
              </div>
            ) : null}

            <div className="mm-cabinet-tabs-wrap">
              <div className="account-cabinet-tabs" role="tablist" aria-label={t('cabinet.tabsAria')}>
                <button
                  type="button"
                  role="tab"
                  aria-selected={accountTab === 'overview'}
                  className={accountTab === 'overview' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                  onClick={() => setAccountTab('overview')}
                >
                  <span className="account-cabinet-tab__icon" aria-hidden>
                    ▦
                  </span>
                  <span>{t('cabinet.tabOverview')}</span>
                </button>
                {isOwner ? (
                  <button
                    type="button"
                    role="tab"
                    aria-selected={accountTab === 'billing'}
                    className={accountTab === 'billing' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                    onClick={() => setAccountTab('billing')}
                  >
                    <span className="account-cabinet-tab__icon" aria-hidden>
                      ◈
                    </span>
                    <span>{t('cabinet.tabBilling')}</span>
                  </button>
                ) : null}
                {isOwner ? (
                  <button
                    type="button"
                    role="tab"
                    aria-selected={accountTab === 'donations'}
                    className={accountTab === 'donations' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                    onClick={() => setAccountTab('donations')}
                  >
                    <span className="account-cabinet-tab__icon" aria-hidden>
                      ♡
                    </span>
                    <span>{t('cabinet.tabDonations')}</span>
                  </button>
                ) : null}
                <button
                  type="button"
                  role="tab"
                  aria-selected={accountTab === 'integrations'}
                  className={accountTab === 'integrations' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                  onClick={() => setAccountTab('integrations')}
                >
                  <span className="account-cabinet-tab__icon" aria-hidden>
                    ⎔
                  </span>
                  <span>{t('cabinet.tabConnections')}</span>
                </button>
                {canStudioModels ? (
                  <button
                    type="button"
                    role="tab"
                    aria-selected={accountTab === 'models'}
                    className={accountTab === 'models' ? 'account-cabinet-tab active' : 'account-cabinet-tab'}
                    onClick={() => setAccountTab('models')}
                  >
                    <span className="account-cabinet-tab__icon" aria-hidden>
                      ◉
                    </span>
                    <span>{t('cabinet.tabModels')}</span>
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
                    <span className="account-cabinet-tab__icon" aria-hidden>
                      ⚇
                    </span>
                    <span>{t('cabinet.tabTeam')}</span>
                  </button>
                ) : null}
              </div>
            </div>

            <div className="mm-cabinet-content">
          {accountTab === 'overview' && (
            <div className="account-cabinet-pane cabinet-overview" role="tabpanel">
              <p className="cabinet-lead muted">{t('cabinet.overviewIntro')}</p>
              <div className="cabinet-dashboard-grid">
                <div className="cabinet-dash-card">
                  <div className="cabinet-dash-label">{t('cabinet.creditBalance')}</div>
                  <div className="cabinet-dash-value">{me?.credits_balance ?? '—'}</div>
                  <p className="cabinet-dash-hint muted">{t('cabinet.creditBalanceHint')}</p>
                </div>
                <div className="cabinet-dash-card">
                  <div className="cabinet-dash-label">{t('cabinet.planLabel')}</div>
                  <div className="cabinet-dash-value">{planDisplayShort(me)}</div>
                  <p className="cabinet-dash-hint muted">{planDisplayLong(me)}</p>
                </div>
                <div className="cabinet-dash-card">
                  <div className="cabinet-dash-label">{t('cabinet.operatorsLabel')}</div>
                  <div className="cabinet-dash-value">{me?.operators_count ?? 0}</div>
                  <p className="cabinet-dash-hint muted">{t('cabinet.operatorsHint')}</p>
                </div>
                <div className="cabinet-dash-card">
                  <div className="cabinet-dash-label">{t('cabinet.subscriptionLabel')}</div>
                  <div className="cabinet-dash-value">{subscriptionStatusLabel(me?.subscription_status)}</div>
                  <p className="cabinet-dash-hint muted">
                    {me?.subscription_period_end
                      ? t('cabinet.subscriptionUntil', { date: formatDateTimeApp(me.subscription_period_end) })
                      : t('cabinet.subscriptionNeedPlan')}
                  </p>
                </div>
                {isOwner && platformDonationsDisplay.visible ? (
                  <div className="cabinet-dash-card">
                    <div className="cabinet-dash-label">{t('overview.platformDonations')}</div>
                    <div className="cabinet-dash-value">{platformDonationsDisplay.label ?? '—'}</div>
                    <p className="cabinet-dash-hint muted">{platformDonationsDisplay.hint}</p>
                    <button
                      type="button"
                      className="ghost-btn"
                      style={{ marginTop: '0.5rem' }}
                      onClick={openCreatorDonations}
                    >
                      {t('overview.openDonations')}
                    </button>
                  </div>
                ) : null}
              </div>
              {(me?.demo_generations_remaining ?? 0) > 0 &&
              me?.billing_require_active_subscription &&
              normalizeBillingPlan(me.billing_plan) === 'credits' ? (
                <div className="banner info" style={{ marginTop: '1rem' }}>
                  <Trans
                    i18nKey="cabinet.demoBanner"
                    ns="workspace"
                    values={{
                      remaining: me.demo_generations_remaining,
                      grant: me.demo_generations_grant ?? 3,
                    }}
                    components={{ strong: <strong /> }}
                  />
                </div>
              ) : me?.billing_require_active_subscription && !studioAccessAllowed(me) ? (
                <div className="banner info" style={{ marginTop: '1rem' }}>
                  <Trans
                    i18nKey="cabinet.studioSubRequired"
                    ns="workspace"
                    values={{ status: subscriptionStatusLabel(me?.subscription_status) }}
                    components={{ strong: <strong /> }}
                  />
                </div>
              ) : null}
              {isOwner && me?.email_setup_required ? (
                <div className="banner warn" style={{ marginTop: '1rem' }}>
                  <OwnerEmailCompleteForm
                    onError={setError}
                    onSuccess={async () => {
                      setError(null)
                      await refreshMe()
                    }}
                  />
                </div>
              ) : null}
              {isOwner ? (
                <div className="cabinet-identity-block" style={{ marginTop: '1.25rem' }}>
                  <h4 className="account-sub">{t('cabinet.telegramTitle')}</h4>
                  {me?.telegram_linked ? (
                    <p className="muted">
                      {t('cabinet.telegramLinked', {
                        username: me.telegram_username
                          ? t('cabinet.telegramLinkedUser', { username: me.telegram_username })
                          : '',
                      })}
                    </p>
                  ) : health?.telegram_login_configured && health.telegram_login_bot_username ? (
                    <>
                      <p className="muted" style={{ marginBottom: '0.75rem' }}>
                        {t('cabinet.telegramLinkHint')}
                      </p>
                      <TelegramLoginButton
                        botUsername={health.telegram_login_bot_username}
                        mode="link"
                        onError={setError}
                        onSuccess={async () => {
                          setError(null)
                          await refreshMe()
                        }}
                      />
                    </>
                  ) : (
                    <p className="muted">{t('cabinet.telegramNotConfigured')}</p>
                  )}
                  {me?.telegram_linked && me.public_email ? (
                    <button
                      type="button"
                      className="ghost-btn"
                      style={{ marginTop: '0.75rem' }}
                      onClick={() =>
                        void (async () => {
                          if (!window.confirm(t('cabinet.telegramUnlinkConfirm'))) return
                          const r = await apiFetch('/api/auth/telegram/link', { method: 'DELETE' })
                          if (!r.ok) {
                            const j = await r.json().catch(() => ({}))
                            setError(formatHttpApiError(r, j))
                            return
                          }
                          await refreshMe()
                        })()
                      }
                    >
                      {t('cabinet.telegramUnlink')}
                    </button>
                  ) : null}
                </div>
              ) : null}
              <div className="cabinet-overview-actions">
                {isOwner ? (
                  <button type="button" className="ghost-btn" onClick={() => setAccountTab('billing')}>
                    {t('cabinet.goBilling')}
                  </button>
                ) : null}
                <button type="button" className="ghost-btn" onClick={() => setAccountTab('integrations')}>
                  {t('cabinet.goConnections')}
                </button>
                {isOwner ? (
                  <button type="button" className="ghost-btn" onClick={() => setAccountTab('team')}>
                    {t('cabinet.goTeam')}
                  </button>
                ) : null}
                {canPlatformAdmin ? (
                  <Link to="/admin" className="ghost-btn cabinet-admin-link">
                    {t('cabinet.adminPanel')}
                  </Link>
                ) : null}
              </div>
            </div>
          )}

          {accountTab === 'billing' && isOwner && (
            <div className="account-cabinet-pane" role="tabpanel">
              <p className="cabinet-lead muted">
                <Trans i18nKey="cabinet.billing.lead1" ns="workspace" components={{ strong: <strong /> }} />
              </p>
              <p className="cabinet-lead muted">
                <Trans i18nKey="cabinet.billing.lead2" ns="workspace" components={{ strong: <strong /> }} />
              </p>
              <div className="cabinet-module cabinet-module--highlight">
                <div className="cabinet-module-head">
                  <span className="cabinet-module-title">{t('cabinet.billing.currentState')}</span>
                  <span
                    className={`cabinet-module-badge ${me?.subscription_status === 'active' ? 'is-ok' : 'is-warn'}`}
                  >
                    {subscriptionStatusLabel(me?.subscription_status)}
                  </span>
                </div>
                <p className="cabinet-module-body">{planDisplayLong(me)}</p>
                <p className="muted cabinet-module-meta">
                  {me?.subscription_period_end
                    ? t('cabinet.billing.periodUntil', {
                        date: formatDateTimeApp(me.subscription_period_end),
                      })
                    : t('cabinet.billing.periodAfterPay')}
                  {' · '}
                  <Trans
                    i18nKey="cabinet.billing.balanceLine"
                    ns="workspace"
                    values={{ balance: me?.credits_balance ?? 0 }}
                    components={{ strong: <strong /> }}
                  />
                </p>
                {me?.plan_usage ? (
                  <ul className="muted small" style={{ margin: '0.75rem 0 0', paddingLeft: '1.1rem' }}>
                    <li>
                      {t('cabinet.billing.usageUsers', {
                        current: me.plan_usage.users,
                        max: me.plan_usage.limits.max_users,
                      })}
                    </li>
                    <li>
                      {t('cabinet.billing.usageModels', {
                        current: me.plan_usage.models,
                        max: me.plan_usage.limits.max_models,
                      })}
                    </li>
                    <li>
                      {t('cabinet.billing.usageDialogs', {
                        current: me.plan_usage.dialogs_this_month,
                        limit:
                          me.plan_usage.limits.max_dialogs_per_month != null
                            ? t('cabinet.billing.usageDialogsLimit', {
                                max: me.plan_usage.limits.max_dialogs_per_month,
                              })
                            : t('cabinet.billing.usageDialogsUnlimited'),
                      })}
                    </li>
                  </ul>
                ) : null}
              </div>
              {referralInfo ? (
                <div className="cabinet-module" style={{ marginBottom: '1rem' }}>
                  <div className="cabinet-module-head">
                    <span className="cabinet-module-title">{t('cabinet.billing.referralTitle')}</span>
                  </div>
                  <p className="cabinet-module-body muted small">
                    <Trans
                      i18nKey="cabinet.billing.referralBody"
                      ns="workspace"
                      values={{
                        friendCredits: referralInfo.friend_referral_credits,
                        reward: referralInfo.referrer_reward_summary,
                        earned:
                          referralInfo.credits_earned > 0
                            ? t('cabinet.billing.referralEarned', {
                                amount: referralInfo.credits_earned,
                              })
                            : '',
                        rubPerCredit: referralInfo.credit_unit_price_rub,
                      }}
                      components={{ strong: <strong /> }}
                    />
                  </p>
                  <p className="mono small" style={{ wordBreak: 'break-all' }}>
                    {referralInfo.referral_link}
                  </p>
                  <p className="muted small">
                    {t('cabinet.billing.referralStats', {
                      invited: referralInfo.invited_count,
                      earned: referralInfo.credits_earned,
                    })}
                  </p>
                </div>
              ) : null}
              <h4 className="account-sub">{t('cabinet.billing.plansTitle')}</h4>
              {me?.tribute_billing_available && !me?.telegram_linked ? (
                <div className="banner info" style={{ marginBottom: '0.75rem' }}>
                  {t('cabinet.billing.tributeNeedTelegram')}
                </div>
              ) : null}
              {me?.online_payment_available || me?.tribute_billing_available ? (
                <>
                  {me?.online_payment_available ? (
                    <p className="muted" style={{ marginBottom: '0.75rem' }}>
                      {t('cabinet.billing.cardPayHint')}
                    </p>
                  ) : null}
                  {me?.tribute_billing_available ? (
                    <p className="muted" style={{ marginBottom: '0.75rem' }}>
                      {t('cabinet.billing.tributePayHint')}
                    </p>
                  ) : null}
                  <div className="mkt-pricing-toggles" style={{ marginBottom: '0.75rem' }}>
                    <button
                      type="button"
                      className={billingPayMode === 'pro' ? 'mkt-toggle active' : 'mkt-toggle'}
                      onClick={() => setBillingPayMode('pro')}
                    >
                      Pro
                    </button>
                    <button
                      type="button"
                      className={billingPayMode === 'standard' ? 'mkt-toggle active' : 'mkt-toggle'}
                      onClick={() => setBillingPayMode('standard')}
                    >
                      Standard
                    </button>
                    <button
                      type="button"
                      className={billingPayPeriod === 'month' ? 'mkt-toggle active' : 'mkt-toggle'}
                      onClick={() => setBillingPayPeriod('month')}
                    >
                      {t('cabinet.billing.month')}
                    </button>
                    <button
                      type="button"
                      className={billingPayPeriod === 'year' ? 'mkt-toggle active' : 'mkt-toggle'}
                      onClick={() => setBillingPayPeriod('year')}
                    >
                      {t('cabinet.billing.year')}
                    </button>
                  </div>
                  <div className="cabinet-yookassa-rows">
                    {billingPlanRows
                      .filter((row) => {
                        if (row.product === 'credits_pack') {
                          const plan = normalizeBillingPlan(me?.billing_plan)
                          return plan === 'credits' || plan === 'standard'
                        }
                        const m = row.product.match(/^sub_(standard|pro)_(solo|pro|studio)_(month|year)$/)
                        if (!m) return false
                        return m[1] === billingPayMode && m[3] === billingPayPeriod
                      })
                      .map((row) => {
                      if (row.product === 'credits_pack' && row.credits_pricing) {
                        const packOk = canPurchaseCredits(me)
                        if (!packOk) {
                          return (
                            <div key={row.product} className="cabinet-yookassa-row">
                              <div>
                                <div className="cabinet-offer-title">{row.title}</div>
                                <p className="muted small" style={{ margin: '0.35rem 0 0' }}>
                                  {t('cabinet.billing.creditsPackUnavailable')}
                                </p>
                              </div>
                              <button type="button" className="send-btn" disabled>
                                {t('cabinet.billing.unavailable')}
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
                                {t('cabinet.billing.creditsPricing', {
                                  min: p.min_quantity,
                                  unit: p.unit_price_rub.toLocaleString('ru-RU', {
                                    minimumFractionDigits: 0,
                                    maximumFractionDigits: 2,
                                  }),
                                  bulkFrom: p.bulk_from,
                                  bulkUnit: p.bulk_unit_price_rub.toLocaleString('ru-RU', {
                                    minimumFractionDigits: 0,
                                    maximumFractionDigits: 2,
                                  }),
                                })}
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
                                {t('cabinet.billing.creditsQtyLabel')}
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
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
                              {me?.online_payment_available ? (
                                <button
                                  type="button"
                                  className="send-btn"
                                  disabled={anyBillingPayBusy || !valid}
                                  onClick={() => void startYookassaPayment('credits_pack', q)}
                                >
                                  {yookassaPayBusy === row.product ? '…' : t('cabinet.billing.payCard')}
                                </button>
                              ) : null}
                              {me?.tribute_billing_available ? (
                                <button
                                  type="button"
                                  className={me?.online_payment_available ? 'ghost-btn' : 'send-btn'}
                                  disabled={
                                    anyBillingPayBusy || !valid || !me.telegram_linked
                                  }
                                  title={
                                    me.telegram_linked
                                      ? t('cabinet.billing.tributeTitleIntl')
                                      : t('cabinet.billing.tributeNeedTelegramShort')
                                  }
                                  onClick={() => void startTributePayment('credits_pack', q)}
                                >
                                  {tributePayBusy === row.product ? '…' : t('cabinet.billing.payTribute')}
                                </button>
                              ) : null}
                            </div>
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
                              {t('cabinet.billing.subOrCredits', {
                                credits: subCredits,
                                rubPerCredit: billingCreditUnitRub,
                                balance,
                              })}
                            </p>
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
                            <button
                              type="button"
                              className="ghost-btn"
                              disabled={anyBillingPayBusy || !canPayCredits}
                              title={
                                canPayCredits
                                  ? undefined
                                  : t('cabinet.billing.needCredits', { need: subCredits, balance })
                              }
                              onClick={() => void paySubscriptionWithCredits(row.product)}
                            >
                              {yookassaPayBusy === row.product ? '…' : t('cabinet.billing.payCredits')}
                            </button>
                            {me?.online_payment_available ? (
                              <button
                                type="button"
                                className="send-btn"
                                disabled={anyBillingPayBusy}
                                onClick={() => void startYookassaPayment(row.product)}
                              >
                                {yookassaPayBusy === row.product ? '…' : t('cabinet.billing.payCard')}
                              </button>
                            ) : null}
                            {me?.tribute_billing_available ? (
                              <button
                                type="button"
                                className={me?.online_payment_available ? 'ghost-btn' : 'send-btn'}
                                disabled={anyBillingPayBusy || !me.telegram_linked}
                                title={
                                  me.telegram_linked
                                    ? t('cabinet.billing.tributeTitle')
                                    : t('cabinet.billing.tributeNeedTelegramOverview')
                                }
                                onClick={() => void startTributePayment(row.product)}
                              >
                                {tributePayBusy === row.product ? '…' : 'Tribute'}
                              </button>
                            ) : null}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </>
              ) : (
                <p className="muted">{t('cabinet.billing.onlinePayOff')}</p>
              )}
              <h4 className="account-sub">{t('cabinet.billing.historyTitle')}</h4>
              {creditHistoryBusy ? (
                <p className="muted">{t('cabinet.billing.loading')}</p>
              ) : creditHistoryItems.length === 0 ? (
                <p className="muted">{t('cabinet.billing.historyEmpty')}</p>
              ) : (
                <div className="cabinet-table-wrap">
                  <table className="cabinet-table">
                    <thead>
                      <tr>
                        <th>{t('cabinet.billing.historyDate')}</th>
                        <th>{t('cabinet.billing.historyOperation')}</th>
                        <th>{t('cabinet.billing.historyCredits')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {creditHistoryItems.map((row) => (
                        <tr key={row.id}>
                          <td className="mono small">{formatDateTimeApp(row.created_at)}</td>
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
                <p className="muted small">{t('cabinet.billing.historyMore')}</p>
              ) : null}
            </div>
          )}

          {accountTab === 'donations' && isOwner && (
            <CreatorDonationsPanel
              studioModels={studioModels.map((m) => ({ id: m.id, name: m.name }))}
              platformConfigured={Boolean(me?.tribute_billing_available)}
            />
          )}

          {accountTab === 'integrations' && (
            <div className="account-cabinet-pane cabinet-connections" role="tabpanel">
              <p className="cabinet-lead muted">{t('cabinet.integrations.lead')}</p>

              {studioNeedsUserWsKey && isOwner ? (
                <WavespeedSetupBanner
                  variant="integrations"
                  canConnect={canIntegrations}
                  onOpenIntegrations={openWavespeedIntegrations}
                />
              ) : null}

              <section
                id="cabinet-wavespeed-key"
                className={`cabinet-module${studioNeedsUserWsKey ? ' cabinet-module--highlight' : ''}${wsSetupPulse ? ' cabinet-module--pulse' : ''}`}
              >
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">{t('cabinet.integrations.wavespeed')}</h4>
                  <span className={`cabinet-module-badge ${integ?.wavespeed_configured ? 'is-ok' : 'is-warn'}`}>
                    {integ?.wavespeed_managed_by_platform
                      ? t('cabinet.integrations.badgePlatformKey')
                      : integ?.wavespeed_configured
                        ? t('cabinet.integrations.badgeKeySaved')
                        : t('cabinet.integrations.badgeNoKey')}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  <Trans
                    i18nKey="cabinet.integrations.wavespeedBody"
                    ns="workspace"
                    components={{
                      strong: <strong />,
                      br: <br />,
                      link: (
                        <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                          wavespeed.ai
                        </a>
                      ),
                    }}
                  />
                </p>
                <div className="cabinet-module-form">
                  <label>
                    {t('cabinet.integrations.apiKey')}
                    <input
                      type="password"
                      autoComplete="off"
                      value={wsApiKey}
                      onChange={(e) => setWsApiKey(e.target.value)}
                      placeholder={t('cabinet.integrations.apiKeyPlaceholder')}
                      disabled={!canIntegrations}
                    />
                  </label>
                  <button
                    type="button"
                    className="send-btn"
                    disabled={!canIntegrations}
                    onClick={() => void saveWavespeed()}
                  >
                    {t('cabinet.integrations.save')}
                  </button>
                </div>
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">{t('cabinet.integrations.telegram')}</h4>
                  <span
                    className={`cabinet-module-badge ${integ?.telegram_configured ? 'is-ok' : 'is-warn'}`}
                  >
                    {(integ?.telegram_connections?.length ?? 0) > 0
                      ? t('cabinet.integrations.connectedCount', {
                          count: integ?.telegram_connections?.length ?? 0,
                        })
                      : t('cabinet.integrations.notConnected')}
                  </span>
                </div>
                <p className="muted cabinet-module-body">{t('cabinet.integrations.telegramBody')}</p>
                {(integ?.telegram_connections ?? []).map((conn) => (
                  <div key={conn.id} className="cabinet-module-form">
                    <p className="small mono">
                      {conn.label ? `${conn.label} · ` : ''}@{conn.bot_username ?? '—'}
                      {conn.webhook_registered
                        ? t('cabinet.integrations.webhookActive')
                        : t('cabinet.integrations.webhookPending')}
                    </p>
                    {studioModels.length > 0 ? (
                      <label>
                        {t('cabinet.integrations.model')}
                        <select
                          value={conn.studio_model_id != null ? String(conn.studio_model_id) : ''}
                          disabled={!canIntegrations}
                          onChange={(e) => {
                            const raw = e.target.value
                            void patchPlatformConnection('telegram', conn.id, {
                              studio_model_id: raw ? Number(raw) : null,
                            })
                          }}
                        >
                          <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                          {studioModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <label>
                      {t('cabinet.integrations.aiCompanion')}
                      <select
                        value={conn.companion_mode ?? 'off'}
                        disabled={!canIntegrations}
                        onChange={(e) => {
                          void patchPlatformConnection('telegram', conn.id, {
                            companion_mode: e.target.value,
                          })
                        }}
                      >
                        {COMPANION_MODE_VALUES.map((value) => (
                          <option key={value} value={value}>
                            {companionModeLabel(value)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <p className="small muted">{t('cabinet.integrations.companionHint')}</p>
                    <div className="companion-timing-grid">
                      <label>
                        {t('cabinet.integrations.delayMin')}
                        <input
                          type="number"
                          min={0}
                          max={300}
                          defaultValue={conn.companion_delay_min_sec ?? 5}
                          disabled={!canIntegrations}
                          onBlur={(e) => {
                            const v = Number(e.target.value)
                            if (!Number.isFinite(v)) return
                            void patchPlatformConnection('telegram', conn.id, {
                              companion_delay_min_sec: v,
                            })
                          }}
                        />
                      </label>
                      <label>
                        {t('cabinet.integrations.delayMax')}
                        <input
                          type="number"
                          min={0}
                          max={600}
                          defaultValue={conn.companion_delay_max_sec ?? 45}
                          disabled={!canIntegrations}
                          onBlur={(e) => {
                            const v = Number(e.target.value)
                            if (!Number.isFinite(v)) return
                            void patchPlatformConnection('telegram', conn.id, {
                              companion_delay_max_sec: v,
                            })
                          }}
                        />
                      </label>
                      <label>
                        {t('integrationsExt.telegram.repliesPerHour')}
                        <input
                          type="number"
                          min={1}
                          max={500}
                          defaultValue={conn.companion_max_replies_per_hour ?? 60}
                          disabled={!canIntegrations}
                          onBlur={(e) => {
                            const v = Number(e.target.value)
                            if (!Number.isFinite(v)) return
                            void patchPlatformConnection('telegram', conn.id, {
                              companion_max_replies_per_hour: v,
                            })
                          }}
                        />
                      </label>
                    </div>
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={!canIntegrations}
                      onClick={() => {
                        setTgEditConnectionId(conn.id)
                        setTgDraftLabel(conn.label ?? '')
                        setTgDraftModelId(conn.studio_model_id ?? '')
                      }}
                    >
                      {t('integrationsExt.telegram.updateToken')}
                    </button>
                  </div>
                ))}
                {(integ?.telegram_connections?.length ?? 0) <
                (integ?.max_connections_per_platform ?? 1) ? (
                  <div className="cabinet-module-form">
                    <label>
                      {t('integrationsExt.telegram.botToken')}
                      <input
                        type="password"
                        autoComplete="off"
                        value={tgToken}
                        onChange={(e) => setTgToken(e.target.value)}
                        placeholder={t('integrationsExt.telegram.botTokenPlaceholder')}
                        disabled={!canIntegrations}
                      />
                    </label>
                    {studioModels.length > 0 ? (
                      <label>
                        {t('cabinet.integrations.model')}
                        <select
                          value={tgDraftModelId === '' ? '' : String(tgDraftModelId)}
                          onChange={(e) => {
                            const v = e.target.value
                            setTgDraftModelId(v ? Number(v) : '')
                          }}
                          disabled={!canIntegrations}
                        >
                          <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                          {studioModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <button
                      type="button"
                      className="send-btn"
                      disabled={!canIntegrations}
                      onClick={() => void saveTelegram()}
                    >
                      {tgEditConnectionId != null ? t('integrationsExt.telegram.saveToken') : t('integrationsExt.telegram.addBot')}
                    </button>
                  </div>
                ) : null}
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">Fanvue</h4>
                  <span className={`cabinet-module-badge ${integ?.fanvue_configured ? 'is-ok' : 'is-warn'}`}>
                    {(integ?.fanvue_connections?.length ?? 0) > 0
                      ? t('cabinet.integrations.connectedCount', { count: integ?.fanvue_connections?.length ?? 0 })
                      : t('cabinet.integrations.notConnected')}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  {t('integrationsExt.fanvue.body')}
                </p>
                {(integ?.fanvue_connections ?? []).map((conn) => (
                  <div key={conn.id} className="cabinet-module-form">
                    <p className="small mono">
                      {conn.label ? `${conn.label} · ` : ''}
                      {conn.creator_uuid ? `${conn.creator_uuid.slice(0, 8)}…` : '—'}
                    </p>
                    {studioModels.length > 0 ? (
                      <label>
                        {t('cabinet.integrations.model')}
                        <select
                          value={conn.studio_model_id != null ? String(conn.studio_model_id) : ''}
                          disabled={!canIntegrations}
                          onChange={(e) => {
                            const raw = e.target.value
                            void patchPlatformConnection('fanvue', conn.id, {
                              studio_model_id: raw ? Number(raw) : null,
                            })
                          }}
                        >
                          <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                          {studioModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <label>
                      {t('cabinet.integrations.aiCompanion')}
                      <select
                        value={conn.companion_mode ?? 'off'}
                        disabled={!canIntegrations}
                        onChange={(e) => {
                          void patchPlatformConnection('fanvue', conn.id, {
                            companion_mode: e.target.value,
                          })
                        }}
                      >
                        {COMPANION_MODE_VALUES.map((value) => (
                          <option key={value} value={value}>
                            {companionModeLabel(value)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <p className="small muted">
                      {t('cabinet.integrations.companionHint')}
                    </p>
                    <div className="companion-timing-grid">
                      <label>
                        {t('cabinet.integrations.delayMin')}
                        <input
                          type="number"
                          min={0}
                          max={300}
                          defaultValue={conn.companion_delay_min_sec ?? 5}
                          disabled={!canIntegrations}
                          onBlur={(e) => {
                            const v = Number(e.target.value)
                            if (!Number.isFinite(v)) return
                            void patchPlatformConnection('fanvue', conn.id, {
                              companion_delay_min_sec: v,
                            })
                          }}
                        />
                      </label>
                      <label>
                        {t('cabinet.integrations.delayMax')}
                        <input
                          type="number"
                          min={0}
                          max={600}
                          defaultValue={conn.companion_delay_max_sec ?? 45}
                          disabled={!canIntegrations}
                          onBlur={(e) => {
                            const v = Number(e.target.value)
                            if (!Number.isFinite(v)) return
                            void patchPlatformConnection('fanvue', conn.id, {
                              companion_delay_max_sec: v,
                            })
                          }}
                        />
                      </label>
                      <label>
                        {t('integrationsExt.autoPerHour')}
                        <input
                          type="number"
                          min={1}
                          max={500}
                          defaultValue={conn.companion_max_replies_per_hour ?? 60}
                          disabled={!canIntegrations}
                          onBlur={(e) => {
                            const v = Number(e.target.value)
                            if (!Number.isFinite(v)) return
                            void patchPlatformConnection('fanvue', conn.id, {
                              companion_max_replies_per_hour: v,
                            })
                          }}
                        />
                      </label>
                    </div>
                    {integ?.fanvue_oauth_available ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <button
                          type="button"
                          className="ghost-btn"
                          disabled={!canIntegrations || fvBusy}
                          onClick={() => void connectFanvueOAuth(conn.id)}
                        >
                          {t('integrationsExt.fanvue.reconnect')}
                        </button>
                        <button
                          type="button"
                          className="ghost-btn"
                          disabled={!canIntegrations || fvBusy}
                          onClick={() => void syncFanvueHistory(conn.id)}
                        >
                          {t('integrationsExt.history')}
                        </button>
                        <button
                          type="button"
                          className="ghost-btn"
                          disabled={!canIntegrations || fvBusy}
                          onClick={() => void disconnectFanvue(conn.id)}
                        >
                          {t('integrationsExt.disconnect')}
                        </button>
                      </div>
                    ) : null}
                  </div>
                ))}
                {integ?.fanvue_webhook_url ? (
                  <div className="cabinet-module-form" style={{ marginBottom: '0.75rem' }}>
                    <label className="cabinet-field-span2">
                      Webhook URL
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                        <input readOnly value={integ.fanvue_webhook_url} />
                        <button type="button" className="ghost-btn" onClick={() => void copyFanvueWebhookUrl()}>
                          {t('integrationsExt.copy')}
                        </button>
                      </div>
                    </label>
                  </div>
                ) : null}
                {(integ?.fanvue_connections?.length ?? 0) <
                (integ?.max_connections_per_platform ?? 1) &&
                integ?.fanvue_oauth_available ? (
                  <div className="cabinet-module-form">
                    {studioModels.length > 0 ? (
                      <label>
                        {t('integrationsExt.fanvue.newConnectionModel')}
                        <select
                          value={fvDraftModelId === '' ? '' : String(fvDraftModelId)}
                          onChange={(e) => {
                            const v = e.target.value
                            setFvDraftModelId(v ? Number(v) : '')
                          }}
                          disabled={!canIntegrations}
                        >
                          <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                          {studioModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <button
                      type="button"
                      className="send-btn"
                      disabled={!canIntegrations || fvBusy}
                      onClick={() => void connectFanvueOAuth(null)}
                    >
                      {fvBusy ? '…' : t('integrationsExt.fanvue.addOAuth')}
                    </button>
                  </div>
                ) : null}
                {fvSyncNote ? (
                  <p className="muted small" style={{ margin: '0.75rem 0 0' }}>
                    {fvSyncNote}
                  </p>
                ) : null}
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">Instagram</h4>
                  <span
                    className={`cabinet-module-badge ${
                      INSTAGRAM_INTEGRATION_IN_DEVELOPMENT
                        ? 'is-warn'
                        : integ?.instagram_configured
                          ? 'is-ok'
                          : 'is-warn'
                    }`}
                  >
                    {INSTAGRAM_INTEGRATION_IN_DEVELOPMENT
                      ? t('integrationsExt.instagram.inDevelopment')
                      : (integ?.instagram_connections?.length ?? 0) > 0
                        ? t('cabinet.integrations.connectedCount', { count: integ?.instagram_connections?.length ?? 0 })
                        : t('cabinet.integrations.notConnected')}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  {t('integrationsExt.instagram.body')}
                </p>
                {INSTAGRAM_INTEGRATION_IN_DEVELOPMENT ? (
                  <p className="banner info cabinet-module-body" style={{ marginBottom: '0.75rem' }}>
                    {t('integrationsExt.instagram.inDevelopmentBanner')}
                  </p>
                ) : null}
                <ol className="muted cabinet-module-body" style={{ margin: '0 0 1rem', paddingLeft: '1.25rem' }}>
                  <li>
                    {t('integrationsExt.instagram.step1')}
                  </li>
                  <li>{t('integrationsExt.instagram.step2')}</li>
                </ol>
                {(integ?.instagram_connections ?? []).map((conn) => (
                  <div key={conn.id} className="cabinet-module-form">
                    <p className="small mono">
                      {conn.label ? `${conn.label} · ` : ''}
                      {conn.instagram_username
                        ? `@${conn.instagram_username}`
                        : conn.instagram_user_id
                          ? `${conn.instagram_user_id.slice(0, 8)}…`
                          : '—'}
                    </p>
                    {studioModels.length > 0 ? (
                      <label>
                        {t('cabinet.integrations.model')}
                        <select
                          value={conn.studio_model_id != null ? String(conn.studio_model_id) : ''}
                          disabled={!canIntegrations || INSTAGRAM_INTEGRATION_IN_DEVELOPMENT}
                          onChange={(e) => {
                            const raw = e.target.value
                            void patchPlatformConnection('instagram', conn.id, {
                              studio_model_id: raw ? Number(raw) : null,
                            })
                          }}
                        >
                          <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                          {studioModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    {!INSTAGRAM_INTEGRATION_IN_DEVELOPMENT && integ?.instagram_oauth_available ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        <button
                          type="button"
                          className="ghost-btn"
                          disabled={!canIntegrations || igBusy}
                          onClick={() => void connectInstagramOAuth(conn.id)}
                        >
                          {t('integrationsExt.reconnect')}
                        </button>
                        <button
                          type="button"
                          className="ghost-btn"
                          disabled={!canIntegrations || igBusy}
                          onClick={() => void disconnectInstagram(conn.id)}
                        >
                          {t('integrationsExt.disconnect')}
                        </button>
                      </div>
                    ) : null}
                  </div>
                ))}
                {!INSTAGRAM_INTEGRATION_IN_DEVELOPMENT &&
                (integ?.instagram_connections?.length ?? 0) <
                  (integ?.max_connections_per_platform ?? 1) &&
                integ?.instagram_oauth_available ? (
                  <div className="cabinet-module-form">
                    {studioModels.length > 0 ? (
                      <label>
                        {t('integrationsExt.fanvue.newConnectionModel')}
                        <select
                          value={igDraftModelId === '' ? '' : String(igDraftModelId)}
                          onChange={(e) => {
                            const v = e.target.value
                            setIgDraftModelId(v ? Number(v) : '')
                          }}
                          disabled={!canIntegrations}
                        >
                          <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                          {studioModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <button
                      type="button"
                      className="send-btn"
                      disabled={!canIntegrations || igBusy}
                      onClick={() => void connectInstagramOAuth(null)}
                    >
                      {igBusy ? '…' : t('integrationsExt.instagram.addOAuth')}
                    </button>
                  </div>
                ) : null}
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">Tribute</h4>
                  <span
                    className={`cabinet-module-badge ${integ?.tribute_configured ? 'is-ok' : 'is-warn'}`}
                  >
                    {(integ?.tribute_connections?.length ?? 0) > 0
                      ? t('cabinet.integrations.connectedCount', { count: integ?.tribute_connections?.length ?? 0 })
                      : t('cabinet.integrations.notConnected')}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  <Trans
                    i18nKey="integrationsExt.tribute.body"
                    ns="workspace"
                    components={{
                      link: (
                        <a
                          href="https://wiki.tribute.tg/ru/api-dokumentaciya"
                          target="_blank"
                          rel="noopener noreferrer"
                        />
                      ),
                    }}
                  />
                </p>
                <ol className="muted cabinet-module-body" style={{ margin: '0 0 1rem', paddingLeft: '1.25rem' }}>
                  <li>
                    <Trans i18nKey="integrationsExt.tribute.step1" ns="workspace" components={{ strong: <strong /> }} />
                  </li>
                  <li>
                    <Trans i18nKey="integrationsExt.tribute.step2" ns="workspace" components={{ strong: <strong /> }} />
                  </li>
                  <li>
                    <Trans i18nKey="integrationsExt.tribute.step3" ns="workspace" components={{ strong: <strong /> }} />
                  </li>
                  <li>{t('integrationsExt.tribute.step4')}</li>
                </ol>
                {(integ?.tribute_connections ?? []).map((conn) => (
                  <div key={conn.id} className="cabinet-module-form">
                    <p className="small mono">{conn.label ? conn.label : t('integrationsExt.tribute.connectionFallback', { id: conn.id })}</p>
                    {studioModels.length > 0 ? (
                      <label>
                        {t('cabinet.integrations.model')}
                        <select
                          value={conn.studio_model_id != null ? String(conn.studio_model_id) : ''}
                          disabled={!canIntegrations}
                          onChange={(e) => {
                            const raw = e.target.value
                            void patchPlatformConnection('tribute', conn.id, {
                              studio_model_id: raw ? Number(raw) : null,
                            })
                          }}
                        >
                          <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                          {studioModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    {conn.webhook_url ? (
                      <label className="cabinet-field-span2">
                        {t('integrationsExt.tribute.webhookLabel')}
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                          <input readOnly value={conn.webhook_url} />
                          <button
                            type="button"
                            className="ghost-btn"
                            onClick={() => void copyTributeWebhookUrl(conn.webhook_url!)}
                          >
                            {t('integrationsExt.copy')}
                          </button>
                        </div>
                      </label>
                    ) : null}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                      <button
                        type="button"
                        className="ghost-btn"
                        disabled={!canIntegrations}
                        onClick={() => {
                          setTributeEditConnectionId(conn.id)
                          setTributeDraftLabel(conn.label ?? '')
                          setTributeDraftModelId(conn.studio_model_id ?? '')
                        }}
                      >
                        {t('integrationsExt.tribute.updateKey')}
                      </button>
                      <button
                        type="button"
                        className="ghost-btn"
                        disabled={!canIntegrations}
                        onClick={() => void disconnectTribute(conn.id)}
                      >
                        {t('integrationsExt.disconnect')}
                      </button>
                    </div>
                  </div>
                ))}
                {(integ?.tribute_connections?.length ?? 0) <
                (integ?.max_connections_per_platform ?? 1) ? (
                  <div className="cabinet-module-form">
                    <label>
                      {t('integrationsExt.labelOptional')}
                      <input
                        value={tributeDraftLabel}
                        onChange={(e) => setTributeDraftLabel(e.target.value)}
                        disabled={!canIntegrations}
                        placeholder={t('integrationsExt.labelPh')}
                      />
                    </label>
                    {studioModels.length > 0 ? (
                      <label>
                        {t('cabinet.integrations.model')}
                        <select
                          value={tributeDraftModelId === '' ? '' : String(tributeDraftModelId)}
                          onChange={(e) => {
                            const v = e.target.value
                            setTributeDraftModelId(v ? Number(v) : '')
                          }}
                          disabled={!canIntegrations}
                        >
                          <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                          {studioModels.map((m) => (
                            <option key={m.id} value={String(m.id)}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                    <label>
                      {t('integrationsExt.tributeApiKey')}
                      <input
                        type="password"
                        autoComplete="off"
                        value={tributeApiKey}
                        onChange={(e) => setTributeApiKey(e.target.value)}
                        placeholder={t('integrationsExt.tributeApiKeyPh')}
                        disabled={!canIntegrations}
                      />
                    </label>
                    <button
                      type="button"
                      className="send-btn"
                      disabled={!canIntegrations}
                      onClick={() => void saveTribute(tributeEditConnectionId)}
                    >
                      {tributeEditConnectionId != null ? t('integrationsExt.saveTributeKey') : t('integrationsExt.addTribute')}
                    </button>
                  </div>
                ) : null}
              </section>

              {canPlatformAdmin ? (
              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">{t('integrationsExt.llm.title')}</h4>
                  <span className={`cabinet-module-badge ${integ?.llm_configured ? 'is-ok' : 'is-warn'}`}>
                    {integ?.llm_configured ? t('integrationsExt.llm.badgeConfigured') : t('integrationsExt.llm.badgeNotConfigured')}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  <Trans i18nKey="integrationsExt.llm.body" ns="workspace" components={{ code: <code /> }} />
                </p>
                <div className="cabinet-module-form cabinet-module-form--grid">
                  <label>
                    {t('integrationsExt.llmApiKey')}
                    <input
                      type="password"
                      autoComplete="off"
                      value={llmApiKey}
                      onChange={(e) => setLlmApiKey(e.target.value)}
                      disabled={!canIntegrations}
                    />
                  </label>
                  <label>
                    {t('integrationsExt.llm.baseUrl')}
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
                    {t('integrationsExt.llmSave')}
                  </button>
                </div>
              </section>
              ) : null}

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">{t('integrationsExt.companionFeedback.title')}</h4>
                  <span className="cabinet-module-badge is-ok">
                    {companionFeedbackLoading ? '…' : t('integrationsExt.companionFeedback.reportsCount', { count: companionFeedbackReports.length })}
                  </span>
                </div>
                <p className="muted cabinet-module-body">
                  {t('integrationsExt.companionFeedback.body')}
                </p>
                {companionFeedbackLoading ? (
                  <p className="muted">{tCommon('loading')}</p>
                ) : companionFeedbackReports.length === 0 ? (
                  <p className="muted small">{t('integrationsExt.companionFeedback.empty')}</p>
                ) : (
                  <div className="companion-feedback-list">
                    {companionFeedbackReports.map((rep) => (
                      <details key={rep.id} className="companion-feedback-item">
                        <summary>
                          {new Date(rep.report_date).toLocaleDateString('ru-RU')}
                          {rep.stats?.rating_positive != null ? (
                            <span className="companion-feedback-stats">
                              {' '}
                              · 👍 {rep.stats.rating_positive} · 👎 {rep.stats.rating_negative ?? 0}
                            </span>
                          ) : null}
                        </summary>
                        <pre className="companion-feedback-body">{rep.content}</pre>
                      </details>
                    ))}
                  </div>
                )}
              </section>

              <section className="cabinet-module">
                <div className="cabinet-module-head">
                  <h4 className="cabinet-module-title">{t('notifications.title')}</h4>
                  <span className={`cabinet-module-badge ${webPushState === 'on' ? 'is-ok' : 'is-warn'}`}>
                    {webPushState === 'loading' || webPushState === 'unknown'
                      ? '…'
                      : webPushState === 'on'
                        ? tCommon('on')
                        : tCommon('off')}
                  </span>
                </div>
                <p className="muted cabinet-module-body">{t('notifications.body')}</p>
                {webPushState === 'denied' ? (
                  <p className="muted small">{t('notifications.denied')}</p>
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
                        {t('integrationsExt.disconnect')}
                      </button>
                    ) : webPushState === 'off' ? (
                      <button
                        type="button"
                        className="send-btn"
                        disabled={pushBusy}
                        onClick={() => void enableWebPush()}
                      >
                        {t('integrationsExt.pushEnable')}
                      </button>
                    ) : null}
                  </div>
                ) : !health?.web_push_configured ? (
                  <p className="muted small">{t('notifications.serverDisabled')}</p>
                ) : null}
              </section>

              {integ?.integration_hint ? (
                <div className="banner info cabinet-hint-banner">{integ.integration_hint}</div>
              ) : null}
              {!canIntegrations ? (
                <p className="muted" style={{ marginTop: '1rem' }}>
                  {t('cabinet.integrations.lead')}
                </p>
              ) : null}
            </div>
          )}

          {accountTab === 'models' && canStudioModels && (
            <div className="account-cabinet-pane" role="tabpanel">
              {studioPaywalled ? (
                <div className="banner info" style={{ marginBottom: '1rem' }}>
                  {ts('models.paywall')}{' '}
                  {isOwner ? (
                    <button
                      type="button"
                      className="ghost-btn"
                      style={{ marginLeft: '0.5rem' }}
                      onClick={() => setAccountTab('billing')}
                    >
                      {ts('models.goBilling')}
                    </button>
                  ) : (
                    <> {ts('models.askOwner')}</>
                  )}
                </div>
              ) : null}
              <p className="cabinet-lead muted">
                {ts('models.lead', { max: STUDIO_MODEL_MAX_IMAGES })}
              </p>

              <h4 className="account-sub">{ts('models.newModel')}</h4>
              <div className="account-grid studio-models-block cabinet-new-model">
                <label>
                  {ts('models.name')}
                  <input
                    value={newModelName}
                    onChange={(e) => setNewModelName(e.target.value)}
                    placeholder={ts('models.namePlaceholder')}
                    disabled={studioPaywalled}
                  />
                </label>
                <label>
                  {ts('models.photos', { max: STUDIO_MODEL_MAX_IMAGES })}
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
                            {STUDIO_MODEL_IMAGE_KIND_VALUES.map((kind) => (
                              <option key={kind} value={kind}>
                                {studioModelImageKindLabel(kind)}
                              </option>
                            ))}
                          </select>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </label>
                <label className="studio-new-model-profile-label">
                  {ts('models.profileJson')}
                  <textarea
                    rows={6}
                    value={newModelProfile}
                    onChange={(e) => setNewModelProfile(e.target.value)}
                    placeholder={ts('models.profilePlaceholder')}
                    className="studio-model-profile-textarea"
                    disabled={studioPaywalled}
                  />
                  <button
                    type="button"
                    className="ghost-btn studio-gen-profile-btn"
                    disabled={studioPaywalled || newModelProfileGenBusy || newModelPhotos.length === 0}
                    title={newModelPhotos.length === 0 ? ts('models.genFromPhotosNeedPhotos') : undefined}
                    onClick={() => void generateModelProfileFromPhotos()}
                  >
                    {newModelProfileGenBusy ? ts('models.genFromPhotosBusy') : ts('models.genFromPhotos')}
                  </button>
                </label>
                <div className="studio-model-export-block account-grid" style={{ gridColumn: '1 / -1' }}>
                  <h4 className="account-sub" style={{ margin: 0 }}>
                    {ts('models.exportPhone')}
                  </h4>
                  <p className="muted small" style={{ margin: 0 }}>
                    {ts('models.exportPhoneHint')}
                  </p>
                  <div className="studio-phone-exif-refs">
                    <p className="studio-phone-exif-refs__title">{ts('models.exifRefsTitle')}</p>
                    <label className="studio-phone-exif-refs__slot">
                      <span>{ts('models.exifSelfie')}</span>
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
                        <span className="muted small">{ts('models.exifSelfieHint')}</span>
                      )}
                    </label>
                    <label className="studio-phone-exif-refs__slot">
                      <span>{ts('models.exifMain')}</span>
                      <input
                        type="file"
                        accept="image/jpeg,image/jpg"
                        disabled={studioPaywalled}
                        onChange={(e) => setNewModelPhoneExifMain(e.target.files?.[0] ?? null)}
                      />
                      {newModelPhoneExifMain ? (
                        <span className="muted small">{newModelPhoneExifMain.name}</span>
                      ) : (
                        <span className="muted small">{ts('models.exifMainHint')}</span>
                      )}
                    </label>
                  </div>
                  <label>
                    {ts('models.cameraPresetFallback')}
                    <select
                      value={newModelCameraPresetId}
                      disabled={studioPaywalled}
                      onChange={(e) => setNewModelCameraPresetId(e.target.value)}
                    >
                      <option value="">{ts('models.cameraPresetNone')}</option>
                      {studioCameraPresets.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {ts('models.latitude')}
                    <input
                      value={newModelExportLat}
                      onChange={(e) => setNewModelExportLat(e.target.value)}
                      placeholder="55.7558"
                      inputMode="decimal"
                      disabled={studioPaywalled}
                    />
                  </label>
                  <label>
                    {ts('models.longitude')}
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
                  {ts('models.createModel')}
                </button>
              </div>

              {studioModels.length === 0 ? (
                <p className="muted cabinet-empty-models">{ts('models.emptyList')}</p>
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
                          <h4 className="model-card-title">{ts('models.modelCardTitle', { id: m.id })}</h4>
                          <button
                            type="button"
                            className="ghost-btn danger-text model-card-delete"
                            disabled={busy || studioPaywalled}
                            onClick={() => {
                              if (window.confirm(ts('models.deleteConfirm'))) void deleteStudioModel(m.id)
                            }}
                          >
                            {ts('models.delete')}
                          </button>
                        </div>
                        <div className="model-card-thumbs" aria-label={ts('models.referencesAria')}>
                          {imgs.length === 0 ? (
                            <span className="model-card-no-photos muted">{ts('models.noPhotos')}</span>
                          ) : (
                            imgs.map((im) => (
                              <div key={im.id} className="model-thumb-wrap">
                                <div className="model-thumb-frame">
                                  <img src={im.url} alt="" className="model-thumb" loading="lazy" />
                                  <button
                                    type="button"
                                    className="model-thumb-remove"
                                    title={ts('models.deletePhoto')}
                                    disabled={busy || studioPaywalled}
                                    onClick={() => void deleteStudioModelImage(m.id, im.id)}
                                  >
                                    ×
                                  </button>
                                </div>
                                <select
                                  className="studio-model-kind-select"
                                  aria-label={ts('models.referenceKindAria')}
                                  value={normalizeStudioImageKind(im.kind)}
                                  disabled={busy || studioPaywalled}
                                  onChange={(e) => {
                                    const v = e.target.value as StudioModelImageKind
                                    void patchStudioModelImage(m.id, im.id, { kind: v })
                                  }}
                                >
                                  {STUDIO_MODEL_IMAGE_KIND_VALUES.map((kind) => (
                                    <option key={kind} value={kind}>
                                      {studioModelImageKindLabel(kind)}
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
                              {t('modelsExt.appendHint')}
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
                                    {STUDIO_MODEL_IMAGE_KIND_VALUES.map((kind) => (
                                      <option key={kind} value={kind}>
                                        {studioModelImageKindLabel(kind)}
                                      </option>
                                    ))}
                                  </select>
                                  <button
                                    type="button"
                                    className="ghost-btn danger-text"
                                    disabled={busy || studioPaywalled}
                                    title={ts('models.removeFromList')}
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
                                {tCommon('cancel')}
                              </button>
                              <button
                                type="button"
                                className="send-btn"
                                disabled={busy || studioPaywalled}
                                onClick={() => void uploadAppendStudioModelImages(m.id, pendingAppend)}
                              >
                                {t('modelsExt.uploadPhotos', { count: pendingAppend.length })}
                              </button>
                            </div>
                          </div>
                        ) : null}
                        <label className="model-card-field">
                          {t('modelsExt.nameLabel')}
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
                          {t('modelsExt.profileLabel')}
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
                            {t('cabinet.integrations.aiCompanion')}
                          </h4>
                          <p className="muted small" style={{ margin: 0 }}>
                            {t('modelsExt.personaLead')}
                          </p>
                          <label>
                            {t('modelsExt.age')}
                            <input
                              value={draft.companion_persona.age ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.agePlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      age: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label>
                            {t('modelsExt.city')}
                            <input
                              value={draft.companion_persona.city ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.cityPlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      city: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label>
                            {t('modelsExt.country')}
                            <input
                              value={draft.companion_persona.country ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.countryPlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      country: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label>
                            {t('modelsExt.timezone')}
                            <input
                              value={draft.companion_persona.timezone ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder="Europe/Madrid"
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      timezone: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label style={{ gridColumn: '1 / -1' }}>
                            {t('modelsExt.personality')}
                            <textarea
                              rows={2}
                              value={draft.companion_persona.personality ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.personalityPlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      personality: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label style={{ gridColumn: '1 / -1' }}>
                            {t('modelsExt.hobbies')}
                            <textarea
                              rows={2}
                              value={draft.companion_persona.hobbies ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.hobbiesPlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      hobbies: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label style={{ gridColumn: '1 / -1' }}>
                            {t('modelsExt.interests')}
                            <textarea
                              rows={2}
                              value={draft.companion_persona.interests ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.interestsPlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      interests: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label style={{ gridColumn: '1 / -1' }}>
                            {t('modelsExt.lifestyle')}
                            <textarea
                              rows={2}
                              value={draft.companion_persona.lifestyle ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.lifestylePlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      lifestyle: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label style={{ gridColumn: '1 / -1' }}>
                            {t('modelsExt.speakingStyle')}
                            <textarea
                              rows={2}
                              value={draft.companion_persona.speaking_style ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.speakingStylePlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      speaking_style: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                          <label style={{ gridColumn: '1 / -1' }}>
                            {t('modelsExt.backstory')}
                            <textarea
                              rows={3}
                              value={draft.companion_persona.backstory ?? ''}
                              disabled={busy || studioPaywalled}
                              placeholder={t('modelsExt.backstoryPlaceholder')}
                              onChange={(e) =>
                                setModelDrafts((prev) => ({
                                  ...prev,
                                  [m.id]: {
                                    ...(prev[m.id] ?? defaultStudioModelCabinetDraft(m)),
                                    companion_persona: {
                                      ...(prev[m.id]?.companion_persona ??
                                        companionPersonaFromModel(m)),
                                      backstory: e.target.value,
                                    },
                                  },
                                }))
                              }
                            />
                          </label>
                        </div>
                        <div className="studio-model-export-block account-grid" style={{ gridColumn: '1 / -1' }}>
                          <h4 className="account-sub" style={{ margin: 0 }}>
                            {t('modelsExt.exportPhoneTitle')}
                          </h4>
                          <p className="muted small" style={{ margin: 0 }}>
                            {t('modelsExt.exportPhoneLead')}
                          </p>
                          <div className="studio-phone-exif-refs">
                            <p className="studio-phone-exif-refs__title">{t('modelsExt.exifRefsTitle')}</p>
                            <div className="studio-phone-exif-refs__slot">
                              <span>{ts('models.exifSelfie')}</span>
                              {m.phone_exif_selfie_ready && m.phone_exif_selfie_summary ? (
                                <p className="muted small studio-phone-exif-refs__ok">
                                  ✓ {m.phone_exif_selfie_summary}
                                </p>
                              ) : (
                                <p className="muted small">{tCommon('notUploaded')}</p>
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
                                    ? tCommon('reading')
                                    : m.phone_exif_selfie_ready
                                      ? tCommon('replace')
                                      : tCommon('upload')}
                                </span>
                              </label>
                              {m.phone_exif_selfie_ready ? (
                                <button
                                  type="button"
                                  className="ghost-btn small"
                                  disabled={busy || studioPaywalled}
                                  onClick={() => void clearModelPhoneExifRef(m.id, 'selfie')}
                                >
                                  {tCommon('reset')}
                                </button>
                              ) : null}
                            </div>
                            <div className="studio-phone-exif-refs__slot">
                              <span>{ts('models.exifMain')}</span>
                              {m.phone_exif_main_ready && m.phone_exif_main_summary ? (
                                <p className="muted small studio-phone-exif-refs__ok">
                                  ✓ {m.phone_exif_main_summary}
                                </p>
                              ) : (
                                <p className="muted small">{tCommon('notUploaded')}</p>
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
                                    ? tCommon('reading')
                                    : m.phone_exif_main_ready
                                      ? tCommon('replace')
                                      : tCommon('upload')}
                                </span>
                              </label>
                              {m.phone_exif_main_ready ? (
                                <button
                                  type="button"
                                  className="ghost-btn small"
                                  disabled={busy || studioPaywalled}
                                  onClick={() => void clearModelPhoneExifRef(m.id, 'main')}
                                >
                                  {tCommon('reset')}
                                </button>
                              ) : null}
                            </div>
                          </div>
                          <label>
                            {ts('models.cameraPresetFallback')}
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
                              <option value="">{ts('models.cameraPresetNone')}</option>
                              {studioCameraPresets.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            {t('modelsExt.latitude')}
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
                            {t('modelsExt.longitude')}
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
                            <span className="ghost-btn model-card-add-btn">{ts('models.addPhoto')}</span>
                          </label>
                          <button
                            type="button"
                            className="send-btn"
                            disabled={busy || studioPaywalled || !draft.name.trim()}
                            onClick={() => void patchStudioModel(m.id)}
                          >
                            {busy ? ts('models.saving') : ts('models.saveChanges')}
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
                {t('cabinet.team.lead', {
                  email: me?.public_email ? ` (${me.public_email})` : '',
                })}
              </p>
              {me?.email_setup_required ? (
                <div className="banner warn" style={{ marginBottom: '1rem' }}>
                  {t('cabinet.team.emailRequired')}
                </div>
              ) : null}
              <h4 className="account-sub">{t('cabinet.team.newMember')}</h4>
              <div className="account-grid cabinet-keys-form">
                <label>
                  {t('cabinet.team.loginLabel')}
                  <input
                    value={newTeamLogin}
                    onChange={(e) => setNewTeamLogin(e.target.value)}
                    placeholder={t('cabinet.team.loginPlaceholder')}
                    autoComplete="off"
                    disabled={teamBusy}
                  />
                </label>
                <label>
                  {t('cabinet.team.passwordLabel')}
                  <input
                    type="password"
                    value={newTeamPassword}
                    onChange={(e) => setNewTeamPassword(e.target.value)}
                    autoComplete="new-password"
                    disabled={teamBusy}
                  />
                </label>
                <div style={{ gridColumn: '1 / -1' }} className="team-perm-grid">
                  {MEMBER_PERMISSION_ITEMS.map(({ bit, key }) => (
                    <label key={bit} className="studio-label studio-check">
                      <input
                        type="checkbox"
                        checked={hasAllBits(newTeamMask, bit)}
                        disabled={teamBusy}
                        onChange={(e) => setNewTeamMask((m) => togglePermission(m, bit, e.target.checked))}
                      />
                      <span>{memberPermissionLabel(key)}</span>
                    </label>
                  ))}
                </div>
                {studioModels.length > 0 ? (
                  <div style={{ gridColumn: '1 / -1' }} className="team-model-grid">
                    <span className="account-sub" style={{ margin: 0 }}>
                      {t('modelsExt.teamStudioModels')}
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
                    {t('cabinet.team.createModelsFirst')}
                  </p>
                )}
                <label>
                  {t('cabinet.team.tributeShare')}
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={1}
                    value={newTeamTributeShare}
                    onChange={(e) => setNewTeamTributeShare(e.target.value)}
                    placeholder="20"
                    disabled={teamBusy}
                  />
                </label>
                <p className="muted small" style={{ gridColumn: '1 / -1', margin: 0 }}>
                  {t('cabinet.team.tributeShareHint')}
                </p>
                <button
                  type="button"
                  className="send-btn"
                  disabled={
                    teamBusy ||
                    me?.email_setup_required ||
                    newTeamLogin.trim().length < 3 ||
                    newTeamPassword.length < 8
                  }
                  onClick={() => void createWorkspaceMember()}
                >
                  {teamBusy ? t('cabinet.team.creating') : t('cabinet.team.createMember')}
                </button>
              </div>

              <h4 className="account-sub">
                {t('cabinet.team.kpiTitle')}
                {chatterStatsDisplay.period ? ` · ${chatterStatsDisplay.period}` : ''}
              </h4>
              {(chatterStats?.members?.length ?? 0) > 0 ? (
                <div className="cabinet-table-wrap" style={{ marginBottom: '1.25rem' }}>
                  <table className="cabinet-table">
                    <thead>
                      <tr>
                        <th>{t('cabinet.team.memberCol')}</th>
                        <th>{t('cabinet.team.repliesCol')}</th>
                        <th>{t('cabinet.team.dialogsCol')}</th>
                        <th>{t('cabinet.team.slaCol')}</th>
                        <th>{t('cabinet.team.firstReplyCol')}</th>
                        <th>{t('cabinet.team.aiRatingsCol')}</th>
                        <th>{t('cabinet.team.tributeCol')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {chatterStats!.members!.map((row) => (
                        <tr key={row.user_id}>
                          <td className="mono">{row.member_login || `#${row.user_id}`}</td>
                          <td>{row.outbound_messages}</td>
                          <td>{row.conversations_replied}</td>
                          <td className="mono">{formatSlaSeconds(row.median_reply_seconds)}</td>
                          <td className="mono">
                            {formatSlaSeconds(row.avg_first_response_seconds)}
                          </td>
                          <td>
                            {row.companion_ratings_positive}/{row.companion_ratings_negative}
                          </td>
                          <td className="mono">
                            {formatAppCurrency(row.tribute_display_minor, row.tribute_currency)}
                            <span className="muted small" style={{ display: 'block' }}>
                              {row.tribute_share_percent}% · {t('cabinet.team.grossLabel')}{' '}
                              {formatAppCurrency(row.tribute_gross_minor, row.tribute_currency)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted" style={{ marginBottom: '1rem' }}>
                  {t('modelsExt.kpiEmpty')}
                </p>
              )}

              <h4 className="account-sub">{tc('templates.title')}</h4>
              <p className="muted small" style={{ marginTop: 0 }}>
                {tc('templates.lead')}
              </p>
              <div className="team-create-grid" style={{ marginBottom: '0.75rem' }}>
                <input
                  placeholder={tc('templates.namePlaceholder')}
                  value={newSnippetTitle}
                  onChange={(e) => setNewSnippetTitle(e.target.value)}
                  disabled={snippetBusy}
                />
                <input
                  placeholder={tc('templates.bodyPlaceholder')}
                  value={newSnippetBody}
                  onChange={(e) => setNewSnippetBody(e.target.value)}
                  disabled={snippetBusy}
                />
                <button
                  type="button"
                  className="send-btn"
                  disabled={snippetBusy || !newSnippetTitle.trim() || !newSnippetBody.trim()}
                  onClick={() => void createChatterSnippet()}
                >
                  {t('modelsExt.snippetAdd')}
                </button>
              </div>
              {chatterSnippets.length > 0 ? (
                <ul className="team-member-list" style={{ marginBottom: '1.25rem' }}>
                  {chatterSnippets.map((sn) => (
                    <li key={sn.id} className="team-member-row">
                      <strong>{sn.title}</strong>
                      <span className="muted small" style={{ display: 'block' }}>
                        {sn.body.slice(0, 120)}
                        {sn.body.length > 120 ? '…' : ''}
                      </span>
                      <button
                        type="button"
                        className="link-btn"
                        disabled={snippetBusy}
                        onClick={() => void deleteChatterSnippet(sn.id)}
                      >
                        {tc('templates.delete')}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted" style={{ marginBottom: '1.25rem' }}>
                  {tc('templates.empty')}
                </p>
              )}

              <h4 className="account-sub">{t('cabinet.team.membersTitle')}</h4>
              {workspaceMembers.length === 0 ? (
                <p className="muted">{t('team.membersEmpty')}</p>
              ) : (
                <ul className="team-member-list">
                  {workspaceMembers.map((row) => {
                    const mask = memberMaskEdits[row.id] ?? row.permissions_mask
                    const modelIds = memberModelEdits[row.id] ?? row.allowed_studio_model_ids ?? []
                    const pwd = memberEditPassword[row.id] ?? ''
                    const tributeShare =
                      memberTributeEdits[row.id] ?? String(row.tribute_share_percent)
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
                            <span>{t('cabinet.team.active')}</span>
                          </label>
                        </div>
                        <div className="team-perm-grid">
                          {MEMBER_PERMISSION_ITEMS.map(({ bit, key }) => (
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
                              <span>{memberPermissionLabel(key)}</span>
                            </label>
                          ))}
                        </div>
                        {studioModels.length > 0 ? (
                          <div className="team-model-grid">
                            <span className="account-sub" style={{ margin: 0 }}>
                              {t('modelsExt.studioModels')}
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
                          {t('modelsExt.teamTributeShare')}
                          <input
                            type="number"
                            min={0}
                            max={100}
                            step={1}
                            value={tributeShare}
                            disabled={teamBusy}
                            onChange={(e) =>
                              setMemberTributeEdits((p) => ({ ...p, [row.id]: e.target.value }))
                            }
                          />
                        </label>
                        <label>
                          {t('modelsExt.newPassword')}
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
                            {t('modelsExt.saveMember')}
                          </button>
                          <button
                            type="button"
                            className="ghost-btn danger-text"
                            disabled={teamBusy}
                            onClick={() => void removeWorkspaceMember(row.id)}
                          >
                            {t('cabinet.team.deleteMember')}
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
          </div>
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
          billingPlanLabel={planDisplayShort(me)}
          demoGenerationsRemaining={me?.demo_generations_remaining ?? 0}
          userTitle={
            me?.is_workspace_owner
              ? me.email
              : `${me?.owner_email ?? ''}${me?.member_login ? ` · ${me.member_login}` : ''}`
          }
          userMeta={t('shell.creditsMeta', { credits: me?.credits_balance ?? 0, plan: planDisplayShort(me) })}
          onAccountOpen={() => setAccountOpen(true)}
          onLogout={handleLogout}
        >
          {health?.legacy_telegram_polling && health.telegram_api_reachable === false && (
            <div className="banner error">
              {t('health.telegramUnreachable')}
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
              billingPlanLabel={planDisplayShort(me)}
              subscriptionLabel={subscriptionStatusLabel(me.subscription_status)}
              unreadTotal={unreadTotal}
              conversationsTotal={conversations.length}
              generationsTotal={studioGenerations.length}
              canChat={canChat}
              canStudioAny={canStudioAny}
              conversations={conversations}
              generations={studioGenerations}
              tributeEarningsLabel={tributeEarningsDisplay.label}
              tributeEarningsHint={tributeEarningsDisplay.hint}
              tributeConfigured={Boolean(integ?.tribute_configured)}
              platformDonationsLabel={platformDonationsDisplay.label}
              platformDonationsHint={platformDonationsDisplay.hint}
              platformDonationsVisible={isOwner && platformDonationsDisplay.visible}
              platformDonationsRecent={platformDonationsDisplay.recent}
              onOpenDonations={openCreatorDonations}
              chatterOutboundCount={chatterStatsDisplay.outbound}
              chatterConversationsCount={chatterStatsDisplay.conversations}
              chatterRatingsHint={chatterStatsDisplay.ratingsHint}
              chatterStatsPeriod={chatterStatsDisplay.period}
              isOwner={isOwner}
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
          {t('health.modeLine', { mode: health.mode ?? '—', conversations: health.conversations_count ?? 0, messages: health.messages_count ?? 0 })}
          {health.legacy_telegram_polling ? (
            <>
              {' '}
              · legacy polling Telegram:{' '}
              {health.telegram_api_reachable === true ? (
                <span className="ok">API OK @{health.telegram_bot_username ?? '?'}</span>
              ) : health.telegram_api_reachable === false ? (
                <span className="warn">{t('health.telegramUnreachable')}</span>
              ) : (
                <span className="muted">{tCommon('checking')}</span>
              )}
            </>
          ) : (
            <span className="muted">{t('health.webhookIntegrations')}</span>
          )}
          {health.telegram_proxy_configured ? <span className="ok">{t('health.telegramProxy')}</span> : null}
          {health.openai_studio_configured ? (
            <span className="ok">
              {' '}
              {t('health.studioPromptOk', { credits: health.studio_prompt_credit_cost ?? '—' })}
            </span>
          ) : (
            <span className="warn">{t('health.studioTextUnavailable')}</span>
          )}
        </div>
      )}

      {hasAnyMainSection && appSection === 'studio' && canStudioAny && (
        <section className="studio-panel studio-workspace-page" aria-labelledby="studio-heading">
          <div className="studio-workspace">
            <div className="studio-workspace__composer" aria-labelledby="studio-heading">
              <header className="studio-workspace__composer-head">
                <h2 id="studio-heading">{ts('page.imagesTitle')}</h2>
                <p className="studio-workspace__tagline">
                  {ts('page.tagline')}
                  {me && normalizeBillingPlan(me.billing_plan) !== 'pro' ? (
                    <span className="studio-workspace__price-hint">
                      {' '}
                      {ts('page.creditPerGen', { credits: studioImageCreditQuote.label })}
                      {studioImageCreditQuote.useDemo ? ts('page.demoSuffix') : ''}
                    </span>
                  ) : null}
                </p>
              </header>
              {!studioPaywalled && studioNeedsUserWsKey ? (
                <WavespeedSetupBanner
                  variant="studio"
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
                {ts('page.paywallBody')}
              </p>
              <p className="muted small" style={{ marginBottom: '1rem' }}>
                {isOwner ? (
                  <Trans i18nKey="page.paywallOwnerHint" ns="studio" components={{ strong: <strong /> }} />
                ) : (
                  ts('page.paywallMemberHint', { email: me?.owner_email ?? '—' })
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
                  {ts('page.goBilling')}
                </button>
              ) : (
                <button type="button" className="ghost-btn" onClick={() => setAccountOpen(true)}>
                  {ts('page.openCabinet')}
                </button>
              )}
            </div>
          ) : (
            <>
              {!canStudioGenerate ? (
                <div className="banner info">{ts('page.noGeneratePermission')}</div>
              ) : null}
              <div className="studio-workspace__composer-scroll">
              <div className="studio-slot-grid studio-slot-grid--composer">
            <div className="studio-mode-row studio-mode-compact" role="group" aria-label={ts('page.modeAria')}>
              <span className="studio-mode-label">{ts('page.modeLabel')}</span>
              <div className="studio-mode-segment">
                {STUDIO_IMAGE_MODE_IDS.map((id) => (
                  <button
                    key={id}
                    type="button"
                    className={`studio-mode-btn${studioMode === id ? ' is-active' : ''}`}
                    onClick={() => setStudioMode(id)}
                  >
                    {studioImageModeLabel(id)}
                  </button>
                ))}
              </div>
            </div>
            {studioMode === 'grok_compose' &&
            health?.studio_grok_scene_compose_configured === false ? (
              <div className="banner warn">
                <Trans i18nKey="page.grokNotConfigured" ns="studio" components={{ mono: <span className="mono" /> }} />
              </div>
            ) : null}
            <div className="studio-mode-row" role="group" aria-label={ts('page.styleAria')}>
              <span className="studio-mode-label">{ts('page.styleLabel')}</span>
              <div className="studio-mode-segment">
                <button
                  type="button"
                  className={`studio-mode-btn${studioWaveProfile === 'regular' ? ' is-active' : ''}`}
                  onClick={() => setStudioWaveProfile('regular')}
                >
                  {ts('page.regular')}
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
            {studioAvailableGenModels.length > 0 ? (
              <StudioPillField
                label={ts('page.modelLabel')}
                hint={ts('page.modelHint')}
                scrollRow
                options={studioAvailableGenModels.map((m) => ({
                  value: m.id,
                  label: m.label,
                  title: m.label,
                }))}
                value={studioWaveModelId}
                onChange={(v) => v != null && setStudioWaveModelId(String(v))}
              />
            ) : null}
            {!studioImageCreditQuote.useDemo &&
            (me?.demo_generations_remaining ?? 0) > 0 &&
            (me?.credits_balance ?? 0) <= 0 &&
            normalizeBillingPlan(me?.billing_plan) === 'credits' ? (
              <p className="studio-mode-hint">{studioDemoModelHint()}</p>
            ) : null}
            {import.meta.env.DEV && health?.studio_allow_prompt_only ? (
              <>
                <div className="studio-mode-row" role="group" aria-label={ts('imageUi.outputDevAria')}>
                  <span className="studio-mode-label">{ts('imageUi.outputLabel')}</span>
                  <div className="studio-mode-segment">
                    <button
                      type="button"
                      className={`studio-mode-btn${!studioDevPromptOnly ? ' is-active' : ''}`}
                      onClick={() => {
                        setStudioDevPromptOnly(false)
                        setStudioRefinedPromptPreview(null)
                      }}
                    >
                      {ts('imageUi.outputImage')}
                    </button>
                    <button
                      type="button"
                      className={`studio-mode-btn${studioDevPromptOnly ? ' is-active' : ''}`}
                      onClick={() => {
                        setStudioDevPromptOnly(true)
                        setStudioRefinedPromptPreview(null)
                      }}
                    >
                      {ts('imageUi.outputPromptOnly')}
                    </button>
                  </div>
                </div>
                <p className="studio-mode-hint">{ts('imageUi.devOutputHintPlain')}</p>
              </>
            ) : null}
            {health?.studio_wan_edit_tier_switch &&
            studioWaveProfile === 'nsfw' &&
            studioWaveModelId === 'wan-2.7' ? (
              <>
                <div className="studio-mode-row" role="group" aria-label={ts('imageUi.qualityAria')}>
                  <span className="studio-mode-label">{ts('page.qualityLabel')}</span>
                  <div className="studio-mode-segment">
                    <button
                      type="button"
                      className={`studio-mode-btn${studioWanEditTier === 'standard' ? ' is-active' : ''}`}
                      onClick={() => setStudioWanEditTier('standard')}
                    >
                      {ts('imageUi.standard')}
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
                <p className="studio-mode-hint">{ts('imageUi.qualityHint')}</p>
              </>
            ) : null}
            <StudioPillField
              label={ts('imageUi.formatLabel')}
              hint={ts('imageUi.formatHint')}
              scrollRow
              options={
                (() => {
                  const fromModel = aspectsForModel(studioGenModels, studioWaveModelId)
                  if (fromModel.length > 0) {
                    return fromModel.map((p) => ({
                      value: p.key,
                      label: p.key,
                      title: p.label,
                    }))
                  }
                  if (studioAspectPresets.length > 0) {
                    return studioAspectPresets.map((p) => ({
                      value: p.key,
                      label: p.key,
                      title: p.label,
                    }))
                  }
                  return [{ value: '9:16', label: '9:16', title: '9:16' }]
                })()
              }
              value={studioOutputAspect}
              onChange={(v) => v != null && setStudioOutputAspect(String(v))}
            />
            <StudioPillField
              label={ts('imageUi.modelLabel')}
              hint={
                studioMode === 'model_scene'
                  ? ts('imageUi.modelHintMain')
                  : studioModeUsesTextOnlyPrompt(studioMode)
                    ? ts('imageUi.modelHintRequired')
                    : studioMode === 'face_swap' || studioMode === 'grok_compose'
                      ? ts('imageUi.modelHintOrUpload')
                      : ts('imageUi.modelHintSheets')
              }
              icon={<IconModel className="studio-slot__icon-svg" />}
              scrollRow={studioModels.length > 4}
              options={studioModels.map((m) => ({ value: m.id, label: m.name }))}
              value={studioSelectedModelId}
              onChange={(v) => setStudioSelectedModelId(v)}
              allowEmpty={studioMode !== 'model_scene' && !studioModeUsesTextOnlyPrompt(studioMode)}
              emptyLabel={ts('imageUi.noModel')}
            />
            {studioMode === 'grok_compose' || studioMode === 'face_swap' ? (
              <StudioMediaSlot
                label={ts('imageUi.identityLabel')}
                hint={
                  studioSelectedModelId != null
                    ? ts('imageUi.identityHintCabinet')
                    : ts('imageUi.identityHintUpload')
                }
                icon="image"
                previewUrl={studioIdentityObjectUrl}
                accept="image/jpeg,image/png,image/webp,image/gif"
                onFile={(f) => setStudioIdentityFile(f)}
                onClear={() => setStudioIdentityFile(null)}
                emptyLabel="JPG, PNG, WebP"
              />
            ) : null}
            {studioMode === 'photo_edit' ? (
              <StudioArchiveThumbPicker
                label={ts('imageUi.archiveLabel')}
                hint={ts('imageUi.archiveHint')}
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
                    ? ts('imageUi.refPhoto')
                    : studioMode === 'face_swap' || studioMode === 'grok_compose'
                      ? ts('imageUi.refScene')
                      : ts('imageUi.refGeneric')
                }
                hint={
                  studioMode === 'photo_edit'
                    ? ts('imageUi.refOrThumb')
                    : studioMode === 'model_scene'
                      ? ts('imageUi.refAnchor')
                      : studioMode === 'grok_compose' || studioMode === 'face_swap'
                        ? ts('imageUi.refPose')
                        : ts('imageUi.refPoseScene')
                }
                icon="image"
                previewUrl={studioReferenceObjectUrl}
                accept="image/jpeg,image/png,image/webp,image/gif"
                onFile={(f) => {
                  setStudioFile(f)
                  if (f) {
                    setStudioPhotoEditArchiveId(null)
                    setStudioReferenceAnalysis(null)
                  }
                }}
                onClear={() => {
                  setStudioFile(null)
                  setStudioReferenceAnalysis(null)
                }}
                emptyLabel="JPG, PNG, WebP"
              />
            ) : (
              <p className="studio-mode-hint">
                {ts('imageUi.promptOnlyHint')}
              </p>
            )}
            {studioFile &&
            STUDIO_REFERENCE_ANALYSIS_MODES.includes(studioMode) ? (
              <div className="studio-ref-analysis-block">
                <p className="muted small" style={{ margin: '0 0 0.5rem' }}>
                  {ts('imageUi.refAnalysisLead')}
                </p>
                <div className="studio-ref-analysis-actions">
                  <button
                    type="button"
                    className="ghost-btn"
                    disabled={studioReferenceAnalyzing || studioBusy}
                    onClick={() => void analyzeStudioReference()}
                  >
                    {studioReferenceAnalyzing
                      ? ts('imageUi.analyzing')
                      : studioReferenceAnalysis
                        ? ts('imageUi.reanalyze')
                        : ts('imageUi.analyze')}
                  </button>
                </div>
                {studioReferenceAnalysis ? (
                  <div className="studio-ref-analysis-result">
                    <p className="studio-ref-analysis-summary">
                      ✓ {studioReferenceAnalysis.summary_ru}
                    </p>
                    {studioReferenceAnalysis.visibility.crop_locked_no_face ? (
                      <p className="muted small">
                        {ts('imageUi.noFaceCrop')}
                      </p>
                    ) : null}
                    {studioReferenceAnalysis.visibility.allowed_image_kinds?.length ? (
                      <p className="muted small">
                        {ts('imageUi.modelRefs')}{' '}
                        {studioReferenceAnalysis.visibility.allowed_image_kinds.join(', ')}
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <p className="muted small">
                    {ts('imageUi.autoAnalyze')}
                  </p>
                )}
              </div>
            ) : null}
            {studioMode === 'model_scene' ? (
              <p className="studio-mode-hint">
                {ts('imageUi.pipelineMain')}
              </p>
            ) : null}
            {studioMode === 'grok_compose' || studioMode === 'face_swap' ? (
              <p className="studio-mode-hint">
                {ts('imageUi.pipelineFaceSwap')}
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
              <span>{ts('imageUi.maskPaint')}</span>
            </label>
            ) : null}
            {!studioModeUsesTextOnlyPrompt(studioMode) &&
            studioMode !== 'model_scene' &&
            studioPaintInpaintMask &&
            studioInpaintBaseImageSrc ? (
              <div className="studio-mask-painter-controls">
                <div className="studio-mask-painter-row">
                  <label className="studio-mask-brush-label">
                    {ts('imageUi.brushLabel')}
                    <select
                      value={studioMaskBrushPreset}
                      onChange={(e) =>
                        setStudioMaskBrushPreset(e.target.value as 's' | 'm' | 'l')
                      }
                    >
                      <option value="s">{ts('imageUi.brushThin')}</option>
                      <option value="m">{ts('imageUi.brushMedium')}</option>
                      <option value="l">{ts('imageUi.brushThick')}</option>
                    </select>
                  </label>
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => studioMaskPainterRef.current?.clearMask()}
                  >
                    {ts('imageUi.clearMask')}
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
              {ts('imageUi.maskFile')}{' '}
              <span className="muted studio-file-name">{ts('imageUi.maskAlt')}</span>
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
                  {ts('imageUi.maskExternal')}
                </span>
              ) : null}
            </label>
            ) : null}
            {studioSelectedModelId != null ? (
              <div className="studio-mode-row" role="group" aria-label={ts('imageUi.exifAria')}>
                <span className="studio-mode-label">EXIF</span>
                <div className="studio-mode-segment">
                  <button
                    type="button"
                    className={`studio-mode-btn${studioExifCamera === 'selfie' ? ' is-active' : ''}`}
                    onClick={() => setStudioExifCamera('selfie')}
                  >
                    {ts('imageUi.exifSelfie')}
                  </button>
                  <button
                    type="button"
                    className={`studio-mode-btn${studioExifCamera === 'main' ? ' is-active' : ''}`}
                    onClick={() => setStudioExifCamera('main')}
                  >
                    {ts('imageUi.exifMain')}
                  </button>
                </div>
              </div>
            ) : null}
            {studioSelectedModelId != null ? (
              <p className="studio-mode-hint">
                {ts('imageUi.exifHint')}
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
                <span>{ts('imageUi.hairFromModel')}</span>
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
                <span>{ts('imageUi.poseRefWs')}</span>
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
                  <span className="studio-slot__label">{ts('imageUi.promptLabel')}</span>
                  <span className="studio-slot__hint">
                    {studioMode === 'model_scene'
                      ? ts('imageUi.promptHintScene')
                      : studioModeUsesTextOnlyPrompt(studioMode)
                        ? ts('imageUi.promptHintDetail')
                        : ts('imageUi.promptHintDefault')}
                  </span>
                </div>
              </div>
              <textarea
                rows={4}
                placeholder={
                  studioMode === 'model_scene'
                    ? ts('imageUi.promptPhOptional')
                    : studioModeUsesTextOnlyPrompt(studioMode)
                      ? ts('imageUi.promptPhExample')
                      : ts('imageUi.promptPhDefault')
                }
                value={studioDesc}
                onChange={(e) => setStudioDesc(e.target.value)}
              />
            </div>
            </div>
            {import.meta.env.DEV &&
            health?.studio_allow_prompt_only &&
            studioDevPromptOnly &&
            studioRefinedPromptPreview ? (
              <label className="studio-label">
                {ts('imageUi.promptOnlyResult')}
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
                  {ts('imageUi.pendingArchive')}
                </p>
                <button
                  type="button"
                  className="ghost-btn"
                  disabled={studioImportArchiveBusy || !canStudioGenerate}
                  onClick={() => void retryImportStudioImageToArchive('studio_photo')}
                >
                  {studioImportArchiveBusy ? ts('imageUi.savingArchive') : ts('imageUi.saveArchive')}
                </button>
              </div>
            ) : null}
            {studioGenImageUrl ? (
              <div className="studio-result-panel studio-generated">
                <h3 className="studio-generated-title">{ts('imageUi.resultTitle')}</h3>
                <div className="studio-generated-frame">
                  <img src={studioGenImageUrl} alt={ts('imageUi.resultAlt')} className="studio-gen-img" />
                </div>
                <div className="studio-upscale-row">
                  <label className="studio-upscale-control">
                    <span className="studio-upscale-control-label">{ts('imageUi.upscale')}</span>
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
                          ? ts('imageUi.upscalePick')
                          : undefined
                    }
                    onClick={() => void upscaleStudioGeneration()}
                  >
                    {studioUpscaleBusy ? ts('imageUi.upscaleBusy') : ts('imageUi.upscale')}
                  </button>
                  {canStudioGenerate && health?.studio_upscale_credit_cost != null ? (
                    <span className="studio-credit-hint">
                      {health.studio_upscale_credit_cost} {ts('imageUi.creditSuffix')}
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
                        : ts('imageUi.carousel3')
                    }
                    onClick={() => void runStudioCarousel(3)}
                  >
                    {studioCarouselBusy ? ts('page.generating') : ts('imageUi.carousel3Btn')}
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
                        : ts('imageUi.carousel4')
                    }
                    onClick={() => void runStudioCarousel(4)}
                  >
                    {studioCarouselBusy ? ts('page.generating') : ts('imageUi.carousel4Btn')}
                  </button>
                  {canStudioGenerate && health?.studio_carousel_credit_cost != null ? (
                    <span className="studio-credit-hint">
                      {health.studio_carousel_credit_cost} {ts('imageUi.creditPerFrame')}
                    </span>
                  ) : null}
                </div>
                <div className="studio-upscale-row">
                  <button
                    type="button"
                    className="ghost-btn studio-video-from-img-btn"
                    disabled={studioGenGenerationId == null || !canStudioGenerate}
                    title={ts('imageUi.toVideoTitle')}
                    onClick={() => {
                      if (studioGenGenerationId == null) return
                      const g = findStudioArchiveItem(studioGenGenerationId)
                      setMotionFrameArchiveId(studioGenGenerationId)
                      if (g?.studio_model_id != null) setStudioSelectedModelId(g.studio_model_id)
                      setMotionFirstFrameFile(null)
                      setAppSection('studio_video')
                    }}
                  >
                    {ts('imageUi.toVideo')}
                  </button>
                </div>
                <button
                  type="button"
                  className="send-btn studio-download"
                  disabled={studioDownloadBusy}
                  title={ts('imageUi.downloadIosTitle')}
                  onClick={() => void downloadStudioResultImage()}
                >
                  {studioDownloadBusy ? ts('imageUi.downloadBusy') : ts('imageUi.download')}
                </button>
              </div>
            ) : null}
              </div>
              <div className="studio-workspace__composer-bar">
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
                        ? ts('page.generating')
                        : studioPromptOnlyDev
                          ? ts('imageUi.buildPrompt')
                          : ts('page.generate')}
                      {canStudioGenerate &&
                      (studioPromptOnlyDev || integ?.wavespeed_configured) ? (
                        <span className="studio-magic-btn__cost">
                          <IconSpark className="studio-slot__icon-svg" />
                          {studioImageCreditQuote.label === 'Pro'
                            ? 'Pro'
                            : `${studioImageCreditQuote.label} ${ts('imageUi.creditSuffix')}`}
                        </span>
                      ) : null}
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}
            </div>
            {canStudioGenerate ? (
              <StudioGenerationGallery
                title={ts('gallery.title')}
                lead={studioArchiveRetentionLead(health)}
                items={studioGenerations}
                loading={studioArchiveInitialLoading}
                hasMore={studioGenHasMore}
                loadingMore={studioGenLoadingMore}
                onLoadMore={() => void loadMoreStudioGenerations()}
                loadMoreLabel={ts('imageUi.loadMore', { count: STUDIO_ARCHIVE_PAGE })}
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
                <h2 id="studio-bootstrap-heading">{ts('page.bootstrapTitle')}</h2>
                <p className="studio-workspace__tagline">
                  {ts('imageUi.bootstrapTagline')}
                </p>
              </header>
              {!canStudioGenerate ? (
                <div className="banner info">{ts('imageUi.noPermBanner')}</div>
              ) : studioPaywalled ? (
                <div className="banner info">
                  {ts('imageUi.subRequired')}
                </div>
              ) : (
                <div className="studio-workspace__composer-scroll">
                <StudioModelBootstrapPanel
                  canGenerate={canStudioGenerate}
                  studioPaywalled={studioPaywalled}
                  studioNeedsUserWsKey={studioNeedsUserWsKey}
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
                </div>
              )}
            </div>
            {canStudioGenerate ? (
              <StudioGenerationGallery
                title={ts('gallery.title')}
                lead={studioArchiveRetentionLead(health)}
                items={studioGenerations}
                loading={studioArchiveInitialLoading}
                hasMore={studioGenHasMore}
                loadingMore={studioGenLoadingMore}
                onLoadMore={() => void loadMoreStudioGenerations()}
                loadMoreLabel={ts('imageUi.loadMore', { count: STUDIO_ARCHIVE_PAGE })}
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
                <h2 id="studio-motion-heading">{ts('page.videoTitle')}</h2>
                <p className="studio-workspace__tagline">
                  {ts('videoUi.tagline')}
                </p>
              </header>
              {!studioPaywalled && studioNeedsUserWsKey ? (
                <WavespeedSetupBanner
                  variant="video"
                  canConnect={isOwner && canIntegrations}
                  onOpenIntegrations={openWavespeedIntegrations}
                />
              ) : null}
            {!canStudioGenerate ? (
              <div className="banner info" role="status">
                {ts('videoUi.noPerm')}
              </div>
            ) : studioPaywalled ? (
              <div className="banner info" role="status">
                {ts('videoUi.paywall')}
              </div>
            ) : (
              <>
              <div className="studio-workspace__composer-scroll">
              <div className="studio-slot-grid studio-slot-grid--composer">
                <StudioPillField
                  label={ts('videoUi.formatLabel')}
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
                  label={ts('videoUi.modelLabel')}
                  icon={<IconModel className="studio-slot__icon-svg" />}
                  options={studioModels.map((m) => ({ value: m.id, label: m.name }))}
                  value={studioSelectedModelId}
                  onChange={(v) => setStudioSelectedModelId(v)}
                  allowEmpty
                  emptyLabel={ts('videoUi.selectModel')}
                />
                {health?.studio_grok_motion_configured === false ? (
                  <div className="banner warn">
                    {ts('videoUi.grokNotConfigured')}
                  </div>
                ) : null}

                <div className="studio-video-step-card">
                  <h3>{ts('videoUi.frameMotion')}</h3>
                  <div className="studio-slot-grid">
                    <StudioMediaSlot
                      label={ts('videoUi.refVideo')}
                      hint={ts('videoUi.refVideoHint')}
                      icon="video"
                      busy={motionDrivingUploadBusy}
                      emptyLabel={motionVideoFile?.name || ts('videoUi.upload')}
                      accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
                      onFile={(f) => {
                        ++motionVideoUploadSeqRef.current
                        setMotionVideoFile(f)
                        setMotionVideoFileId(null)
                        resetMotionVideoWorkflow()
                        if (f) void uploadMotionDrivingVideo(f)
                      }}
                      onClear={() => {
                        ++motionVideoUploadSeqRef.current
                        setMotionVideoFile(null)
                        setMotionVideoFileId(null)
                        resetMotionVideoWorkflow()
                      }}
                    />
                    <StudioMediaSlot
                      label={ts('videoUi.firstFrame')}
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
                    label={ts('videoUi.archiveFrameLabel')}
                    hint={ts('videoUi.archiveFrameHint')}
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
                    label={ts('videoUi.frameStyle')}
                    options={[
                      { value: 'regular', label: ts('videoUi.frameRegular') },
                      { value: 'nsfw', label: 'NSFW' },
                    ]}
                    value={motionFirstFrameWaveProfile}
                    onChange={(v) =>
                      v != null &&
                      setMotionFirstFrameWaveProfile(v as 'regular' | 'nsfw')
                    }
                  />
                  {studioSelectedModelId != null ? (
                    <div className="studio-mode-row" role="group" aria-label={ts('videoUi.exifAria')}>
                      <span className="studio-mode-label">EXIF</span>
                      <div className="studio-mode-segment">
                        <button
                          type="button"
                          className={`studio-mode-btn${studioExifCamera === 'selfie' ? ' is-active' : ''}`}
                          onClick={() => setStudioExifCamera('selfie')}
                        >
                          {ts('imageUi.exifSelfie')}
                        </button>
                        <button
                          type="button"
                          className={`studio-mode-btn${studioExifCamera === 'main' ? ' is-active' : ''}`}
                          onClick={() => setStudioExifCamera('main')}
                        >
                          {ts('imageUi.exifMain')}
                        </button>
                      </div>
                    </div>
                  ) : null}
                  <div className="studio-toggles">
                    <label className="studio-toggle-row">
                      <span>{ts('videoUi.timelineFromVideo')}</span>
                      <input
                        type="checkbox"
                        checked={motionAutoPrompt}
                        onChange={(e) => setMotionAutoPrompt(e.target.checked)}
                      />
                    </label>
                    <label className="studio-toggle-row">
                      <span>{ts('videoUi.lockHairstyle')}</span>
                      <input
                        type="checkbox"
                        checked={motionLockHairstyle}
                        onChange={(e) => setMotionLockHairstyle(e.target.checked)}
                      />
                    </label>
                    <label className="studio-toggle-row">
                      <span>{ts('videoUi.frameNoWs')}</span>
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
                    placeholder={ts('videoUi.frameNotesPh')}
                    value={motionFrameNotes}
                    onChange={(e) => setMotionFrameNotes(e.target.value)}
                  />
                  {motionStep1Preview ? (
                    <details className="studio-video-auto-block">
                      <summary>{ts('videoUi.grokSummary')}</summary>
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
                      {motionBusyCompose ? ts('videoUi.grokBusy') : ts('videoUi.promptFromVideo')}
                    </button>
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={
                        motionBusyFrame ||
                        (motionDrivingUploadBusy && Boolean(motionVideoFile)) ||
                        !integ?.wavespeed_configured ||
                        studioSelectedModelId == null ||
                        (!motionVideoFile &&
                          !motionFirstFrameFile &&
                          motionFrameArchiveId == null)
                      }
                      title={
                        motionDrivingUploadBusy && motionVideoFile
                          ? ts('videoUi.waitVideoUpload')
                          : undefined
                      }
                      onClick={() => void runMotionFirstFrame()}
                    >
                      {motionBusyFrame
                        ? ts('videoUi.frameBusy')
                        : motionDrivingUploadBusy && motionVideoFile
                          ? ts('videoUi.videoUploading')
                          : ts('videoUi.genFrame')}
                    </button>
                  </div>
                </div>

                <div className="studio-video-step-card">
                  <h3>Seedance</h3>
                  <StudioArchiveThumbPicker
                    label={ts('videoUi.outfit')}
                    hint={ts('videoUi.outfitHint')}
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
                        <span className="studio-slot__label">{ts('videoUi.brief')}</span>
                        <span className="studio-slot__hint">{ts('videoUi.briefHint')}</span>
                      </div>
                    </div>
                    <textarea
                      rows={4}
                      placeholder={ts('videoUi.briefPh')}
                      value={motionDesc}
                      onChange={(e) => setMotionDesc(e.target.value)}
                    />
                  </div>
                  <StudioPillField
                    label={ts('videoUi.modelLabel')}
                    options={[
                      {
                        value: 'standard',
                        label: 'Seedance 2.0',
                      },
                      {
                        value: 'mini',
                        label: 'Seedance 2.0 Mini',
                      },
                    ]}
                    value={motionSeedanceVariant}
                    onChange={(v) => v != null && setMotionSeedanceVariant(v as SeedanceT2vVariant)}
                  />
                  <StudioPillField
                    label={ts('videoUi.qualityLabel')}
                    options={(health?.studio_seedance_t2v_resolutions ?? ['480p', '720p', '1080p']).map(
                      (res) => ({
                        value: res,
                        label: res.toUpperCase(),
                      }),
                    )}
                    value={motionVideoResolution}
                    onChange={(v) => v != null && setMotionVideoResolution(v as SeedanceT2vResolution)}
                  />
                  <StudioPillField
                    label={ts('videoUi.duration')}
                    options={Array.from(
                      { length: Math.max(0, seedanceDurationMax - seedanceDurationMin + 1) },
                      (_, i) => {
                        const sec = seedanceDurationMin + i
                        const cost = computeMotionVideoCreditCost(
                          sec,
                          motionHasReferenceVideo,
                          motionVideoPricing,
                          {
                            variant: motionSeedanceVariant,
                            resolution: motionVideoResolution,
                          },
                        )
                        const costSuffix = ` · ${cost} ${ts('imageUi.creditSuffix')}`
                        return { value: sec, label: ts('videoUi.durationSec', { sec }) + costSuffix }
                      },
                    )}
                    value={motionSeedanceDuration}
                    onChange={(v) => v != null && setMotionSeedanceDuration(Number(v))}
                  />
                  <p className="muted studio-field-hint">
                    {ts('videoUi.costHint', {
                      usdPerSec: motionVideoUsdPerSecDisplay.toFixed(3),
                      creditPerSec: computeMotionVideoCreditCost(1, motionHasReferenceVideo, motionVideoPricing, {
                        variant: motionSeedanceVariant,
                        resolution: motionVideoResolution,
                      }),
                      resolution: motionVideoResolution,
                      variant:
                        motionSeedanceVariant === 'mini'
                          ? ts('videoUi.costVariantMini')
                          : ts('videoUi.costVariantStandard'),
                      refVideoSuffix: motionHasReferenceVideo ? ts('videoUi.costRefVideoSuffix') : '',
                      rubPerUsd: motionVideoPricing.rub_per_usd,
                      rubPerCredit: motionVideoPricing.rub_per_credit,
                    })}
                  </p>
                  <label className="studio-field-optional">
                    {ts('videoUi.negativeLabel')}
                    <textarea
                      rows={2}
                      placeholder={ts('videoUi.negativePlaceholder')}
                      value={motionVideoNegPrompt}
                      onChange={(e) => setMotionVideoNegPrompt(e.target.value)}
                    />
                  </label>
                  <div className="studio-toggles">
                    <label className="studio-toggle-row">
                      <span>{ts('videoUi.soundToggle')}</span>
                      <input
                        type="checkbox"
                        checked={motionKeepSound}
                        onChange={(e) => setMotionKeepSound(e.target.checked)}
                      />
                    </label>
                  </div>
                  {motionAutoTextPreview ? (
                    <details className="studio-video-auto-block">
                      <summary>{ts('videoUi.seedancePrompt')}</summary>
                      <div className="studio-motion-auto-preview">{motionAutoTextPreview}</div>
                    </details>
                  ) : null}
                  {motionMsg ? (
                    <p className="muted studio-inline-msg">{motionMsg}</p>
                  ) : null}
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
                          {motionVideoDownloadBusy ? ts('imageUi.downloadBusy') : ts('imageUi.download')}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
              </div>
              <div className="studio-workspace__composer-bar">
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
                      {motionBusyVideo ? ts('videoUi.videoBusy') : ts('videoUi.genVideo')}
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
              </div>
              </>
            )}
            </div>
            {canStudioGenerate ? (
              <StudioGenerationGallery
                title={ts('gallery.title')}
                lead={studioArchiveRetentionLead(health, 'video')}
                items={studioVideoGalleryItems}
                loading={studioArchiveInitialLoading}
                hasMore={studioGenHasMore}
                loadingMore={studioGenLoadingMore}
                onLoadMore={() => void loadMoreStudioGenerations()}
                loadMoreLabel={ts('imageUi.loadMore', { count: STUDIO_ARCHIVE_PAGE })}
                emptyText={ts('videoUi.galleryEmpty')}
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
            <h2>{tc('sidebar.title')}</h2>
            <span className="sidebar-hint">{filteredConversations.length}</span>
          </div>
          <ConversationPlatformTabs
            platforms={chatVisiblePlatforms}
            active={chatPlatformTab}
            conversations={conversations}
            onChange={setChatPlatformTab}
          />
          <ConversationCategoryTabs
            active={chatCategoryTab}
            conversations={platformFilteredConversations}
            onChange={setChatCategoryTab}
          />
          {filteredConversations.length === 0 && (
            <p className="muted empty-hint">
              {conversations.length === 0
                ? tc('sidebar.emptyNoConversations')
                : chatCategoryTab !== 'all'
                  ? tc('sidebar.emptyCategory', {
                      category: conversationCategoryLabel(chatCategoryTab),
                    })
                  : tc('sidebar.emptyPlatform', { platform: platformLabel(chatPlatformTab) })}
            </p>
          )}
          <div className="sidebar-conv-scroll">
          <ul className="conv-list">
            {filteredConversations.map((c) => {
              const unread = c.unread_count ?? 0
              const isActive = c.id === selectedId
              const showUnread = unread > 0 && !isActive
              const catBadge = conversationCategoryBadgeLabel(c)
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    className={
                      isActive
                        ? 'conv active'
                        : showUnread
                          ? 'conv has-unread'
                          : c.peer_unavailable
                            ? 'conv is-unavailable'
                            : c.is_blocked
                              ? 'conv is-blocked'
                              : 'conv'
                    }
                    onClick={() => selectConversation(c.id)}
                  >
                    <span className="conv-avatar-wrap">
                      <ConvAvatarThumb conv={c} />
                      {showUnread ? <span className="conv-unread-dot" aria-hidden /> : null}
                      {catBadge ? (
                        <span className={`conv-avatar-badge conv-cat-badge conv-cat-badge--${catBadge.key}`}>
                          {catBadge.label}
                        </span>
                      ) : null}
                    </span>
                    <span className="conv-main">
                    <span className="conv-row-top">
                      <span className={`name${showUnread ? ' name--unread' : ''}`}>
                        {c.user_display_name ?? tc('thread.unnamed')}
                      </span>
                      {showUnread ? (
                        <span className="conv-unread-label">{tc('sidebar.unreadLabel')}</span>
                      ) : null}
                      {(c.outbound_lang || c.user_lang) && (
                        <span
                          className="lang"
                          title={
                            c.outbound_lang
                              ? tc('thread.replyLangForced', { lang: c.outbound_lang })
                              : tc('thread.replyLang', { lang: c.user_lang ?? '—' })
                          }
                        >
                          {c.outbound_lang ? `${c.outbound_lang}*` : c.user_lang}
                        </span>
                      )}
                      {showUnread ? (
                        <span className="unread-badge" title={tc('thread.unreadTitle')}>
                          {unread > 99 ? '99+' : unread}
                        </span>
                      ) : null}
                    </span>
                    {c.studio_model_id != null ? (
                      <span className="conv-model-line">
                        {tc('thread.modelLine')}{' '}
                        <strong>
                          {studioModels.find((m) => m.id === c.studio_model_id)?.name ??
                            `#${c.studio_model_id}`}
                        </strong>
                      </span>
                    ) : chatVisiblePlatforms.length <= 1 ? (
                      <span className="conv-model-line">{platformLabel(c.platform)}</span>
                    ) : null}
                    {c.last_message_preview && (
                      <span className={`preview${showUnread ? ' preview--unread' : ''}`}>
                        {c.last_message_preview}
                      </span>
                    )}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
          </div>
        </aside>

        <div className="chat-thread-wrap">
        <main className="thread">
          {!selected && (
            <div className="empty-thread">
              <div className="empty-card">
                <p className="empty-title">{tc('thread.selectTitle')}</p>
                <p className="empty-sub">{tc('thread.selectSub')}</p>
              </div>
            </div>
          )}
          {selected && (
            <>
              <div
                className={[
                  'thread-head',
                  isMobileLayout ? 'thread-head--mobile' : '',
                  isMobileLayout && threadSettingsOpen ? 'thread-head--settings-open' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                <div className="thread-head-identity">
                  {isMobileLayout && !showThreadDock ? (
                    <button
                      type="button"
                      className="back-btn"
                      onClick={() => setSelectedId(null)}
                      aria-label={tc('thread.backAria')}
                    >
                      <span className="back-btn-icon" aria-hidden>
                        ‹
                      </span>
                    </button>
                  ) : null}
                  <ThreadAvatar conv={selected} />
                  <div className="thread-head-text">
                    <h3>
                      {selected.user_display_name ?? tc('thread.dialogFallback')}
                      {(() => {
                        const headBadge = conversationCategoryBadgeLabel(selected)
                        return headBadge ? (
                          <span
                            className={`thread-head-cat-badge conv-cat-badge conv-cat-badge--${headBadge.key}`}
                          >
                            {headBadge.label}
                          </span>
                        ) : null
                      })()}
                    </h3>
                    <span className="meta">
                      {platformLabel(selected.platform)}
                      {!isMobileLayout ? ` · topic ${selected.external_topic_id}` : null}
                      {isMobileLayout &&
                      isOwner &&
                      selected.studio_model_id != null &&
                      studioModels.length > 0 ? (
                        <>
                          {' · '}
                          {studioModels.find((m) => m.id === selected.studio_model_id)?.name ??
                            `#${selected.studio_model_id}`}
                        </>
                      ) : null}
                    </span>
                  </div>
                  {!isMobileLayout &&
                  isOwner &&
                  selected.studio_model_id != null &&
                  studioModels.length > 0 ? (
                    <div className="thread-head-model-chip">
                      <span className="thread-head-model-chip__label">{tc('thread.modelLabel')}</span>
                      <span className="thread-head-model-chip__value">
                        {studioModels.find((m) => m.id === selected.studio_model_id)?.name ??
                          `#${selected.studio_model_id}`}
                      </span>
                    </div>
                  ) : null}
                  {isMobileLayout ? (
                    <div className="thread-head-actions">
                      <button
                        type="button"
                        className="thread-head-icon-btn"
                        title={tc('thread.notesTitle')}
                        onClick={() => setConvNotesOpen(true)}
                      >
                        <span aria-hidden>📝</span>
                      </button>
                      <button
                        type="button"
                        className="thread-head-icon-btn"
                      title={tc('thread.settingsTitle')}
                        aria-expanded={threadSettingsOpen}
                        onClick={() => setThreadSettingsOpen((o) => !o)}
                      >
                        <span aria-hidden>⚙</span>
                      </button>
                    </div>
                  ) : null}
                </div>
                <div
                  className={[
                    'thread-head-toolbar',
                    isMobileLayout && !threadSettingsOpen ? 'thread-head-toolbar--collapsed' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                    <div
                      className="outbound-lang-field thread-head-lang"
                      title={tc('thread.outboundLangTitle')}
                    >
                      {!isMobileLayout ? (
                        <label className="outbound-lang-label" htmlFor="outbound-lang-select">
                          {tc('thread.outboundLangLabel')}
                        </label>
                      ) : null}
                      <select
                        id="outbound-lang-select"
                        className="outbound-lang-select"
                        aria-label={tc('thread.outboundLangAria')}
                        value={selected.outbound_lang ?? ''}
                        disabled={outboundLangBusy}
                        onChange={(e) => void saveOutboundLang(selected.id, e.target.value)}
                      >
                        {outboundLangOptions().map((o) => (
                          <option key={o.value || 'auto'} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div
                      className="outbound-lang-field auto-translate-toggle"
                      title={tc('thread.autoTranslateTitle')}
                    >
                      <label className="auto-translate-label">
                        <input
                          type="checkbox"
                          checked={Boolean(selected.auto_translate_disabled)}
                          disabled={autoTranslateBusy}
                          onChange={(e) =>
                            void saveAutoTranslateDisabled(selected.id, e.target.checked)
                          }
                        />
                        <span>{tc('thread.noTranslate')}</span>
                      </label>
                    </div>
                    <div className="outbound-lang-field thread-head-lang">
                      <label className="outbound-lang-label" htmlFor="companion-mode-select">
                        {t('cabinet.integrations.aiCompanion')}
                      </label>
                      <select
                        id="companion-mode-select"
                        className="outbound-lang-select"
                        value={selected.companion_mode_override ?? ''}
                        disabled={companionModeBusy}
                        onChange={(e) =>
                          void saveCompanionModeOverride(selected.id, e.target.value)
                        }
                      >
                        {COMPANION_CONVERSATION_MODE_VALUES.map((value) => (
                          <option key={value || 'inherit'} value={value}>
                            {companionModeLabel(value, 'conversation')}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="outbound-lang-field thread-head-lang">
                      <label className="outbound-lang-label" htmlFor="conv-category-select">
                        {tc('thread.categoryLabel')}
                      </label>
                      <select
                        id="conv-category-select"
                        className="outbound-lang-select"
                        value={selected.manual_category ?? ''}
                        disabled={convCategoryBusy}
                        onChange={(e) =>
                          void saveManualCategory(selected.id, e.target.value)
                        }
                      >
                        {MANUAL_CATEGORY_VALUES.map((value) => (
                          <option key={value || 'none'} value={value}>
                            {manualCategoryLabel(value)}
                          </option>
                        ))}
                      </select>
                    </div>
                    {isOwner ? (
                      <div className="outbound-lang-field thread-head-lang">
                        <label className="outbound-lang-label" htmlFor="conv-assignee-select">
                          {tc('thread.chatterLabel')}
                        </label>
                        <select
                          id="conv-assignee-select"
                          className="outbound-lang-select"
                          value={selected.assigned_user_id ?? ''}
                          disabled={assigneeBusy}
                          onChange={(e) =>
                            void saveAssignedUser(selected.id, e.target.value)
                          }
                        >
                          <option value="">{tc('thread.chatterAny')}</option>
                          {workspaceMembers.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.member_login || `#${m.id}`}
                            </option>
                          ))}
                        </select>
                      </div>
                    ) : null}
                    <div
                      className="outbound-lang-field auto-translate-toggle"
                      title={tc('thread.blockTitle')}
                    >
                      <label className="auto-translate-label">
                        <input
                          type="checkbox"
                          checked={Boolean(selected.is_blocked)}
                          disabled={convBlockedBusy}
                          onChange={(e) =>
                            void saveConversationBlocked(selected.id, e.target.checked)
                          }
                        />
                        <span>{tc('thread.block')}</span>
                      </label>
                    </div>
                    <div className="outbound-lang-field" style={{ gridColumn: '1 / -1' }}>
                      <button
                        type="button"
                        className="ghost-btn"
                        disabled={convHideBusy}
                        onClick={() => void hideConversation(selected.id)}
                      >
                        {convHideBusy ? '…' : tc('threadExtra.hideFromList')}
                      </button>
                    </div>
                    {companionHealth &&
                    (companionHealth.reasons.length > 0 ||
                      companionHealth.status !== 'ok') ? (
                      <div
                        className="companion-health-hint muted small"
                        title={companionHealth.reasons.join(' · ')}
                        style={{ gridColumn: '1 / -1' }}
                      >
                        AI: {companionHealth.status}
                        {companionHealth.pending_jobs > 0
                          ? tc('companion.queue', { count: companionHealth.pending_jobs })
                          : ''}
                        {companionHealth.reasons[0]
                          ? ` · ${companionHealth.reasons[0]}`
                          : ''}
                      </div>
                    ) : null}
                    {selected.peer_unavailable ? (
                      <div className="thread-peer-unavailable-banner" role="status">
                        {tc('threadExtra.fanvueUnavailableBanner')}
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
                          <span className="muted">{tc('messages.loadingHistory')}</span>
                        </div>
                      ) : null}
                      {displayMessages.map((m) => {
                        const hasMedia =
                          Boolean(m.localPreviewUrl) ||
                          Boolean(m.attachments && m.attachments.length > 0)
                        const noTranslate = Boolean(selected.auto_translate_disabled)
                        const displayInboundText = noTranslate
                          ? m.text_original
                          : m.text_translated ?? m.text_original
                        const hasText = Boolean(
                          (m.direction === 'inbound'
                            ? displayInboundText
                            : m.text_original
                          )?.trim(),
                        )
                        const reactionCounts = new Map<
                          string,
                          { count: number; hasOwner: boolean }
                        >()
                        for (const r of m.reactions ?? []) {
                          const cur = reactionCounts.get(r.emoji) ?? {
                            count: 0,
                            hasOwner: false,
                          }
                          cur.count += 1
                          if (r.actor === 'owner') cur.hasOwner = true
                          reactionCounts.set(r.emoji, cur)
                        }
                        return (
                      <article
                        key={m.id}
                        data-msg-id={m.id}
                        className={
                          m.direction === 'inbound'
                            ? 'bubble in msg-enter'
                            : m.pending
                              ? 'bubble out msg-enter bubble-out-pending'
                              : 'bubble out msg-enter'
                        }
                      >
                        {m.reply_preview ? (
                          <button
                            type="button"
                            className="bubble-reply-quote"
                            onClick={() => scrollToMessage(m.reply_to_message_id)}
                            title={tc('messages.gotoTitle')}
                          >
                            {m.reply_preview}
                          </button>
                        ) : null}
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
                          noTranslate ? (
                            <div className="ru">{m.text_original}</div>
                          ) : (
                            <>
                              <div className="ru">{displayInboundText}</div>
                              <div className="orig" title={tc('messages.originalTitle')}>
                                {m.text_original}
                              </div>
                            </>
                          )
                        ) : hasText ? (
                          noTranslate ? (
                            <div className="ru">{m.text_original}</div>
                          ) : (
                            <>
                              <div className="ru">{m.text_original}</div>
                              <div
                                className={m.pending ? 'orig bubble-pending-meta' : 'orig'}
                                title={tc('messages.sentTitle')}
                              >
                                →{' '}
                                {m.pending
                                  ? tc('messages.translating')
                                  : m.text_translated ?? '—'}
                              </div>
                            </>
                          )
                        ) : null}
                        {reactionCounts.size > 0 ? (
                          <div className="bubble-reactions" aria-label={tc('reactions.aria')}>
                            {[...reactionCounts.entries()].map(([emoji, info]) => (
                              <button
                                key={emoji}
                                type="button"
                                className={
                                  info.hasOwner
                                    ? 'bubble-reaction-chip bubble-reaction-chip--mine'
                                    : 'bubble-reaction-chip'
                                }
                                disabled={Boolean(reactionBusyKey?.startsWith(`${m.id}:`))}
                                onClick={() => void toggleReaction(m, emoji)}
                                title={info.hasOwner ? tc('reactions.removeTitle') : tc('reactions.addTitle')}
                              >
                                <span>{emoji}</span>
                                {info.count > 1 ? (
                                  <span className="bubble-reaction-count">{info.count}</span>
                                ) : null}
                              </button>
                            ))}
                          </div>
                        ) : null}
                        <div className="bubble-foot">
                          <time>
                            {new Date(m.created_at).toLocaleString('ru-RU', {
                              day: '2-digit',
                              month: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </time>
                          {!m.pending ? (
                            <div className="bubble-actions">
                              <button
                                type="button"
                                className="bubble-action-btn"
                                title={tc('reactions.replyTitle')}
                                onClick={() => setReplyToMessage(m)}
                              >
                                ↩
                              </button>
                              {CHAT_REACTIONS.map((emoji) => {
                                const info = reactionCounts.get(emoji)
                                const busy = reactionBusyKey === `${m.id}:${emoji}`
                                return (
                                  <button
                                    key={emoji}
                                    type="button"
                                    className={
                                      info?.hasOwner
                                        ? 'bubble-action-btn bubble-action-btn--active'
                                        : 'bubble-action-btn'
                                    }
                                    title={tc('reactions.emojiTitle')}
                                    disabled={busy}
                                    onClick={() => void toggleReaction(m, emoji)}
                                  >
                                    {emoji}
                                  </button>
                                )
                              })}
                            </div>
                          ) : null}
                        </div>
                        {m.companion_bot && m.direction === 'outbound' && !m.pending ? (
                          <div
                            className={
                              m.operator_rating === 1
                                ? 'bubble-companion-rate bubble-companion-rate--rated-up'
                                : m.operator_rating === -1
                                  ? 'bubble-companion-rate bubble-companion-rate--rated-down'
                                  : 'bubble-companion-rate'
                            }
                            aria-label={tc('companion.rateAria')}
                          >
                            <span className="bubble-companion-rate-label">{tc('companion.rateLabel')}</span>
                            <div className="bubble-companion-rate-actions">
                              <button
                                type="button"
                                className={
                                  m.operator_rating === 1
                                    ? 'bubble-companion-rate-btn bubble-companion-rate-btn--up bubble-companion-rate-btn--selected'
                                    : 'bubble-companion-rate-btn bubble-companion-rate-btn--up'
                                }
                                title={
                                  m.operator_rating === 1
                                    ? tc('companion.unrateGood')
                                    : tc('companion.goodTitle')
                                }
                                disabled={companionRatingBusy === m.id}
                                onClick={() => void rateCompanionMessage(m.id, 1)}
                              >
                                👍
                              </button>
                              <button
                                type="button"
                                className={
                                  m.operator_rating === -1
                                    ? 'bubble-companion-rate-btn bubble-companion-rate-btn--down bubble-companion-rate-btn--selected'
                                    : 'bubble-companion-rate-btn bubble-companion-rate-btn--down'
                                }
                                title={
                                  m.operator_rating === -1
                                    ? tc('companion.unrateBad')
                                    : tc('companion.badTitle')
                                }
                                disabled={companionRatingBusy === m.id}
                                onClick={() => void rateCompanionMessage(m.id, -1)}
                              >
                                👎
                              </button>
                            </div>
                            <span
                              className={
                                companionRatingBusy === m.id
                                  ? 'bubble-companion-rate-status bubble-companion-rate-status--busy'
                                  : companionRatingSavedId === m.id
                                    ? 'bubble-companion-rate-status bubble-companion-rate-status--saved'
                                    : m.operator_rating === 1
                                      ? 'bubble-companion-rate-status bubble-companion-rate-status--up'
                                      : m.operator_rating === -1
                                        ? 'bubble-companion-rate-status bubble-companion-rate-status--down'
                                        : 'bubble-companion-rate-status bubble-companion-rate-status--hint'
                              }
                              aria-live="polite"
                            >
                              {companionRatingBusy === m.id
                                ? tCommon('saving')
                                : companionRatingSavedId === m.id
                                  ? tCommon('saved')
                                  : m.operator_rating === 1
                                    ? tc('companion.ratedGood')
                                    : m.operator_rating === -1
                                      ? tc('companion.ratedBad')
                                      : tc('companion.helpLearn')}
                            </span>
                          </div>
                        ) : null}
                      </article>
                        )
                      })}
                      {companionDrafts.map((draft) => {
                        const effectiveMode = selected
                          ? resolveEffectiveCompanionMode(selected)
                          : null
                        const manualDraft = isCompanionManualDraftMode(effectiveMode)
                        return (
                        <article
                          key={`draft-${draft.id}`}
                          className="bubble out msg-enter companion-draft-bubble"
                        >
                          <div className="companion-draft-label">
                            {manualDraft ? tc('companion.draftLabel') : tc('companion.failedLabel')}
                          </div>
                          <div className="ru">{draft.draft_text}</div>
                          {draft.target_lang ? (
                            <div className="orig">→ {draft.target_lang}</div>
                          ) : null}
                          <div className="companion-draft-actions">
                            <button
                              type="button"
                              className="send-btn"
                              disabled={companionDraftBusy === draft.id}
                              onClick={() => void approveCompanionDraft(draft)}
                            >
                              {tc('thread.send')}
                            </button>
                            <button
                              type="button"
                              className="ghost-btn"
                              disabled={companionDraftBusy === draft.id}
                              onClick={() => void rejectCompanionDraft(draft.id)}
                            >
                              {tc('companion.reject')}
                            </button>
                          </div>
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
                    {tc('composer.scrollToLatest')}
                  </button>
                )}

                <div className="composer-shell" ref={composerRef}>
                  <div className="composer-inner" ref={emojiWrapRef}>
                    {replyToMessage ? (
                      <div className="composer-reply-bar">
                        <div className="composer-reply-bar__main">
                          <span className="composer-reply-bar__label">{tc('composer.replyTo')}</span>
                          <span className="composer-reply-bar__text">
                            {(
                              replyToMessage.text_original ||
                              replyToMessage.text_translated ||
                              tc('composer.messageFallback')
                            ).slice(0, 120)}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="composer-reply-bar__clear"
                          onClick={() => setReplyToMessage(null)}
                          title={tc('composer.cancelReplyTitle')}
                        >
                          ×
                        </button>
                      </div>
                    ) : null}
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
                              <span className="muted">{tc('composer.archiveBadge', { id: chatReplyArchiveId })}</span>
                            )
                          })()
                        ) : null}
                        <button
                          type="button"
                          className="chat-composer-attach-preview__clear"
                          onClick={clearChatReplyAttachment}
                          title={tc('composer.removeAttachmentTitle')}
                        >
                          ×
                        </button>
                      </div>
                    )}
                    {chatArchivePickerOpen ? (
                      <div className="chat-composer-archive">
                        <StudioArchiveThumbPicker
                          label={tc('composer.archiveLabel')}
                          hint={tc('composer.archiveHint')}
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
                    {chatterSnippets.length > 0 ? (
                      <div className="chatter-snippets-row">
                        {chatterSnippets.slice(0, 8).map((sn) => (
                          <button
                            key={sn.id}
                            type="button"
                            className="chatter-snippet-btn"
                            title={sn.body}
                            onClick={() => insertChatterSnippet(sn.body)}
                          >
                            {sn.title}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    <div className="composer-field">
                    <textarea
                      ref={textareaRef}
                      rows={3}
                      placeholder={
                        selected.peer_unavailable
                          ? tc('composer.hintFanvueBlocked')
                          : tc('composer.hintTranslate')
                      }
                      title={
                        selected.peer_unavailable
                          ? tc('composer.titleFanvueBlocked')
                          : tc('composer.titleTranslate')
                      }
                      value={draft}
                      disabled={Boolean(selected.peer_unavailable)}
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
                    <div className="composer-bottom-bar">
                      <div className="composer-toolbar">
                        <label
                          className="icon-btn icon-btn--file"
                          title={tc('composer.photoDeviceTitle')}
                        >
                          <input
                            ref={chatReplyFileInputRef}
                            type="file"
                            accept="image/jpeg,image/png,image/webp,image/gif"
                            className="chat-composer-file-input"
                            disabled={Boolean(selected.peer_unavailable)}
                            onChange={(e) => {
                              const f = e.target.files?.[0]
                              if (!f) return
                              setChatReplyFile(f)
                              setChatReplyArchiveId(null)
                            }}
                          />
                          <span aria-hidden>📎</span>
                        </label>
                        <button
                          type="button"
                          className="icon-btn"
                          title={tc('composer.archiveTitle')}
                          aria-expanded={chatArchivePickerOpen}
                          disabled={Boolean(selected.peer_unavailable)}
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
                          className="icon-btn icon-btn--emoji"
                          title={tc('composer.emojiTitle')}
                          aria-expanded={emojiOpen}
                          aria-haspopup="dialog"
                          disabled={Boolean(selected.peer_unavailable)}
                          onClick={(e) => {
                            e.stopPropagation()
                            setEmojiOpen((o) => !o)
                          }}
                        >
                          <span className="icon-emoji" aria-hidden>
                            🙂
                          </span>
                        </button>
                        {emojiOpen ? (
                          <div
                            className="emoji-popover"
                            onMouseDown={(e) => e.stopPropagation()}
                            onTouchStart={(e) => e.stopPropagation()}
                          >
                            <EmojiPicker
                              theme={Theme.DARK}
                              onEmojiClick={onEmojiPick}
                              width={320}
                              height={380}
                              lazyLoadEmojis
                            />
                          </div>
                        ) : null}
                      </div>
                      <div className="composer-actions">
                        <span className="hint">{tc('composer.shortcut')}</span>
                        <button
                          type="button"
                          className="send-btn"
                          onClick={() => void sendReply()}
                          disabled={
                            Boolean(selected.peer_unavailable) ||
                            (!draft.trim() && !chatReplyHasAttachment)
                          }
                        >
                          {tc('thread.send')}
                        </button>
                      </div>
                    </div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </main>
        </div>

        {selected ? (
          <>
            {convNotesOpen && isMobileLayout ? (
              <button
                type="button"
                className="conv-notes-backdrop"
                aria-label={tc('notes.closeAria')}
                onClick={() => setConvNotesOpen(false)}
              />
            ) : null}
            <aside
              className={['conv-notes-panel', convNotesOpen ? 'open' : ''].filter(Boolean).join(' ')}
              aria-label={tc('notes.panelAria')}
            >
              <button
                type="button"
                className="conv-notes-tab"
                aria-expanded={convNotesOpen}
                title={convNotesOpen ? tc('notes.toggleHide') : tc('notes.toggleTitle')}
                onClick={() => setConvNotesOpen((o) => !o)}
              >
                <span className="conv-notes-tab-label" aria-hidden>
                  {tc('notes.title')}
                </span>
              </button>
              <div className="conv-notes-panel-inner">
                <div className="conv-notes-head">
                  <h4>{tc('notes.title')}</h4>
                  <span className="muted conv-notes-sub">
                    {selected.user_display_name ?? tc('notes.userFallback')}
                  </span>
                  {isMobileLayout ? (
                    <button
                      type="button"
                      className="conv-notes-close"
                      aria-label={tc('notes.closeAria')}
                      onClick={() => setConvNotesOpen(false)}
                    >
                      {tCommon('close')}
                    </button>
                  ) : null}
                </div>

                {convNotesLoading ? (
                  <div className="conv-notes-loading">
                    <span className="skeleton-line" />
                    <span className="skeleton-line short" />
                  </div>
                ) : (
                  <div className="conv-notes-body">
                    {convNotesPinned.length > 0 ? (
                      <div className="conv-notes-pinned">
                        {convNotesPinned.map((n) => (
                          <article
                            key={n.id}
                            className={`conv-note conv-note--${n.kind}${n.is_pinned ? ' conv-note--pinned' : ''}`}
                          >
                            <div className="conv-note-meta">
                              <span className={`conv-note-badge conv-note-badge--${n.kind}`}>
                                {conversationNoteKindLabel(n.kind)}
                              </span>
                              <time className="muted" dateTime={n.updated_at}>
                                {formatNoteUpdatedAtApp(n.updated_at)}
                              </time>
                            </div>
                            <p className="conv-note-body">{n.content}</p>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="conv-notes-empty muted">
                        {tc('notes.emptyProfile')}
                      </p>
                    )}

                    <div className="conv-notes-scroll">
                      {convNotesScroll.map((n) => (
                        <article
                          key={n.id}
                          className={`conv-note conv-note--${n.kind}${n.is_pinned ? ' conv-note--pinned' : ''}`}
                        >
                          <div className="conv-note-meta">
                            <span className={`conv-note-badge conv-note-badge--${n.kind}`}>
                              {conversationNoteKindLabel(n.kind)}
                            </span>
                            <span className="muted">{n.author_label}</span>
                            <time className="muted" dateTime={n.updated_at}>
                              {formatNoteUpdatedAtApp(n.updated_at)}
                            </time>
                          </div>
                          <p className="conv-note-body">{n.content}</p>
                          {n.kind === 'manual' ? (
                            <div className="conv-note-actions">
                              <button
                                type="button"
                                className="conv-note-action"
                                disabled={convNotesBusy}
                                title={n.is_pinned ? tc('notes.unpin') : tc('notes.pin')}
                                onClick={() => void toggleConvNotePin(n)}
                              >
                                {n.is_pinned ? tc('notes.unpin') : tc('notes.pin')}
                              </button>
                              <button
                                type="button"
                                className="conv-note-action conv-note-action--danger"
                                disabled={convNotesBusy}
                                onClick={() => void deleteConvNote(n.id)}
                              >
                                {tc('notes.delete')}
                              </button>
                            </div>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  </div>
                )}

                <div className="conv-notes-compose">
                  {convNoteComposeOpen ? (
                    <>
                      <textarea
                        ref={convNoteDraftRef}
                        rows={3}
                        className="conv-notes-draft"
                        placeholder={tc('notes.placeholder')}
                        value={convNoteDraft}
                        disabled={convNotesBusy}
                        onChange={(e) => setConvNoteDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Escape') {
                            e.preventDefault()
                            closeConvNoteCompose()
                            return
                          }
                          if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                            e.preventDefault()
                            void addConvNote()
                          }
                        }}
                      />
                      <div className="conv-notes-compose-actions">
                        <button
                          type="button"
                          className="conv-notes-cancel-btn"
                          disabled={convNotesBusy}
                          onClick={closeConvNoteCompose}
                        >
                          {tc('notes.cancel')}
                        </button>
                        <button
                          type="button"
                          className="send-btn conv-notes-add-btn"
                          disabled={convNotesBusy || !convNoteDraft.trim()}
                          onClick={() => void addConvNote()}
                        >
                          {tc('notes.save')}
                        </button>
                      </div>
                    </>
                  ) : (
                    <div className="conv-notes-compose-actions conv-notes-compose-actions--quick">
                      <button
                        type="button"
                        className="conv-notes-analyze-btn"
                        disabled={convNotesAnalyzeBusy || convNotesLoading}
                        onClick={() => void analyzeConvNotes()}
                      >
                        {convNotesAnalyzeBusy ? tc('notes.analyzing') : tc('notes.analyzeQuick')}
                      </button>
                      <button
                        type="button"
                        className="send-btn conv-notes-add-btn"
                        disabled={convNotesLoading}
                        onClick={openConvNoteCompose}
                      >
                        {tc('notes.addQuick')}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </aside>
          </>
        ) : null}
      </div>
      )}
        </AppShell>
      ) : null}
    </div>
  )
}
