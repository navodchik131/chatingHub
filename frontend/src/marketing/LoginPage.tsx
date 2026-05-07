import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthPanel } from '../AuthPanel'
import { getToken } from '../api'

export function LoginPage() {
  const navigate = useNavigate()

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
        <AuthPanel onSuccess={() => navigate('/workspace', { replace: true })} />
      </div>
    </>
  )
}
