import { useTranslation } from 'react-i18next'
import '../styles/auth-ui.css'

type Variant = 'auth' | 'cabinet'

export function AuthCheckingScreen({ variant = 'auth' }: { variant?: Variant }) {
  const { t } = useTranslation('auth')

  if (variant === 'cabinet') {
    return (
      <div className="cabinet-auth-check">
        <p className="auth-checking">{t('loading')}</p>
      </div>
    )
  }

  return (
    <div className="auth-page">
      <div className="auth-page-inner">
        <p className="auth-checking">{t('loading')}</p>
      </div>
    </div>
  )
}
