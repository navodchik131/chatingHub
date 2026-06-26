import type { Edge, Node } from '@xyflow/react'
import { HandleIds, IMAGE_OUTPUT_NODE_TYPES, type ProjectGraph } from './types'
import { isWorkflowNodeDisabled } from './workflowNodeState'

const RUNTIME_NODE_DATA_KEYS = ['isRunning', 'error'] as const

const OUTPUT_HANDLES = new Set([
  HandleIds.imageGenOut,
  HandleIds.videoOut,
])

export function getDownstreamPreviewNodeIds(sourceNodeId: string, edges: Edge[]): string[] {
  return edges
    .filter(
      (edge) =>
        edge.source === sourceNodeId &&
        (edge.sourceHandle === HandleIds.imageGenOut ||
          edge.sourceHandle === HandleIds.videoOut),
    )
    .map((edge) => edge.target)
}

function mediaFromSourceNode(sourceNode: Node): {
  imageUrl?: string
  videoUrl?: string
  mediaKind?: 'image' | 'video'
} {
  const data = (sourceNode.data ?? {}) as Record<string, unknown>
  if (sourceNode.type === 'videoGeneration') {
    const videoUrl = data.videoUrl
    if (typeof videoUrl === 'string' && videoUrl) {
      return { videoUrl, mediaKind: 'video' }
    }
    return {}
  }
  const imageUrl = data.imageUrl
  if (typeof imageUrl === 'string' && imageUrl) {
    return { imageUrl, mediaKind: 'image' }
  }
  return {}
}

export function resolveConnectedPreviewMedia(
  nodeId: string,
  nodes: Node[],
  edges: Edge[],
): { imageUrl?: string; videoUrl?: string; mediaKind?: 'image' | 'video' } {
  for (const edge of edges) {
    if (edge.target !== nodeId) continue
    if (edge.targetHandle !== HandleIds.previewIn) continue
    const sourceNode = nodes.find((node) => node.id === edge.source)
    if (!sourceNode || isWorkflowNodeDisabled(sourceNode.data as Record<string, unknown>)) continue
    const outHandle = edge.sourceHandle
    if (outHandle && !OUTPUT_HANDLES.has(outHandle as typeof HandleIds.imageGenOut)) continue
    if (
      sourceNode.type &&
      (IMAGE_OUTPUT_NODE_TYPES.has(sourceNode.type) ||
        sourceNode.type === 'videoGeneration')
    ) {
      const media = mediaFromSourceNode(sourceNode)
      if (media.imageUrl || media.videoUrl) return media
    }
  }
  return {}
}

/** @deprecated use resolveConnectedPreviewMedia */
export function resolveConnectedImageUrl(
  nodeId: string,
  nodes: Node[],
  edges: Edge[],
): string | undefined {
  return resolveConnectedPreviewMedia(nodeId, nodes, edges).imageUrl
}

export function serializeGraph(nodes: Node[], edges: Edge[]) {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: sanitizeNodeDataForPersist(n.type, n.data as Record<string, unknown>),
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
    })),
  }
}

function stripRuntimeNodeFields(data: Record<string, unknown>): Record<string, unknown> {
  const next = { ...data }
  for (const key of RUNTIME_NODE_DATA_KEYS) {
    delete next[key]
  }
  return next
}

/** blob: URL не переживают перезагрузку — не сохраняем в рабочее пространство. */
export function sanitizeNodeDataForPersist(
  type: string | undefined,
  data: Record<string, unknown>,
): Record<string, unknown> {
  const base = stripRuntimeNodeFields(data)
  if (type !== 'reference') return base
  const { previewUrl: _preview, ...rest } = base
  return rest
}

function stripGenerationResults(base: Record<string, unknown>): Record<string, unknown> {
  const {
    imageUrl: _imageUrl,
    videoUrl: _videoUrl,
    generationId: _generationId,
    ...rest
  } = base
  return rest
}

/** JSON-экспорт: только структура графа, тексты и настройки — без рефов, моделей и результатов. */
export function sanitizeNodeDataForExport(
  type: string | undefined,
  data: Record<string, unknown>,
): Record<string, unknown> {
  const base = stripRuntimeNodeFields(data)

  switch (type) {
    case 'reference': {
      const { refId: _refId, previewUrl: _preview, fileName: _fileName, ...rest } = base
      return rest
    }
    case 'model': {
      const { modelId: _modelId, modelName: _modelName, ...rest } = base
      return rest
    }
    case 'imageGeneration':
    case 'firstFrameGeneration':
    case 'turnaroundSheet':
    case 'videoGeneration':
      return stripGenerationResults(base)
    case 'videoPromptCompose': {
      const { composedAt: _at, ...rest } = base
      return rest
    }
    case 'motionVideo': {
      const { motionVideoFileId: _id, fileName: _fn, ...rest } = base
      return rest
    }
    case 'preview': {
      const { imageUrl: _imageUrl, videoUrl: _videoUrl, mediaKind: _mk, ...rest } = base
      return rest
    }
    default:
      return base
  }
}

export function sanitizeGraphForExport(graph: ProjectGraph): ProjectGraph {
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : []
  const edges = Array.isArray(graph.edges) ? graph.edges : []
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: sanitizeNodeDataForExport(n.type, (n.data ?? {}) as Record<string, unknown>),
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle,
      targetHandle: e.targetHandle,
    })),
  }
}

/** Есть ли на typed handle реальный реф (загруженный refId или generationId). */
export function upstreamBoardstoryRefHasContent(
  targetNodeId: string,
  targetHandle: string,
  nodes: Node[],
  edges: Edge[],
): boolean {
  const edge = edges.find(
    (e) => e.target === targetNodeId && e.targetHandle === targetHandle,
  )
  if (!edge?.source) return false
  const src = nodes.find((n) => n.id === edge.source)
  if (!src?.type) return false
  const data = (src.data ?? {}) as Record<string, unknown>
  if (src.type === 'reference') {
    return Boolean(String(data.refId ?? '').trim())
  }
  if (IMAGE_OUTPUT_NODE_TYPES.has(src.type)) {
    const raw = data.generationId
    if (raw == null || String(raw).trim() === '') return false
    const n = Number(raw)
    return Number.isFinite(n) && n > 0
  }
  return false
}

export function hydrateGraphFromServer(graph: {
  nodes?: Node[]
  edges?: Edge[]
}): { nodes: Node[]; edges: Edge[] } {
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : []
  const edges = Array.isArray(graph.edges) ? graph.edges : []
  return {
    nodes: nodes.map((n) => ({
      ...n,
      data: sanitizeNodeDataForPersist(n.type, (n.data ?? {}) as Record<string, unknown>),
    })),
    edges,
  }
}
