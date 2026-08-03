import { useCallback, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import {
  localeFromPathname,
  marketingPath,
  type MarketingLocale,
} from './marketingLocale'

export function useMarketingPath() {
  const location = useLocation()
  const { i18n } = useTranslation('marketing')
  const locale: MarketingLocale = localeFromPathname(location.pathname || i18n.language || '/')

  const prefix = locale === 'en' ? '/en' : ''

  const path = useCallback((route: string) => marketingPath(route, locale), [locale])

  return useMemo(() => ({ locale, prefix, path }), [locale, prefix, path])
}
