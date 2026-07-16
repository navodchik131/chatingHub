import { parseCatalogFromHealth } from '../billing/planCatalog'
import { usePublicHealth } from './usePublicHealth'
import { MmHero, MmCtaBanner } from './components/MmSections'
import {
  MmBeforeAfterSlider,
  MmCompareWorkflow,
  MmEnginesShowcase,
  MmLandingFaq,
  MmLandingPain,
  MmModesShowcase,
  MmModuleShowcase,
  MmPlatformCounters,
  MmPlatformTicker,
  MmReviewsCarousel,
  MmSecurityBlock,
  MmSolutionBlock,
  MmTelegramReferralRow,
} from './components/MmLandingRedesign'
import { PricingSection } from './PricingSection'

export function LandingPage() {
  const health = usePublicHealth()
  const plans = parseCatalogFromHealth(health)

  return (
    <>
      <MmHero />
      <MmPlatformTicker />
      <MmLandingPain />
      <MmCompareWorkflow />
      <MmSolutionBlock />
      <MmModuleShowcase />
      <MmModesShowcase />
      <MmEnginesShowcase />
      <MmBeforeAfterSlider />
      <MmTelegramReferralRow />
      <MmPlatformCounters />
      <MmReviewsCarousel />
      <PricingSection plans={plans} />
      <MmLandingFaq />
      <MmSecurityBlock />
      <MmCtaBanner />
    </>
  )
}
