const AI_MODEL_MAP = {
  nano: 'nano-banana-pro',
  gpt: 'gpt-image-2',
  seedream: 'seedream-v5.0-pro',
  wan: 'wan-2.7-pro',
}

/** Ключ слота в slotArchivePicks и slotSource: «swap:0», «outfit:1». */
export function slotStateKey(mode, index) {
  return `${mode}:${index}`
}

/**
 * Отдельный upload-key на каждый режим — face swap / outfit / location не делят один файл.
 * Раньше slot 0 всех режимов использовал общий ключ «ref», из‑за чего реф «течёт» между режимами.
 */
export function slotUploadKey(mode, index) {
  if (mode === 'outfit') return index === 0 ? 'outfit-scene' : 'outfit-cloth'
  if (mode === 'location') return index === 0 ? 'location-scene' : 'location-photo'
  if (mode === 'carousel') return 'carousel'
  if (mode === 'edit') return index === 0 ? 'edit-scene' : 'edit-detail'
  if (mode === 'swap') return 'swap-scene'
  if (mode === 'ref') return 'ref-scene'
  return `${mode}-scene`
}

/** Старый общий ключ — только fallback для сессий до разделения по режимам. */
export const LEGACY_SHARED_REF_UPLOAD_KEY = 'ref'

export function slotSourceKind(slotSourceMap, mode, index) {
  const key = slotStateKey(mode, index)
  return slotSourceMap?.[key] === 'archive' ? 'archive' : 'upload'
}

/**
 * Активный источник слота: учитывает вкладку «Загрузить» / «Архив» (slotSource).
 * file и archiveId не смешиваются — stale upload не перебивает новый pick из архива.
 */
export function resolveActiveSlotSource(mode, index, uploadFiles, slotArchivePicks, slotSourceMap) {
  const uploadKey = slotUploadKey(mode, index)
  const slotKey = slotStateKey(mode, index)
  const kind = slotSourceKind(slotSourceMap, mode, index)
  const rawFile = uploadFiles?.[uploadKey] || null
  const rawArchiveId = slotArchivePicks?.[slotKey] ?? null
  const legacyFile =
    !rawFile && index === 0 && uploadFiles?.[LEGACY_SHARED_REF_UPLOAD_KEY]
      ? uploadFiles[LEGACY_SHARED_REF_UPLOAD_KEY]
      : null

  if (kind === 'archive') {
    return {
      file: null,
      archiveId: rawArchiveId,
      uploadKey,
      slotKey,
      preferredSource: 'archive',
    }
  }
  // Карусель из lightbox: pick в slotArchivePicks, но slotSource ещё не успел обновиться.
  if (
    mode === 'carousel'
    && rawArchiveId != null
    && !rawFile
    && !legacyFile
  ) {
    return {
      file: null,
      archiveId: rawArchiveId,
      uploadKey,
      slotKey,
      preferredSource: 'archive',
    }
  }
  return {
    file: rawFile || legacyFile,
    archiveId: null,
    uploadKey,
    slotKey,
    preferredSource: 'upload',
  }
}

function slotHasActiveSource(mode, index, uploadFiles, slotArchivePicks, slotSourceMap) {
  const src = resolveActiveSlotSource(mode, index, uploadFiles, slotArchivePicks, slotSourceMap)
  return Boolean(src.file || src.archiveId != null)
}
export const FALLBACK_GEN_MODELS = [
  { id: 'nano-banana-2', label: 'Nano Banana', nsfw: false, note: '' },
  { id: 'nano-banana-pro', label: 'Nano Banana Pro', nsfw: false, note: '' },
  { id: 'gpt-image-2', label: 'GPT Image 2', nsfw: false, note: '' },
  { id: 'seedream-v5.0-pro', label: 'Seedream 5 Pro', nsfw: false, note: '' },
  { id: 'wan-2.7', label: 'Wan 2.7', nsfw: true, note: '' },
  { id: 'wan-2.7-pro', label: 'Wan 2.7 Pro', nsfw: true, note: '' },
]

/** Как backend WORKFLOW_REGULAR_MODELS — все обычные движки WaveSpeed. */
export const REGULAR_ENGINE_IDS = ['nano-banana-2', 'nano-banana-pro', 'gpt-image-2', 'seedream-v5.0-pro']
/** NSFW + Seedream (cross-profile), как в workflow и mm-os-bridge. */
export const NSFW_ENGINE_IDS = ['seedream-v5.0-pro', 'wan-2.7', 'wan-2.7-pro']

export const SIMPLIFIED_CONTENT_MODE = 'nsfw'
export const SIMPLIFIED_AI_MODEL = 'seedream-v5.0-pro'

export function isUiSimplified(me) {
  return me?.ui_simplified !== false
}

export function effectiveStudioState(appState, me) {
  if (!isUiSimplified(me)) return appState
  return { ...appState, contentMode: SIMPLIFIED_CONTENT_MODE, aiModel: SIMPLIFIED_AI_MODEL }
}

export function isNsfwMode(s) {
  return s?.contentMode === 'nsfw' || !!s?.nsfw
}

export function waveModelFromState(s) {
  const mapped = AI_MODEL_MAP[s?.aiModel]
  if (mapped) return mapped
  return s?.aiModel || (isNsfwMode(s) ? 'seedream-v5.0-pro' : 'nano-banana-pro')
}

export function normalizeWaveModel(id, nsfw) {
  const x = String(id || '').trim().toLowerCase()
  const mapped = AI_MODEL_MAP[x] || x
  if (mapped === 'wan-2.7-pro') return { apiId: 'wan-2.7', tier: 'pro' }
  if (mapped === 'wan-2.7') return { apiId: 'wan-2.7', tier: 'standard' }
  if (REGULAR_ENGINE_IDS.includes(mapped) || NSFW_ENGINE_IDS.includes(mapped)) {
    return { apiId: mapped, tier: 'standard' }
  }
  return { apiId: nsfw ? 'seedream-v5.0-pro' : 'nano-banana-pro', tier: 'standard' }
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

/** Валидация формы студии перед генерацией (как mm-os-bridge validateImageGen). */
export function validateStudioForm(appState, studioStore, t) {
  const errs = []
  const mode = appState.imgMode || 'prompt'
  const slotCounts = { ref: 1, swap: 1, outfit: 2, location: 2, prompt: 0, carousel: 1, edit: 1 }
  const slotN = slotCounts[mode] ?? 0
  const { uploadFiles, slotArchivePicks, selectedModelId } = studioStore
  const slotSourceMap = appState.slotSource || {}

  const hasCarouselSrc = slotHasActiveSource(
    'carousel',
    0,
    uploadFiles,
    slotArchivePicks,
    slotSourceMap,
  ) || appState.carouselPickId != null

  const hasFrame =
    mode === 'carousel'
      ? hasCarouselSrc
      : slotHasActiveSource(mode, 0, uploadFiles, slotArchivePicks, slotSourceMap)

  if (slotN > 0 && !hasFrame) errs.push(t.errNoRef)
  if (mode === 'outfit' && !slotHasActiveSource('outfit', 1, uploadFiles, slotArchivePicks, slotSourceMap)) {
    errs.push(t.errNoRef)
  }
  if (mode === 'location' && !slotHasActiveSource('location', 1, uploadFiles, slotArchivePicks, slotSourceMap)) {
    errs.push(t.errNoRef)
  }
  if (mode === 'prompt' && !(appState.studioPrompt || '').trim()) errs.push(t.errNoPrompt)
  if (mode === 'edit') {
    if (!(appState.studioPrompt || '').trim()) errs.push(t.errNoPrompt)
    if (
      appState.needsRef === 'yes'
      && !slotHasActiveSource('edit', 1, uploadFiles, slotArchivePicks, slotSourceMap)
    ) {
      errs.push(t.errNoRef)
    }
  }
  if (mode !== 'outfit' && mode !== 'location' && mode !== 'edit' && mode !== 'prompt' && mode !== 'carousel' && !selectedModelId) errs.push(t.errNoChar)

  return errs
}

export function sumOutboundMessages(chatterStats) {
  if (!chatterStats) return 0
  const self = chatterStats.self || chatterStats.self_row
  let n = self?.outbound_messages || 0
  for (const m of chatterStats.members || []) n += m.outbound_messages || 0
  return n
}

/** Pick из архива — только для текущего режима/слота, без копирования в swap/outfit/ref. */
export function syncRefArchivePicks(prev, mode, index, archiveId) {
  const key = slotStateKey(mode, index)
  return { ...prev, [key]: archiveId }
}

/** Сброс archive pick при загрузке файла в тот же слот. */
export function clearSlotArchivePick(prev, mode, index) {
  const key = slotStateKey(mode, index)
  if (prev[key] == null) return prev
  const next = { ...prev }
  delete next[key]
  return next
}
