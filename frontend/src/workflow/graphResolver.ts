import type { Edge, Node } from '@xyflow/react'
import { HandleIds } from './types'

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

/** blob: URL не переживают перезагрузку — не сохраняем в рабочее пространство. */
export function sanitizeNodeDataForPersist(
  type: string | undefined,
  data: Record<string, unknown>,
): Record<string, unknown> {
  if (type !== 'reference') return data
  const { previewUrl: _preview, ...rest } = data
  return rest
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
