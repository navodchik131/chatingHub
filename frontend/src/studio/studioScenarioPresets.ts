import type { Edge, Node } from '@xyflow/react'
import type { ProjectGraph } from '../workflow/types'
import {
  DEFAULT_NSFW_MODEL_ID,
  DEFAULT_REGULAR_MODEL_ID,
} from '../workflow/wavespeedModels'

export type StudioWaveProfile = 'regular' | 'nsfw'

export interface StudioScenarioGenOptions {
  outputAspect: string
  waveProfile: StudioWaveProfile
  waveModelId?: string
  wanEditTier?: 'standard' | 'pro'
  exifCamera?: string
  realismEnabled?: boolean
  userPrompt?: string
}

export interface BuiltStudioScenario {
  graph: ProjectGraph
  targetNodeId: string
}

const FACE_SWAP_IDENTITY_ROLE = 'model / identity'
const FACE_SWAP_SCENE_ROLE = 'scene / pose / camera'
const PO_REFU_SCENE_ROLE = 'pose + camera + framing + light donor'

const FACE_SWAP_DEFAULT_PROMPT =
  'Replace the person in the scene reference with the identity from the identity reference.\n' +
  'Keep exact pose, camera angle, crop, background, props, and lighting from the scene reference.\n' +
  'Do NOT copy the original person\'s face, hair, or body.'

const PO_REFU_DEFAULT_PROMPT =
  'PRIORITY: match USER_SCENE_REFERENCE geometry as closely as possible.\n' +
  'If text conflicts with the reference image, the reference wins for pose/camera/light/crop.'

const FACE_SWAP_IDENTITY_DESC =
  'Фото модели — лицо, кожа, волосы, телосложение. Pose и фон с этого снимка НЕ копировать.'

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

export function pickWaveModelId(opts: StudioScenarioGenOptions): string {
  const explicit = (opts.waveModelId || '').trim()
  if (explicit) return explicit
  return opts.waveProfile === 'nsfw' ? DEFAULT_NSFW_MODEL_ID : DEFAULT_REGULAR_MODEL_ID
}

function mergePrompt(base: string, userPrompt?: string): string {
  const user = (userPrompt || '').trim()
  if (!user) return base
  if (!base.trim()) return user
  return `${base.trim()}\n\n${user}`
}

function imageGenData(opts: StudioScenarioGenOptions): Record<string, unknown> {
  const nsfwEnabled = opts.waveProfile === 'nsfw'
  return {
    waveModelId: pickWaveModelId(opts),
    nsfwEnabled,
    outputAspect: opts.outputAspect,
    wanEditTier: opts.wanEditTier ?? 'standard',
    exifCamera: opts.exifCamera ?? 'main',
  }
}

function node(id: string, type: string, data: Record<string, unknown> = {}): Node {
  return { id, type, position: { x: 0, y: 0 }, data }
}

function edge(
  id: string,
  source: string,
  target: string,
  sourceHandle: string,
  targetHandle: string,
): Edge {
  return { id, source, target, sourceHandle, targetHandle }
}

function realismBlock(
  targetId: string,
  targetHandle: string,
  enabled: boolean,
): { nodes: Node[]; edges: Edge[] } {
  if (!enabled) return { nodes: [], edges: [] }
  return {
    nodes: [node('realism-1', 'realism', { enabled: true })],
    edges: [edge('e-realism', 'realism-1', targetId, 'realism-out', targetHandle)],
  }
}

export function buildFaceSwapDualRefGraph(
  identityRefId: string,
  sceneRefId: string,
  opts: StudioScenarioGenOptions,
): BuiltStudioScenario {
  const targetNodeId = 'imageGeneration-1'
  const scenarioId = 'scenario-faceswap'
  const realism = realismBlock(scenarioId, 'realism-in', opts.realismEnabled !== false)
  const graph: ProjectGraph = {
    nodes: [
      ...realism.nodes,
      node('refDescription-identity', 'refDescription', {
        role: FACE_SWAP_IDENTITY_ROLE,
        description: FACE_SWAP_IDENTITY_DESC,
      }),
      node('reference-identity', 'reference', { refId: identityRefId }),
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
      edge('e-desc-id', 'refDescription-identity', 'reference-identity', 'description-out', 'description-in'),
      edge('e-desc-scene', 'refDescription-scene', 'reference-scene', 'description-out', 'description-in'),
      edge('e-id-scenario', 'reference-identity', 'scenario-faceswap', 'reference-out', 'identity-ref-in'),
      edge('e-scene-scenario', 'reference-scene', 'scenario-faceswap', 'reference-out', 'reference-in'),
      edge('e-prompt-scenario', 'prompt-1', 'scenario-faceswap', 'prompt-out', 'prompt-in'),
      edge('e-scenario-gen', 'scenario-faceswap', targetNodeId, 'pipeline-out', 'pipeline-in'),
    ],
  }
  return { graph, targetNodeId }
}

export function buildFaceSwapModelGraph(
  modelId: number,
  sceneRefId: string,
  opts: StudioScenarioGenOptions,
): BuiltStudioScenario {
  const targetNodeId = 'imageGeneration-1'
  const scenarioId = 'scenario-faceswap'
  const realism = realismBlock(scenarioId, 'realism-in', opts.realismEnabled !== false)
  const graph: ProjectGraph = {
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

export function buildPoRefuGraph(
  modelId: number,
  sceneRefId: string,
  opts: StudioScenarioGenOptions,
): BuiltStudioScenario {
  const targetNodeId = 'imageGeneration-1'
  const realism = realismBlock(targetNodeId, 'realism-in', opts.realismEnabled !== false)
  const graph: ProjectGraph = {
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

export function buildPromptOnlyGraph(
  modelId: number,
  opts: StudioScenarioGenOptions,
): BuiltStudioScenario {
  const targetNodeId = 'imageGeneration-1'
  const realism = realismBlock(targetNodeId, 'realism-in', opts.realismEnabled !== false)
  const graph: ProjectGraph = {
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

export function buildPhotoEditGraph(
  sceneRefId: string,
  opts: StudioScenarioGenOptions & { userPrompt: string },
): BuiltStudioScenario {
  const targetNodeId = 'imageGeneration-1'
  const realism = realismBlock(targetNodeId, 'realism-in', opts.realismEnabled !== false)
  const graph: ProjectGraph = {
    nodes: [
      ...realism.nodes,
      node('model-1', 'model', { disabled: true }),
      node('reference-scene', 'reference', { refId: sceneRefId }),
      node('prompt-1', 'prompt', { prompt: opts.userPrompt.trim() }),
      node(targetNodeId, 'imageGeneration', imageGenData(opts)),
    ],
    edges: [
      ...realism.edges,
      edge('e-ref-gen', 'reference-scene', targetNodeId, 'reference-out', 'reference-in'),
      edge('e-prompt-gen', 'prompt-1', targetNodeId, 'prompt-out', 'prompt-in'),
    ],
  }
  return { graph, targetNodeId }
}
