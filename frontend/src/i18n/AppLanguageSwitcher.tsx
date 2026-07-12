import { useTranslation } from 'react-i18next'
import { persistMarketingLocale } from '../marketing/i18n/marketingLocale'
import './lang-switch.css'

export function AppLanguageSwitcher({ className }: { className?: string }) {
  const { i18n, t } = useTranslation('workspace')
  const current = i18n.language?.startsWith('en') ? 'en' : 'ru'

  const setLocale = (next: 'ru' | 'en') => {
    if (next === current) return
    persistMarketingLocale(next)
    void i18n.changeLanguage(next)
    document.documentElement.lang = next
  }

  return (
    <div
      className={className ?? 'mm-lang-switch mm-lang-switch--compact'}
      role="group"
      aria-label={t('langSwitchAria')}
    >
      <button
        type="button"
        className={`mm-lang-switch__btn${current === 'ru' ? ' is-active' : ''}`}
        lang="ru"
        aria-pressed={current === 'ru'}
        onClick={() => setLocale('ru')}
      >
        RU
      </button>
      <button
        type="button"
        className={`mm-lang-switch__btn${current === 'en' ? ' is-active' : ''}`}
        lang="en"
        aria-pressed={current === 'en'}
        onClick={() => setLocale('en')}
      >
        EN
      </button>
    </div>
  )
}
