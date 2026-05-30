import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useMarketingPath } from './useMarketingPath'
import { MmContainer } from '../components/MmUi'

type LegalSection = {
  title: string
  paragraphs?: string[]
  list?: string[]
  linkToTerms?: boolean
  linkToPrivacy?: boolean
}

export function LegalDocument({ doc }: { doc: 'privacy' | 'terms' }) {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const year = new Date().getFullYear()
  const sections = t(`legal.${doc}.sections`, { returnObjects: true }) as LegalSection[]

  return (
    <div className="mm-main--page">
      <MmContainer>
        <header className="mm-page-head">
          <h1>{t(`legal.${doc}.title`)}</h1>
          <p className="mm-muted" style={{ margin: 0 }}>
            {t(`legal.${doc}.intro`)}
          </p>
        </header>

        <article className="mm-legal" aria-labelledby={`legal-${doc}`}>
          <p className="mm-legal-meta" id={`legal-${doc}`}>
            {t(`legal.${doc}.meta`, { year })}
          </p>

          {Array.isArray(sections)
            ? sections.map((section) => (
                <section key={section.title} className="mm-legal-block">
                  <h2>{section.title}</h2>
                  {section.paragraphs?.map((p) => (
                    <p key={p.slice(0, 24)}>{p}</p>
                  ))}
                  {section.list?.length ? (
                    <ul>
                      {section.list.map((item) => (
                        <li key={item.slice(0, 24)}>
                          <Trans
                            ns="marketing"
                            defaults={item}
                            components={{ strong: <strong /> }}
                          >
                            {item}
                          </Trans>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {section.linkToTerms ? (
                    <p>
                      <Link to={path('/terms')} className="mm-link-arrow">
                        {t('legal.privacy.linkTerms')}
                      </Link>
                    </p>
                  ) : null}
                  {section.linkToPrivacy ? (
                    <p>
                      <Link to={path('/privacy')} className="mm-link-arrow">
                        {t('legal.terms.linkPrivacy')}
                      </Link>
                    </p>
                  ) : null}
                </section>
              ))
            : null}
        </article>
      </MmContainer>
    </div>
  )
}
