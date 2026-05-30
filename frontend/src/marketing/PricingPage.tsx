import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { parseCatalogFromHealth } from '../billing/planCatalog'
import { MmButton, MmContainer, MmEyebrow } from './components/MmUi'
import { PricingSection } from './PricingSection'
import { usePublicHealth } from './usePublicHealth'
import { useMarketingPath } from './i18n/useMarketingPath'

const FALLBACK_CREDITS_MIN = 50
const FALLBACK_CREDITS_BULK_FROM = 200
const FALLBACK_UNIT = 3
const FALLBACK_BULK_UNIT = 2.7

export function PricingPage() {
  const { t, i18n } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const health = usePublicHealth()
  const plans = parseCatalogFromHealth(health)
  const creditsMin = health?.billing_credits_min_purchase ?? FALLBACK_CREDITS_MIN
  const creditsBulkFrom = health?.billing_credits_bulk_from ?? FALLBACK_CREDITS_BULK_FROM
  const creditsUnit = health?.billing_credits_unit_price_rub ?? FALLBACK_UNIT
  const creditsBulkUnit = health?.billing_credits_bulk_unit_price_rub ?? FALLBACK_BULK_UNIT
  const signupCredits = health?.signup_bonus_credits ?? 100
  const locale = i18n.language === 'en' ? 'en-US' : 'ru-RU'

  return (
    <div className="mm-main--page">
      <MmContainer>
        <header className="mm-page-head">
          <MmEyebrow>{t('pricingPage.eyebrow')}</MmEyebrow>
          <h1>{t('pricingPage.title')}</h1>
          <p>{t('pricingPage.intro', { signupCredits })}</p>
        </header>
      </MmContainer>
      <PricingSection plans={plans} id="plans" />
      <MmContainer>
        <section className="mm-section mm-section--border" aria-labelledby="credits-heading">
          <MmEyebrow>{t('pricingPage.creditsEyebrow')}</MmEyebrow>
          <h2 id="credits-heading" className="mm-display-lg" style={{ fontSize: 'clamp(1.5rem, 3vw, 2rem)' }}>
            {t('pricingPage.creditsTitle')}
          </h2>
          <p className="mm-muted">
            {t('pricingPage.creditsDek', {
              creditsMin,
              creditsUnit: creditsUnit.toLocaleString(locale, { maximumFractionDigits: 2 }),
              creditsBulkFrom,
              creditsBulkUnit: creditsBulkUnit.toLocaleString(locale, { maximumFractionDigits: 2 }),
            })}
          </p>
          <div style={{ marginTop: 'var(--s-4)' }}>
            <MmButton to="/login">{t('pricingPage.creditsCta')}</MmButton>
          </div>
        </section>
        <section className="mm-section mm-section--border">
          <MmEyebrow>{t('pricingPage.trialEyebrow')}</MmEyebrow>
          <h2 className="mm-display-lg" style={{ fontSize: 'clamp(1.5rem, 3vw, 2rem)' }}>
            {t('pricingPage.trialTitle')}
          </h2>
          <p className="mm-muted">{t('pricingPage.trialDek', { signupCredits })}</p>
        </section>
        <p className="mm-muted">
          <Link to={path('/faq')} className="mm-link-arrow">
            {t('pricingPage.footerFaq')}
          </Link>{' '}
          ·{' '}
          <Link to={path('/')} className="mm-link-arrow">
            {t('pricingPage.footerHome')}
          </Link>
        </p>
      </MmContainer>
    </div>
  )
}
