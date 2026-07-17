import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { parseReferralFromHealth } from '../billing/referral'
import { MmButton, MmContainer, MmEyebrow } from './components/MmUi'
import { usePublicHealth } from './usePublicHealth'
import { useMarketingPath } from './i18n/useMarketingPath'

export function ReferralPage() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const health = usePublicHealth()
  const ref = parseReferralFromHealth(health)
  const steps = t('referralPage.steps', { returnObjects: true, ref }) as Array<{
    title: string
    text: string
  }>
  const conditions = t('referralPage.conditions', { returnObjects: true, ref }) as string[]
  const examples = t('referralPage.examples', { returnObjects: true, ref }) as Array<{
    label: string
    value: string
    hint: string
  }>

  return (
    <div className="mm-main--page">
      <MmContainer>
        <header className="mm-page-head">
          <MmEyebrow>{t('referralPage.eyebrow')}</MmEyebrow>
          <h1>{t('referralPage.title')}</h1>
          <p>{t('referralPage.intro', { ref })}</p>
        </header>

        <div className="mm-info-grid" role="list">
          <article className="mm-info-card" role="listitem">
            <span className="mm-info-card__label">{t('referral.cardFriendWho')}</span>
            <strong className="mm-info-card__value">{t('referral.cardFriendValue', { ref })}</strong>
            <p>{t('referral.cardFriendHint')}</p>
          </article>
          <article className="mm-info-card mm-info-card--accent" role="listitem">
            <span className="mm-info-card__label">{t('referral.cardReferrerWho')}</span>
            <strong className="mm-info-card__value">{t('referral.cardReferrerValue', { ref })}</strong>
            <p>{t('referral.cardReferrerHint', { ref })}</p>
          </article>
          <article className="mm-info-card" role="listitem">
            <span className="mm-info-card__label">{t('referral.cardPayWho')}</span>
            <strong className="mm-info-card__value">{t('referral.cardPayValue', { ref })}</strong>
            <p>{t('referral.cardPayHint')}</p>
          </article>
        </div>

        <section className="mm-section mm-section--border" aria-labelledby="ref-how-title">
          <MmEyebrow>{t('referralPage.howEyebrow')}</MmEyebrow>
          <h2 id="ref-how-title" className="mm-display-lg mm-info-h2">
            {t('referralPage.howTitle')}
          </h2>
          <ol className="mm-info-steps">
            {Array.isArray(steps)
              ? steps.map((step, i) => (
                  <li key={step.title}>
                    <span className="mm-info-steps__n" aria-hidden>
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <div>
                      <h3>{t(`referralPage.steps.${i}.title`, { defaultValue: step.title })}</h3>
                      <p>{t(`referralPage.steps.${i}.text`, { ref, defaultValue: step.text })}</p>
                    </div>
                  </li>
                ))
              : null}
          </ol>
        </section>

        <section className="mm-section mm-section--border" aria-labelledby="ref-ex-title">
          <MmEyebrow>{t('referralPage.examplesEyebrow')}</MmEyebrow>
          <h2 id="ref-ex-title" className="mm-display-lg mm-info-h2">
            {t('referralPage.examplesTitle')}
          </h2>
          <div className="mm-info-grid mm-info-grid--2">
            {Array.isArray(examples)
              ? examples.map((ex, i) => (
                  <article key={ex.label} className="mm-info-card">
                    <span className="mm-info-card__label">
                      {t(`referralPage.examples.${i}.label`, { defaultValue: ex.label })}
                    </span>
                    <strong className="mm-info-card__value">
                      {t(`referralPage.examples.${i}.value`, { ref, defaultValue: ex.value })}
                    </strong>
                    <p>{t(`referralPage.examples.${i}.hint`, { ref, defaultValue: ex.hint })}</p>
                  </article>
                ))
              : null}
          </div>
        </section>

        <section className="mm-section mm-section--border" aria-labelledby="ref-cond-title">
          <MmEyebrow>{t('referralPage.conditionsEyebrow')}</MmEyebrow>
          <h2 id="ref-cond-title" className="mm-display-lg mm-info-h2">
            {t('referralPage.conditionsTitle')}
          </h2>
          <ul className="mm-info-list">
            {Array.isArray(conditions)
              ? conditions.map((item, i) => (
                  <li key={item}>{t(`referralPage.conditions.${i}`, { ref, defaultValue: item })}</li>
                ))
              : null}
          </ul>
          <p className="mm-muted" style={{ marginTop: 'var(--s-6)' }}>
            {t('referral.note')}
          </p>
        </section>

        <div className="mm-info-cta">
          <MmButton to="/login" size="lg">
            {t('referral.ctaPrimary')}
          </MmButton>
          <MmButton to="/pricing" variant="secondary" size="lg">
            {t('referralPage.ctaPricing')}
          </MmButton>
        </div>

        <p className="mm-muted" style={{ marginTop: 'var(--s-8)' }}>
          <Link to={path('/demo')} className="mm-link-arrow">
            {t('referralPage.footerDemo')}
          </Link>{' '}
          ·{' '}
          <Link to={path('/faq')} className="mm-link-arrow">
            {t('referralPage.footerFaq')}
          </Link>{' '}
          ·{' '}
          <Link to={path('/')} className="mm-link-arrow">
            {t('referralPage.footerHome')}
          </Link>
        </p>
      </MmContainer>
    </div>
  )
}
