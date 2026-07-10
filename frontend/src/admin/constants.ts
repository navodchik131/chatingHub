import i18n from '../i18n'

export const SUBSCRIPTION_STATUS_OPTIONS = [
  'none',
  'incomplete',
  'trialing',
  'active',
  'past_due',
  'canceled',
  'unpaid',
] as const

export function subscriptionStatusLabel(status: string): string {
  const key = `subscriptionStatus.${status}`
  const translated = i18n.t(key, { ns: 'admin', defaultValue: '' })
  return translated || status
}

export const PLAN_TIER_OPTIONS = ['solo', 'pro', 'studio'] as const

export const BILLING_PLAN_OPTIONS = ['credits', 'standard', 'pro'] as const

export function billingPlanLabel(plan: string): string {
  const p = (plan || 'standard').trim().toLowerCase()
  if (p === 'credits') return 'Credits'
  if (p === 'pro' || p === 'byok') return 'Pro'
  if (p === 'standard' || p === 'managed') return 'Standard'
  return p.charAt(0).toUpperCase() + p.slice(1)
}

export function planTierLabel(tier: string | null | undefined): string {
  const t = (tier || 'solo').toLowerCase()
  return t.charAt(0).toUpperCase() + t.slice(1)
}

export function usageKindLabel(kind: string): string {
  const key = `usageKind.${kind}`
  const translated = i18n.t(key, { ns: 'admin', defaultValue: '' })
  return translated || kind
}
