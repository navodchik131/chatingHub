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
  const [billing, setBilling] = useState<BillingPlanKind>('byok')
  const [period, setPeriod] = useState<BillingPeriod>('month')
  const visible = useMemo(() => filterPlans(plans, billing, period), [plans, billing, period])

  return (
    <section className="mm-pricing-section" id={id} aria-labelledby={`${id}-title`}>
      <MmContainer>
        <div className="mm-pricing-section__head">
          <MmEyebrow>Pricing · BYOK · Managed</MmEyebrow>
          <MmDisplayLg id={`${id}-title`}>
            Платишь за <MmSerifAccent>подписку</MmSerifAccent>.
            <br />
            Генерация — по правилам тарифа.
          </MmDisplayLg>
          <p className="mm-muted" style={{ marginTop: 'var(--s-4)' }}>
            Свой ключ{' '}
            <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
              WaveSpeed
            </a>{' '}
            (BYOK) или кредиты платформы (Managed). Год — скидка 25%.
          </p>
        </div>
        <div className="mm-pricing-toggles" role="group" aria-label="Формат тарифа">
          <button
            type="button"
            className={billing === 'byok' ? 'mm-toggle active' : 'mm-toggle'}
            onClick={() => setBilling('byok')}
          >
            Со своим ключом (BYOK)
          </button>
          <button
            type="button"
            className={billing === 'managed' ? 'mm-toggle active' : 'mm-toggle'}
            onClick={() => setBilling('managed')}
          >
            Всё включено (Managed)
          </button>
        </div>
        <div className="mm-pricing-toggles" role="group" aria-label="Период оплаты">
          <button
            type="button"
            className={period === 'month' ? 'mm-toggle active' : 'mm-toggle'}
            onClick={() => setPeriod('month')}
          >
            Месяц
          </button>
          <button
            type="button"
            className={period === 'year' ? 'mm-toggle active' : 'mm-toggle'}
            onClick={() => setPeriod('year')}
          >
            Год — скидка 25%
          </button>
        </div>
        <div className="mm-price-grid">
          {visible.map((plan) => (
            <article key={plan.product} className={`mm-price-card${plan.popular ? ' featured' : ''}`}>
              {plan.popular ? <span className="mm-badge mm-badge--new">Популярный</span> : null}
              <h3>{plan.title}</h3>
              <div className="mm-price-card__amount">{formatRub(plan.price_rub)}</div>
              <div className="mm-price-card__period">{period === 'year' ? 'в год' : 'в месяц'}</div>
              <ul>
                {tierFeatures(plan.tier, plan.billing_plan, plan.period, plan.managed_monthly_credits).map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <MmButton to="/login" variant={plan.popular ? 'primary' : 'secondary'} size="md">
                {plan.tier === 'studio' ? 'Связаться / начать' : 'Попробовать бесплатно'}
              </MmButton>
            </article>
          ))}
        </div>
        {!compact ? (
          <div className="mm-byok-explainer">
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
            <p className="mm-muted">
              Не хотите регистрироваться на WaveSpeed — выберите Managed: кредиты на студию уже в
              подписке, докупка от 50 шт. по текущим ценам в кабинете.
            </p>
          </div>
        ) : null}
      </MmContainer>
    </section>
  )
}
