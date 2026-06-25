import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  filterPlans,
  managedPeriodCredits,
  parseCatalogFromHealth,
  type CatalogPlan,
  type PlanTier,
} from '../billing/planCatalog'
import { formatRub, usePublicHealth } from './usePublicHealth'
import { useMarketingPath } from './i18n/useMarketingPath'

const COMPARE_TIERS: PlanTier[] = ['solo', 'pro', 'studio']

function findPlan(plans: CatalogPlan[], billing: 'standard' | 'pro', tier: PlanTier): CatalogPlan | undefined {
  return filterPlans(plans, billing, 'month').find((p) => p.tier === tier)
}

export function LandingCompareTable() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const health = usePublicHealth()
  const plans = parseCatalogFromHealth(health)
  const demoGenerations = health?.demo_generations_grant ?? 3
  const creditUnit = health?.billing_credits_unit_price_rub ?? 10

  const columns: Array<{ key: string; title: string; plan?: CatalogPlan; isCredits?: boolean }> = [
    { key: 'credits', title: t('landing.compare.colCredits'), isCredits: true },
    ...COMPARE_TIERS.flatMap((tier) => {
      const std = findPlan(plans, 'standard', tier)
      const pro = findPlan(plans, 'pro', tier)
      return [
        std ? { key: `std-${tier}`, title: std.title, plan: std } : null,
        pro ? { key: `pro-${tier}`, title: pro.title, plan: pro } : null,
      ].filter(Boolean) as Array<{ key: string; title: string; plan: CatalogPlan }>
    }),
  ]

  const yes = t('landing.compare.yes')
  const no = t('landing.compare.no')

  const cell = (col: (typeof columns)[number], row: string): string => {
    if (col.isCredits) {
      switch (row) {
        case 'price':
          return t('landing.compare.creditsPriceValue', { unit: creditUnit })
        case 'users':
        case 'models':
          return '1'
        case 'ownKey':
          return no
        case 'credits':
          return t('landing.compare.creditsDemoValue', { count: demoGenerations })
        case 'chat':
          return no
        default:
          return no
      }
    }
    const plan = col.plan!
    const periodCredits = managedPeriodCredits(plan)
    switch (row) {
      case 'price':
        return formatRub(plan.price_rub)
      case 'users':
        return String(plan.limits.max_users)
      case 'models':
        return String(plan.limits.max_models)
      case 'ownKey':
        return plan.billing_plan === 'pro' ? yes : no
      case 'credits':
        return plan.billing_plan === 'standard' && periodCredits > 0
          ? t('landing.compare.standardCreditsValue', { count: periodCredits })
          : no
      case 'chat':
        return yes
      default:
        return no
    }
  }

  const rows = ['price', 'users', 'models', 'ownKey', 'credits', 'chat'] as const
  const rowLabels: Record<(typeof rows)[number], string> = {
    price: t('landing.compare.rowPrice'),
    users: t('landing.compare.rowUsers'),
    models: t('landing.compare.rowModels'),
    ownKey: t('landing.compare.rowOwnKey'),
    credits: t('landing.compare.rowCredits'),
    chat: t('landing.compare.rowChat'),
  }

  return (
    <>
      <div className="mm-table-wrap mm-table-wrap--scroll">
        <table className="mm-table">
          <thead>
            <tr>
              <th>{t('landing.compare.colFeature')}</th>
              {columns.map((col) => (
                <th key={col.key}>{col.title}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row}>
                <td>{rowLabels[row]}</td>
                {columns.map((col) => (
                  <td key={col.key}>{cell(col, row)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mm-muted" style={{ marginTop: 'var(--s-4)' }}>
        <Link to={path('/pricing')} className="mm-link-arrow">
          {t('landing.compare.linkFull')}
        </Link>
      </p>
    </>
  )
}
