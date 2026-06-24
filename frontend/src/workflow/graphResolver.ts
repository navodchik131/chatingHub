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
      data: n.data,
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
