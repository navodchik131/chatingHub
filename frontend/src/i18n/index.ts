import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import enMarketing from './locales/en/marketing.json'
import ruMarketing from './locales/ru/marketing.json'
import {
  DEFAULT_MARKETING_LOCALE,
  MARKETING_LOCALE_STORAGE_KEY,
  type MarketingLocale,
} from '../marketing/i18n/marketingLocale'

export const MARKETING_NS = 'marketing'

const detector = new LanguageDetector()
detector.addDetector({
  name: 'mmPath',
  lookup() {
    if (typeof window === 'undefined') return undefined
    const p = window.location.pathname
    if (p === '/en' || p.startsWith('/en/')) return 'en'
    return 'ru'
  },
})

void i18n
  .use(detector)
  .use(initReactI18next)
  .init({
    resources: {
      ru: { [MARKETING_NS]: ruMarketing },
      en: { [MARKETING_NS]: enMarketing },
    },
    fallbackLng: DEFAULT_MARKETING_LOCALE,
    supportedLngs: ['ru', 'en'],
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    ns: [MARKETING_NS],
    defaultNS: MARKETING_NS,
    interpolation: { escapeValue: false },
    detection: {
      order: ['mmPath', 'localStorage', 'navigator'],
      lookupLocalStorage: MARKETING_LOCALE_STORAGE_KEY,
      caches: ['localStorage'],
      convertDetectedLanguage: (lng: string) => {
        const base = lng.split('-')[0]?.toLowerCase()
        return base === 'en' ? 'en' : 'ru'
      },
    },
  })

export function syncI18nMarketingLocale(locale: MarketingLocale): void {
  if (i18n.language !== locale) {
    void i18n.changeLanguage(locale)
  }
}

export default i18n
