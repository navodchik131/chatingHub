import type { NodeType } from './types'

export const WORKFLOW_GRAPH_STORAGE_KEY = 'mm_workflow_graph_v2'

export const NODE_LABELS: Record<NodeType, string> = {
  model: 'Модель',
  realism: 'Реализм',
  prompt: 'Промпт',
  refDescription: 'Описание',
  reference: 'Референс',
  imageGeneration: 'Генерация',
  preview: 'Просмотр',
}

export const NODE_DESCRIPTIONS: Record<NodeType, string> = {
  model: 'Модель из кабинета студии',
  realism: 'Реалистичный вид снимка',
  prompt: 'Дополнительные указания для сцены',
  refDescription: 'Роль и назначение референса',
  reference: 'Фото-референс с входом для описания',
  imageGeneration: 'Сборка промпта и генерация',
  preview: 'Просмотр и скачивание результата',
}

export const NODE_PALETTE: NodeType[] = [
  'model',
  'realism',
  'prompt',
  'refDescription',
  'reference',
  'imageGeneration',
  'preview',
]

export const NODE_ICONS: Record<NodeType, string> = {
  model: '👤',
  realism: '◉',
  prompt: '✦',
  refDescription: '📝',
  reference: '◎',
  imageGeneration: '⚡',
  preview: '◈',
}
