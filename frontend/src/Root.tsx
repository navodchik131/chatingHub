import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import App from './App'
import { FaqPage } from './marketing/FaqPage'
import { LandingPage } from './marketing/LandingPage'
import { LoginPage } from './marketing/LoginPage'
import { MarketingLayout } from './marketing/MarketingLayout'
import { PricingPage } from './marketing/PricingPage'
import { PrivacyPage } from './marketing/PrivacyPage'
import { TermsPage } from './marketing/TermsPage'
import { AdminPage } from './admin/AdminPage'

function MarketingRoutes() {
  return (
    <>
      <Route index element={<LandingPage />} />
      <Route path="pricing" element={<PricingPage />} />
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
        <Route element={<MarketingLayout />}>
          <MarketingRoutes />
        </Route>
        <Route path="en" element={<MarketingLayout />}>
          <MarketingRoutes />
        </Route>
        <Route path="/workspace/*" element={<App />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
