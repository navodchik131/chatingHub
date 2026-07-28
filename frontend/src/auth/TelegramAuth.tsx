import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch, setToken } from '../api'
import { formatHttpApiError } from '../apiErrors'
import { signInWithTelegramBot } from './telegramBotLogin'
import {
  mountTelegramLoginWidget,
  postTelegramAuth,
  type TelegramLoginUser,
} from './telegramLogin'

type Props = {
  botUsername: string
  mode: 'login' | 'link'
  referralCode?: string | null
  onSuccess: () => void | Promise<void>
  onError?: (message: string) => void
}

export function TelegramLoginButton({ botUsername, mode, referralCode, onSuccess, onError }: Props) {
  const { t } = useTranslation('auth')
  const hostRef = useRef<HTMLDivElement>(null)
  const onSuccessRef = useRef(onSuccess)
  const onErrorRef = useRef(onError)
  const [busy, setBusy] = useState(false)

  onSuccessRef.current = onSuccess
  onErrorRef.current = onError

  useEffect(() => {
    if (mode !== 'link') return
    const el = hostRef.current
    if (!el || !botUsername.trim()) return

    const cleanup = mountTelegramLoginWidget(el, botUsername, (user: TelegramLoginUser) => {
      void (async () => {
        setBusy(true)
        try {
          const r = await postTelegramAuth('/api/auth/telegram/link', user, null)
          if (!r.ok) {
            const j = await r.json().catch(() => ({}))
            onErrorRef.current?.(formatHttpApiError(r, j))
            return
          }
          await onSuccessRef.current()
        } finally {
          setBusy(false)
        }
      })()
    })
    return cleanup
  }, [botUsername, mode, referralCode])

  const runBotLogin = async () => {
    setBusy(true)
    try {
      const token = await signInWithTelegramBot(referralCode)
      setToken(token)
      await onSuccessRef.current()
    } catch (e) {
      onErrorRef.current?.(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  if (mode === 'link') {
    return (
      <div className="telegram-login-wrap">
        <div ref={hostRef} className="telegram-login-host" aria-busy={busy} />
        {busy ? <p className="auth-hint">{t('telegramChecking')}</p> : null}
      </div>
    )
  }

  return (
    <div className="telegram-login-wrap">
      <button
        type="button"
        className="telegram-bot-btn"
        disabled={busy}
        onClick={() => void runBotLogin()}
      >
        {busy ? t('telegramWaiting') : t('telegramBotLogin')}
      </button>
      {busy ? <p className="auth-hint auth-hint--center">{t('telegramBotHint')}</p> : null}
    </div>
  )
}

type EmailCompleteProps = {
  onSuccess: () => void | Promise<void>
  onError?: (message: string) => void
}

export function OwnerEmailCompleteForm({ onSuccess, onError }: EmailCompleteProps) {
  const { t } = useTranslation('auth')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      const r = await apiFetch('/api/auth/email/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        onError?.(formatHttpApiError(r, j))
        return
      }
      const data = (await r.json()) as { access_token: string }
      setToken(data.access_token)
      await onSuccess()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-card-inner email-complete-card">
      <h3 className="auth-title">{t('emailCompleteTitle')}</h3>
      <p className="auth-sub">{t('emailCompleteSubtitle')}</p>
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
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={t('passwordPlaceholderMin')}
        />
      </label>
      <button
        type="button"
        className="send-btn auth-submit"
        disabled={busy || !email.trim() || password.length < 8}
        onClick={() => void submit()}
      >
        {t('saveEmail')}
      </button>
    </div>
  )
}
