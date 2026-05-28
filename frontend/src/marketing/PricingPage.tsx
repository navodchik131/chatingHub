import { Link } from 'react-router-dom'
import { parseCatalogFromHealth } from '../billing/planCatalog'
import { PricingSection } from './PricingSection'
import { usePublicHealth } from './usePublicHealth'

const FALLBACK_CREDITS_MIN = 50
const FALLBACK_CREDITS_BULK_FROM = 200
const FALLBACK_UNIT = 3
const FALLBACK_BULK_UNIT = 2.7

export function PricingPage() {
  const health = usePublicHealth()
  const plans = parseCatalogFromHealth(health)
  const creditsMin = health?.billing_credits_min_purchase ?? FALLBACK_CREDITS_MIN
  const creditsBulkFrom = health?.billing_credits_bulk_from ?? FALLBACK_CREDITS_BULK_FROM
  const creditsUnit = health?.billing_credits_unit_price_rub ?? FALLBACK_UNIT
  const creditsBulkUnit = health?.billing_credits_bulk_unit_price_rub ?? FALLBACK_BULK_UNIT
  const signupCredits = health?.signup_bonus_credits ?? 100

  return (
    <>
      <header className="mkt-section-head">
        <h1 className="mkt-h1" style={{ fontSize: 'clamp(1.65rem, 4vw, 2.25rem)' }}>
          Тарифы
        </h1>
        <p>
          Шесть планов: BYOK и Managed в трёх размерах (Solo, Pro, Studio). Оплата в кабинете через
          ЮKassa. Триал — {signupCredits} кредитов без срока.
        </p>
      </header>

      <PricingSection plans={plans} id="plans" />

      <section className="mkt-section" aria-labelledby="credits-heading">
        <h2 id="credits-heading">Докупка кредитов (Managed)</h2>
        <p>
          Любое количество от {creditsMin} шт. —{' '}
          {creditsUnit.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽/кредит; от{' '}
          {creditsBulkFrom} шт. —{' '}
          {creditsBulkUnit.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽/кредит. Фиксированных
          пакетов нет.
        </p>
        <Link to="/login" className="mkt-nav-cta" style={{ marginTop: '0.75rem' }}>
          Пополнить в кабинете
        </Link>
      </section>

      <section className="mkt-section mkt-section--alt">
        <h2>Триал</h2>
        <p>
          {signupCredits} кредитов при регистрации, без привязки карты. Для генерации подключите свой
          ключ WaveSpeed в интеграциях. Кредиты не сгорают по времени.
        </p>
      </section>

      <p className="muted">
        <Link to="/faq">FAQ</Link> · <Link to="/">На главную</Link>
      </p>
    </>
  )
}
