/**
 * Workflow-графы студии — те же пресеты, что public/mm-os-studio-scenarios.js
 * и шаблоны backend/data/workflow_templates.
 */

const FACE_SWAP_IDENTITY_ROLE = 'model / identity'
const FACE_SWAP_SCENE_ROLE = 'scene / pose / camera'
const PO_REFU_SCENE_ROLE = 'pose + camera + framing + light donor'

const FACE_SWAP_DEFAULT_PROMPT =
  'Replace the person in the scene reference with the identity from the identity reference.\n' +
  'Keep exact pose, camera angle, crop, background, props, and lighting from the scene reference.\n' +
  "Do NOT copy the original person's face, hair, or body."

const PO_REFU_DEFAULT_PROMPT =
  'PRIORITY: match USER_SCENE_REFERENCE geometry as closely as possible.\n' +
  'If text conflicts with the reference image, the reference wins for pose/camera/light/crop.'

const FACE_SWAP_SCENE_DESC =
  'Исходная сцена с человеком — фиксируем pose, ракурс, кроп, фон, свет, реквизит.\n' +
  'Лицо, кожу, волосы и тело с этого фото НЕ копировать — identity из identity ref.'

const PO_REFU_SCENE_DESC =
  'This image locks ONLY: body pose, limb angles, head yaw/gaze (if visible),\n' +
  'camera height/angle/distance, crop edges, background layout,\n' +
  'environmental light direction, wardrobe/nudity coverage zones.\n' +
  'Do NOT copy from this image: face, skin tone, hair, body proportions,\n' +
  'bust/waist/hip size, muscle build, glute volume, ethnicity, age look.\n' +
  'Identity comes from the studio model photos only.'

const LOCATION_BASE_ROLE = 'photo base / model'
const LOCATION_BASE_DESC =
  'Кого переносим — identity + pose + camera + crop. Фон и локацию НЕ копировать.'
const LOCATION_ENV_ROLE = 'location / environment'
const LOCATION_ENV_DESC =
  'Целевая локация — фон, окружение, атмосфера и освещение сцены. Без человека.'
const LOCATION_DEFAULT_PROMPT =
  'Replace background and environment with location reference(s).\n' +
  'Keep same person, identity, pose, wardrobe, camera angle, framing, and crop as photo-base reference.\n' +
  'Adapt scene lighting to the new location while preserving subject geometry.'

const OUTFIT_BASE_ROLE = 'photo base / model'
const OUTFIT_BASE_DESC = 'Кого и какой кадр редактируем — identity + pose + фон'
const OUTFIT_CLOTHES_ROLE = 'clothes / outfit'
const OUTFIT_CLOTHES_DESC = 'Донор одежды'
const OUTFIT_DEFAULT_PROMPT =
  'Replace wardrobe on photo-base reference with outfit from clothes reference.\n' +
  'Keep same person, pose, face, background, camera, and lighting.\n' +
  'без сумки яндекса'

const DETAIL_BASE_ROLE = 'photo base / frame to edit'
const DETAIL_BASE_DESC = 'Кадр, который редактируем — сохраняем композицию, позу и свет.'
const DETAIL_REF_ROLE = 'detail / element reference'
const DETAIL_REF_DESC = 'Опциональный референс детали, которую нужно добавить или изменить.'
const DETAIL_DEFAULT_PROMPT =
  'Edit the photo-base reference according to the user prompt.\n' +
  'Keep identity, pose, camera, lighting and background unless the prompt asks to change them.\n' +
  'If a detail reference is provided, use it only for the element described in the prompt.'

function node(id, type, data) {
  return { id, type, position: { x: 0, y: 0 }, data: data || {} }
}

function edge(id, source, target, sourceHandle, targetHandle) {
  return { id, source, target, sourceHandle, targetHandle }
}

function mergePrompt(base, userPrompt) {
  const user = (userPrompt || '').trim()
  if (user) return user
  return (base || '').trim()
}

const MODE_DEFAULT_PROMPTS = {
  ref: PO_REFU_DEFAULT_PROMPT,
  swap: FACE_SWAP_DEFAULT_PROMPT,
  outfit: OUTFIT_DEFAULT_PROMPT,
  location: LOCATION_DEFAULT_PROMPT,
  prompt: '',
  carousel: '',
}

function imageGenData(opts) {
  const nsfwEnabled = opts.waveProfile === 'nsfw'
  const wanTier =
    opts.waveModelId === 'wan-2.7' && opts.wanEditTier ? opts.wanEditTier : opts.wanEditTier || 'standard'
  return {
    waveModelId: opts.waveModelId,
    nsfwEnabled,
    outputAspect: opts.outputAspect,
    wanEditTier: wanTier,
    exifCamera: opts.exifCamera || 'main',
  }
}

function realismBlock(targetId, targetHandle, enabled) {
  if (enabled === false) return { nodes: [], edges: [] }
  return {
    nodes: [node('realism-1', 'realism', { enabled: true })],
    edges: [edge('e-realism', 'realism-1', targetId, 'realism-out', targetHandle)],
  }
}

function buildFaceSwapModelGraph(modelId, sceneRefId, opts) {
  const targetNodeId = 'imageGeneration-1'
  const scenarioId = 'scenario-faceswap'
  const realism = realismBlock(scenarioId, 'realism-in', opts.realismEnabled !== false)
  const graph = {
    nodes: [
      ...realism.nodes,
      node('model-1', 'model', { modelId }),
      node('refDescription-scene', 'refDescription', {
        role: FACE_SWAP_SCENE_ROLE,
        description: FACE_SWAP_SCENE_DESC,
      }),
      node('reference-scene', 'reference', { refId: sceneRefId }),
      node('scenario-faceswap', 'scenarioFaceSwap', {}),
      node('prompt-1', 'prompt', {
        prompt: mergePrompt(FACE_SWAP_DEFAULT_PROMPT, opts.userPrompt),
      }),
      node(targetNodeId, 'imageGeneration', imageGenData(opts)),
    ],
    edges: [
      ...realism.edges,
      edge('e-desc-scene', 'refDescription-scene', 'reference-scene', 'description-out', 'description-in'),
      edge('e-model-scenario', 'model-1', 'scenario-faceswap', 'model-out', 'model-in'),
      edge('e-scene-scenario', 'reference-scene', 'scenario-faceswap', 'reference-out', 'reference-in'),
      edge('e-prompt-scenario', 'prompt-1', 'scenario-faceswap', 'prompt-out', 'prompt-in'),
      edge('e-scenario-gen', 'scenario-faceswap', targetNodeId, 'pipeline-out', 'pipeline-in'),
    ],
  }
  return { graph, targetNodeId }
}

function buildPoRefuGraph(modelId, sceneRefId, opts) {
  const targetNodeId = 'imageGeneration-1'
  const realism = realismBlock(targetNodeId, 'realism-in', opts.realismEnabled !== false)
  const graph = {
    nodes: [
      ...realism.nodes,
      node('model-1', 'model', { modelId }),
      node('refDescription-scene', 'refDescription', {
        role: PO_REFU_SCENE_ROLE,
        description: PO_REFU_SCENE_DESC,
      }),
      node('reference-scene', 'reference', { refId: sceneRefId }),
      node('prompt-1', 'prompt', {
        prompt: mergePrompt(PO_REFU_DEFAULT_PROMPT, opts.userPrompt),
      }),
      node(targetNodeId, 'imageGeneration', imageGenData(opts)),
    ],
    edges: [
      ...realism.edges,
      edge('e-desc-scene', 'refDescription-scene', 'reference-scene', 'description-out', 'description-in'),
      edge('e-model-gen', 'model-1', targetNodeId, 'model-out', 'model-in'),
      edge('e-ref-gen', 'reference-scene', targetNodeId, 'reference-out', 'reference-in'),
      edge('e-prompt-gen', 'prompt-1', targetNodeId, 'prompt-out', 'prompt-in'),
    ],
  }
  return { graph, targetNodeId }
}

function buildLocationChangeGraph(baseRefId, locationRefId, opts) {
  const targetNodeId = 'imageGeneration-1'
  const scenarioId = 'scenario-location'
  const realism = realismBlock(scenarioId, 'realism-in', opts.realismEnabled !== false)
  const graph = {
    nodes: [
      ...realism.nodes,
      node('refDescription-base', 'refDescription', {
        role: LOCATION_BASE_ROLE,
        description: LOCATION_BASE_DESC,
      }),
      node('reference-base', 'reference', { refId: baseRefId }),
      node('refDescription-loc1', 'refDescription', {
        role: LOCATION_ENV_ROLE,
        description: LOCATION_ENV_DESC,
      }),
      node('reference-loc1', 'reference', { refId: locationRefId }),
      node('scenario-location', 'scenarioLocationChange', {}),
      node('prompt-1', 'prompt', {
        prompt: mergePrompt(LOCATION_DEFAULT_PROMPT, opts.userPrompt),
      }),
      node(targetNodeId, 'imageGeneration', imageGenData(opts)),
    ],
    edges: [
      ...realism.edges,
      edge('e-desc-base', 'refDescription-base', 'reference-base', 'description-out', 'description-in'),
      edge('e-desc-loc1', 'refDescription-loc1', 'reference-loc1', 'description-out', 'description-in'),
      edge('e-ref-base-scenario', 'reference-base', 'scenario-location', 'reference-out', 'reference-in'),
      edge('e-ref-loc1-scenario', 'reference-loc1', 'scenario-location', 'reference-out', 'reference-in'),
      edge('e-prompt-scenario', 'prompt-1', 'scenario-location', 'prompt-out', 'prompt-in'),
      edge('e-scenario-gen', 'scenario-location', targetNodeId, 'pipeline-out', 'pipeline-in'),
    ],
  }
  return { graph, targetNodeId }
}

function buildOutfitChangeGraph(baseRefId, clothesRefId, opts) {
  const targetNodeId = 'imageGeneration-1'
  const realism = realismBlock(targetNodeId, 'realism-in', opts.realismEnabled !== false)
  const graph = {
    nodes: [
      ...realism.nodes,
      node('refDescription-base', 'refDescription', {
        role: OUTFIT_BASE_ROLE,
        description: OUTFIT_BASE_DESC,
      }),
      node('reference-base', 'reference', { refId: baseRefId }),
      node('refDescription-clothes', 'refDescription', {
        role: OUTFIT_CLOTHES_ROLE,
        description: OUTFIT_CLOTHES_DESC,
      }),
      node('reference-clothes', 'reference', { refId: clothesRefId }),
      node('prompt-1', 'prompt', {
        prompt: mergePrompt(OUTFIT_DEFAULT_PROMPT, opts.userPrompt),
      }),
      node(targetNodeId, 'imageGeneration', imageGenData(opts)),
    ],
    edges: [
      ...realism.edges,
      edge('e-desc-base', 'refDescription-base', 'reference-base', 'description-out', 'description-in'),
      edge('e-desc-clothes', 'refDescription-clothes', 'reference-clothes', 'description-out', 'description-in'),
      edge('e-ref-base-gen', 'reference-base', targetNodeId, 'reference-out', 'reference-in'),
      edge('e-ref-clothes-gen', 'reference-clothes', targetNodeId, 'reference-out', 'reference-in'),
      edge('e-prompt-gen', 'prompt-1', targetNodeId, 'prompt-out', 'prompt-in'),
    ],
  }
  return { graph, targetNodeId }
}

function buildPromptOnlyGraph(modelId, opts) {
  const targetNodeId = 'imageGeneration-1'
  const realism = realismBlock(targetNodeId, 'realism-in', opts.realismEnabled !== false)
  const graph = {
    nodes: [
      ...realism.nodes,
      node('model-1', 'model', { modelId }),
      node('prompt-1', 'prompt', { prompt: (opts.userPrompt || '').trim() }),
      node(targetNodeId, 'imageGeneration', imageGenData(opts)),
    ],
    edges: [
      ...realism.edges,
      edge('e-model-gen', 'model-1', targetNodeId, 'model-out', 'model-in'),
      edge('e-prompt-gen', 'prompt-1', targetNodeId, 'prompt-out', 'prompt-in'),
    ],
  }
  return { graph, targetNodeId }
}

function buildDetailEditGraph(baseRefId, detailRefId, _modelId, opts) {
  const targetNodeId = 'imageGeneration-1'
  const realism = realismBlock(targetNodeId, 'realism-in', opts.realismEnabled !== false)
  const nodes = [
    ...realism.nodes,
    node('refDescription-base', 'refDescription', {
      role: DETAIL_BASE_ROLE,
      description: DETAIL_BASE_DESC,
    }),
    node('reference-base', 'reference', { refId: baseRefId }),
    node('prompt-1', 'prompt', {
      prompt: mergePrompt(DETAIL_DEFAULT_PROMPT, opts.userPrompt),
    }),
    node(targetNodeId, 'imageGeneration', imageGenData(opts)),
  ]
  const edges = [
    ...realism.edges,
    edge('e-desc-base', 'refDescription-base', 'reference-base', 'description-out', 'description-in'),
    edge('e-ref-base-gen', 'reference-base', targetNodeId, 'reference-out', 'reference-in'),
    edge('e-prompt-gen', 'prompt-1', targetNodeId, 'prompt-out', 'prompt-in'),
  ]
  if (detailRefId) {
    nodes.push(
      node('refDescription-detail', 'refDescription', {
        role: DETAIL_REF_ROLE,
        description: DETAIL_REF_DESC,
      }),
      node('reference-detail', 'reference', { refId: detailRefId }),
    )
    edges.push(
      edge('e-desc-detail', 'refDescription-detail', 'reference-detail', 'description-out', 'description-in'),
      edge('e-ref-detail-gen', 'reference-detail', targetNodeId, 'reference-out', 'reference-in'),
    )
  }
  // Персонаж кабинета не нужен: identity берётся из кадра; WaveSpeed получает только photo-base.
  return { graph: { nodes, edges }, targetNodeId }
}

async function uploadWorkflowReference(API, file) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await API.apiFetch('/api/studio/workflow/reference', { method: 'POST', body: fd })
  const data = await API.readJson(res)
  if (!res.ok) throw new Error(API.formatDetail(data) || 'Не удалось загрузить референс')
  if (!data.ref_id) throw new Error('Сервер не вернул ref_id')
  return data.ref_id
}

async function resolveRefId(API, store, archiveThumbUrlFn, source) {
  if (source.file) return uploadWorkflowReference(API, source.file)
  if (source.archiveId != null) {
    const item = (store.archiveImages || []).find((x) => x.id === source.archiveId)
    if (!item) throw new Error('Кадр не найден в архиве')
    const url = archiveThumbUrlFn(item)
    if (!url) throw new Error('Нет изображения для кадра из архива')
    const res = await API.apiFetch(url)
    if (!res.ok) throw new Error('Не удалось загрузить кадр из архива')
    const blob = await res.blob()
    const fileObj = new File([blob], `archive-${source.archiveId}.jpg`, {
      type: blob.type || 'image/jpeg',
    })
    return uploadWorkflowReference(API, fileObj)
  }
  throw new Error('Загрузите файл или выберите кадр из архива')
}

function genOptionsFromState(s, store, helpers) {
  const wave = helpers.normalizeWaveModel(helpers.waveModelFromState(s), helpers.isNsfwMode(s))
  return {
    outputAspect: store.selectedAspect || '9:16',
    waveProfile: helpers.isNsfwMode(s) ? 'nsfw' : 'regular',
    waveModelId: wave.apiId,
    wanEditTier: wave.tier,
    realismEnabled: true,
    userPrompt: helpers.userPrompt || '',
  }
}

async function buildGraphForMode(mode, ctx) {
  const { API, store, archiveThumbUrl: archiveThumbUrlFn, s, modelId, userPrompt, helpers } = ctx
  const opts = genOptionsFromState(s, store, { ...helpers, userPrompt })
  const slot0 = helpers.resolveSlotSource
    ? helpers.resolveSlotSource(mode, 0)
    : {
        file: store.uploadFiles.ref,
        archiveId: store.slotArchivePicks[helpers.slotStateKey(mode, 0)],
      }

  if (mode === 'ref') {
    const sceneRefId = await resolveRefId(API, store, archiveThumbUrlFn, slot0)
    return buildPoRefuGraph(modelId, sceneRefId, opts)
  }
  if (mode === 'swap') {
    const sceneRefId = await resolveRefId(API, store, archiveThumbUrlFn, slot0)
    return buildFaceSwapModelGraph(modelId, sceneRefId, opts)
  }
  if (mode === 'prompt') {
    return buildPromptOnlyGraph(modelId, opts)
  }
  if (mode === 'location') {
    const slot1 = helpers.resolveSlotSource
      ? helpers.resolveSlotSource('location', 1)
      : {
          file: store.uploadFiles['location-photo'],
          archiveId: store.slotArchivePicks[helpers.slotStateKey('location', 1)],
        }
    const baseRefId = await resolveRefId(API, store, archiveThumbUrlFn, slot0)
    const locRefId = await resolveRefId(API, store, archiveThumbUrlFn, slot1)
    return buildLocationChangeGraph(baseRefId, locRefId, opts)
  }
  if (mode === 'outfit') {
    const slot1 = helpers.resolveSlotSource
      ? helpers.resolveSlotSource('outfit', 1)
      : {
          file: store.uploadFiles['outfit-cloth'],
          archiveId: store.slotArchivePicks[helpers.slotStateKey('outfit', 1)],
        }
    const baseRefId = await resolveRefId(API, store, archiveThumbUrlFn, slot0)
    const clothesRefId = await resolveRefId(API, store, archiveThumbUrlFn, slot1)
    return buildOutfitChangeGraph(baseRefId, clothesRefId, opts)
  }
  if (mode === 'edit') {
    const baseRefId = await resolveRefId(API, store, archiveThumbUrlFn, slot0)
    let detailRefId = null
    if (s?.needsRef === 'yes') {
      const slot1 = helpers.resolveSlotSource
        ? helpers.resolveSlotSource('edit', 1)
        : {
            file: store.uploadFiles['edit-detail'],
            archiveId: store.slotArchivePicks[helpers.slotStateKey('edit', 1)],
          }
      detailRefId = await resolveRefId(API, store, archiveThumbUrlFn, slot1)
    }
    return buildDetailEditGraph(baseRefId, detailRefId, null, opts)
  }
  return null
}

const MMOS_STUDIO_SCENARIOS = {
  MODE_DEFAULT_PROMPTS,
  buildPoRefuGraph,
  buildFaceSwapModelGraph,
  buildLocationChangeGraph,
  buildOutfitChangeGraph,
  buildPromptOnlyGraph,
  buildDetailEditGraph,
  buildGraphForMode,
  resolveRefId,
  genOptionsFromState,
}

if (typeof window !== 'undefined') {
  window.MMOS_STUDIO_SCENARIOS = MMOS_STUDIO_SCENARIOS
}

export default MMOS_STUDIO_SCENARIOS
