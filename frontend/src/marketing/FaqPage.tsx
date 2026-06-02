import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { parseReferralFromHealth } from '../billing/referral'
import { renderWithWavespeedRef } from '../billing/wavespeedRefLink'
import { MmContainer } from './components/MmUi'
import { usePublicHealth } from './usePublicHealth'
import { useMarketingPath } from './i18n/useMarketingPath'

type FaqItemData = {
  question: string
  paragraphs: string[]
}

function FaqAnswerParagraph({ text }: { text: string }) {
  const { path } = useMarketingPath()
  const lower = text.toLowerCase()
  if (text.includes('→') && (lower.includes('вход') || lower.includes('sign in') || lower.includes('log in'))) {
    return (
      <p>
        <Link to={path('/login')} className="mm-link-arrow">
          {text}
        </Link>
      </p>
    )
  }
  if (text.includes('→') && (lower.includes('тариф') || lower.includes('pricing') || lower.includes('plan'))) {
    return (
      <p>
        <Link to={path('/pricing')} className="mm-link-arrow">
          {text}
        </Link>
      </p>
    )
  }
  return <p>{renderWithWavespeedRef(text)}</p>
}

export function FaqPage() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const health = usePublicHealth()
  const ref = parseReferralFromHealth(health)
  const items = t('faq.items', { returnObjects: true }) as FaqItemData[]

  return (
    <div className="mm-main--page">
      <MmContainer>
        <header className="mm-page-head">
          <h1>{t('faq.title')}</h1>
          <p>{t('faq.intro')}</p>
        </header>
        <section className="mm-faq" aria-label={t('faq.listAria')}>
          {Array.isArray(items)
            ? items.map((item, itemIdx) => (
                <details key={item.question} className="mm-details">
                  <summary>{t(`faq.items.${itemIdx}.question`, { defaultValue: item.question })}</summary>
                  <div className="mm-details__body">
                    {item.paragraphs.map((p, pIdx) => (
                      <FaqAnswerParagraph
                        key={`${itemIdx}-${pIdx}`}
                        text={t(`faq.items.${itemIdx}.paragraphs.${pIdx}`, {
                          ref,
                          defaultValue: p,
                        })}
                      />
                    ))}
                  </div>
                </details>
              ))
            : null}
        </section>
        <p className="mm-muted" style={{ marginTop: 'var(--s-8)' }}>
          <Link to={path('/pricing')} className="mm-link-arrow">
            {t('faq.footerPricing')}
          </Link>{' '}
          ·{' '}
          <Link to={path('/')} className="mm-link-arrow">
            {t('faq.footerHome')}
          </Link>
        </p>
      </MmContainer>
    </div>
  )
}
