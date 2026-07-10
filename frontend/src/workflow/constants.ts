import type { NodeType } from './types'
import { workflowNodeDescription, workflowNodeLabel, workflowPaletteSectionTitle } from './workflowI18n'

export const WORKFLOW_GRAPH_STORAGE_KEY = 'mm_workflow_graph_v2'
export const WORKFLOW_PALETTE_COLLAPSED_KEY = 'mm_workflow_palette_collapsed'

/** @deprecated use workflowNodeLabel() for locale-aware label */
export const NODE_LABELS: Record<NodeType, string> = new Proxy({} as Record<NodeType, string>, {
  get(_target, prop: string) {
    return workflowNodeLabel(prop as NodeType)
  },
})

/** @deprecated use workflowNodeDescription() for locale-aware description */
export const NODE_DESCRIPTIONS: Record<NodeType, string> = new Proxy({} as Record<NodeType, string>, {
  get(_target, prop: string) {
    return workflowNodeDescription(prop as NodeType)
  },
})

export type NodePaletteSection = {
  id: string
  title: string
  badge?: string
  types: NodeType[]
}

/** Секции палитры: общие → картинки → видео → сценарии. */
export const NODE_PALETTE_SECTIONS: NodePaletteSection[] = [
  {
    id: 'common',
    get title() {
      return workflowPaletteSectionTitle('common')
    },
    types: ['model', 'realism', 'selfie', 'prompt', 'textNote', 'refDescription', 'reference', 'preview'],
  },
  {
    id: 'image',
    get title() {
      return workflowPaletteSectionTitle('image')
    },
    badge: '🖼',
    types: ['imageGeneration', 'firstFrameGeneration', 'turnaroundSheet'],
  },
  {
    id: 'video',
    get title() {
      return workflowPaletteSectionTitle('video')
    },
    badge: '🎬',
    types: ['motionVideo', 'videoPromptCompose', 'videoGeneration', 'videoUpscale'],
  },
  {
    id: 'scenarios',
    get title() {
      return workflowPaletteSectionTitle('scenarios')
    },
    badge: '⚡',
    types: [
      'scenarioOutfitChange',
      'scenarioLocationChange',
      'scenarioFaceSwap',
      'scenarioFirstFrame',
      'scenarioMotionVideo',
    ],
  },
]

/** @deprecated используйте NODE_PALETTE_SECTIONS */
export const NODE_PALETTE: NodeType[] = NODE_PALETTE_SECTIONS.flatMap((s) => s.types)
