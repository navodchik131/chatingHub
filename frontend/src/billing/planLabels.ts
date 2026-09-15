import i18n from '../i18n'
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
  chat_allowed?: boolean
  companion_allowed?: boolean
  workflow_demo_limited?: boolean
}

/** Диалоги — на Standard / Pro (сервер: chat_allowed). */
export function chatAllowedForPlan(me: BillingMeLike): boolean {
  if (me.chat_allowed != null) return me.chat_allowed
  return normalizeBillingPlan(me.billing_plan) !== 'credits'
}

/** AI-бот — только Standard Studio / Pro Studio. */
export function companionAllowedForPlan(me: BillingMeLike): boolean {
  if (me.companion_allowed != null) return me.companion_allowed
  const plan = normalizeBillingPlan(me.billing_plan)
  if (plan !== 'standard' && plan !== 'pro') return false
  if ((me.plan_tier || '').toLowerCase() !== 'studio') return false
  return subscriptionPaidActive(me)
}

export function subscriptionPeriodExpired(me: BillingMeLike | null | undefined): boolean {
  if (!me?.subscription_period_end) return false
  const end = new Date(me.subscription_period_end).getTime()
  return !Number.isNaN(end) && end < Date.now()
}

/** UI: active | trialing | expired | inactive (согласовано с public_subscription_status на API). */
export function subscriptionUiState(me: BillingMeLike | null | undefined): 'active' | 'trialing' | 'expired' | 'inactive' {
  if (!me) return 'inactive'
  const st = (me.subscription_status || '').toLowerCase()
  if (st === 'expired') return 'expired'
  if (st === 'active') return subscriptionPeriodExpired(me) ? 'expired' : 'active'
  if (st === 'trialing') return subscriptionPeriodExpired(me) ? 'expired' : 'trialing'
  return 'inactive'
}

/** Оплаченная подписка, период не истёк (как subscription_is_paid_active на сервере). */
export function subscriptionPaidActive(me: BillingMeLike | null | undefined): boolean {
  return subscriptionUiState(me) === 'active'
}

/** Соответствует серверной subscription_active: active/trialing и период не истёк. */
export function subscriptionCoversStudioAccess(me: BillingMeLike): boolean {
  const s = subscriptionUiState(me)
  return s === 'active' || s === 'trialing'
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
    return i18n.t('plan.creditsLong', { demo, tier, ns: 'workspace' })
  }
  if (plan === 'pro') {
    return i18n.t('plan.proLong', { tier, ns: 'workspace' })
  }
  return i18n.t('plan.standardLong', { tier, ns: 'workspace' })
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

/** Покупка кредитов — только при активной оплаченной подписке. */
export function canPurchaseCredits(me: BillingMeLike | null | undefined): boolean {
  if (!me) return false
  return subscriptionPaidActive(me)
}

/** Бейдж статуса подписки в кабинете. */
export function subscriptionBadgeProps(
  me: BillingMeLike | null | undefined,
  lang: 'ru' | 'en',
): { tone: 'active' | 'warn' | 'dim'; text: string } {
  const state = subscriptionUiState(me)
  if (state === 'active') {
    return { tone: 'active', text: lang === 'ru' ? 'АКТИВНА' : 'ACTIVE' }
  }
  if (state === 'trialing') {
    return { tone: 'warn', text: lang === 'ru' ? 'ПРОБНЫЙ ПЕРИОД' : 'TRIAL' }
  }
  if (state === 'expired') {
    return { tone: 'warn', text: lang === 'ru' ? 'ИСТЕКЛА' : 'EXPIRED' }
  }
  return { tone: 'warn', text: lang === 'ru' ? 'НЕТ ПОДПИСКИ' : 'NO SUB' }
}

export function billingPlanKindLabel(plan: CreditsPlanKind | string): string {
  const p = normalizeBillingPlan(plan)
  if (p === 'credits') return 'Credits'
  if (p === 'pro') return 'Pro'
  return 'Standard'
}
