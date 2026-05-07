import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import App from './App'
import { FaqPage } from './marketing/FaqPage'
import { LandingPage } from './marketing/LandingPage'
import { LoginPage } from './marketing/LoginPage'
import { MarketingLayout } from './marketing/MarketingLayout'
import { PricingPage } from './marketing/PricingPage'

export default function Root() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MarketingLayout />}>
          <Route index element={<LandingPage />} />
          <Route path="pricing" element={<PricingPage />} />
          <Route path="faq" element={<FaqPage />} />
          <Route path="login" element={<LoginPage />} />
        </Route>
        <Route path="/workspace/*" element={<App />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
