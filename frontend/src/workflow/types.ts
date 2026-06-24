import type { Edge, Node } from '@xyflow/react'

export interface ProjectGraph {
  nodes: Node[]
  edges: Edge[]
}

export type NodeType =
  | 'model'
  | 'realism'
  | 'prompt'
  | 'refDescription'
  | 'reference'
  | 'imageGeneration'
  | 'preview'

export interface ModelNodeData {
  modelId?: number | null
  modelName?: string
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface RealismNodeData {
  enabled?: boolean
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface PromptNodeData {
  prompt: string
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface RefDescriptionNodeData {
  role: string
  description: string
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface ReferenceNodeData {
  refId?: string
  fileName?: string
  previewUrl?: string
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface ImageGenerationNodeData {
  waveModelId?: string
  nsfwEnabled?: boolean
  outputAspect?: string
  imageUrl?: string
  generationId?: number | null
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface PreviewNodeData {
  imageUrl?: string
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export type AppNodeData =
  | ModelNodeData
  | RealismNodeData
  | PromptNodeData
  | RefDescriptionNodeData
  | ReferenceNodeData
  | ImageGenerationNodeData
  | PreviewNodeData

export type AppNode = Node<AppNodeData, NodeType>

export interface StudioModelOption {
  id: number
  name: string
}

export const HandleIds = {
  modelOut: 'model-out',
  realismOut: 'realism-out',
  promptOut: 'prompt-out',
  descriptionOut: 'description-out',
  referenceOut: 'reference-out',
  referenceDescriptionIn: 'description-in',
  imageGenModelIn: 'model-in',
  imageGenRealismIn: 'realism-in',
  imageGenPromptIn: 'prompt-in',
  imageGenReferenceIn: 'reference-in',
  imageGenOut: 'image-out',
  previewIn: 'image-in',
} as const
