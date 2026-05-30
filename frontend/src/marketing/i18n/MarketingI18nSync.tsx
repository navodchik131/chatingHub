import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { syncI18nMarketingLocale } from '../../i18n'
import {
  detectMarketingLocale,
  localeFromPathname,
  MARKETING_LOCALE_DETECTED_KEY,
  marketingPath,
  persistMarketingLocale,
  stripMarketingLocalePrefix,
  type MarketingLocale,
} from './marketingLocale'

const MARKETING_ROUTE_RE =
  /^\/(?:en\/)?(?:pricing|faq|privacy|terms|login)?$/

function isMarketingSurface(pathname: string): boolean {
  return MARKETING_ROUTE_RE.test(pathname)
}

/** Синхрон URL ↔ i18n, hreflang, авто-локаль при первом визите. */
export function MarketingI18nSync() {
  const { i18n } = useTranslation('marketing')
  const location = useLocation()
  const navigate = useNavigate()

  const urlLocale = localeFromPathname(location.pathname)

  useEffect(() => {
    syncI18nMarketingLocale(urlLocale)
    persistMarketingLocale(urlLocale)
    document.documentElement.lang = urlLocale
  }, [urlLocale])

  useEffect(() => {
    if (!isMarketingSurface(location.pathname)) return

    let detected: MarketingLocale | null = null
    try {
      if (!sessionStorage.getItem(MARKETING_LOCALE_DETECTED_KEY)) {
        sessionStorage.setItem(MARKETING_LOCALE_DETECTED_KEY, '1')
        detected = detectMarketingLocale()
      }
    } catch {
      detected = detectMarketingLocale()
    }

    if (urlLocale === 'en') {
      persistMarketingLocale('en')
      return
    }
    if (detected === 'en') {
      const base = stripMarketingLocalePrefix(location.pathname)
      navigate(
        {
          pathname: marketingPath(base, 'en'),
          search: location.search,
          hash: location.hash,
        },
        { replace: true },
      )
    }
  }, []) // только первый mount layout

  useEffect(() => {
    const origin = window.location.origin
    const ruUrl = `${origin}${stripMarketingLocalePrefix(location.pathname)}${location.search}`
    const enPath = marketingPath(stripMarketingLocalePrefix(location.pathname), 'en')
    const enUrl = `${origin}${enPath}${location.search}`

    const upsert = (hreflang: string, href: string) => {
      const sel = `link[rel="alternate"][hreflang="${hreflang}"]`
      let el = document.querySelector(sel) as HTMLLinkElement | null
      if (!el) {
        el = document.createElement('link')
        el.rel = 'alternate'
        el.hreflang = hreflang
        document.head.appendChild(el)
      }
      el.href = href
    }

    upsert('ru', ruUrl)
    upsert('en', enUrl)
    upsert('x-default', ruUrl)

    let canonical = document.querySelector('link[rel="canonical"]') as HTMLLinkElement | null
    if (!canonical) {
      canonical = document.createElement('link')
      canonical.rel = 'canonical'
      document.head.appendChild(canonical)
    }
    canonical.href = urlLocale === 'en' ? enUrl : ruUrl

    return () => {
      /* оставляем alternate на всех маркетинг-страницах */
    }
  }, [location.pathname, location.search, urlLocale])

  useEffect(() => {
    void i18n.changeLanguage(urlLocale)
  }, [urlLocale, i18n])

  return null
}
