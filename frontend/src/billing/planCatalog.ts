/** Каталог тарифов (синхрон с backend plan_catalog.py). */

export const WAVESPEED_REF_URL = 'https://wavespeed.ai/?ref=modelmate'

export type PlanTier = 'solo' | 'pro' | 'studio'
export type BillingPlanKind = 'standard' | 'pro'
export type CreditsPlanKind = 'credits' | 'standard' | 'pro'
export type BillingPeriod = 'month' | 'year'

export interface PlanLimits {
  max_users: number
  max_models: number
  max_dialogs_per_month: number | null
  max_grok_per_month: number | null
}

export interface CatalogPlan {
  product: string
  billing_plan: BillingPlanKind
  tier: PlanTier
  period: BillingPeriod
  price_rub: number
  title: string
  popular: boolean
  managed_monthly_credits: number
  /** Кредиты за оплаченный период (год = 12× monthly). С бэкенда; иначе считается на клиенте. */
  managed_period_credits?: number
  limits: PlanLimits
}

const LEGACY_BILLING_ALIASES: Record<string, CreditsPlanKind> = {
  managed: 'standard',
  byok: 'pro',
}

/** Нормализация billing_plan с учётом legacy managed/byok. */
export function normalizeBillingPlan(raw: string | null | undefined): CreditsPlanKind {
  const s = (raw || 'standard').trim().toLowerCase()
  if (s in LEGACY_BILLING_ALIASES) return LEGACY_BILLING_ALIASES[s]
  if (s === 'credits' || s === 'standard' || s === 'pro') return s
  return 'standard'
}

/** Кредиты при оплате подписки Standard за выбранный период. */
export function managedPeriodCredits(
  plan: Pick<CatalogPlan, 'billing_plan' | 'period' | 'managed_monthly_credits' | 'managed_period_credits'>,
): number {
  if (plan.managed_period_credits != null && plan.managed_period_credits > 0) {
    return plan.managed_period_credits
  }
  if (plan.billing_plan !== 'standard' || plan.managed_monthly_credits <= 0) return 0
  return plan.period === 'year' ? plan.managed_monthly_credits * 12 : plan.managed_monthly_credits
}

export const LIMITS: Record<PlanTier, PlanLimits> = {
  solo: { max_users: 1, max_models: 1, max_dialogs_per_month: 1000, max_grok_per_month: 500 },
  pro: { max_users: 3, max_models: 3, max_dialogs_per_month: 5000, max_grok_per_month: 2000 },
  studio: { max_users: 10, max_models: 10, max_dialogs_per_month: null, max_grok_per_month: 10000 },
}

function spec(
  billing: BillingPlanKind,
  tier: PlanTier,
  period: BillingPeriod,
  price: number,
  credits: number,
): CatalogPlan {
  const mode = billing === 'pro' ? 'Pro' : 'Standard'
  const tierLabel = { solo: 'Solo', pro: 'Pro', studio: 'Studio' }[tier]
  return {
    product: `sub_${billing}_${tier}_${period}`,
    billing_plan: billing,
    tier,
    period,
    price_rub: price,
    title: `${mode} ${tierLabel}`,
    popular: tier === 'pro',
    managed_monthly_credits: credits,
    limits: LIMITS[tier],
  }
}

/** Fallback, если /api/health недоступен. */
export const FALLBACK_CATALOG_PLANS: CatalogPlan[] = [
  spec('pro', 'solo', 'month', 990, 0),
  spec('pro', 'pro', 'month', 2490, 0),
  spec('pro', 'studio', 'month', 5990, 0),
  spec('standard', 'solo', 'month', 1990, 150),
  spec('standard', 'pro', 'month', 4990, 400),
  spec('standard', 'studio', 'month', 11990, 1200),
  spec('pro', 'solo', 'year', 8900, 0),
  spec('pro', 'pro', 'year', 22400, 0),
  spec('pro', 'studio', 'year', 53900, 0),
  spec('standard', 'solo', 'year', 17900, 150),
  spec('standard', 'pro', 'year', 44900, 400),
  spec('standard', 'studio', 'year', 107900, 1200),
]

function normalizeCatalogPlan(raw: unknown): CatalogPlan | null {
  if (!raw || typeof raw !== 'object') return null
  const p = raw as Record<string, unknown>
  const billing = normalizeBillingPlan(String(p.billing_plan ?? ''))
  if (billing !== 'standard' && billing !== 'pro') return null
  return { ...(raw as CatalogPlan), billing_plan: billing }
}

export function parseCatalogFromHealth(
  health: { billing_catalog?: { plans?: unknown } } | null | undefined,
): CatalogPlan[] {
  const raw = health?.billing_catalog?.plans
  if (Array.isArray(raw) && raw.length) {
    const plans = raw.map(normalizeCatalogPlan).filter((p): p is CatalogPlan => p != null)
    if (plans.length) return plans
  }
  return FALLBACK_CATALOG_PLANS
}

export function filterPlans(
  plans: CatalogPlan[],
  billing: BillingPlanKind,
  period: BillingPeriod,
): CatalogPlan[] {
  return plans.filter((p) => p.billing_plan === billing && p.period === period)
}

export function tierFeatures(
  tier: PlanTier,
  billing: BillingPlanKind,
  period: BillingPeriod = 'month',
  managedMonthlyCredits?: number,
): string[] {
  const l = LIMITS[tier]
  const users =
    l.max_users === 1
      ? '1 пользователь'
      : `До ${l.max_users} пользователей`
  const models =
    l.max_models === 1 ? '1 модель' : `До ${l.max_models} моделей`
  const base = [
    users,
    models,
    billing === 'pro'
      ? 'Свой ключ WaveSpeed — без списаний на платформе'
      : 'Кредиты на генерацию включены',
    'Чат Fanvue + Telegram',
    'Авто-перевод переписок',
    'История генераций',
  ]
  if (billing === 'standard' && LIMITS[tier]) {
    const monthly = managedMonthlyCredits ?? { solo: 150, pro: 400, studio: 1200 }[tier]
    const total = period === 'year' ? monthly * 12 : monthly
    base[2] =
      period === 'year'
        ? `${total.toLocaleString('ru-RU')} кредитов за год (${monthly} / мес.)`
        : `${total} кредитов за месяц`
  }
  if (tier === 'pro') base.push('Командная работа и роли')
  if (tier === 'studio') base.push('Расширенные лимиты диалогов')
  return base
}
