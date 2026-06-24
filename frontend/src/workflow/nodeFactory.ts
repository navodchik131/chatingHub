import type { AppNode, AppNodeData, NodeType } from './types'

let nodeIdCounter = 0

export function createNodeId(type: NodeType): string {
  nodeIdCounter += 1
  return `${type}-${nodeIdCounter}`
}

export function createDefaultNodeData(type: NodeType): AppNodeData {
  switch (type) {
    case 'model':
      return { modelId: null }
    case 'realism':
      return { enabled: true }
    case 'prompt':
      return { prompt: '' }
    case 'reference':
      return {}
    case 'imageGeneration':
      return {
        outputAspect: '3:4',
        waveProfile: 'nsfw',
        wanEditTier: 'standard',
        exifCamera: 'main',
      }
    case 'preview':
      return {}
    default: {
      const _exhaustive: never = type
      return _exhaustive
    }
  }
}

export function createNode(type: NodeType, position: { x: number; y: number }): AppNode {
  return {
    id: createNodeId(type),
    type,
    position,
    data: createDefaultNodeData(type),
  }
}

export const REACT_FLOW_DRAG_TYPE = 'application/reactflow'
