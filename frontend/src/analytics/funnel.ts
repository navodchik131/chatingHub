/** События воронки активации → POST /api/analytics/funnel */

import { apiFetch } from '../api'

export type FunnelEventName =
  | 'workspace_opened'
  | 'integrations_opened'
  | 'onboarding_wizard_opened'
  | 'onboarding_wizard_skipped'
  | 'onboarding_wizard_completed'
  | 'onboarding_model_photo_set'
  | 'onboarding_ref_photo_set'
  | 'onboarding_profile_generated'
  | 'onboarding_generate_clicked'
  | 'onboarding_generation_success'
  | 'onboarding_model_save_clicked'
  | 'onboarding_model_saved'
  | 'onboarding_ws_key_saved'
  | 'studio_opened'
  | 'generate_clicked'

const queue: { event: FunnelEventName; meta?: Record<string, unknown> }[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null

async function flushFunnelQueue(): Promise<void> {
  if (queue.length === 0) return
  const batch = queue.splice(0, 20)
  try {
    await apiFetch('/api/analytics/funnel', {
      method: 'POST',
      body: JSON.stringify({ events: batch }),
    })
  } catch {
    queue.unshift(...batch)
  }
}

export function trackFunnelEvent(
  event: FunnelEventName,
  meta?: Record<string, unknown>,
): void {
  queue.push(meta ? { event, meta } : { event })
  if (flushTimer) clearTimeout(flushTimer)
  flushTimer = setTimeout(() => {
    flushTimer = null
    void flushFunnelQueue()
  }, 400)
}

/** sessionStorage: показать wizard после регистрации (снимается при открытии). */
export const FIRST_GEN_WIZARD_PENDING_SS = 'mm_first_gen_wizard_pending'

/** localStorage: id владельца, для которого wizard завершён/пропущен. */
export const FIRST_GEN_WIZARD_DONE_LS = 'mm_first_gen_wizard_done_uid'

const FIRST_GEN_WIZARD_LS_LEGACY = 'mm_first_gen_wizard_v1'

export function markFirstGenWizardPending(): void {
  try {
    sessionStorage.setItem(FIRST_GEN_WIZARD_PENDING_SS, '1')
  } catch {
    /* ignore */
  }
}

export function hasFirstGenWizardPending(): boolean {
  try {
    return sessionStorage.getItem(FIRST_GEN_WIZARD_PENDING_SS) === '1'
  } catch {
    return false
  }
}

export function clearFirstGenWizardPending(): void {
  try {
    sessionStorage.removeItem(FIRST_GEN_WIZARD_PENDING_SS)
  } catch {
    /* ignore */
  }
}

export function readFirstGenWizardDoneForUser(ownerId: number): boolean {
  if (!Number.isFinite(ownerId) || ownerId <= 0) return false
  try {
    return localStorage.getItem(FIRST_GEN_WIZARD_DONE_LS) === String(ownerId)
  } catch {
    return false
  }
}

export function markFirstGenWizardDoneForUser(ownerId: number): void {
  if (!Number.isFinite(ownerId) || ownerId <= 0) return
  try {
    localStorage.setItem(FIRST_GEN_WIZARD_DONE_LS, String(ownerId))
    localStorage.removeItem(FIRST_GEN_WIZARD_LS_LEGACY)
    clearFirstGenWizardPending()
  } catch {
    /* private mode */
  }
}

/** @deprecated глобальный флаг — не используйте для новых аккаунтов. */
export function readFirstGenWizardDone(): boolean {
  try {
    return localStorage.getItem(FIRST_GEN_WIZARD_LS_LEGACY) === '1'
  } catch {
    return false
  }
}

/** @deprecated — предпочитайте markFirstGenWizardDoneForUser */
export function markFirstGenWizardDone(): void {
  try {
    localStorage.setItem(FIRST_GEN_WIZARD_LS_LEGACY, '1')
  } catch {
    /* private mode */
  }
}

/** @deprecated alias */
export function markJustRegistered(): void {
  markFirstGenWizardPending()
}
