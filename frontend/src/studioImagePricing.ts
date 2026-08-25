import { normalizeBillingPlan } from './billing/planCatalog'

export type GrokPipelineKind = 'none' | 'light' | 'standard' | 'heavy' | 'workflow'
export type WaveProfile = 'regular' | 'nsfw'
export type WanEditTier = 'standard' | 'pro'

export type StudioImagePricingHealth = {
  models?: Array<{
    wave_model_id: string
    credits_standard_tier?: number
    credits_pro_tier?: number | null
    usd_standard_tier?: number
  }>
}

/** Fallback cent-credits (1 cr = $0.01), aligned with backend defaults. */
const DEFAULT_CREDITS: Record<string, number> = {
  'nano-banana-2': 13,
  'nano-banana-pro': 17,
  'gpt-image-2': 10,
  'wan-2.7': 8,
  'seedream-v5.0-pro': 9,
}

const GROK_SURCHARGE_CREDITS: Record<GrokPipelineKind, number> = {
  none: 0,
  light: 1,
  standard: 2,
  heavy: 3,
  workflow: 3,
}

const WAN_PRO_EXTRA = 3

export function normalizeWaveModelId(raw: string | null | undefined): string {
  const m = (raw || 'wan-2.7').trim().toLowerCase()
  if (m === 'wan-2.7-pro') return 'wan-2.7'
  return m in DEFAULT_CREDITS ? m : 'wan-2.7'
}

export function wanEditTierFromUiModelId(raw: string | null | undefined): WanEditTier {
  return (raw || '').trim().toLowerCase() === 'wan-2.7-pro' ? 'pro' : 'standard'
}

export function normalizeWaveProfile(raw: string | null | undefined): WaveProfile {
  return (raw || '').trim().toLowerCase() === 'regular' ? 'regular' : 'nsfw'
}

export function effectiveWaveModelForStudio(
  waveModelId: string | null | undefined,
  waveProfile: WaveProfile,
): string {
  const explicit = (waveModelId || '').trim().toLowerCase()
  if (explicit in DEFAULT_CREDITS) return explicit
  return waveProfile === 'regular' ? 'nano-banana-pro' : 'wan-2.7'
}

export function grokPipelineForStudioMode(
  mode: string,
  opts?: { workflow?: boolean },
): GrokPipelineKind {
  if (opts?.workflow) return 'workflow'
  const m = (mode || '').trim().toLowerCase()
  if (m === 'model' || m === 'model_scene' || m === 'grok_compose') return 'standard'
  return 'light'
}

function lookupHealthCredits(
  health: StudioImagePricingHealth | null | undefined,
  model: string,
  tier: WanEditTier,
): number | null {
  const rows = health?.models
  if (!Array.isArray(rows)) return null
  const row = rows.find((r) => r.wave_model_id === model)
  if (!row) return null
  if (model === 'wan-2.7' && tier === 'pro') {
    const pro = row.credits_pro_tier
    if (typeof pro === 'number' && pro > 0) return pro
  }
  const std = row.credits_standard_tier
  if (typeof std === 'number' && std > 0) return std
  return null
}

export function quoteStudioImageCredits(
  params: {
    waveModelId?: string | null
    waveProfile?: WaveProfile | string | null
    wanEditTier?: WanEditTier | string | null
    grokPipeline?: GrokPipelineKind
    studioMode?: string
    workflow?: boolean
    extraReferenceCount?: number
  },
  health?: StudioImagePricingHealth | null,
): number {
  const profile = normalizeWaveProfile(params.waveProfile ?? 'nsfw')
  const model = params.waveModelId
    ? normalizeWaveModelId(params.waveModelId)
    : effectiveWaveModelForStudio(null, profile)
  const tier = (params.wanEditTier || 'standard').toString().toLowerCase() === 'pro' ? 'pro' : 'standard'
  const grok =
    params.grokPipeline ??
    grokPipelineForStudioMode(params.studioMode ?? 'model_scene', {
      workflow: params.workflow,
    })

  let base = lookupHealthCredits(health, model, tier)
  if (base == null) {
    base = DEFAULT_CREDITS[model] ?? 8
    if (model === 'wan-2.7' && tier === 'pro') base += WAN_PRO_EXTRA
  }

  const refs = Math.max(0, Number(params.extraReferenceCount) || 0)
  const refExtra = Math.min(2, Math.floor(refs / 2))
  const total = base + (GROK_SURCHARGE_CREDITS[grok] ?? 2) + refExtra
  return Math.max(1, total)
}

/** Режимы кабинета с Anchor pipeline (wardrobe prep + финальный кадр). */
export function cabinetModeUsesAnchorPipeline(modeId: string | null | undefined): boolean {
  const m = (modeId || '').trim().toLowerCase()
  return m === 'ref' || m === 'swap'
}

function grokPipelineForCabinetMode(modeId: string): GrokPipelineKind {
  const m = (modeId || '').trim().toLowerCase()
  if (m === 'swap') return 'light'
  if (m === 'location' || m === 'outfit') return 'workflow'
  return 'standard'
}

/**
 * Полная цена генерации в кабинете «Картинки»: модель + Grok + prompt refine (+ anchor prep при ref/swap).
 * Совпадает с backend _refine_prompt_billing_quote (worst-case для anchor — prep не из кэша).
 */
export function quoteCabinetImageGenerationCredits(
  params: {
    waveModelId?: string | null
    waveProfile?: WaveProfile | string | null
    wanEditTier?: WanEditTier | string | null
    modeId?: string | null
    extraReferenceCount?: number
  },
  health?: StudioImagePricingHealth | null,
  opts?: { promptRefineCredits?: number | null },
): number {
  const modeId = (params.modeId || 'ref').trim().toLowerCase()
  const waveParams = {
    waveModelId: params.waveModelId,
    waveProfile: params.waveProfile,
    wanEditTier: params.wanEditTier,
    grokPipeline: grokPipelineForCabinetMode(modeId),
    studioMode: MODE_STUDIO_MODE[modeId] || 'model_scene',
    workflow: modeId === 'location' || modeId === 'outfit',
    extraReferenceCount: params.extraReferenceCount,
  }
  const imageCore = quoteStudioImageCredits(waveParams, health)
  const promptRefine = Math.max(0, Number(opts?.promptRefineCredits ?? 2) || 2)
  let total = imageCore + promptRefine
  if (cabinetModeUsesAnchorPipeline(modeId)) {
    total += quoteStudioImageCredits(
      { ...waveParams, grokPipeline: 'none' },
      health,
    )
  }
  return Math.max(1, total)
}

const MODE_STUDIO_MODE: Record<string, string> = {
  ref: 'model_scene',
  swap: 'model',
  outfit: 'model_scene',
  location: 'model_scene',
  prompt: 'model_scene',
  edit: 'photo_edit',
  carousel: 'photo_edit',
}

export function studioGenerationUsesDemo(params: {
  billingPlan?: string | null
  demoRemaining: number
  creditsBalance: number
  waveProfile: WaveProfile
  waveModelId?: string | null
  wanEditTier?: WanEditTier | string | null
  studioMode?: string
  workflow?: boolean
}): boolean {
  if (normalizeBillingPlan(params.billingPlan) !== 'credits') return false
  if (params.demoRemaining <= 0) return false
  if (params.creditsBalance > 0) return false
  const profile = normalizeWaveProfile(params.waveProfile)
  const model = params.waveModelId
    ? normalizeWaveModelId(params.waveModelId)
    : effectiveWaveModelForStudio(null, profile)
  const tier =
    (params.wanEditTier || 'standard').toString().toLowerCase() === 'pro' ? 'pro' : 'standard'
  if (tier === 'pro') return false

  const regularModels = new Set(['nano-banana-2', 'nano-banana-pro', 'gpt-image-2', 'seedream-v5.0-pro'])
  const nsfwModels = new Set(['wan-2.7', 'seedream-v5.0-pro'])

  if (profile === 'regular') return regularModels.has(model)
  return nsfwModels.has(model)
}

export function formatStudioImageCostLabel(
  credits: number | null,
  opts?: { isProPlan?: boolean; demoRemaining?: number; useDemo?: boolean; lang?: string },
): string {
  if (opts?.isProPlan) return 'Pro'
  if (opts?.useDemo && (opts.demoRemaining ?? 0) > 0) return '0'
  if (credits == null) return '—'
  const usd = (credits / 100).toFixed(2)
  const lang = opts?.lang
  if (lang === 'ru') return `${credits} кр. ($${usd})`
  if (lang === 'en') return `${credits} cr ($${usd})`
  return String(credits)
}

export function formatImageCostBadge(
  credits: number,
  lang: string,
  opts?: { perFrame?: boolean },
): string {
  const cr = lang === 'ru' ? 'кр.' : 'cr'
  const usd = `$${(credits / 100).toFixed(2)}`
  if (opts?.perFrame) {
    return lang === 'ru' ? `−${credits} ${cr}/кадр (${usd})` : `−${credits} ${cr}/frame (${usd})`
  }
  return lang === 'ru' ? `−${credits} ${cr} (${usd})` : `−${credits} ${cr} (${usd})`
}
