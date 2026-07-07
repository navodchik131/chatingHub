import { normalizeBillingPlan } from './billing/planCatalog'

export type GrokPipelineKind = 'none' | 'light' | 'standard' | 'heavy' | 'workflow'
export type WaveProfile = 'regular' | 'nsfw'
export type WanEditTier = 'standard' | 'pro'

const WS_BASE_CREDITS: Record<string, number> = {
  'nano-banana-2': 2,
  'nano-banana-pro': 3,
  'gpt-image-2': 3,
  'wan-2.7': 2,
}

const GROK_SURCHARGE: Record<GrokPipelineKind, number> = {
  none: 0,
  light: 1,
  standard: 2,
  heavy: 3,
  workflow: 3,
}

const WAN_PRO_EXTRA = 2

export function normalizeWaveModelId(raw: string | null | undefined): string {
  const m = (raw || 'wan-2.7').trim().toLowerCase()
  if (m === 'wan-2.7-pro') return 'wan-2.7'
  return m in WS_BASE_CREDITS ? m : 'wan-2.7'
}

export function wanEditTierFromUiModelId(raw: string | null | undefined): WanEditTier {
  return (raw || '').trim().toLowerCase() === 'wan-2.7-pro' ? 'pro' : 'standard'
}

export function normalizeWaveProfile(raw: string | null | undefined): WaveProfile {
  return (raw || '').trim().toLowerCase() === 'regular' ? 'regular' : 'nsfw'
}

/** Модель для расчёта, если workflow_wave_model не задан (как в студии). */
export function effectiveWaveModelForStudio(
  waveModelId: string | null | undefined,
  waveProfile: WaveProfile,
): string {
  const explicit = (waveModelId || '').trim().toLowerCase()
  if (explicit in WS_BASE_CREDITS) return explicit
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

export function quoteStudioImageCredits(params: {
  waveModelId?: string | null
  waveProfile?: WaveProfile | string | null
  wanEditTier?: WanEditTier | string | null
  grokPipeline?: GrokPipelineKind
  studioMode?: string
  workflow?: boolean
}): number {
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

  let base = WS_BASE_CREDITS[model] ?? 2
  if (model === 'wan-2.7' && tier === 'pro') base += WAN_PRO_EXTRA
  const total = base + (GROK_SURCHARGE[grok] ?? 2)
  return Math.max(1, total)
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
  const profile = normalizeWaveProfile(params.waveProfile)
  const model = params.waveModelId
    ? normalizeWaveModelId(params.waveModelId)
    : effectiveWaveModelForStudio(null, profile)
  const tier =
    (params.wanEditTier || 'standard').toString().toLowerCase() === 'pro' ? 'pro' : 'standard'
  const pipeline = grokPipelineForStudioMode(params.studioMode ?? 'model_scene', {
    workflow: params.workflow,
  })
  if (profile === 'regular') {
    return model === 'nano-banana-2' && (pipeline === 'light' || pipeline === 'none' || pipeline === 'workflow')
  }
  if (model !== 'wan-2.7' || tier === 'pro') return false
  return pipeline === 'light' || pipeline === 'standard' || pipeline === 'none' || pipeline === 'workflow'
}

export function formatStudioImageCostLabel(
  credits: number | null,
  opts?: { isProPlan?: boolean; demoRemaining?: number; useDemo?: boolean },
): string {
  if (opts?.isProPlan) return 'Pro'
  if (opts?.useDemo && (opts.demoRemaining ?? 0) > 0) return '0'
  if (credits == null) return '—'
  return String(credits)
}
