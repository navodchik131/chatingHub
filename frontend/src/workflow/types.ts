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
  | 'videoPromptCompose'
  | 'scenarioOutfitChange'
  | 'scenarioMotionVideo'
  | 'scenarioFirstFrame'
  | 'videoGeneration'
  | 'videoUpscale'
  | 'preview'

export interface ModelNodeData {
  modelId?: number | null
  modelName?: string
  disabled?: boolean
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

export interface VideoPromptComposeNodeData {
  prompt?: string
  composedAt?: string
  disabled?: boolean
  isRunning?: boolean
  error?: string
  generateClothingFromVideo?: boolean
  generateEnvironmentFromVideo?: boolean
  clothingGenerationId?: number | null
  environmentGenerationId?: number | null
  clothingImageUrl?: string
  environmentImageUrl?: string
  /** true = @Video1 уходит в Seedance (model swap); false = только текст, без @Video */
  sendVideoReference?: boolean
  outputAspect?: string
  [key: string]: unknown
}

export type ScenarioMotionVideoNodeData = VideoPromptComposeNodeData & {
  generateAudio?: boolean
  autoMotionPrompt?: boolean
  negativePrompt?: string
}

export interface ScenarioOutfitChangeNodeData {
  disabled?: boolean
  error?: string
  [key: string]: unknown
}

export interface ScenarioFirstFrameNodeData {
  disabled?: boolean
  error?: string
  [key: string]: unknown
}

export type SeedanceT2vVariant = 'standard' | 'mini'
export type SeedanceT2vResolution = '480p' | '720p' | '1080p'
export type GrokImagineI2vResolution = '480p' | '720p'
export type WorkflowVideoProvider = 'seedance_t2v' | 'grok_imagine_i2v'

export interface VideoGenerationNodeData {
  outputAspect?: string
  durationSeconds?: number
  videoProvider?: WorkflowVideoProvider
  seedanceVariant?: SeedanceT2vVariant
  videoResolution?: SeedanceT2vResolution | GrokImagineI2vResolution
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

export interface VideoUpscaleNodeData {
  targetResolution?: string
  videoUrl?: string
  generationId?: number | null
  disabled?: boolean
  isRunning?: boolean
  error?: string
  [key: string]: unknown
}

export interface PreviewNodeData {
  imageUrl?: string
  videoUrl?: string
  mediaKind?: 'image' | 'video'
  generationId?: number | null
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
  | VideoPromptComposeNodeData
  | ScenarioMotionVideoNodeData
  | ScenarioOutfitChangeNodeData
  | ScenarioFirstFrameNodeData
  | VideoGenerationNodeData
  | VideoUpscaleNodeData
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
  clothingIn: 'clothing-in',
  environmentIn: 'environment-in',
  motionVideoIn: 'motion-video-in',
  motionVideoOut: 'motion-video-out',
  videoIn: 'video-in',
  videoOut: 'video-out',
  previewIn: 'image-in',
  pipelineIn: 'pipeline-in',
  pipelineOut: 'pipeline-out',
} as const

export const IMAGE_OUTPUT_NODE_TYPES = new Set([
  'imageGeneration',
  'firstFrameGeneration',
  'turnaroundSheet',
])
