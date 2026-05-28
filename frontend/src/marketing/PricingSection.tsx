import { Link } from 'react-router-dom'
import { useMemo, useState } from 'react'
import {
  type BillingPeriod,
  type BillingPlanKind,
  type CatalogPlan,
  filterPlans,
  tierFeatures,
  WAVESPEED_REF_URL,
} from '../billing/planCatalog'
import { formatRub } from './usePublicHealth'

export function PricingSection({
  plans,
  id = 'pricing',
  compact = false,
}: {
  plans: CatalogPlan[]
  id?: string
  compact?: boolean
}) {
  const [billing, setBilling] = useState<BillingPlanKind>('byok')
  const [period, setPeriod] = useState<BillingPeriod>('month')
  const visible = useMemo(() => filterPlans(plans, billing, period), [plans, billing, period])

  return (
    <section className="mkt-section" id={id} aria-labelledby={`${id}-title`}>
      <div className="mkt-section-head">
        <h2 id={`${id}-title`}>Тарифы</h2>
        <p>
          Свой ключ{' '}
          <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
            WaveSpeed
          </a>{' '}
          (дешевле) или всё включено (удобнее).
        </p>
      </div>
      <div className="mkt-pricing-toggles" role="group" aria-label="Формат тарифа">
        <button
          type="button"
          className={billing === 'byok' ? 'mkt-toggle active' : 'mkt-toggle'}
          onClick={() => setBilling('byok')}
        >
          Со своим ключом (BYOK)
        </button>
        <button
          type="button"
          className={billing === 'managed' ? 'mkt-toggle active' : 'mkt-toggle'}
          onClick={() => setBilling('managed')}
        >
          Всё включено (Managed)
        </button>
      </div>
      <div className="mkt-pricing-toggles" role="group" aria-label="Период оплаты">
        <button
          type="button"
          className={period === 'month' ? 'mkt-toggle active' : 'mkt-toggle'}
          onClick={() => setPeriod('month')}
        >
          Месяц
        </button>
        <button
          type="button"
          className={period === 'year' ? 'mkt-toggle active' : 'mkt-toggle'}
          onClick={() => setPeriod('year')}
        >
          Год — скидка 25%
        </button>
      </div>
      <div className="mkt-price-row mkt-price-row--3">
        {visible.map((plan) => (
          <article
            key={plan.product}
            className={`mkt-price-card${plan.popular ? ' featured' : ''}`}
          >
            {plan.popular ? <span className="badge">Популярный</span> : null}
            <h3>{plan.title}</h3>
            <div className="amount">{formatRub(plan.price_rub)}</div>
            <div className="period">{period === 'year' ? 'в год' : 'в месяц'}</div>
            <ul>
              {tierFeatures(plan.tier, plan.billing_plan).map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
            <Link to="/login" className="mkt-nav-cta" style={{ width: 'fit-content' }}>
              {plan.tier === 'studio' ? 'Связаться / начать' : 'Попробовать бесплатно'}
            </Link>
          </article>
        ))}
      </div>
      {!compact ? (
        <div className="mkt-byok-explainer">
          <h3>Что такое BYOK?</h3>
          <p>
            BYOK (Bring Your Own Key) — вы подключаете API-ключ{' '}
            <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
              wavespeed.ai
            </a>
            . Платите провайдеру напрямую по реальной цене генерации, без наценки платформы на
            картинки и видео. ModelMate берёт плату за инфраструктуру, чат, команду и GROK для
            промптов.
          </p>
          <p className="muted">
            Не хотите регистрироваться на WaveSpeed — выберите Managed: кредиты на студию уже в
            подписке, докупка от 50 шт. по текущим ценам в кабинете.
          </p>
        </div>
      ) : null}
    </section>
  )
}
