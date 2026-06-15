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

export const FIRST_GEN_WIZARD_LS = 'mm_first_gen_wizard_done'
export const JUST_REGISTERED_SS = 'mm_just_registered'

export function readFirstGenWizardDone(): boolean {
  try {
    return localStorage.getItem(FIRST_GEN_WIZARD_LS) === '1'
  } catch {
    return false
  }
}

export function markFirstGenWizardDone(): void {
  try {
    localStorage.setItem(FIRST_GEN_WIZARD_LS, '1')
  } catch {
    /* private mode */
  }
}

export function consumeJustRegistered(): boolean {
  try {
    if (sessionStorage.getItem(JUST_REGISTERED_SS) !== '1') return false
    sessionStorage.removeItem(JUST_REGISTERED_SS)
    return true
  } catch {
    return false
  }
}

export function markJustRegistered(): void {
  try {
    sessionStorage.setItem(JUST_REGISTERED_SS, '1')
  } catch {
    /* ignore */
  }
}
