import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch, setToken } from './api'
import { formatHttpApiError } from './apiErrors'
import { markFirstGenWizardPending } from './analytics/funnel'
import { TelegramLoginButton } from './auth/TelegramAuth'

export function AuthPanel({
  onSuccess,
  referralCode,
}: {
  onSuccess: (fromRegister?: boolean) => void | Promise<void>
  referralCode?: string | null
}) {
  const { t } = useTranslation('auth')
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [memberLogin, setMemberLogin] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [tgBotUsername, setTgBotUsername] = useState<string | null>(null)

  useEffect(() => {
    void apiFetch('/api/health')
      .then(async (r) => {
        if (!r.ok) return
        const h = (await r.json()) as {
          telegram_login_configured?: boolean
          telegram_login_bot_username?: string | null
        }
        if (h.telegram_login_configured && h.telegram_login_bot_username) {
          setTgBotUsername(h.telegram_login_bot_username)
        }
      })
      .catch(() => {})
  }, [])

  const submit = async () => {
    setErr(null)
    setBusy(true)
    try {
      const path = tab === 'login' ? '/api/auth/login' : '/api/auth/register'
      const ml = memberLogin.trim().toLowerCase()
      const body =
        tab === 'login' && ml
          ? { email, password, member_login: ml }
          : tab === 'register' && referralCode
            ? { email, password, referral_code: referralCode }
            : { email, password }
      const r = await apiFetch(path, {
        method: 'POST',
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setErr(formatHttpApiError(r, j))
        return
      }
      const data = (await r.json()) as { access_token: string }
      setToken(data.access_token)
      if (tab === 'register') markFirstGenWizardPending()
      onSuccess(tab === 'register')
    } finally {
      setBusy(false)
    }
  }

  const onTelegramSuccess = async () => {
    setErr(null)
    markFirstGenWizardPending()
    await onSuccess(true)
  }

  return (
    <div className="auth-card">
      <div className="auth-card-inner">
        <h2 className="auth-title">{t('title')}</h2>
        <p className="auth-sub">{t('subtitle')}</p>
        <div className="auth-tabs" role="tablist" aria-label={t('tabsAria')}>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'login'}
            className={tab === 'login' ? 'auth-tab active' : 'auth-tab'}
            onClick={() => {
              setTab('login')
            }}
          >
            {t('login')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'register'}
            className={tab === 'register' ? 'auth-tab active' : 'auth-tab'}
            onClick={() => {
              setTab('register')
              setMemberLogin('')
            }}
          >
            {t('register')}
          </button>
        </div>
        {err ? <div className="banner error">{err}</div> : null}
        {tgBotUsername && tab === 'register' ? (
          <>
            <TelegramLoginButton
              botUsername={tgBotUsername}
              mode="login"
              onSuccess={onTelegramSuccess}
              onError={setErr}
            />
            <p className="auth-hint auth-hint--center">{t('orEmail')}</p>
          </>
        ) : null}
        {tgBotUsername && tab === 'login' && !memberLogin.trim() ? (
          <>
            <TelegramLoginButton
              botUsername={tgBotUsername}
              mode="login"
              onSuccess={() => onSuccess(false)}
              onError={setErr}
            />
            <p className="auth-hint auth-hint--center">{t('orEmail')}</p>
          </>
        ) : null}
        <label className="auth-label">
          <span className="auth-label-text">{t('email')}</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
          />
        </label>
        <label className="auth-label">
          <span className="auth-label-text">{t('password')}</span>
          <input
            type="password"
            autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
        </label>
        {tab === 'login' ? (
          <label className="auth-label">
            <span className="auth-label-text">{t('teamLoginOptional')}</span>
            <input
              type="text"
              autoComplete="username"
              value={memberLogin}
              onChange={(e) => setMemberLogin(e.target.value)}
              placeholder={t('teamLoginPlaceholder')}
            />
          </label>
        ) : null}
        <button
          type="button"
          className="send-btn auth-submit"
          disabled={
            busy ||
            !email.trim() ||
            password.length < 8 ||
            (tab === 'login' && memberLogin.trim().length > 0 && memberLogin.trim().length < 3)
          }
          onClick={() => void submit()}
        >
          {tab === 'login' ? t('submitLogin') : t('submitRegister')}
        </button>
        <p className="auth-hint">{t('passwordHint')}</p>
      </div>
    </div>
  )
}
