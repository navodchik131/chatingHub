import type { TFunction } from 'i18next'

import type { BillingPeriod, BillingPlanKind, PlanTier } from '../../billing/planCatalog'
import { LIMITS } from '../../billing/planCatalog'

/** Локализованные пункты карточки тарифа (маркетинг). */
export function marketingTierFeatures(
  t: TFunction<'marketing'>,
  tier: PlanTier,
  billing: BillingPlanKind,
  period: BillingPeriod = 'month',
  managedMonthlyCredits?: number,
): string[] {
  const l = LIMITS[tier]
  const users =
    l.max_users === 1
      ? t('pricing.features.usersOne')
      : t('pricing.features.usersMany', { count: l.max_users })
  const models =
    l.max_models === 1
      ? t('pricing.features.modelsOne')
      : t('pricing.features.modelsMany', { count: l.max_models })

  const base = [
    users,
    models,
    billing === 'pro' ? t('pricing.features.proKey') : t('pricing.features.standardCredits'),
    t('pricing.features.chat'),
    t('pricing.features.translation'),
    t('pricing.features.history'),
  ]

  if (billing === 'standard' && LIMITS[tier]) {
    const monthly = managedMonthlyCredits ?? { solo: 150, pro: 400, studio: 1200 }[tier]
    const total = period === 'year' ? monthly * 12 : monthly
    base[2] =
      period === 'year'
        ? t('pricing.features.creditsYear', { total, monthly })
        : t('pricing.features.creditsMonth', { total })
  }
  if (tier === 'pro') base.push(t('pricing.features.team'))
  if (tier === 'studio') base.push(t('pricing.features.studioLimits'))
  return base
}
