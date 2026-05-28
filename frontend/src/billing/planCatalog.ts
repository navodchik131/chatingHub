/** Каталог тарифов (синхрон с backend plan_catalog.py). */

export const WAVESPEED_REF_URL = 'https://wavespeed.ai/?ref=modelmate'

export type PlanTier = 'solo' | 'pro' | 'studio'
export type BillingPlanKind = 'managed' | 'byok'
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
  limits: PlanLimits
}

const LIMITS: Record<PlanTier, PlanLimits> = {
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
  const mode = billing === 'byok' ? 'BYOK' : 'Managed'
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
  spec('byok', 'solo', 'month', 990, 0),
  spec('byok', 'pro', 'month', 2490, 0),
  spec('byok', 'studio', 'month', 5990, 0),
  spec('managed', 'solo', 'month', 1990, 150),
  spec('managed', 'pro', 'month', 4990, 400),
  spec('managed', 'studio', 'month', 11990, 1200),
  spec('byok', 'solo', 'year', 8900, 0),
  spec('byok', 'pro', 'year', 22400, 0),
  spec('byok', 'studio', 'year', 53900, 0),
  spec('managed', 'solo', 'year', 17900, 150),
  spec('managed', 'pro', 'year', 44900, 400),
  spec('managed', 'studio', 'year', 107900, 1200),
]

export function parseCatalogFromHealth(
  health: { billing_catalog?: { plans?: unknown } } | null | undefined,
): CatalogPlan[] {
  const raw = health?.billing_catalog?.plans
  if (Array.isArray(raw) && raw.length) return raw as CatalogPlan[]
  return FALLBACK_CATALOG_PLANS
}

export function filterPlans(
  plans: CatalogPlan[],
  billing: BillingPlanKind,
  period: BillingPeriod,
): CatalogPlan[] {
  return plans.filter((p) => p.billing_plan === billing && p.period === period)
}

export function tierFeatures(tier: PlanTier, billing: BillingPlanKind): string[] {
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
    billing === 'byok' ? 'Свой ключ WaveSpeed' : 'Кредиты на генерацию включены',
    'Чат Fanvue + Telegram',
    'Авто-перевод переписок',
    'GROK для промптов и сцен',
    'История генераций',
  ]
  if (billing === 'managed' && LIMITS[tier]) {
    const cr = { solo: 150, pro: 400, studio: 1200 }[tier]
    base[2] = `${cr} кредитов за период подписки`
  }
  if (tier === 'pro') base.push('Командная работа и роли')
  if (tier === 'studio') base.push('Расширенные лимиты диалогов и GROK')
  return base
}
