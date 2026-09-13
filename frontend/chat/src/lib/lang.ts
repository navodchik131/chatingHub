/** Языки перевода диалогов — как в кабинете /workspace/dialogs. */

export const LANG_MAP: Record<string, string> = {
  es: 'Español',
  en: 'English',
  de: 'Deutsch',
  ru: 'Русский',
  fr: 'Français',
  it: 'Italiano',
  pt: 'Português',
  nl: 'Nederlands',
}

export const OUTBOUND_LANG_CODES = ['ru', 'en', 'es', 'de', 'fr', 'it', 'pt', 'nl'] as const

export function normalizeLangCode(raw: unknown): string {
  return String(raw || '').trim().toLowerCase().replace('*', '')
}

/** Текущий язык исходящих: принудительный или авто по user_lang. */
export function replyLangDisplay(conv: {
  outbound_lang?: string | null
  user_lang?: string | null
}): string {
  const forced = normalizeLangCode(conv?.outbound_lang)
  if (forced) return LANG_MAP[forced] || forced.toUpperCase()
  const detected = normalizeLangCode(conv?.user_lang)
  if (detected) return LANG_MAP[detected] || detected.toUpperCase()
  return 'Авто'
}

export function outboundLangOptions(detectedCode?: string | null): Array<{ value: string; label: string }> {
  const autoLabel = `Авто · ${replyLangDisplay({ user_lang: detectedCode })}`
  return [
    { value: 'auto', label: autoLabel },
    ...OUTBOUND_LANG_CODES.map((code) => ({
      value: code,
      label: LANG_MAP[code] || code.toUpperCase(),
    })),
  ]
}

/** Короткая метка для строки перевода под пузырём. */
export function translationLineLabel(outbound: boolean, conv: {
  outbound_lang?: string | null
  user_lang?: string | null
  tr?: { lang?: string }
}): string {
  if (outbound) {
    const code = normalizeLangCode(conv.outbound_lang) || normalizeLangCode(conv.user_lang) || normalizeLangCode(conv.tr?.lang) || 'en'
    return code.toUpperCase()
  }
  return 'RU'
}
