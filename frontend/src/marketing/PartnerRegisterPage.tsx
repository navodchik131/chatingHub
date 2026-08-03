import { useCallback, useEffect } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AuthCheckingScreen } from '../auth/AuthCheckingScreen'
import { useAuthSessionGate } from '../auth/useAuthSessionGate'
import { AuthPanel } from '../AuthPanel'
import { useMarketingPath } from './i18n/useMarketingPath'
import '../styles/auth-ui.css'

function safeNext(raw: string | null): string {
  if (!raw) return '/workspace'
  try {
    const path = decodeURIComponent(raw)
    if (!path.startsWith('/') || path.startsWith('//')) return '/workspace'
    return path
  } catch {
    return '/workspace'
  }
}

/** /partners/register — регистрация партнёра с is_partner=true */
export function PartnerRegisterPage() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const session = useAuthSessionGate()

  useEffect(() => {
    if (session === 'authenticated') {
      navigate(next, { replace: true })
    }
  }, [session, navigate, next])

  const onSuccess = useCallback(() => {
    navigate(next, { replace: true })
  }, [navigate, next])

  if (session === 'checking' || session === 'authenticated') {
    return <AuthCheckingScreen />
  }

  return (
    <div className="auth-page">
      <div className="auth-page-inner">
        <AuthPanel onSuccess={onSuccess} partnerSignup registerOnly />
        <p className="auth-page-back">
          <Link to={path('/partners')}>{t('partnerRegisterPage.backToPartners')}</Link>
        </p>
        <p className="auth-page-back auth-page-back--muted">
          {t('partnerRegisterPage.hasAccount')}{' '}
          <Link to={path('/login')}>{t('partnerRegisterPage.loginLink')}</Link>
        </p>
      </div>
    </div>
  )
}
