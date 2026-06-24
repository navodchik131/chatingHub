import type { NodeType } from './types'

export const WORKFLOW_GRAPH_STORAGE_KEY = 'mm_workflow_graph_v1'

export const NODE_LABELS: Record<NodeType, string> = {
  model: 'Модель',
  realism: 'Реализм',
  prompt: 'Промпт',
  reference: 'Референс',
  imageGeneration: 'Генерация',
  preview: 'Просмотр',
}

export const NODE_DESCRIPTIONS: Record<NodeType, string> = {
  model: 'Модель из кабинета студии',
  realism: 'Phone candid realism engine',
  prompt: 'Дополнительные указания для Grok',
  reference: 'Референс сцены для Grok',
  imageGeneration: 'Grok → WaveSpeed (режим «Основная»)',
  preview: 'Просмотр и скачивание результата',
}

export const NODE_PALETTE: NodeType[] = [
  'model',
  'realism',
  'prompt',
  'reference',
  'imageGeneration',
  'preview',
]

export const NODE_ICONS: Record<NodeType, string> = {
  model: '👤',
  realism: '◉',
  prompt: '✦',
  reference: '◎',
  imageGeneration: '⚡',
  preview: '◈',
}
