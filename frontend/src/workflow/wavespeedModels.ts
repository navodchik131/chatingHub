import { apiFetch } from '../api'
import i18n, { WORKFLOW_NS } from '../i18n'
import type { WanEditTier } from '../studioImagePricing'

export interface GenerationAspectOption {
  key: string
  label: string
  size: string
}

export interface GenerationResolutionOption {
  id: string
  label: string
}

export interface GenerationModelDefinition {
  id: string
  label: string
  nsfwOnly: boolean
  aspects: GenerationAspectOption[]
  resolutions?: GenerationResolutionOption[]
}

/** UI id в селекте workflow-нод (regular). */
export const REGULAR_IMAGE_MODEL_IDS = [
  'nano-banana-2',
  'nano-banana-pro',
  'gpt-image-2',
  'seedream-v5.0-pro',
] as const

/** UI id в селекте workflow-нод (NSFW). */
export const NSFW_IMAGE_MODEL_IDS = ['wan-2.7', 'wan-2.7-pro', 'seedream-v5.0-pro'] as const

export type WorkflowUiModelId =
  | (typeof REGULAR_IMAGE_MODEL_IDS)[number]
  | (typeof NSFW_IMAGE_MODEL_IDS)[number]

export const DEFAULT_REGULAR_MODEL_ID: WorkflowUiModelId = 'nano-banana-pro'
export const DEFAULT_NSFW_MODEL_ID: WorkflowUiModelId = 'wan-2.7'

/** @deprecated use DEFAULT_NSFW_MODEL_ID for NSFW defaults */
export const DEFAULT_GENERATION_MODEL_ID = 'wan-2.7'
export const DEFAULT_OUTPUT_ASPECT = '3:4'

/** @deprecated use DEFAULT_GENERATION_MODEL_ID */
export const DEFAULT_WAVESPEED_MODEL_ID = DEFAULT_GENERATION_MODEL_ID

let cachedModels: GenerationModelDefinition[] | null = null

export async function fetchGenerationModelOptions(): Promise<GenerationModelDefinition[]> {
  if (cachedModels) return cachedModels
  const r = await apiFetch('/api/studio/workflow/model-options')
  if (!r.ok) {
    return fallbackGenerationModels()
  }
  const data = (await r.json()) as {
    models?: Array<{
      id: string
      label: string
      nsfw_only?: boolean
      aspects?: GenerationAspectOption[]
      resolutions?: GenerationResolutionOption[]
    }>
  }
  if (!Array.isArray(data.models) || !data.models.length) {
    return fallbackGenerationModels()
  }
  cachedModels = data.models.map((m) => ({
    id: m.id,
    label: m.label,
    nsfwOnly: Boolean(m.nsfw_only),
    aspects: Array.isArray(m.aspects) ? m.aspects : [],
    resolutions: Array.isArray(m.resolutions) ? m.resolutions : undefined,
  }))
  return cachedModels
}

function aspectLabel(key: string): string {
  return i18n.t(`aspects.${key}`, { ns: WORKFLOW_NS, defaultValue: key })
}

function defaultAspects(): GenerationAspectOption[] {
  return [
    { key: '9:16', label: aspectLabel('9:16'), size: '1080x1920' },
    { key: '3:4', label: aspectLabel('3:4'), size: '768x1024' },
    { key: '1:1', label: aspectLabel('1:1'), size: '1024x1024' },
    { key: '16:9', label: aspectLabel('16:9'), size: '1920x1080' },
  ]
}

function defaultResolutionsForModel(modelId: string): GenerationResolutionOption[] {
  const id = normalizeWaveModelSelection(modelId).apiWaveModelId
  const map: Record<string, string[]> = {
    'nano-banana-2': ['1k', '2k', '4k'],
    'nano-banana-pro': ['1k', '2k', '4k'],
    'gpt-image-2': ['1k', '2k', '4k'],
    'seedream-v5.0-pro': ['1k', '2k'],
    'wan-2.7': ['1k', '2k', '4k'],
  }
  const ids = map[id] ?? ['2k']
  return ids.map((rid) => ({ id: rid, label: rid.toUpperCase() }))
}

function defaultResolutionForModel(modelId: string): string {
  const id = normalizeWaveModelSelection(modelId).apiWaveModelId
  const defaults: Record<string, string> = {
    'nano-banana-2': '1k',
    'nano-banana-pro': '2k',
    'gpt-image-2': '1k',
    'seedream-v5.0-pro': '1k',
    'wan-2.7': '2k',
  }
  return defaults[id] ?? '2k'
}

function fallbackGenerationModels(): GenerationModelDefinition[] {
  const aspects = defaultAspects()
  const withRes = (id: string, label: string, nsfwOnly: boolean): GenerationModelDefinition => ({
    id,
    label,
    nsfwOnly,
    aspects,
    resolutions: defaultResolutionsForModel(id),
  })
  return [
    withRes('nano-banana-2', 'Nano Banana', false),
    withRes('nano-banana-pro', 'Nano Banana Pro', false),
    withRes('gpt-image-2', 'GPT Image', false),
    withRes('seedream-v5.0-pro', 'Seedream V5 Pro', false),
    withRes('wan-2.7', 'Wan 2.7', true),
    withRes('wan-2.7-pro', 'Wan 2.7 Pro', true),
  ]
}

export function normalizeWaveModelSelection(uiModelId: string | undefined): {
  uiModelId: WorkflowUiModelId
  apiWaveModelId: string
  wanEditTier: WanEditTier
} {
  const id = (uiModelId || '').trim().toLowerCase()
  if (id === 'wan-2.7-pro') {
    return { uiModelId: 'wan-2.7-pro', apiWaveModelId: 'wan-2.7', wanEditTier: 'pro' }
  }
  if (id === 'wan-2.7') {
    return { uiModelId: 'wan-2.7', apiWaveModelId: 'wan-2.7', wanEditTier: 'standard' }
  }
  if (id === 'seedream-v5.0-pro') {
    return {
      uiModelId: 'seedream-v5.0-pro',
      apiWaveModelId: 'seedream-v5.0-pro',
      wanEditTier: 'standard',
    }
  }
  if ((REGULAR_IMAGE_MODEL_IDS as readonly string[]).includes(id)) {
    return { uiModelId: id as WorkflowUiModelId, apiWaveModelId: id, wanEditTier: 'standard' }
  }
  return {
    uiModelId: DEFAULT_REGULAR_MODEL_ID,
    apiWaveModelId: DEFAULT_REGULAR_MODEL_ID,
    wanEditTier: 'standard',
  }
}

export function defaultUiModelForNsfw(nsfwEnabled: boolean): WorkflowUiModelId {
  return nsfwEnabled ? DEFAULT_NSFW_MODEL_ID : DEFAULT_REGULAR_MODEL_ID
}

export function modelsForNsfwMode(
  models: GenerationModelDefinition[],
  nsfwEnabled: boolean,
): GenerationModelDefinition[] {
  const allowed = nsfwEnabled ? NSFW_IMAGE_MODEL_IDS : REGULAR_IMAGE_MODEL_IDS
  const byId = new Map(models.map((m) => [m.id, m]))
  const fallback = fallbackGenerationModels()
  const fallbackById = new Map(fallback.map((m) => [m.id, m]))
  return allowed.map((id) => byId.get(id) ?? fallbackById.get(id)).filter(Boolean) as GenerationModelDefinition[]
}

export function aspectsForModel(
  models: GenerationModelDefinition[],
  modelId: string,
): GenerationAspectOption[] {
  const sel = normalizeWaveModelSelection(modelId)
  const model = models.find((m) => m.id === sel.uiModelId)
  if (model?.aspects?.length) return model.aspects
  const fb = fallbackGenerationModels().find((m) => m.id === sel.uiModelId)
  return fb?.aspects?.length ? fb.aspects : defaultAspects()
}

export function pickValidModelId(
  models: GenerationModelDefinition[],
  nsfwEnabled: boolean,
  currentId: string | undefined,
): WorkflowUiModelId {
  const available = modelsForNsfwMode(models, nsfwEnabled)
  const current = (currentId || '').trim().toLowerCase()
  if (available.some((m) => m.id === current)) {
    return current as WorkflowUiModelId
  }
  return (available[0]?.id ?? defaultUiModelForNsfw(nsfwEnabled)) as WorkflowUiModelId
}

export function pickValidAspect(
  aspects: GenerationAspectOption[],
  current: string | undefined,
): string {
  if (current && aspects.some((a) => a.key === current)) return current
  if (aspects.some((a) => a.key === DEFAULT_OUTPUT_ASPECT)) return DEFAULT_OUTPUT_ASPECT
  return aspects[0]?.key ?? DEFAULT_OUTPUT_ASPECT
}

export function resolutionsForModel(
  models: GenerationModelDefinition[],
  modelId: string,
): GenerationResolutionOption[] {
  const sel = normalizeWaveModelSelection(modelId)
  const model = models.find((m) => m.id === sel.uiModelId)
  if (model?.resolutions?.length) return model.resolutions
  return defaultResolutionsForModel(modelId)
}

export function pickValidResolution(
  models: GenerationModelDefinition[],
  modelId: string,
  current: string | undefined,
): string {
  const options = resolutionsForModel(models, modelId)
  const currentId = (current || '').trim().toLowerCase()
  if (currentId && options.some((o) => o.id === currentId)) return currentId
  const fallback = defaultResolutionForModel(modelId)
  if (options.some((o) => o.id === fallback)) return fallback
  return options[0]?.id ?? '2k'
}
