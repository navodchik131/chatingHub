const AI_MODEL_MAP = {
  nano: 'nano-banana-pro',
  gpt: 'gpt-image-2',
  seedream: 'seedream-v5.0-pro',
  wan: 'wan-2.7-pro',
}

function slotUploadKey(mode, index) {
  if (mode === 'outfit') return index === 0 ? 'ref' : 'outfit-cloth'
  if (mode === 'location') return index === 0 ? 'ref' : 'location-photo'
  if (mode === 'carousel') return 'carousel'
  if (mode === 'edit') return index === 0 ? 'ref' : 'edit-detail'
  return 'ref'
}

function resolveSlot(mode, index, uploadFiles, slotArchivePicks) {
  const uploadKey = slotUploadKey(mode, index)
  return {
    file: uploadFiles[uploadKey] || null,
    archiveId: slotArchivePicks[`${mode}:${index}`] ?? null,
  }
}
export const FALLBACK_GEN_MODELS = [
  { id: 'nano-banana-pro', label: 'Nano Banana Pro', nsfw: false, note: '' },
  { id: 'gpt-image-2', label: 'GPT Image 2', nsfw: false, note: '' },
  { id: 'seedream-v5.0-pro', label: 'Seedream 5 Pro', nsfw: false, note: '' },
  { id: 'wan-2.7', label: 'Wan 2.7', nsfw: true, note: '' },
  { id: 'wan-2.7-pro', label: 'Wan 2.7 Pro', nsfw: true, note: '' },
]

export const REGULAR_ENGINE_IDS = ['nano-banana-pro', 'gpt-image-2', 'seedream-v5.0-pro']
export const NSFW_ENGINE_IDS = ['wan-2.7', 'wan-2.7-pro', 'seedream-v5.0-pro']

export function isNsfwMode(s) {
  return s?.contentMode === 'nsfw' || !!s?.nsfw
}

export function waveModelFromState(s) {
  const mapped = AI_MODEL_MAP[s?.aiModel]
  if (mapped) return mapped
  return s?.aiModel || (isNsfwMode(s) ? 'wan-2.7' : 'nano-banana-pro')
}

export function normalizeWaveModel(id, nsfw) {
  const x = String(id || '').trim().toLowerCase()
  const mapped = AI_MODEL_MAP[x] || x
  if (mapped === 'wan-2.7-pro') return { apiId: 'wan-2.7', tier: 'pro' }
  if (mapped === 'wan-2.7') return { apiId: 'wan-2.7', tier: 'standard' }
  if (REGULAR_ENGINE_IDS.includes(mapped) || NSFW_ENGINE_IDS.includes(mapped)) {
    return { apiId: mapped, tier: 'standard' }
  }
  return { apiId: nsfw ? 'wan-2.7' : 'nano-banana-pro', tier: 'standard' }
}

export function waveModelParamsFromState(appState) {
  const wave = normalizeWaveModel(waveModelFromState(appState), isNsfwMode(appState))
  return { waveModelId: wave.apiId, wanTier: wave.tier }
}

export function mapGenModelsFromApi(modelOpts) {
  const raw = Array.isArray(modelOpts?.models) ? modelOpts.models : []
  if (!raw.length) return FALLBACK_GEN_MODELS
  return raw.map((m) => ({
    id: m.id,
    label: m.label || m.id,
    nsfw: Boolean(m.nsfw_only),
    note: m.note || '',
  }))
}

/** Как mm-os-bridge enginesForNsfw: Seedream доступен и в NSFW-режиме. */
export function enginesForNsfw(nsfw, genModels) {
  const allowed = nsfw ? NSFW_ENGINE_IDS : REGULAR_ENGINE_IDS
  const source = genModels?.length ? genModels : FALLBACK_GEN_MODELS
  const byId = new Map(source.map((m) => [m.id, m]))
  return allowed
    .map((id) => byId.get(id))
    .filter(Boolean)
    .map((m) => ({
      id: m.id,
      name: m.label || m.name || m.id,
      note: m.note || '',
    }))
}

export function normalizeStudioModelId(id) {
  if (id == null || id === '') return null
  const n = Number(id)
  return Number.isFinite(n) ? n : null
}

export function sameStudioModelId(a, b) {
  const na = normalizeStudioModelId(a)
  const nb = normalizeStudioModelId(b)
  return na != null && nb != null && na === nb
}

function slotHasSource(mode, index, uploadFiles, slotArchivePicks) {
  const src = resolveSlot(mode, index, uploadFiles, slotArchivePicks)
  return Boolean(src.file || src.archiveId != null)
}

/** Валидация формы студии перед генерацией (как mm-os-bridge validateImageGen). */
export function validateStudioForm(appState, studioStore, t) {
  const errs = []
  const mode = appState.imgMode || 'prompt'
  const slotCounts = { ref: 1, swap: 1, outfit: 2, location: 2, prompt: 0, carousel: 1, edit: 1 }
  const slotN = slotCounts[mode] ?? 0
  const { uploadFiles, slotArchivePicks, selectedModelId } = studioStore

  const hasCarouselSrc =
    Boolean(uploadFiles.carousel) ||
    appState.carouselPickId != null ||
    slotArchivePicks['carousel:0'] != null

  const hasFrame = mode === 'carousel' ? hasCarouselSrc : slotHasSource(mode, 0, uploadFiles, slotArchivePicks)

  if (slotN > 0 && !hasFrame) errs.push(t.errNoRef)
  if (mode === 'outfit' && !slotHasSource('outfit', 1, uploadFiles, slotArchivePicks)) errs.push(t.errNoRef)
  if (mode === 'location' && !slotHasSource('location', 1, uploadFiles, slotArchivePicks)) errs.push(t.errNoRef)
  if (mode === 'prompt' && !(appState.studioPrompt || '').trim()) errs.push(t.errNoPrompt)
  if (mode === 'edit') {
    if (!(appState.studioPrompt || '').trim()) errs.push(t.errNoPrompt)
    if (appState.needsRef === 'yes' && !slotHasSource('edit', 1, uploadFiles, slotArchivePicks)) errs.push(t.errNoRef)
  }
  if (mode !== 'outfit' && mode !== 'location' && !selectedModelId) errs.push(t.errNoChar)

  return errs
}

export function sumOutboundMessages(chatterStats) {
  if (!chatterStats) return 0
  const self = chatterStats.self || chatterStats.self_row
  let n = self?.outbound_messages || 0
  for (const m of chatterStats.members || []) n += m.outbound_messages || 0
  return n
}

export function syncRefArchivePicks(prev, mode, index, archiveId) {
  const key = `${mode}:${index}`
  const next = { ...prev, [key]: archiveId }
  if (mode === 'ref' || mode === 'swap' || mode === 'outfit' || mode === 'location') {
    for (const m of ['ref', 'swap', 'outfit', 'location']) {
      next[`${m}:0`] = archiveId
    }
  }
  return next
}
