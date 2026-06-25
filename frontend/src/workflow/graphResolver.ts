import type { Edge, Node } from '@xyflow/react'
import { HandleIds, type ProjectGraph } from './types'

const RUNTIME_NODE_DATA_KEYS = ['isRunning', 'error'] as const

export function getDownstreamPreviewNodeIds(sourceNodeId: string, edges: Edge[]): string[] {
  return edges
    .filter(
      (edge) =>
        edge.source === sourceNodeId && edge.sourceHandle === HandleIds.imageGenOut,
    )
    .map((edge) => edge.target)
}

export function resolveConnectedImageUrl(
  nodeId: string,
  nodes: Node[],
  edges: Edge[],
): string | undefined {
  for (const edge of edges) {
    if (edge.target !== nodeId) continue
    if (edge.targetHandle !== HandleIds.previewIn) continue
    const sourceNode = nodes.find((node) => node.id === edge.source)
    if (!sourceNode || sourceNode.type !== 'imageGeneration') continue
    const url = sourceNode.data?.imageUrl
    if (typeof url === 'string' && url) return url
  }
  return undefined
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
    case 'imageGeneration': {
      const { imageUrl: _imageUrl, generationId: _generationId, ...rest } = base
      return rest
    }
    case 'preview': {
      const { imageUrl: _imageUrl, ...rest } = base
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
