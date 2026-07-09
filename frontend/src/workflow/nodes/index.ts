import type { NodeTypes } from '@xyflow/react'
import { FirstFrameGenerationNode } from './FirstFrameGenerationNode'
import { ImageGenerationNode } from './ImageGenerationNode'
import { ModelNode } from './ModelNode'
import { MotionVideoNode } from './MotionVideoNode'
import { PreviewNode } from './PreviewNode'
import { PromptNode } from './PromptNode'
import { TextNoteNode } from './TextNoteNode'
import { RealismNode } from './RealismNode'
import { SelfieNode } from './SelfieNode'
import { RefDescriptionNode } from './RefDescriptionNode'
import { ReferenceNode } from './ReferenceNode'
import { TurnaroundSheetNode } from './TurnaroundSheetNode'
import { VideoGenerationNode } from './VideoGenerationNode'
import { VideoPromptComposeNode } from './VideoPromptComposeNode'
import { ScenarioOutfitChangeNode } from './ScenarioOutfitChangeNode'
import { ScenarioLocationChangeNode } from './ScenarioLocationChangeNode'
import { ScenarioFaceSwapNode } from './ScenarioFaceSwapNode'
import { ScenarioFirstFrameNode } from './ScenarioFirstFrameNode'
import { ScenarioMotionVideoNode } from './ScenarioMotionVideoNode'

import { VideoUpscaleNode } from './VideoUpscaleNode'

export const nodeTypes: NodeTypes = {
  model: ModelNode,
  realism: RealismNode,
  selfie: SelfieNode,
  prompt: PromptNode,
  textNote: TextNoteNode,
  refDescription: RefDescriptionNode,
  reference: ReferenceNode,
  imageGeneration: ImageGenerationNode,
  firstFrameGeneration: FirstFrameGenerationNode,
  turnaroundSheet: TurnaroundSheetNode,
  motionVideo: MotionVideoNode,
  videoPromptCompose: VideoPromptComposeNode,
  scenarioOutfitChange: ScenarioOutfitChangeNode,
  scenarioLocationChange: ScenarioLocationChangeNode,
  scenarioFaceSwap: ScenarioFaceSwapNode,
  scenarioMotionVideo: ScenarioMotionVideoNode,
  scenarioFirstFrame: ScenarioFirstFrameNode,
  videoGeneration: VideoGenerationNode,
  videoUpscale: VideoUpscaleNode,
  preview: PreviewNode,
}
