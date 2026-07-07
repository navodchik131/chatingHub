import { apiFetch } from '../api'
import type { WanEditTier } from '../studioImagePricing'

export interface GenerationAspectOption {
  key: string
  label: string
  size: string
}

export interface GenerationModelDefinition {
  id: string
  label: string
  nsfwOnly: boolean
  aspects: GenerationAspectOption[]
}

/** UI id в селекте workflow-нод (regular). */
export const REGULAR_IMAGE_MODEL_IDS = ['nano-banana-2', 'nano-banana-pro', 'gpt-image-2'] as const

/** UI id в селекте workflow-нод (NSFW). */
export const NSFW_IMAGE_MODEL_IDS = ['wan-2.7', 'wan-2.7-pro'] as const

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
  }))
  return cachedModels
}

function defaultAspects(): GenerationAspectOption[] {
  return [
    { key: '9:16', label: '9:16 — вертикаль', size: '1080x1920' },
    { key: '3:4', label: '3:4 — вертикальный портрет', size: '768x1024' },
    { key: '1:1', label: '1:1 — квадрат', size: '1024x1024' },
    { key: '16:9', label: '16:9 — горизонталь', size: '1920x1080' },
  ]
}

function fallbackGenerationModels(): GenerationModelDefinition[] {
  const aspects = defaultAspects()
  return [
    { id: 'nano-banana-2', label: 'Nano Banana', nsfwOnly: false, aspects },
    { id: 'nano-banana-pro', label: 'Nano Banana Pro', nsfwOnly: false, aspects },
    { id: 'gpt-image-2', label: 'GPT Image', nsfwOnly: false, aspects },
    { id: 'wan-2.7', label: 'Wan 2.7', nsfwOnly: true, aspects },
    { id: 'wan-2.7-pro', label: 'Wan 2.7 Pro', nsfwOnly: true, aspects },
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
