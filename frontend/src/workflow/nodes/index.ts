import type { NodeTypes } from '@xyflow/react'
import { FirstFrameGenerationNode } from './FirstFrameGenerationNode'
import { ImageGenerationNode } from './ImageGenerationNode'
import { ModelNode } from './ModelNode'
import { MotionVideoNode } from './MotionVideoNode'
import { PreviewNode } from './PreviewNode'
import { PromptNode } from './PromptNode'
import { RealismNode } from './RealismNode'
import { RefDescriptionNode } from './RefDescriptionNode'
import { ReferenceNode } from './ReferenceNode'
import { TurnaroundSheetNode } from './TurnaroundSheetNode'
import { VideoGenerationNode } from './VideoGenerationNode'
import { VideoPromptComposeNode } from './VideoPromptComposeNode'

import { VideoUpscaleNode } from './VideoUpscaleNode'

export const nodeTypes: NodeTypes = {
  model: ModelNode,
  realism: RealismNode,
  prompt: PromptNode,
  refDescription: RefDescriptionNode,
  reference: ReferenceNode,
  imageGeneration: ImageGenerationNode,
  firstFrameGeneration: FirstFrameGenerationNode,
  turnaroundSheet: TurnaroundSheetNode,
  motionVideo: MotionVideoNode,
  videoPromptCompose: VideoPromptComposeNode,
  videoGeneration: VideoGenerationNode,
  videoUpscale: VideoUpscaleNode,
  preview: PreviewNode,
}
