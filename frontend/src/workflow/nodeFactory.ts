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
    case 'refDescription':
      return { role: '', description: '' }
    case 'reference':
      return {}
    case 'imageGeneration':
      return {
        waveModelId: 'nano-banana-pro',
        nsfwEnabled: false,
        outputAspect: '3:4',
      }
    case 'firstFrameGeneration':
      return {
        waveModelId: 'nano-banana-pro',
        nsfwEnabled: false,
        outputAspect: '9:16',
      }
    case 'turnaroundSheet':
      return {}
    case 'motionVideo':
      return {}
    case 'videoGeneration':
      return {
        outputAspect: '9:16',
        durationSeconds: 5,
        seedanceVariant: 'standard',
        videoResolution: '720p',
        generateAudio: true,
        autoMotionPrompt: true,
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
