import { useEffect, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AuthPanel } from '../AuthPanel'
import { AppLanguageSwitcher } from '../i18n/AppLanguageSwitcher'
import { getToken } from '../api'
import '../App.css'
import { MmContainer } from './components/MmUi'
import { useMarketingPath } from './i18n/useMarketingPath'

export function LoginPage() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
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
        <Link to={path('/')} className="mm-link-arrow" style={{ marginBottom: 'var(--s-6)', display: 'inline-flex' }}>
          {t('loginPage.backHome')}
        </Link>
        <header className="mm-page-head">
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--s-4)' }}>
            <AppLanguageSwitcher />
          </div>
          <h1>{t('loginPage.title')}</h1>
          <p className="mm-muted">{t('loginPage.intro')}</p>
        </header>
        <div className="mm-login-wrap">
          {referralCode ? (
            <p className="mm-muted" style={{ marginBottom: 'var(--s-4)', fontSize: '0.8125rem' }}>
              {t('loginPage.referralNotice', { code: referralCode })}
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
          {t('loginPage.legalPrefix')}{' '}
          <Link to={path('/terms')}>{t('loginPage.legalTerms')}</Link> {t('loginPage.legalAnd')}{' '}
          <Link to={path('/privacy')}>{t('loginPage.legalPrivacy')}</Link>.
        </p>
      </MmContainer>
    </div>
  )
}
