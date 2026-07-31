import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch, setToken } from '../api'
import { formatHttpApiError } from '../apiErrors'
import {
  hasPendingTelegramAuth,
  resumePendingTelegramBotAuth,
  signInWithTelegramBot,
  clearPendingTelegramAuth,
} from './telegramBotLogin'
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
  const pollingRef = useRef(false)
  const [busy, setBusy] = useState(() => mode === 'login' && hasPendingTelegramAuth())

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

  useEffect(() => {
    if (mode !== 'login') return

    const finish = async (token: string) => {
      setToken(token)
      await onSuccessRef.current()
    }

    const tryResume = async () => {
      if (!hasPendingTelegramAuth() || pollingRef.current) return
      pollingRef.current = true
      setBusy(true)
      try {
        const token = await resumePendingTelegramBotAuth()
        if (token) {
          await finish(token)
          return
        }
        if (hasPendingTelegramAuth()) {
          onErrorRef.current?.(t('telegramBotHint'))
        }
      } catch (e) {
        onErrorRef.current?.(e instanceof Error ? e.message : String(e))
      } finally {
        pollingRef.current = false
        setBusy(false)
      }
    }

    void tryResume()

    const onVis = () => {
      if (document.visibilityState === 'visible') void tryResume()
    }
    const onFocus = () => {
      void tryResume()
    }
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted || hasPendingTelegramAuth()) void tryResume()
    }

    document.addEventListener('visibilitychange', onVis)
    window.addEventListener('focus', onFocus)
    window.addEventListener('pageshow', onPageShow)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('pageshow', onPageShow)
    }
  }, [mode, t])

  const runBotLogin = async () => {
    if (pollingRef.current) return
    pollingRef.current = true
    setBusy(true)
    const preopenedPopup = typeof window !== 'undefined'
      ? window.open('about:blank', '_blank', 'noopener,noreferrer')
      : null
    try {
      const token = await signInWithTelegramBot(referralCode, { preopenedPopup })
      setToken(token)
      await onSuccessRef.current()
    } catch (e) {
      if (!hasPendingTelegramAuth()) {
        onErrorRef.current?.(e instanceof Error ? e.message : String(e))
      }
    } finally {
      pollingRef.current = false
      setBusy(false)
    }
  }

  const cancelPending = () => {
    clearPendingTelegramAuth()
    pollingRef.current = false
    setBusy(false)
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
      {busy ? (
        <>
          <p className="auth-hint auth-hint--center">{t('telegramBotHint')}</p>
          <button type="button" className="auth-link-btn" onClick={cancelPending}>
            {t('telegramCancel', { defaultValue: 'Cancel' })}
          </button>
        </>
      ) : null}
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
