import { useCallback, useEffect } from 'react'
import { useNavigate, useSearchParams, type NavigateFunction } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AuthCheckingScreen } from '../auth/AuthCheckingScreen'
import { useAuthSessionGate } from '../auth/useAuthSessionGate'
import { AuthPanel } from '../AuthPanel'
import { mergePartnerAttribution } from './partnerAttribution'
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

/** Unibox и другие SPA вне marketing/cabinet — только полная перезагрузка, не React Router. */
function isExternalAppPath(path: string): boolean {
  return path === '/chat' || path.startsWith('/chat/')
}

function goAfterLogin(next: string, navigate: NavigateFunction) {
  if (isExternalAppPath(next)) {
    const target = next.endsWith('/') ? next : `${next}/`
    window.location.assign(target)
    return
  }
  navigate(next, { replace: true })
}

/** /login — форма входа в едином SPA, после успеха → /workspace или ?next= */
export function LoginPage() {
  const { t } = useTranslation('auth')
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const referralCode = params.get('ref') || params.get('referral') || undefined
  const partnerAtt = mergePartnerAttribution(params)
  const partnerSlug = params.get('pref') || params.get('partner') || partnerAtt.pref || undefined
  const partnerSourceTag = params.get('src') || partnerAtt.src || undefined
  const session = useAuthSessionGate()

  useEffect(() => {
    if (session === 'authenticated') {
      goAfterLogin(next, navigate)
    }
  }, [session, navigate, next])

  const onSuccess = useCallback(() => {
    goAfterLogin(next, navigate)
  }, [navigate, next])

  if (session === 'checking' || session === 'authenticated') {
    return <AuthCheckingScreen />
  }

  return (
    <div className="auth-page">
      <div className="auth-page-inner">
        <AuthPanel
          onSuccess={onSuccess}
          referralCode={referralCode}
          partnerSlug={partnerSlug}
          partnerSourceTag={partnerSourceTag}
        />
        <p className="auth-page-back">
          <a href="/">{t('backToSite', { defaultValue: '← На главную' })}</a>
        </p>
      </div>
    </div>
  )
}
