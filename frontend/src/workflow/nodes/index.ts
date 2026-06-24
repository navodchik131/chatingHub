import type { NodeTypes } from '@xyflow/react'
import { ImageGenerationNode } from './ImageGenerationNode'
import { ModelNode } from './ModelNode'
import { PreviewNode } from './PreviewNode'
import { PromptNode } from './PromptNode'
import { RealismNode } from './RealismNode'
import { ReferenceNode } from './ReferenceNode'

export const nodeTypes: NodeTypes = {
  model: ModelNode,
  realism: RealismNode,
  prompt: PromptNode,
  reference: ReferenceNode,
  imageGeneration: ImageGenerationNode,
  preview: PreviewNode,
}
