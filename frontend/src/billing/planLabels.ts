import { normalizeBillingPlan, type CreditsPlanKind } from './planCatalog'

export { normalizeBillingPlan }

export interface BillingMeLike {
  billing_plan?: string
  plan_tier?: string
  plan_display_name?: string
  subscription_status?: string
  subscription_period_end?: string | null
  credits_balance?: number
  demo_generations_remaining?: number
  demo_generations_grant?: number
  online_payment_available?: boolean
  is_platform_admin?: boolean
  billing_require_active_subscription?: boolean
}

/** Соответствует серверной subscription_active: active/trialing и период не истёк. */
export function subscriptionCoversStudioAccess(me: BillingMeLike): boolean {
  const st = (me.subscription_status || '').toLowerCase()
  if (st !== 'active' && st !== 'trialing') return false
  if (me.subscription_period_end) {
    const end = new Date(me.subscription_period_end).getTime()
    if (!Number.isNaN(end) && end < Date.now()) return false
  }
  return true
}

export function planDisplayShort(me: BillingMeLike | null | undefined): string {
  if (me?.plan_display_name) return me.plan_display_name
  const plan = normalizeBillingPlan(me?.billing_plan)
  if (plan === 'credits') return 'Credits'
  const tier = (me?.plan_tier || 'solo').toLowerCase()
  const mode = plan === 'pro' ? 'Pro' : 'Standard'
  return `${mode} ${tier.charAt(0).toUpperCase() + tier.slice(1)}`
}

export function planDisplayLong(me: BillingMeLike | null | undefined): string {
  const plan = normalizeBillingPlan(me?.billing_plan)
  const tier = (me?.plan_tier || 'solo').toUpperCase()
  if (plan === 'credits') {
    const demo = me?.demo_generations_remaining ?? 0
    return `Credits — ${demo} бесплатных генераций, далее списание кредитов · тариф ${tier}`
  }
  if (plan === 'pro') {
    return `Pro — свой ключ WaveSpeed, без списаний на платформе · тариф ${tier}`
  }
  return `Standard — кредиты на студию включены, чат и команда · тариф ${tier}`
}

export function studioAccessAllowed(me: BillingMeLike): boolean {
  if (me.is_platform_admin) return true
  const gate = me.billing_require_active_subscription ?? true
  if (!gate) return true

  const plan = normalizeBillingPlan(me.billing_plan)
  if (plan === 'credits') {
    return (me.demo_generations_remaining ?? 0) > 0 || (me.credits_balance ?? 0) > 0
  }
  return subscriptionCoversStudioAccess(me)
}

export function canPurchaseCredits(me: BillingMeLike | null | undefined): boolean {
  if (!me?.online_payment_available) return false
  const plan = normalizeBillingPlan(me.billing_plan)
  if (plan === 'credits') return true
  if (plan === 'standard') {
    return (me.subscription_status || '').toLowerCase() === 'active'
  }
  return false
}

export function billingPlanKindLabel(plan: CreditsPlanKind | string): string {
  const p = normalizeBillingPlan(plan)
  if (p === 'credits') return 'Credits'
  if (p === 'pro') return 'Pro'
  return 'Standard'
}
