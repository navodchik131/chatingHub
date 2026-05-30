import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
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
import { useMarketingPath } from './i18n/useMarketingPath'

export function LandingPage() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
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
          <MmEyebrow>{t('landing.compare.eyebrow')}</MmEyebrow>
          <MmDisplayLg as="h2" id="compare-title" className="mm-section__title--sm">
            {t('landing.compare.title')}
          </MmDisplayLg>
          <div className="mm-table-wrap">
            <table className="mm-table">
              <thead>
                <tr>
                  <th>{t('landing.compare.colFeature')}</th>
                  <th>{t('landing.compare.colByokSolo')}</th>
                  <th>{t('landing.compare.colByokPro')}</th>
                  <th>{t('landing.compare.colByokStudio')}</th>
                  <th>{t('landing.compare.colManagedPro')}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{t('landing.compare.rowPrice')}</td>
                  <td>{formatRub(990)}</td>
                  <td>{formatRub(2490)}</td>
                  <td>{formatRub(5990)}</td>
                  <td>{formatRub(4990)}</td>
                </tr>
                <tr>
                  <td>{t('landing.compare.rowUsers')}</td>
                  <td>1</td>
                  <td>3</td>
                  <td>10</td>
                  <td>3</td>
                </tr>
                <tr>
                  <td>{t('landing.compare.rowModels')}</td>
                  <td>1</td>
                  <td>3</td>
                  <td>10</td>
                  <td>3</td>
                </tr>
                <tr>
                  <td>{t('landing.compare.rowByokKey')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.no')}</td>
                </tr>
                <tr>
                  <td>{t('landing.compare.rowCredits')}</td>
                  <td>{t('landing.compare.no')}</td>
                  <td>{t('landing.compare.no')}</td>
                  <td>{t('landing.compare.no')}</td>
                  <td>{t('landing.compare.managedCreditsValue')}</td>
                </tr>
                <tr>
                  <td>{t('landing.compare.rowChat')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.yes')}</td>
                </tr>
                <tr>
                  <td>{t('landing.compare.rowGrok')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.yes')}</td>
                  <td>{t('landing.compare.yes')}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mm-muted" style={{ marginTop: 'var(--s-4)' }}>
            <Link to={path('/pricing')} className="mm-link-arrow">
              {t('landing.compare.linkFull')}
            </Link>
          </p>
        </MmContainer>
      </section>
      <MmTrialBand />
      <section className="mm-section mm-section--compact">
        <MmContainer>
          <MmEyebrow>{t('landing.faqTeaser.eyebrow')}</MmEyebrow>
          <p className="mm-muted">
            <Link to={path('/faq')} className="mm-link-arrow">
              {t('landing.faqTeaser.link')}
            </Link>
          </p>
        </MmContainer>
      </section>
      <MmCtaBanner />
    </>
  )
}
