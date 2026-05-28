import { Link } from 'react-router-dom'
import { parseCatalogFromHealth } from '../billing/planCatalog'
import { formatRub, usePublicHealth } from './usePublicHealth'
import {
  MmCtaBanner,
  MmCommunityBand,
  MmHero,
  MmReferralBand,
  MmHowSection,
  MmModelStrip,
  MmPainSection,
  MmShowcase,
  MmToolGrid,
  MmTrialBand,
} from './components/MmSections'
import { MmContainer, MmEyebrow, MmDisplayLg } from './components/MmUi'
import { PricingSection } from './PricingSection'

export function LandingPage() {
  const health = usePublicHealth()
  const plans = parseCatalogFromHealth(health)

  return (
    <>
      <MmHero />
      <MmCommunityBand />
      <MmReferralBand />
      <MmToolGrid />
      <MmPainSection />
      <MmShowcase />
      <MmHowSection />
      <MmModelStrip />
      <PricingSection plans={plans} />
      <section className="mm-section mm-section--border" aria-labelledby="compare-title">
        <MmContainer>
          <MmEyebrow>Таблица</MmEyebrow>
          <MmDisplayLg as="h2" id="compare-title" className="mm-section__title--sm">
            Сравни тарифы
          </MmDisplayLg>
          <div className="mm-table-wrap">
            <table className="mm-table">
              <thead>
                <tr>
                  <th>Функция</th>
                  <th>BYOK Solo</th>
                  <th>BYOK Pro</th>
                  <th>BYOK Studio</th>
                  <th>Managed Pro</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Цена / мес</td>
                  <td>{formatRub(990)}</td>
                  <td>{formatRub(2490)}</td>
                  <td>{formatRub(5990)}</td>
                  <td>{formatRub(4990)}</td>
                </tr>
                <tr>
                  <td>Пользователей</td>
                  <td>1</td>
                  <td>3</td>
                  <td>10</td>
                  <td>3</td>
                </tr>
                <tr>
                  <td>Моделей</td>
                  <td>1</td>
                  <td>3</td>
                  <td>10</td>
                  <td>3</td>
                </tr>
                <tr>
                  <td>Свой ключ WaveSpeed</td>
                  <td>✓</td>
                  <td>✓</td>
                  <td>✓</td>
                  <td>—</td>
                </tr>
                <tr>
                  <td>Кредиты в подписке</td>
                  <td>—</td>
                  <td>—</td>
                  <td>—</td>
                  <td>400 / мес</td>
                </tr>
                <tr>
                  <td>Чат + перевод</td>
                  <td>✓</td>
                  <td>✓</td>
                  <td>✓</td>
                  <td>✓</td>
                </tr>
                <tr>
                  <td>GROK</td>
                  <td>✓</td>
                  <td>✓</td>
                  <td>✓</td>
                  <td>✓</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mm-muted" style={{ marginTop: 'var(--s-4)' }}>
            <Link to="/pricing" className="mm-link-arrow">
              Полная таблица и детали →
            </Link>
          </p>
        </MmContainer>
      </section>
      <MmTrialBand />
      <section className="mm-section mm-section--compact">
        <MmContainer>
          <MmEyebrow>FAQ</MmEyebrow>
          <p className="mm-muted">
            <Link to="/faq" className="mm-link-arrow">
              Частые вопросы о BYOK, триале и оплате →
            </Link>
          </p>
        </MmContainer>
      </section>
      <MmCtaBanner />
    </>
  )
}
