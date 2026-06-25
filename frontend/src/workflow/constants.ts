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
  videoGeneration: 'Видео',
  preview: 'Просмотр',
}

export const NODE_DESCRIPTIONS: Record<NodeType, string> = {
  model: 'Модель из кабинета студии',
  realism: 'Реалистичный вид снимка',
  prompt: 'Доп. указания (опционально; сцена берётся из первого кадра)',
  refDescription: 'Роль и назначение референса (photo base, clothes, pose…)',
  reference: 'Фото-референс — к генерации можно подключить несколько',
  imageGeneration: 'Сборка промпта и генерация',
  firstFrameGeneration: 'Первый кадр сцены для motion-пайплайна',
  turnaroundSheet: 'Character sheet GPT Image 2.0 — сетка на лице (кроме вида сзади)',
  motionVideo: 'Референс движения для Seedance',
  videoGeneration: 'Seedance 2.0 / Mini — @Image1 кадр, @Image2 модель, @Video1 motion',
  preview: 'Просмотр и скачивание результата',
}

export const NODE_PALETTE: NodeType[] = [
  'model',
  'realism',
  'prompt',
  'refDescription',
  'reference',
  'firstFrameGeneration',
  'turnaroundSheet',
  'motionVideo',
  'videoGeneration',
  'imageGeneration',
  'preview',
]
