import { normalizeBillingPlan } from './planCatalog'
import type { BillingMeLike } from './planLabels'

export function isCreditsPlanWithDemo(me: BillingMeLike | null | undefined): boolean {
  if (!me) return false
  return normalizeBillingPlan(me.billing_plan) === 'credits'
}

export function demoGenerationsRemaining(me: BillingMeLike | null | undefined): number {
  return Math.max(0, Number(me?.demo_generations_remaining) || 0)
}

export function demoGenerationsGrant(me: BillingMeLike | null | undefined): number {
  const grant = Number(me?.demo_generations_grant)
  if (Number.isFinite(grant) && grant > 0) return grant
  return 3
}

export function formatDemoCounterShort(lang: string, remaining: number, grant: number): string {
  if (lang === 'ru') return `${remaining}/${grant} демо`
  return `${remaining}/${grant} demo`
}

export function formatDemoCounterLong(lang: string, remaining: number, grant: number): string {
  if (lang === 'ru') {
    if (remaining <= 0) return `Бесплатные генерации закончились (всего было ${grant})`
    const mod10 = remaining % 10
    const mod100 = remaining % 100
    let word = 'бесплатных генераций'
    if (mod100 < 11 || mod100 > 14) {
      if (mod10 === 1) word = 'бесплатная генерация'
      else if (mod10 >= 2 && mod10 <= 4) word = 'бесплатные генерации'
    }
    return `Осталось ${remaining} ${word} из ${grant}`
  }
  if (remaining <= 0) return `Free generations used (${grant} on signup)`
  return `${remaining} of ${grant} free generations left`
}
