import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AuthCheckingScreen } from '../auth/AuthCheckingScreen'
import { useAuthSessionGate } from '../auth/useAuthSessionGate'
import { AuthPanel } from '../AuthPanel'
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

/** /login — форма входа в едином SPA, после успеха → /workspace или ?next= */
export function LoginPage() {
  const { t } = useTranslation('auth')
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const referralCode = params.get('ref') || params.get('referral') || undefined
  const session = useAuthSessionGate()

  useEffect(() => {
    if (session === 'authenticated') {
      navigate(next, { replace: true })
    }
  }, [session, navigate, next])

  const onSuccess = () => {
    navigate(next, { replace: true })
  }

  if (session === 'checking' || session === 'authenticated') {
    return <AuthCheckingScreen />
  }

  return (
    <div className="auth-page">
      <div className="auth-page-inner">
        <AuthPanel onSuccess={onSuccess} referralCode={referralCode} />
        <p className="auth-page-back">
          <a href="/">{t('backToSite', { defaultValue: '← На главную' })}</a>
        </p>
      </div>
    </div>
  )
}
