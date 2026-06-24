import { apiFetch } from '../api'

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

function fallbackGenerationModels(): GenerationModelDefinition[] {
  const aspects: GenerationAspectOption[] = [
    { key: '9:16', label: '9:16 — вертикаль', size: '1080x1920' },
    { key: '3:4', label: '3:4 — вертикальный портрет', size: '768x1024' },
    { key: '1:1', label: '1:1 — квадрат', size: '1024x1024' },
    { key: '16:9', label: '16:9 — горизонталь', size: '1920x1080' },
  ]
  return [
    { id: 'wan-2.7', label: 'Wan 2.7', nsfwOnly: true, aspects },
    { id: 'nano-banana-2', label: 'Nano Banana 2', nsfwOnly: false, aspects },
    { id: 'nano-banana-pro', label: 'Nano Banana Pro', nsfwOnly: false, aspects },
    { id: 'gpt-image-2', label: 'GPT Image 2', nsfwOnly: false, aspects },
  ]
}

export function modelsForNsfwMode(
  models: GenerationModelDefinition[],
  nsfwEnabled: boolean,
): GenerationModelDefinition[] {
  if (nsfwEnabled) {
    return models.filter((m) => m.nsfwOnly || m.id === 'wan-2.7')
  }
  return models.filter((m) => !m.nsfwOnly && m.id !== 'wan-2.7')
}

export function aspectsForModel(
  models: GenerationModelDefinition[],
  modelId: string,
): GenerationAspectOption[] {
  const model = models.find((m) => m.id === modelId)
  return model?.aspects?.length ? model.aspects : fallbackGenerationModels()[0].aspects
}

export function pickValidModelId(
  models: GenerationModelDefinition[],
  nsfwEnabled: boolean,
  currentId: string | undefined,
): string {
  const available = modelsForNsfwMode(models, nsfwEnabled)
  if (available.some((m) => m.id === currentId)) {
    return currentId ?? available[0].id
  }
  return available[0]?.id ?? DEFAULT_GENERATION_MODEL_ID
}

export function pickValidAspect(
  aspects: GenerationAspectOption[],
  current: string | undefined,
): string {
  if (current && aspects.some((a) => a.key === current)) return current
  if (aspects.some((a) => a.key === DEFAULT_OUTPUT_ASPECT)) return DEFAULT_OUTPUT_ASPECT
  return aspects[0]?.key ?? DEFAULT_OUTPUT_ASPECT
}
