import { apiFetch } from '../../api'
import { mergeVideoArchiveWithMotionRenders } from '../../studioArchive'
import { withVideoDownloadParam } from './archiveDownload'
import { postStudioJobStart, waitForStudioJobResult } from '../../studioJobs'
import MMOS_STUDIO_SCENARIOS from '../../studio/mmOsStudioScenarios.js'
import {
  isNsfwMode,
  normalizeWaveModel,
  waveModelFromState,
} from './studioHelpers'
import { apiJson, apiJsonOptional, normalizePhotoKind } from './helpers'

const OP_BITS = { chat: 1, studio: 2, models: 4, keys: 8, billing: 16 }

export function maskFromOpRights(orR) {
  let mask = 0
  for (const [k, bit] of Object.entries(OP_BITS)) {
    if (orR?.[k]) mask |= bit
  }
  return mask
}

export function rightsFromMask(mask) {
  const m = Number(mask) || 0
  return {
    chat: (m & OP_BITS.chat) === OP_BITS.chat,
    studio: (m & OP_BITS.studio) === OP_BITS.studio,
    models: (m & OP_BITS.models) === OP_BITS.models,
    keys: (m & OP_BITS.keys) === OP_BITS.keys,
    billing: (m & OP_BITS.billing) === OP_BITS.billing,
  }
}

export async function saveWavespeedKey(apiKey) {
  await apiJson('/api/integrations/wavespeed', {
    method: 'PUT',
    body: JSON.stringify({ api_key: apiKey }),
  })
}

export async function addTelegramBot(botToken, studioModelId) {
  const body = { bot_token: botToken }
  if (studioModelId) body.studio_model_id = Number(studioModelId)
  await apiJson('/api/integrations/telegram', { method: 'PUT', body: JSON.stringify(body) })
}

export async function startFanvueOAuth(studioModelId) {
  const body = {}
  if (studioModelId) body.studio_model_id = Number(studioModelId)
  return apiJson('/api/integrations/fanvue/oauth/start', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function saveTributeKey(apiKey, label, studioModelId) {
  const body = { api_key: apiKey }
  if (label) body.label = label
  if (studioModelId) body.studio_model_id = Number(studioModelId)
  await apiJson('/api/integrations/tribute', { method: 'PUT', body: JSON.stringify(body) })
}

export async function saveDonationLink(payload, editingId) {
  if (editingId) {
    return apiJson(`/api/creator-donations/${editingId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  }
  return apiJson('/api/creator-donations', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function requestDonationPayout(sourceCurrency = 'RUB') {
  await apiJson('/api/creator-donations/payout-requests', {
    method: 'POST',
    body: JSON.stringify({ source_currency: sourceCurrency }),
  })
}

export async function savePayoutSettings(walletAddress, asset) {
  await apiJson('/api/creator-donations/payout-settings', {
    method: 'PUT',
    body: JSON.stringify({ wallet_address: walletAddress, asset: asset || 'USDT' }),
  })
}

export async function payTributeCheckout(product, creditsQuantity) {
  const body = product === 'credits_pack' ? { product, credits_quantity: creditsQuantity } : { product }
  return apiJson('/api/billing/tribute/checkout', { method: 'POST', body: JSON.stringify(body) })
}

export async function payYookassa(product, creditsQuantity) {
  const body = product === 'credits_pack' ? { product, credits_quantity: creditsQuantity } : { product }
  return apiJson('/api/billing/yookassa/payment', { method: 'POST', body: JSON.stringify(body) })
}

export async function subscribeWithCredits(product) {
  await apiJson('/api/billing/subscribe-with-credits', {
    method: 'POST',
    body: JSON.stringify({ product }),
  })
}

export async function addWorkspaceMember(payload) {
  await apiJson('/api/workspace/members', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateWorkspaceMember(memberId, payload) {
  return apiJson(`/api/workspace/members/${memberId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteWorkspaceMember(memberId) {
  await apiJson(`/api/workspace/members/${memberId}`, { method: 'DELETE' })
}

export async function deleteTelegramConnection(connectionId) {
  return apiJson(`/api/integrations/telegram/${connectionId}`, { method: 'DELETE' })
}

export async function deleteFanvueConnection(connectionId) {
  const q = connectionId ? `?connection_id=${connectionId}` : ''
  return apiJson(`/api/integrations/fanvue${q}`, { method: 'DELETE' })
}

export async function deleteTributeConnection(connectionId) {
  const q = connectionId ? `?connection_id=${connectionId}` : ''
  return apiJson(`/api/integrations/tribute${q}`, { method: 'DELETE' })
}

export async function fetchCameraPresets() {
  return apiJson('/api/studio/camera-presets')
}

export async function uploadPhoneExifReference(modelId, role, file) {
  const fd = new FormData()
  fd.append('role', role)
  fd.append('image', file, file.name || 'photo.jpg')
  const res = await apiFetch(`/api/studio/models/${modelId}/phone-exif-reference`, { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось загрузить EXIF-эталон')
  return data
}

export async function deletePhoneExifReference(modelId, role) {
  return apiJson(`/api/studio/models/${modelId}/phone-exif-reference?role=${role}`, { method: 'DELETE' })
}

export async function addSnippet(title, body) {
  await apiJson('/api/workspace/snippets', {
    method: 'POST',
    body: JSON.stringify({ title, body }),
  })
}

export async function updateSnippet(snippetId, title, body) {
  await apiJson(`/api/workspace/snippets/${snippetId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title, body }),
  })
}

export async function deleteSnippet(snippetId) {
  await apiJson(`/api/workspace/snippets/${snippetId}`, { method: 'DELETE' })
}

export async function deleteConversation(convId) {
  await apiFetch(`/api/conversations/${convId}`, { method: 'DELETE' })
}

export async function fetchConversationFolders() {
  return apiJsonOptional('/api/conversation-folders', {}, [])
}

export async function createConversationFolder(name, conversationIds = []) {
  return apiJson('/api/conversation-folders', {
    method: 'POST',
    body: JSON.stringify({ name, conversation_ids: conversationIds }),
  })
}

export async function patchConversationFolder(folderId, patch) {
  return apiJson(`/api/conversation-folders/${folderId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function deleteConversationFolder(folderId) {
  await apiFetch(`/api/conversation-folders/${folderId}`, { method: 'DELETE' })
}

export async function addConversationToFolder(folderId, convId) {
  return apiJson(`/api/conversation-folders/${folderId}/conversations/${convId}`, {
    method: 'POST',
    body: '{}',
  })
}

export async function removeConversationFromFolder(folderId, convId) {
  return apiJson(`/api/conversation-folders/${folderId}/conversations/${convId}`, {
    method: 'DELETE',
  })
}

export async function fetchConversationNotes(convId, { autoRefresh = false } = {}) {
  const q = autoRefresh ? '?auto_refresh=true' : '?auto_refresh=false'
  const data = await apiJson(`/api/conversations/${convId}/notes${q}`)
  return Array.isArray(data) ? data : []
}

export async function saveConversationNote(convId, content) {
  await apiJson(`/api/conversations/${convId}/notes`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

export async function analyzeConversationNotes(convId) {
  return apiJson(`/api/conversations/${convId}/notes/analyze`, {
    method: 'POST',
    body: '{}',
  })
}

export async function toggleMessageReaction(convId, messageId, emoji) {
  const res = await apiFetch(`/api/conversations/${convId}/messages/${messageId}/reactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emoji }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || res.statusText)
  return data
}

export async function sendReplyWithImage(convId, text, imageFile) {
  const fd = new FormData()
  if (text?.trim()) fd.append('text', text.trim())
  fd.append('image', imageFile, imageFile.name || 'photo.jpg')
  const res = await apiFetch(`/api/conversations/${convId}/reply`, { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось отправить')
  return data
}

const ARCHIVE_PAGE_LIMIT = 40

export async function refreshArchiveImages(skip = 0) {
  const [page, pending] = await Promise.all([
    apiJsonOptional(
      `/api/studio/generations?limit=${ARCHIVE_PAGE_LIMIT}&skip=${skip}&media_kind=image`,
      {},
      { items: [], has_more: false },
    ),
    skip === 0
      ? apiJsonOptional('/api/studio/generations/pending?media_kind=image', {}, { items: [] })
      : Promise.resolve({ items: [] }),
  ])
  const items = mergeArchiveItems([...(page.items || []), ...(pending.items || [])])
  return { items, has_more: Boolean(page.has_more) }
}

export async function refreshArchiveVideos(skip = 0) {
  const [page, pending, motion] = await Promise.all([
    apiJsonOptional(
      `/api/studio/generations?limit=${ARCHIVE_PAGE_LIMIT}&skip=${skip}&media_kind=video`,
      {},
      { items: [], has_more: false },
    ),
    skip === 0
      ? apiJsonOptional('/api/studio/generations/pending?media_kind=video', {}, { items: [] })
      : Promise.resolve({ items: [] }),
    skip === 0
      ? apiJsonOptional(`/api/studio/motion/renders?limit=${ARCHIVE_PAGE_LIMIT}&skip=0`, {}, [])
      : Promise.resolve([]),
  ])
  const merged = mergeArchiveItems([...(page.items || []), ...(pending.items || [])])
  const motionRows = Array.isArray(motion?.items) ? motion.items : Array.isArray(motion) ? motion : []
  const items = mergeVideoArchiveWithMotionRenders(merged, motionRows)
  return { items, has_more: Boolean(page.has_more) }
}

function dedupeArchiveById(items) {
  const seen = new Set()
  return items.filter((g) => {
    if (seen.has(g.id)) return false
    seen.add(g.id)
    return true
  })
}

function mergeArchiveItems(incoming) {
  return dedupeArchiveById(incoming)
}

export function isArchivePending(item) {
  if (!item) return false
  const st = (item.status || '').trim()
  if (st === 'processing' || st === 'archiving') return true
  if (st === 'failed' || st === 'ready') return false
  if (st === 'provider_ready') {
    if (item.media_kind === 'video') return !(item.video_url || '').trim()
    return !(item.image_url || '').trim()
  }
  return false
}

export function archiveThumbUrl(item) {
  if (!item) return ''
  if (item.media_kind === 'video') {
    return (item.image_url || '').trim()
  }
  return (item.image_url || '').trim()
}

export function archiveVideoUrl(item) {
  if (!item || item.media_kind !== 'video') return ''
  return (item.video_url || '').trim()
}

export function archiveDownloadUrl(item) {
  if (!item) return ''
  if (item.media_kind === 'video') return withVideoDownloadParam((item.video_url || '').trim())
  return (item.image_url || '').trim()
}

export async function postStudioJob(path, body) {
  const accepted = await postStudioJobStart(path, body)
  if (accepted.job_id) {
    await waitForStudioJobResult(accepted.job_id, { maxWaitMs: 15 * 60 * 1000 }).catch(() => {})
  }
  return accepted
}

let cachedDemoWorkflowWorkspaceId = null

/** Демо-тариф: backend требует workspace_id (проект «Смена модели»). */
export async function resolveDemoWorkflowWorkspaceId() {
  if (cachedDemoWorkflowWorkspaceId != null) return cachedDemoWorkflowWorkspaceId
  const list = await apiJsonOptional('/api/studio/workflow/workspaces', {}, [])
  const id = Array.isArray(list) && list[0]?.id != null ? Number(list[0].id) : null
  if (id) cachedDemoWorkflowWorkspaceId = id
  return id
}

export async function executeWorkflowGraph(graph, targetNodeId, opts = {}) {
  const fd = new FormData()
  fd.append('graph', JSON.stringify(graph))
  fd.append('target_node_id', targetNodeId)
  if (opts.workflowDemoLimited) {
    const wsId = opts.workspaceId ?? (await resolveDemoWorkflowWorkspaceId())
    if (!wsId) {
      throw new Error('Не найден workflow-проект для демо-тарифа. Обновите страницу.')
    }
    fd.append('workspace_id', String(wsId))
  }
  return postStudioJobStart('/api/studio/workflow/execute', { method: 'POST', body: fd })
}

export async function runCarouselGeneration(params) {
  const fd = new FormData()
  fd.append('model_id', String(params.modelId))
  fd.append('count', String(params.count))
  fd.append('description', params.prompt || '')
  fd.append('output_aspect', params.aspect || '9:16')
  fd.append('studio_wave_profile', params.nsfw ? 'nsfw' : 'regular')
  if (params.waveModelId) fd.append('workflow_wave_model', params.waveModelId)
  if (params.wanTier) fd.append('wan_edit_tier', params.wanTier)
  if (params.existingGenerationId) fd.append('existing_generation_id', String(params.existingGenerationId))
  else if (params.imageFile) fd.append('image', params.imageFile, params.imageFile.name || 'carousel.jpg')
  return postStudioJobStart('/api/studio/carousel', { method: 'POST', body: fd })
}

export async function runMotionFirstFrame(params) {
  const fd = new FormData()
  if (params.modelId) fd.append('model_id', String(params.modelId))
  fd.append('output_aspect', params.aspect || '9:16')
  fd.append('studio_wave_profile', params.nsfw ? 'nsfw' : 'regular')
  if (params.videoFile) fd.append('video', params.videoFile)
  if (params.frameFile) fd.append('first_frame_image', params.frameFile)
  if (params.existingGenerationId) fd.append('existing_generation_id', String(params.existingGenerationId))
  if (params.description) fd.append('description', params.description)
  if (params.autoMotionPrompt !== false) fd.append('auto_motion_prompt', '1')
  const accepted = await postStudioJobStart('/api/studio/motion/first-frame', { method: 'POST', body: fd })
  if (accepted.job_id) {
    const result = await waitForStudioJobResult(accepted.job_id, { maxWaitMs: 10 * 60 * 1000 })
    return { accepted, result }
  }
  return { accepted, result: null }
}

export async function runMotionVideo(params) {
  const fd = new FormData()
  fd.append('model_id', String(params.modelId))
  fd.append('prompt', params.prompt || '')
  fd.append('output_aspect', params.aspect || '9:16')
  const raw = String(params.resolution || '1080').toLowerCase()
  const videoResolution = raw === '4k' || raw === '1080' || raw === '1080p'
    ? '1080p'
    : raw === '720' || raw === '720p'
      ? '720p'
      : raw === '480' || raw === '480p'
        ? '480p'
        : '720p'
  fd.append('video_resolution', videoResolution)
  if (params.durationSeconds) fd.append('duration_seconds', String(params.durationSeconds))
  if (params.motionVideoFileId) fd.append('motion_video_file_id', params.motionVideoFileId)
  if (params.firstFrameGenerationId) {
    fd.append('first_frame_generation_id', String(params.firstFrameGenerationId))
  }
  if (params.autoMotionPrompt) fd.append('auto_motion_prompt', '1')
  if (params.promptOnlyMode) fd.append('prompt_only_mode', '1')
  return postStudioJob('/api/studio/motion/render-video', { method: 'POST', body: fd })
}

export async function fetchSupportTickets() {
  return apiJsonOptional('/api/support/tickets', {}, [])
}

export async function fetchSupportTicket(ticketId) {
  return apiJson(`/api/support/tickets/${ticketId}`)
}

export async function createSupportTicket(payload) {
  return apiJson('/api/support/tickets', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function patchProfileEmail(email) {
  return apiJson('/api/auth/profile', {
    method: 'PATCH',
    body: JSON.stringify({ email }),
  })
}

export async function changePassword(currentPassword, newPassword) {
  await apiJson('/api/auth/password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
}

export async function uploadWorkflowReference(file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await apiFetch('/api/studio/workflow/reference', { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || 'Не удалось загрузить референс')
  if (!data.ref_id) throw new Error('Сервер не вернул ref_id')
  return data.ref_id
}

export async function uploadMotionDrivingVideo(file) {
  const fd = new FormData()
  fd.append('video', file)
  const res = await apiFetch('/api/studio/motion/upload-driving-video', { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось загрузить видео')
  const id = String(data.motion_video_file_id || '').trim()
  if (!id) throw new Error('Сервер не вернул id видео')
  return id
}

export async function createStudioModel(name) {
  const fd = new FormData()
  fd.append('name', name.trim())
  fd.append('profile_text', '')
  const res = await apiFetch('/api/studio/models', { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось создать персонажа')
  return data
}

export async function patchStudioModel(charId, patch) {
  return apiJson(`/api/studio/models/${charId}`, { method: 'PATCH', body: JSON.stringify(patch) })
}

export async function deleteStudioModel(charId) {
  await apiJson(`/api/studio/models/${charId}`, { method: 'DELETE' })
}

export async function uploadStudioModelImage(charId, file, kind = 'face') {
  const fd = new FormData()
  fd.append('images', file)
  fd.append('image_kinds', JSON.stringify([normalizePhotoKind(kind)]))
  const res = await apiFetch(`/api/studio/models/${charId}/images`, { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось загрузить фото')
  return data
}

export async function deleteStudioModelImage(charId, imageId) {
  await apiJson(`/api/studio/models/${charId}/images/${imageId}`, { method: 'DELETE' })
}

export async function patchStudioModelImageKind(charId, imageId, kind) {
  return apiJson(`/api/studio/models/${charId}/images/${imageId}`, {
    method: 'PATCH',
    body: JSON.stringify({ kind: normalizePhotoKind(kind) }),
  })
}

export async function generateStudioModelProfile(images) {
  const fd = new FormData()
  for (const im of images.slice(0, 8)) {
    const res = await apiFetch(im.url)
    if (!res.ok) throw new Error('Не удалось прочитать фото модели')
    const blob = await res.blob()
    fd.append('images', blob, `model-${im.id}.jpg`)
  }
  const res = await apiFetch('/api/studio/models/generate-profile', { method: 'POST', body: fd })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Генерация не удалась')
  return data
}

/** Workflow-сценарии студии (встроены в SPA-бандл). */
export function ensureStudioScenarios() {
  if (MMOS_STUDIO_SCENARIOS?.buildGraphForMode) {
    return Promise.resolve(MMOS_STUDIO_SCENARIOS)
  }
  return Promise.reject(new Error('Workflow-сценарии не загружены'))
}

function slotUploadKey(mode, index) {
  if (mode === 'outfit') return index === 0 ? 'ref' : 'outfit-cloth'
  if (mode === 'location') return index === 0 ? 'ref' : 'location-photo'
  if (mode === 'carousel') return 'carousel'
  if (mode === 'edit') return index === 0 ? 'ref' : 'edit-detail'
  return 'ref'
}

function slotStateKey(mode, index) {
  return `${mode}:${index}`
}

function resolveSlotSource(mode, index, uploadFiles, slotArchivePicks) {
  const uploadKey = slotUploadKey(mode, index)
  return {
    file: uploadFiles[uploadKey] || null,
    archiveId: slotArchivePicks[slotStateKey(mode, index)] ?? null,
    uploadKey,
    slotKey: slotStateKey(mode, index),
  }
}

export { resolveSlotSource }

/** Генерация изображений через workflow execute (как mm-os-bridge). */
export async function runImageGeneration({ appState, studioStore, userPrompt, workflowDemoLimited = false, workspaceId = null }) {
  const scenarios = await ensureStudioScenarios()
  const mode = appState.imgMode || 'prompt'
  const modelId = studioStore.selectedModelId
  const needsModel = mode === 'ref' || mode === 'swap' || mode === 'prompt' || mode === 'edit'
  if (needsModel && !modelId) throw new Error('Выберите персонажа')

  const bridgeApi = {
    apiFetch,
    readJson: async (r) => r.json().catch(() => ({})),
    formatDetail: (d) => (typeof d?.detail === 'string' ? d.detail : ''),
  }

  const helpers = {
    normalizeWaveModel,
    waveModelFromState: () => waveModelFromState(appState),
    isNsfwMode: () => isNsfwMode(appState),
    slotStateKey,
    slotUploadKey,
    resolveSlotSource: (m, i) =>
      resolveSlotSource(m, i, studioStore.uploadFiles, studioStore.slotArchivePicks),
    userPrompt,
  }

  const built = await scenarios.buildGraphForMode(mode, {
    API: bridgeApi,
    store: studioStore,
    archiveThumbUrl,
    s: appState,
    modelId,
    userPrompt,
    helpers,
  })
  if (!built) throw new Error('Неизвестный режим генерации')
  return executeWorkflowGraph(built.graph, built.targetNodeId, { workflowDemoLimited, workspaceId })
}
