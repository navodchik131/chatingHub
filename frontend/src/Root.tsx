import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { FaqPage } from './marketing/FaqPage'
import { LandingPage } from './marketing/LandingPage'
import { LoginPage } from './marketing/LoginPage'
import { MarketingLayout } from './marketing/MarketingLayout'
import { PricingPage } from './marketing/PricingPage'
import { PrivacyPage } from './marketing/PrivacyPage'
import { ReferralPage } from './marketing/ReferralPage'
import { DemoCreditsPage } from './marketing/DemoCreditsPage'
import { TermsPage } from './marketing/TermsPage'
import { AdminPage } from './admin/AdminPage'
import { WorkflowPage } from './workflow/WorkflowPage'

/** Client-side /workspace/* остаётся в маркетинг-SPA — принудительно уходим на nginx → frontend-os. */
function WorkspaceHandoff() {
  const location = useLocation()
  useEffect(() => {
    const target = `${location.pathname}${location.search}${location.hash}`
    window.location.replace(target === '/workspace' ? '/workspace/' : target)
  }, [location.pathname, location.search, location.hash])
  return null
}

/** Дочерние <Route> маркетинга (не компонент-обёртка — RR требует Route напрямую). */
function marketingRouteChildren() {
  return (
    <>
      <Route index element={<LandingPage />} />
      <Route path="pricing" element={<PricingPage />} />
      <Route path="referral" element={<ReferralPage />} />
      <Route path="demo" element={<DemoCreditsPage />} />
      <Route path="faq" element={<FaqPage />} />
      <Route path="privacy" element={<PrivacyPage />} />
      <Route path="terms" element={<TermsPage />} />
      <Route path="login" element={<LoginPage />} />
    </>
  )
}

export default function Root() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MarketingLayout />}>{marketingRouteChildren()}</Route>
        <Route path="en" element={<MarketingLayout />}>
          {marketingRouteChildren()}
        </Route>
        <Route path="/workspace/workflow" element={<WorkflowPage />} />
        <Route path="/workspace/*" element={<WorkspaceHandoff />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
