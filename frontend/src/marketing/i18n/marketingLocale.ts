/** Локали публичного маркетингового сайта (не ЛК /workspace). */

export const MARKETING_LOCALES = ['ru', 'en'] as const
export type MarketingLocale = (typeof MARKETING_LOCALES)[number]

export const DEFAULT_MARKETING_LOCALE: MarketingLocale = 'ru'
export const MARKETING_LOCALE_STORAGE_KEY = 'mm_locale'
export const MARKETING_LOCALE_DETECTED_KEY = 'mm_locale_detected'

/** Часовые пояса РФ и распространённые для RU-аудитории. */
const RU_TIMEZONES = new Set([
  'Europe/Moscow',
  'Europe/Kaliningrad',
  'Europe/Samara',
  'Europe/Volgograd',
  'Europe/Saratov',
  'Europe/Kirov',
  'Europe/Astrakhan',
  'Europe/Ulyanovsk',
  'Asia/Yekaterinburg',
  'Asia/Omsk',
  'Asia/Novosibirsk',
  'Asia/Barnaul',
  'Asia/Tomsk',
  'Asia/Novokuznetsk',
  'Asia/Krasnoyarsk',
  'Asia/Irkutsk',
  'Asia/Chita',
  'Asia/Yakutsk',
  'Asia/Khandyga',
  'Asia/Vladivostok',
  'Asia/Ust-Nera',
  'Asia/Magadan',
  'Asia/Sakhalin',
  'Asia/Srednekolymsk',
  'Asia/Kamchatka',
  'Asia/Anadyr',
])

export function isMarketingLocale(value: string | undefined | null): value is MarketingLocale {
  return value === 'ru' || value === 'en'
}

/** Публичные маркетинговые маршруты (с опциональным префиксом /en). */
const MARKETING_PATH_RE = /^\/(?:pricing|faq|privacy|terms|login)?$/

export function isMarketingPathname(pathname: string): boolean {
  return MARKETING_PATH_RE.test(stripMarketingLocalePrefix(pathname))
}

export function readStoredMarketingLocale(): MarketingLocale | null {
  if (typeof window === 'undefined') return null
  try {
    const stored = localStorage.getItem(MARKETING_LOCALE_STORAGE_KEY)
    if (isMarketingLocale(stored)) return stored
  } catch {
    /* ignore */
  }
  return null
}

export function localeFromPathname(pathname: string): MarketingLocale {
  return pathname === '/en' || pathname.startsWith('/en/') ? 'en' : 'ru'
}

/** Путь маркетинга с учётом локали: `/login` → `/en/login` для EN. */
export function marketingPath(route: string, locale: MarketingLocale): string {
  const raw = route.startsWith('/') ? route : `/${route}`
  const hashIdx = raw.indexOf('#')
  const pathPart = hashIdx >= 0 ? raw.slice(0, hashIdx) : raw
  const hash = hashIdx >= 0 ? raw.slice(hashIdx) : ''

  if (locale === 'en') {
    if (pathPart === '/' || pathPart === '') return `/en${hash}`
    return `/en${pathPart}${hash}`
  }
  return `${pathPart}${hash}` || '/'
}

export function stripMarketingLocalePrefix(pathname: string): string {
  if (pathname === '/en') return '/'
  if (pathname.startsWith('/en/')) return pathname.slice(3) || '/'
  return pathname
}

/** Первый визит: ru для RU/TZ/языка браузера, иначе en. */
export function detectMarketingLocale(): MarketingLocale {
  if (typeof window === 'undefined') return DEFAULT_MARKETING_LOCALE

  const stored = readStoredMarketingLocale()
  if (stored) return stored

  const nav = (navigator.language || navigator.languages?.[0] || '').toLowerCase()
  if (nav.startsWith('ru') || nav.startsWith('uk') || nav.startsWith('be')) return 'ru'

  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (tz && RU_TIMEZONES.has(tz)) return 'ru'
  } catch {
    /* ignore */
  }

  return 'en'
}

export function persistMarketingLocale(locale: MarketingLocale): void {
  try {
    localStorage.setItem(MARKETING_LOCALE_STORAGE_KEY, locale)
  } catch {
    /* ignore */
  }
}
