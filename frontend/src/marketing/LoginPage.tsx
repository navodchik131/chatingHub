import { useEffect, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthPanel } from '../AuthPanel'
import { getToken } from '../api'
import '../App.css'
import { MmContainer } from './components/MmUi'

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
    <div className="mm-main--page">
      <MmContainer>
        <Link to="/" className="mm-link-arrow" style={{ marginBottom: 'var(--s-6)', display: 'inline-flex' }}>
          ← На главную
        </Link>
        <header className="mm-page-head">
          <h1>Доступ к кабинету</h1>
          <p className="mm-muted">
            Войдите или создайте пространство — интеграции и студию настроите после входа.
          </p>
        </header>
        <div className="mm-login-wrap">
          {referralCode ? (
            <p className="mm-muted" style={{ marginBottom: 'var(--s-4)', fontSize: '0.8125rem' }}>
              Регистрация по приглашению: код <strong>{referralCode}</strong>
            </p>
          ) : null}
          <AuthPanel referralCode={referralCode} onSuccess={() => navigate('/workspace', { replace: true })} />
        </div>
        <p
          className="mm-muted"
          style={{
            margin: 'var(--s-6) auto 0',
            maxWidth: 480,
            textAlign: 'center',
            fontSize: '0.8125rem',
            lineHeight: 1.55,
          }}
        >
          Продолжая, вы соглашаетесь с{' '}
          <Link to="/terms">соглашением</Link> и <Link to="/privacy">политикой конфиденциальности</Link>.
        </p>
      </MmContainer>
    </div>
  )
}
