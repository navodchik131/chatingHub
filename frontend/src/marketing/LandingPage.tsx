import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { parseCatalogFromHealth } from '../billing/planCatalog'
import { usePublicHealth } from './usePublicHealth'
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
import { LandingCompareTable } from './LandingCompareTable'
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
          <LandingCompareTable />
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
