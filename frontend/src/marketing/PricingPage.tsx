import { Link } from 'react-router-dom'
import { parseCatalogFromHealth } from '../billing/planCatalog'
import { MmButton, MmContainer, MmEyebrow } from './components/MmUi'
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
    <div className="mm-main--page">
      <MmContainer>
        <header className="mm-page-head">
          <MmEyebrow>Тарифы · ЮKassa</MmEyebrow>
          <h1>Тарифы</h1>
          <p>
            Шесть планов: BYOK и Managed в трёх размерах (Solo, Pro, Studio). Оплата в кабинете через
            ЮKassa. Триал — {signupCredits} кредитов без срока.
          </p>
        </header>
      </MmContainer>
      <PricingSection plans={plans} id="plans" />
      <MmContainer>
        <section className="mm-section mm-section--border" aria-labelledby="credits-heading">
          <MmEyebrow>Managed · докупка</MmEyebrow>
          <h2 id="credits-heading" className="mm-display-lg" style={{ fontSize: 'clamp(1.5rem, 3vw, 2rem)' }}>
            Кредиты без пакетов
          </h2>
          <p className="mm-muted">
            Любое количество от {creditsMin} шт. —{' '}
            {creditsUnit.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽/кредит; от{' '}
            {creditsBulkFrom} шт. —{' '}
            {creditsBulkUnit.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽/кредит.
          </p>
          <div style={{ marginTop: 'var(--s-4)' }}>
            <MmButton to="/login">Пополнить в кабинете</MmButton>
          </div>
        </section>
        <section className="mm-section mm-section--border">
          <MmEyebrow>Триал</MmEyebrow>
          <h2 className="mm-display-lg" style={{ fontSize: 'clamp(1.5rem, 3vw, 2rem)' }}>
            Старт без карты
          </h2>
          <p className="mm-muted">
            {signupCredits} кредитов при регистрации. Для генерации подключите свой ключ WaveSpeed в
            интеграциях. Кредиты не сгорают по времени.
          </p>
        </section>
        <p className="mm-muted">
          <Link to="/faq" className="mm-link-arrow">
            FAQ →
          </Link>{' '}
          ·{' '}
          <Link to="/" className="mm-link-arrow">
            На главную ↗
          </Link>
        </p>
      </MmContainer>
    </div>
  )
}
