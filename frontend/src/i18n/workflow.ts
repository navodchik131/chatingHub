import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import enCommon from './locales/en/common.json'
import enWorkflow from './locales/en/workflow.json'
import enWorkspace from './locales/en/workspace.json'
import ruCommon from './locales/ru/common.json'
import ruWorkflow from './locales/ru/workflow.json'
import ruWorkspace from './locales/ru/workspace.json'
import { MARKETING_LOCALE_STORAGE_KEY } from '../marketing/i18n/marketingLocale'

export const WORKFLOW_NS = 'workflow'
export const WORKSPACE_NS = 'workspace'
export const COMMON_NS = 'common'

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      ru: {
        [WORKFLOW_NS]: ruWorkflow,
        [WORKSPACE_NS]: ruWorkspace,
        [COMMON_NS]: ruCommon,
      },
      en: {
        [WORKFLOW_NS]: enWorkflow,
        [WORKSPACE_NS]: enWorkspace,
        [COMMON_NS]: enCommon,
      },
    },
    ns: [WORKFLOW_NS, WORKSPACE_NS, COMMON_NS],
    defaultNS: WORKFLOW_NS,
    fallbackLng: 'ru',
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: MARKETING_LOCALE_STORAGE_KEY,
    },
    interpolation: { escapeValue: false },
  })

export default i18n
