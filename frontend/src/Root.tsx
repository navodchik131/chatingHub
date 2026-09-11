import { useEffect } from 'react'

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { FaqPage } from './marketing/FaqPage'

import { LandingPage } from './marketing/LandingPage'

import { LoginPage } from './marketing/LoginPage'

import { MarketingLayout } from './marketing/MarketingLayout'

import { PartnersPage } from './marketing/PartnersPage'

import { PartnerRegisterPage } from './marketing/PartnerRegisterPage'

import { PricingPage } from './marketing/PricingPage'

import { PrivacyPage } from './marketing/PrivacyPage'

import { ReferralPage } from './marketing/ReferralPage'

import { DemoCreditsPage } from './marketing/DemoCreditsPage'

import { AboutServicePage } from './marketing/AboutServicePage'

import { TermsPage } from './marketing/TermsPage'

import { AdminPage } from './admin/AdminPage'

import { CabinetRoute } from './cabinet/CabinetRoute'

import { WorkflowPage } from './workflow/WorkflowPage'

import { getToken } from './api'



function marketingRouteChildren() {

  return (

    <>

      <Route index element={<LandingPage />} />

      <Route path="pricing" element={<PricingPage />} />

      <Route path="referral" element={<ReferralPage />} />

      <Route path="partners" element={<PartnersPage />} />

      <Route path="partners/register" element={<PartnerRegisterPage />} />

      <Route path="demo" element={<DemoCreditsPage />} />

      <Route path="faq" element={<FaqPage />} />

      <Route path="about" element={<AboutServicePage />} />

      <Route path="privacy" element={<PrivacyPage />} />

      <Route path="terms" element={<TermsPage />} />

      <Route path="login" element={<LoginPage />} />

    </>

  )

}



function AdminGate() {

  if (!getToken()) return <Navigate to="/login?next=%2Fadmin" replace />

  return <AdminPage />

}



/** Если React Router оказался на /chat/ (после login navigate) — полный reload на Unibox SPA. */
function ChatExternalReload() {

  useEffect(() => {

    window.location.replace(

      `${window.location.pathname}${window.location.search}${window.location.hash}`,

    )

  }, [])

  return null

}



export default function Root() {

  return (

    <BrowserRouter>

      <Routes>

        <Route element={<MarketingLayout />}>{marketingRouteChildren()}</Route>

        <Route path="en" element={<MarketingLayout />}>

          {marketingRouteChildren()}

        </Route>



        <Route path="/workspace/workflow/*" element={<WorkflowPage />} />

        <Route path="/workspace/*" element={<CabinetRoute />} />

        <Route path="/workspace" element={<CabinetRoute />} />



        <Route path="/admin" element={<AdminGate />} />

        <Route path="/chat/*" element={<ChatExternalReload />} />

        <Route path="*" element={<Navigate to="/" replace />} />

      </Routes>

    </BrowserRouter>

  )

}


