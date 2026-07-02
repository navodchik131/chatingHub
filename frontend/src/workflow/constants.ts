import type { NodeType } from './types'

export const WORKFLOW_GRAPH_STORAGE_KEY = 'mm_workflow_graph_v2'

export const NODE_LABELS: Record<NodeType, string> = {
  model: 'Модель',
  realism: 'Реализм',
  prompt: 'Промпт',
  refDescription: 'Описание',
  reference: 'Референс',
  imageGeneration: 'Генерация',
  firstFrameGeneration: 'Первый кадр',
  turnaroundSheet: 'Развёртка',
  motionVideo: 'Motion-видео',
  videoPromptCompose: 'Промпт по видео',
  scenarioOutfitChange: 'Смена одежды',
  scenarioMotionVideo: 'Motion-видео',
  scenarioFirstFrame: 'Первый кадр (сценарий)',
  videoGeneration: 'Видео',
  videoUpscale: 'Апскейл видео',
  preview: 'Просмотр',
}

export const NODE_DESCRIPTIONS: Record<NodeType, string> = {
  model: 'Модель из кабинета студии',
  realism: 'Реалистичный вид снимка',
  prompt: 'Доп. указания (опционально; сцена берётся из первого кадра)',
  refDescription: 'Роль и назначение референса (photo base, clothes, pose…)',
  reference: 'Фото-референс — к генерации можно подключить несколько',
  imageGeneration: 'Сборка промпта и генерация (plain или через pipeline)',
  firstFrameGeneration: 'Первый кадр сцены для motion-пайплайна (plain или через pipeline)',
  turnaroundSheet: 'Character sheet GPT Image 2.0 — сетка на лице (кроме вида сзади)',
  motionVideo: 'Референс движения для Seedance',
  videoPromptCompose:
    'Grok: детальный промпт из motion + BoardStory refs (одежда, окружение, модель)',
  scenarioOutfitChange:
    'Сценарий: photo base + outfit refs → pipeline → генерация изображения',
  scenarioMotionVideo:
    'Сценарий: motion + BoardStory → Grok-промпт, звук и Seedance-настройки → pipeline → видео',
  scenarioFirstFrame:
    'Сценарий: модель + motion/refs → still t=0 → pipeline → «Первый кадр»',
  videoGeneration:
    'Рендер видео: модель Seedance/Grok + длительность. Сценарий — через pipeline-in.',
  videoUpscale: 'Video Upscaler Pro — upscale готового ролика (720p–4K)',
  preview: 'Просмотр и скачивание результата',
}

export const NODE_PALETTE: NodeType[] = [
  'model',
  'realism',
  'prompt',
  'refDescription',
  'reference',
  'motionVideo',
  'scenarioOutfitChange',
  'scenarioFirstFrame',
  'scenarioMotionVideo',
  'videoPromptCompose',
  'videoGeneration',
  'videoUpscale',
  'imageGeneration',
  'firstFrameGeneration',
  'turnaroundSheet',
  'preview',
]
