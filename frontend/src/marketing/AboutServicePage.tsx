import { useTranslation } from 'react-i18next'
import './about-service.css'

export function AboutServicePage() {
  const { t } = useTranslation('marketing')

  return (
    <div className="mm-about-service">
      <iframe
        src="/about-service.html"
        title={t('aboutService.iframeTitle')}
        className="mm-about-service__frame"
      />
    </div>
  )
}
