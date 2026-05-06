/** Синхронно с backend/app/services/workspace.py (битовая маска). */

export const PERM_CHAT = 1
export const PERM_STUDIO_GENERATE = 2
export const PERM_STUDIO_MODELS = 4
export const PERM_INTEGRATIONS = 8
export const PERM_BILLING = 16
export const PERM_MANAGE_MEMBERS = 32

export const DEFAULT_MEMBER_PERMISSIONS = PERM_CHAT | PERM_STUDIO_GENERATE | PERM_STUDIO_MODELS

/** Чекбоксы при создании/редактировании участника (без MANAGE_MEMBERS — в API пока только владелец). */
export const MEMBER_PERMISSION_LABELS: { bit: number; label: string }[] = [
  { bit: PERM_CHAT, label: 'Диалоги и ответы клиентам' },
  { bit: PERM_STUDIO_GENERATE, label: 'Генерация промпта и картинок (студия)' },
  { bit: PERM_STUDIO_MODELS, label: 'Модели студии (создание, фото, правки)' },
  { bit: PERM_INTEGRATIONS, label: 'Ключи Telegram, Fanvue, WaveSpeed' },
  { bit: PERM_BILLING, label: 'Оплата и биллинг' },
]

export function togglePermission(mask: number, bit: number, on: boolean): number {
  if (on) return mask | bit
  return mask & ~bit
}

export function hasAllBits(mask: number, bit: number): boolean {
  return (mask & bit) === bit
}
