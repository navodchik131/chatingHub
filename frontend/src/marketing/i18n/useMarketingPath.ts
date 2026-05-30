import { useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import {
  isMarketingLocale,
  localeFromPathname,
  marketingPath,
  type MarketingLocale,
} from './marketingLocale'

export function useMarketingPath() {
  const { i18n } = useTranslation('marketing')
  const locale: MarketingLocale = isMarketingLocale(i18n.language)
    ? i18n.language
    : localeFromPathname(typeof window !== 'undefined' ? window.location.pathname : '/')

  const prefix = locale === 'en' ? '/en' : ''

  const path = useCallback((route: string) => marketingPath(route, locale), [locale])

  return useMemo(() => ({ locale, prefix, path }), [locale, prefix, path])
}
