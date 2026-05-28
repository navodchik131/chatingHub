import { useEffect, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthPanel } from '../AuthPanel'
import { getToken } from '../api'

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const referralCode = useMemo(() => {
    const ref = (searchParams.get('ref') || '').trim().toUpperCase()
    return ref || null
  }, [searchParams])

  useEffect(() => {
    if (getToken()) navigate('/workspace', { replace: true })
  }, [navigate])

  return (
    <>
      <div style={{ marginBottom: '1.25rem' }}>
        <Link to="/" className="mkt-link-arrow">
          ← На главную
        </Link>
      </div>
      <header className="mkt-section-head" style={{ marginBottom: '1rem' }}>
        <h1 className="mkt-h1" style={{ fontSize: 'clamp(1.35rem, 3vw, 1.75rem)' }}>
          Доступ к кабинету
        </h1>
        <p className="muted" style={{ margin: 0 }}>
          Войдите или создайте пространство — интеграции Telegram/Fanvue и студию настроите после входа.
        </p>
      </header>
      <div className="mkt-login-wrap">
        {referralCode ? (
          <p className="muted small" style={{ marginBottom: '0.75rem' }}>
            Регистрация по приглашению: код <strong>{referralCode}</strong>
          </p>
        ) : null}
        <AuthPanel
          referralCode={referralCode}
          onSuccess={() => navigate('/workspace', { replace: true })}
        />
      </div>
      <p
        className="muted small"
        style={{
          margin: '0.5rem auto 0',
          maxWidth: 480,
          textAlign: 'center',
          fontSize: '0.8125rem',
          lineHeight: 1.55,
        }}
      >
        Продолжая, вы соглашаетесь с{' '}
        <Link to="/terms" className="mkt-link-arrow" style={{ display: 'inline' }}>
          пользовательским соглашением
        </Link>{' '}
        и{' '}
        <Link to="/privacy" className="mkt-link-arrow" style={{ display: 'inline' }}>
          политикой конфиденциальности
        </Link>
        .
      </p>
    </>
  )
}
