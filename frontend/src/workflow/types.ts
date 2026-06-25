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
  | 'firstFrameGeneration'
  | 'turnaroundSheet'
  | 'motionVideo'
  | 'videoGeneration'
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

export type FirstFrameGenerationNodeData = ImageGenerationNodeData

export interface TurnaroundSheetNodeData {
  imageUrl?: string
  generationId?: number | null
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface MotionVideoNodeData {
  motionVideoFileId?: string
  fileName?: string
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export type SeedanceT2vVariant = 'standard' | 'mini'
export type SeedanceT2vResolution = '480p' | '720p' | '1080p'

export interface VideoGenerationNodeData {
  outputAspect?: string
  durationSeconds?: number
  seedanceVariant?: SeedanceT2vVariant
  videoResolution?: SeedanceT2vResolution
  generateAudio?: boolean
  autoMotionPrompt?: boolean
  negativePrompt?: string
  motionVideoFileId?: string
  videoUrl?: string
  generationId?: number | null
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface PreviewNodeData {
  imageUrl?: string
  videoUrl?: string
  mediaKind?: 'image' | 'video'
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
  | FirstFrameGenerationNodeData
  | TurnaroundSheetNodeData
  | MotionVideoNodeData
  | VideoGenerationNodeData
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
  firstFrameIn: 'first-frame-in',
  sheetIn: 'sheet-in',
  motionVideoIn: 'motion-video-in',
  motionVideoOut: 'motion-video-out',
  videoOut: 'video-out',
  previewIn: 'image-in',
} as const

export const IMAGE_OUTPUT_NODE_TYPES = new Set([
  'imageGeneration',
  'firstFrameGeneration',
  'turnaroundSheet',
])
