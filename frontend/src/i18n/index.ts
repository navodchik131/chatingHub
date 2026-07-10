import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import enAdmin from './locales/en/admin.json'
import enAuth from './locales/en/auth.json'
import enChat from './locales/en/chat.json'
import enCommon from './locales/en/common.json'
import enMarketing from './locales/en/marketing.json'
import enStudio from './locales/en/studio.json'
import enWorkflow from './locales/en/workflow.json'
import enWorkspace from './locales/en/workspace.json'
import ruAdmin from './locales/ru/admin.json'
import ruAuth from './locales/ru/auth.json'
import ruChat from './locales/ru/chat.json'
import ruCommon from './locales/ru/common.json'
import ruMarketing from './locales/ru/marketing.json'
import ruStudio from './locales/ru/studio.json'
import ruWorkflow from './locales/ru/workflow.json'
import ruWorkspace from './locales/ru/workspace.json'
import {
  DEFAULT_MARKETING_LOCALE,
  isMarketingPathname,
  MARKETING_LOCALE_STORAGE_KEY,
  type MarketingLocale,
} from '../marketing/i18n/marketingLocale'

export const MARKETING_NS = 'marketing'
export const AUTH_NS = 'auth'
export const WORKSPACE_NS = 'workspace'
export const WORKFLOW_NS = 'workflow'
export const STUDIO_NS = 'studio'
export const CHAT_NS = 'chat'
export const COMMON_NS = 'common'
export const ADMIN_NS = 'admin'

const APP_NAMESPACES = [AUTH_NS, WORKSPACE_NS, WORKFLOW_NS, STUDIO_NS, CHAT_NS, COMMON_NS, ADMIN_NS] as const

const detector = new LanguageDetector()
detector.addDetector({
  name: 'mmPath',
  lookup() {
    if (typeof window === 'undefined') return undefined
    const p = window.location.pathname
    // Только маркетинг: в /workspace и ЛК язык берётся из localStorage.
    if (!isMarketingPathname(p)) return undefined
    if (p === '/en' || p.startsWith('/en/')) return 'en'
    return 'ru'
  },
})

void i18n
  .use(detector)
  .use(initReactI18next)
  .init({
    resources: {
      ru: {
        [MARKETING_NS]: ruMarketing,
        [AUTH_NS]: ruAuth,
        [WORKSPACE_NS]: ruWorkspace,
        [WORKFLOW_NS]: ruWorkflow,
        [STUDIO_NS]: ruStudio,
        [CHAT_NS]: ruChat,
        [COMMON_NS]: ruCommon,
        [ADMIN_NS]: ruAdmin,
      },
      en: {
        [MARKETING_NS]: enMarketing,
        [AUTH_NS]: enAuth,
        [WORKSPACE_NS]: enWorkspace,
        [WORKFLOW_NS]: enWorkflow,
        [STUDIO_NS]: enStudio,
        [CHAT_NS]: enChat,
        [COMMON_NS]: enCommon,
        [ADMIN_NS]: enAdmin,
      },
    },
    fallbackLng: DEFAULT_MARKETING_LOCALE,
    supportedLngs: ['ru', 'en'],
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    ns: [MARKETING_NS, ...APP_NAMESPACES],
    defaultNS: WORKSPACE_NS,
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'mmPath', 'navigator'],
      lookupLocalStorage: MARKETING_LOCALE_STORAGE_KEY,
      caches: ['localStorage'],
      convertDetectedLanguage: (lng: string) => {
        const base = lng.split('-')[0]?.toLowerCase()
        return base === 'en' ? 'en' : 'ru'
      },
    },
  })

if (typeof document !== 'undefined') {
  document.documentElement.lang = i18n.language?.startsWith('en') ? 'en' : 'ru'
  i18n.on('languageChanged', (lng) => {
    document.documentElement.lang = lng.startsWith('en') ? 'en' : 'ru'
  })
}

export function syncI18nMarketingLocale(locale: MarketingLocale): void {
  if (i18n.language !== locale) {
    void i18n.changeLanguage(locale)
  }
}

export function appLocale(): 'ru' | 'en' {
  return i18n.language?.startsWith('en') ? 'en' : 'ru'
}

export function formatAppNumber(value: number): string {
  return value.toLocaleString(appLocale() === 'en' ? 'en-US' : 'ru-RU')
}

export default i18n
