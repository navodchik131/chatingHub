import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { MmButton, MmContainer, MmEyebrow } from './components/MmUi'
import { usePublicHealth } from './usePublicHealth'
import { useMarketingPath } from './i18n/useMarketingPath'

const FALLBACK_CREDITS_MIN = 50
const FALLBACK_UNIT = 3

export function DemoCreditsPage() {
  const { t, i18n } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const health = usePublicHealth()
  const demoGenerations = health?.demo_generations_grant ?? 3
  const creditsMin = health?.billing_credits_min_purchase ?? FALLBACK_CREDITS_MIN
  const creditsUnit = health?.billing_credits_unit_price_rub ?? FALLBACK_UNIT
  const locale = i18n.language === 'en' ? 'en-US' : 'ru-RU'
  const ctx = {
    demoGenerations,
    creditsMin,
    creditsUnit: creditsUnit.toLocaleString(locale, { maximumFractionDigits: 2 }),
  }

  const demoPoints = t('demoPage.demoPoints', { returnObjects: true, ...ctx }) as string[]
  const creditPoints = t('demoPage.creditPoints', { returnObjects: true, ...ctx }) as string[]
  const afterItems = t('demoPage.afterItems', { returnObjects: true, ...ctx }) as Array<{
    title: string
    text: string
  }>

  return (
    <div className="mm-main--page">
      <MmContainer>
        <header className="mm-page-head">
          <MmEyebrow>{t('demoPage.eyebrow')}</MmEyebrow>
          <h1>{t('demoPage.title')}</h1>
          <p>{t('demoPage.intro', ctx)}</p>
        </header>

        <div className="mm-info-grid mm-info-grid--2">
          <article className="mm-info-card mm-info-card--accent">
            <span className="mm-info-card__label">{t('demoPage.demoCardLabel')}</span>
            <strong className="mm-info-card__value">{t('demoPage.demoCardValue', ctx)}</strong>
            <p>{t('demoPage.demoCardHint', ctx)}</p>
          </article>
          <article className="mm-info-card">
            <span className="mm-info-card__label">{t('demoPage.creditsCardLabel')}</span>
            <strong className="mm-info-card__value">{t('demoPage.creditsCardValue', ctx)}</strong>
            <p>{t('demoPage.creditsCardHint', ctx)}</p>
          </article>
        </div>

        <section className="mm-section mm-section--border" aria-labelledby="demo-what-title">
          <MmEyebrow>{t('demoPage.demoEyebrow')}</MmEyebrow>
          <h2 id="demo-what-title" className="mm-display-lg mm-info-h2">
            {t('demoPage.demoTitle')}
          </h2>
          <p className="mm-muted">{t('demoPage.demoDek', ctx)}</p>
          <ul className="mm-info-list">
            {Array.isArray(demoPoints)
              ? demoPoints.map((item, i) => (
                  <li key={item}>{t(`demoPage.demoPoints.${i}`, { ...ctx, defaultValue: item })}</li>
                ))
              : null}
          </ul>
        </section>

        <section className="mm-section mm-section--border" aria-labelledby="credits-what-title">
          <MmEyebrow>{t('demoPage.creditsEyebrow')}</MmEyebrow>
          <h2 id="credits-what-title" className="mm-display-lg mm-info-h2">
            {t('demoPage.creditsTitle')}
          </h2>
          <p className="mm-muted">{t('demoPage.creditsDek', ctx)}</p>
          <ul className="mm-info-list">
            {Array.isArray(creditPoints)
              ? creditPoints.map((item, i) => (
                  <li key={item}>{t(`demoPage.creditPoints.${i}`, { ...ctx, defaultValue: item })}</li>
                ))
              : null}
          </ul>
        </section>

        <section className="mm-section mm-section--border" aria-labelledby="after-title">
          <MmEyebrow>{t('demoPage.afterEyebrow')}</MmEyebrow>
          <h2 id="after-title" className="mm-display-lg mm-info-h2">
            {t('demoPage.afterTitle')}
          </h2>
          <div className="mm-info-grid">
            {Array.isArray(afterItems)
              ? afterItems.map((item, i) => (
                  <article key={item.title} className="mm-info-card">
                    <span className="mm-info-card__label">
                      {t(`demoPage.afterItems.${i}.title`, { defaultValue: item.title })}
                    </span>
                    <p>{t(`demoPage.afterItems.${i}.text`, { ...ctx, defaultValue: item.text })}</p>
                  </article>
                ))
              : null}
          </div>
        </section>

        <div className="mm-info-cta">
          <MmButton to="/login" size="lg">
            {t('demoPage.ctaPrimary', ctx)}
          </MmButton>
          <MmButton to="/pricing" variant="secondary" size="lg">
            {t('demoPage.ctaPricing')}
          </MmButton>
        </div>

        <p className="mm-muted" style={{ marginTop: 'var(--s-8)' }}>
          <Link to={path('/referral')} className="mm-link-arrow">
            {t('demoPage.footerReferral')}
          </Link>{' '}
          ·{' '}
          <Link to={path('/faq')} className="mm-link-arrow">
            {t('demoPage.footerFaq')}
          </Link>{' '}
          ·{' '}
          <Link to={path('/')} className="mm-link-arrow">
            {t('demoPage.footerHome')}
          </Link>
        </p>
      </MmContainer>
    </div>
  )
}
