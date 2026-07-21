import { useEffect, useReducer, useState } from 'react'
import { NavLink, Outlet, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { getToken } from '../api'
import { MmButton, MmContainer } from './components/MmUi'
import { LanguageSwitcher } from './i18n/LanguageSwitcher'
import { MarketingI18nSync } from './i18n/MarketingI18nSync'
import { useMarketingPath } from './i18n/useMarketingPath'
import './mm-tokens.css'
import './mm-site.css'

function useBillingBanner(param: string | null) {
  const { t } = useTranslation('marketing')
  const k = (param || '').trim().toLowerCase()
  if (!k) return null
  if (k === 'success' || k === 'ok' || k === 'paid') {
    return {
      variant: 'success' as const,
      title: t('layout.billingSuccessTitle'),
      body: t('layout.billingSuccessBody'),
    }
  }
  if (k === 'cancel' || k === 'cancelled' || k === 'canceled') {
    return {
      variant: 'warn' as const,
      title: t('layout.billingCancelTitle'),
      body: t('layout.billingCancelBody'),
    }
  }
  if (k === 'fail' || k === 'failed' || k === 'error') {
    return {
      variant: 'error' as const,
      title: t('layout.billingFailTitle'),
      body: t('layout.billingFailBody'),
    }
  }
  return {
    variant: 'warn' as const,
    title: t('layout.billingUnknownTitle'),
    body: t('layout.billingUnknownBody'),
  }
}

export function MarketingLayout() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const [, bump] = useReducer((x: number) => x + 1, 0)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'chating_token') bump()
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const hasToken = Boolean(getToken())
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const billingCopy = useBillingBanner(searchParams.get('billing'))
  const year = new Date().getFullYear()

  useEffect(() => {
    if (!hasToken) return
    if (searchParams.get('account') !== 'integrations') return
    const next = new URLSearchParams()
    const fanvue = searchParams.get('fanvue')
    const instagram = searchParams.get('instagram')
    const reason = searchParams.get('reason')
    if (fanvue) next.set('fanvue', fanvue)
    if (instagram) next.set('instagram', instagram)
    if (reason) next.set('reason', reason)
    const q = next.toString()
    navigate(`/workspace/connections${q ? `?${q}` : ''}`, { replace: true })
  }, [hasToken, navigate, searchParams])

  const dismissBillingBanner = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('billing')
    setSearchParams(next, { replace: true })
  }

  const homePath = path('/')

  return (
    <div className="mm-root">
      <MarketingI18nSync />
      <a className="mm-skip" href="#main-content">
        {t('layout.skipLink')}
      </a>
      <header className={`mm-header${scrolled ? ' is-scrolled' : ''}`}>
        <MmContainer className="mm-header__inner">
          <NavLink to={homePath} className="mm-wordmark" end>
            MODELMATE
            <span className="mm-wordmark__dot" aria-hidden />
          </NavLink>
          <nav className="mm-nav" aria-label={t('layout.navAria')}>
            <NavLink to={homePath} end className="mm-nav__link">
              {t('layout.navHome')}
            </NavLink>
            <NavLink to={path('/pricing')} className="mm-nav__link">
              {t('layout.navPricing')}
            </NavLink>
            <NavLink to={path('/faq')} className="mm-nav__link">
              {t('layout.navFaq')}
            </NavLink>
          </nav>
          <div className="mm-header__actions">
            <LanguageSwitcher />
            {hasToken ? (
              <NavLink to="/workspace" className="mm-header__login">
                {t('layout.headerWorkspace')}
              </NavLink>
            ) : (
              <NavLink to={path('/login')} className="mm-header__login">
                {t('layout.headerLogin')}
              </NavLink>
            )}
            <MmButton to={hasToken ? '/workspace' : '/login'} size="sm">
              {t('layout.headerCta')}
            </MmButton>
          </div>
        </MmContainer>
      </header>
      <main id="main-content" className="mm-main">
        {billingCopy ? (
          <div
            className={`billing-return-banner billing-return-banner--${billingCopy.variant}`}
            role="status"
          >
            <div className="billing-return-banner__text">
              <h2 className="billing-return-banner__title">{billingCopy.title}</h2>
              <p className="billing-return-banner__body">{billingCopy.body}</p>
            </div>
            <div className="billing-return-banner__actions">
              {hasToken ? (
                <MmButton to="/workspace" size="sm">
                  {t('layout.billingToWorkspace')}
                </MmButton>
              ) : (
                <MmButton to="/login" size="sm">
                  {t('layout.billingLogin')}
                </MmButton>
              )}
              <button type="button" className="mm-btn mm-btn--ghost mm-btn--sm" onClick={dismissBillingBanner}>
                {t('layout.billingDismiss')}
              </button>
            </div>
          </div>
        ) : null}
        <Outlet />
      </main>
      <footer className="mm-footer">
        <MmContainer>
          <div className="mm-footer__grid">
            <div className="mm-footer__brand">
              <NavLink to={homePath} className="mm-wordmark" end>
                MODELMATE
                <span className="mm-wordmark__dot" aria-hidden />
              </NavLink>
              <p>{t('layout.footerBrand')}</p>
            </div>
            <div className="mm-footer__col">
              <h4>{t('layout.footerPricing')}</h4>
              <ul>
                <li>
                  <NavLink to={path('/pricing')}>{t('layout.footerPricingPlans')}</NavLink>
                </li>
                <li>
                  <NavLink to={path('/referral')}>{t('layout.footerPricingReferral')}</NavLink>
                </li>
                <li>
                  <NavLink to={path('/demo')}>{t('layout.footerPricingTrial')}</NavLink>
                </li>
              </ul>
            </div>
            <div className="mm-footer__col">
              <h4>{t('layout.footerHelp')}</h4>
              <ul>
                <li>
                  <NavLink to={path('/faq')}>{t('layout.footerHelpFaq')}</NavLink>
                </li>
                <li>
                  <a href={path('/login')}>{t('layout.footerHelpLogin')}</a>
                </li>
              </ul>
            </div>
            <div className="mm-footer__col">
              <h4>{t('layout.footerLegal')}</h4>
              <ul>
                <li>
                  <NavLink to={path('/terms')}>{t('layout.footerLegalTerms')}</NavLink>
                </li>
                <li>
                  <NavLink to={path('/privacy')}>{t('layout.footerLegalPrivacy')}</NavLink>
                </li>
              </ul>
            </div>
          </div>
          <div className="mm-footer__bottom">
            <span>{t('layout.footerCopyright', { year })}</span>
            <span>{t('layout.footerTagline')}</span>
          </div>
        </MmContainer>
      </footer>
    </div>
  )
}
