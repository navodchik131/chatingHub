import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  type BillingPeriod,
  type BillingPlanKind,
  type CatalogPlan,
  filterPlans,
  WAVESPEED_REF_URL,
} from '../billing/planCatalog'
import { formatRub } from './usePublicHealth'
import { marketingTierFeatures } from './i18n/pricingFeatures'
import { MmButton, MmContainer, MmDisplayLg, MmEyebrow, MmSerifAccent } from './components/MmUi'

export function PricingSection({
  plans,
  id = 'pricing',
  compact = false,
}: {
  plans: CatalogPlan[]
  id?: string
  compact?: boolean
}) {
  const { t } = useTranslation('marketing')
  const [billing, setBilling] = useState<BillingPlanKind>('pro')
  const [period, setPeriod] = useState<BillingPeriod>('month')
  const visible = useMemo(() => filterPlans(plans, billing, period), [plans, billing, period])

  return (
    <section className="mm-pricing-section" id={id} aria-labelledby={`${id}-title`}>
      <MmContainer>
        <div className="mm-pricing-section__head">
          <MmEyebrow>{t('pricing.section.eyebrow')}</MmEyebrow>
          <MmDisplayLg id={`${id}-title`}>
            {t('pricing.section.titleBefore')}
            <MmSerifAccent>{t('pricing.section.titleAccent')}</MmSerifAccent>
            <br />
            {t('pricing.section.titleLine2')}
          </MmDisplayLg>
          <p className="mm-muted" style={{ marginTop: 'var(--s-4)' }}>
            {t('pricing.section.dekBefore')}
            <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
              {t('pricing.section.dekWavespeed')}
            </a>
            {t('pricing.section.dekAfter')}
          </p>
        </div>
        <div className="mm-pricing-toggles" role="group" aria-label={t('pricing.toggles.kindAria')}>
          <button
            type="button"
            className={billing === 'pro' ? 'mm-toggle active' : 'mm-toggle'}
            onClick={() => setBilling('pro')}
          >
            {t('pricing.toggles.pro')}
          </button>
          <button
            type="button"
            className={billing === 'standard' ? 'mm-toggle active' : 'mm-toggle'}
            onClick={() => setBilling('standard')}
          >
            {t('pricing.toggles.standard')}
          </button>
        </div>
        <div className="mm-pricing-toggles" role="group" aria-label={t('pricing.toggles.periodAria')}>
          <button
            type="button"
            className={period === 'month' ? 'mm-toggle active' : 'mm-toggle'}
            onClick={() => setPeriod('month')}
          >
            {t('pricing.toggles.month')}
          </button>
          <button
            type="button"
            className={period === 'year' ? 'mm-toggle active' : 'mm-toggle'}
            onClick={() => setPeriod('year')}
          >
            {t('pricing.toggles.year')}
          </button>
        </div>
        <div className="mm-price-grid">
          {visible.map((plan) => (
            <article key={plan.product} className={`mm-price-card${plan.popular ? ' featured' : ''}`}>
              {plan.popular ? <span className="mm-badge mm-badge--new">{t('pricing.cards.popular')}</span> : null}
              <h3>{plan.title}</h3>
              <div className="mm-price-card__amount">{formatRub(plan.price_rub)}</div>
              <div className="mm-price-card__period">
                {period === 'year' ? t('pricing.cards.periodYear') : t('pricing.cards.periodMonth')}
              </div>
              <ul>
                {marketingTierFeatures(
                  t,
                  plan.tier,
                  plan.billing_plan,
                  plan.period,
                  plan.managed_monthly_credits,
                ).map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <MmButton to="/login" variant={plan.popular ? 'primary' : 'secondary'} size="md">
                {plan.tier === 'studio' ? t('pricing.cards.ctaStudio') : t('pricing.cards.ctaDefault')}
              </MmButton>
            </article>
          ))}
        </div>
        {!compact ? (
          <div className="mm-pro-explainer">
            <h3>{t('pricing.proExplainer.title')}</h3>
            <p>
              {t('pricing.proExplainer.p1Before')}
              <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                {t('pricing.proExplainer.p1Wavespeed')}
              </a>
              {t('pricing.proExplainer.p1After')}
            </p>
            <p className="mm-muted">{t('pricing.proExplainer.p2')}</p>
          </div>
        ) : null}
      </MmContainer>
    </section>
  )
}
