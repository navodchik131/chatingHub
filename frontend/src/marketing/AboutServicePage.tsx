import { useTranslation } from 'react-i18next'
import { useMarketingPath } from './i18n/useMarketingPath'
import './about-service.css'

export function AboutServicePage() {
  const { t } = useTranslation('marketing')
  const { locale } = useMarketingPath()
  const src = locale === 'en' ? '/about-service.en.html' : '/about-service.html'

  return (
    <div className="mm-about-service">
      <iframe
        src={src}
        title={t('aboutService.iframeTitle')}
        className="mm-about-service__frame"
      />
    </div>
  )
}
