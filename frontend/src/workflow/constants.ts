import type { NodeType } from './types'

export const WORKFLOW_GRAPH_STORAGE_KEY = 'mm_workflow_graph_v2'
export const WORKFLOW_PALETTE_COLLAPSED_KEY = 'mm_workflow_palette_collapsed'

export const NODE_LABELS: Record<NodeType, string> = {
  model: 'Модель',
  realism: 'Реализм',
  selfie: 'Селфи',
  prompt: 'Промпт',
  refDescription: 'Описание референса',
  reference: 'Images ref',
  imageGeneration: 'Генерация фото',
  firstFrameGeneration: 'Первый кадр',
  turnaroundSheet: 'Развёртка',
  motionVideo: 'Реф. видео',
  videoPromptCompose: 'Промпт из видео',
  scenarioOutfitChange: 'Сценарий: одежда',
  scenarioLocationChange: 'Сценарий: локация',
  scenarioMotionVideo: 'Сценарий: motion',
  scenarioFirstFrame: 'Сценарий: 1-й кадр',
  videoGeneration: 'Генерация видео',
  videoUpscale: 'Апскейл видео',
  preview: 'Просмотр',
}

export const NODE_DESCRIPTIONS: Record<NodeType, string> = {
  model: 'Модель из кабинета студии',
  realism: 'Реалистичный вид снимка',
  selfie: 'Селфи с вытянутой руки — фронталка, перебивает противоречия в промпте',
  prompt: 'Доп. указания (опционально; сцена берётся из первого кадра)',
  refDescription: 'Роль и назначение референса (photo base, clothes, pose…)',
  reference: 'Фото-референс — к генерации можно подключить несколько',
  imageGeneration: 'Сборка промпта и генерация изображения (plain или через pipeline)',
  firstFrameGeneration: 'Still t=0 для motion-пайплайна (plain или через pipeline)',
  turnaroundSheet: 'Character sheet GPT Image 2.0 — сетка на лице (кроме вида сзади)',
  motionVideo: 'Референс движения (@Video) для Seedance',
  videoPromptCompose:
    'Grok: детальный промпт из motion + BoardStory refs (одежда, окружение, модель)',
  scenarioOutfitChange:
    'Сценарий: photo base + outfit refs → pipeline → генерация изображения',
  scenarioLocationChange:
    'Сценарий: photo base / модель + refs локаций → pipeline → генерация изображения',
  scenarioMotionVideo:
    'Сценарий: motion + BoardStory → Grok-промпт, звук и Seedance → pipeline → видео',
  scenarioFirstFrame:
    'Сценарий: модель + motion/refs → still t=0 → pipeline → «Первый кадр»',
  videoGeneration:
    'Рендер видео: Seedance/Grok + длительность. Сценарий — через pipeline-in.',
  videoUpscale: 'Video Upscaler Pro — upscale готового ролика (720p–4K)',
  preview:
    'Просмотр результата. Можно подключить «Описание референса» и отдать картинку дальше как ref.',
}

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
    title: 'Общие',
    types: ['model', 'realism', 'selfie', 'prompt', 'refDescription', 'reference', 'preview'],
  },
  {
    id: 'image',
    title: 'Картинки',
    badge: '🖼',
    types: ['imageGeneration', 'firstFrameGeneration', 'turnaroundSheet'],
  },
  {
    id: 'video',
    title: 'Видео',
    badge: '🎬',
    types: ['motionVideo', 'videoPromptCompose', 'videoGeneration', 'videoUpscale'],
  },
  {
    id: 'scenarios',
    title: 'Сценарии',
    badge: '⚡',
    types: ['scenarioOutfitChange', 'scenarioLocationChange', 'scenarioFirstFrame', 'scenarioMotionVideo'],
  },
]

/** @deprecated используйте NODE_PALETTE_SECTIONS */
export const NODE_PALETTE: NodeType[] = NODE_PALETTE_SECTIONS.flatMap((s) => s.types)
