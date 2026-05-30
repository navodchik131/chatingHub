import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import {
  localeFromPathname,
  marketingPath,
  persistMarketingLocale,
  stripMarketingLocalePrefix,
  type MarketingLocale,
} from './marketingLocale'

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation('marketing')
  const location = useLocation()
  const navigate = useNavigate()
  const current = localeFromPathname(location.pathname)

  const setLocale = (next: MarketingLocale) => {
    if (next === current) return
    persistMarketingLocale(next)
    void i18n.changeLanguage(next)
    const base = stripMarketingLocalePrefix(location.pathname)
    navigate(
      {
        pathname: marketingPath(base, next),
        search: location.search,
        hash: location.hash,
      },
      { replace: false },
    )
  }

  return (
    <div className="mm-lang-switch" role="group" aria-label={t('layout.langSwitchAria')}>
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
