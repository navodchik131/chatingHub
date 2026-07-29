import type { ConversationOut } from '@/src/api/types';

export type ConversationSettingsPatch = {
  outbound_lang?: string | null;
  auto_translate_disabled?: boolean;
  companion_mode_override?: 'off' | 'draft' | 'semi_auto' | 'auto';
};

const LANG_MAP: Record<string, string> = {
  es: 'Español',
  en: 'English',
  de: 'Deutsch',
  ru: 'Русский',
  fr: 'Français',
  it: 'Italiano',
  pt: 'Português',
  nl: 'Nederlands',
};

const OUTBOUND_LANG_CODES = ['ru', 'en', 'es', 'de', 'fr', 'it', 'pt', 'nl'] as const;

export function normalizeLangCode(raw?: string | null) {
  return String(raw || '').trim().toLowerCase().replace('*', '');
}

export function replyLangDisplay(
  conv: Pick<ConversationOut, 'outbound_lang' | 'user_lang'> | null | undefined,
  lang: 'ru' | 'en' = 'ru',
) {
  const forced = normalizeLangCode(conv?.outbound_lang);
  if (forced) return LANG_MAP[forced] || forced.toUpperCase();
  const detected = normalizeLangCode(conv?.user_lang);
  if (detected) return LANG_MAP[detected] || detected.toUpperCase();
  return lang === 'ru' ? 'Авто' : 'Auto';
}

export function outboundLangOptions(lang: 'ru' | 'en', detectedCode?: string | null) {
  const autoLabel = `${lang === 'ru' ? 'Авто' : 'Auto'} · ${replyLangDisplay({ user_lang: detectedCode ?? undefined }, lang)}`;
  return [
    { value: 'auto', label: autoLabel },
    ...OUTBOUND_LANG_CODES.map((code) => ({
      value: code,
      label: LANG_MAP[code] || code.toUpperCase(),
    })),
  ];
}

export function companionModeShort(mode?: string | null, lang: 'ru' | 'en' = 'ru') {
  const m = String(mode || 'off').toLowerCase();
  if (m === 'off') return lang === 'ru' ? 'Откл' : 'Off';
  if (m === 'semi_auto') return lang === 'ru' ? 'Полуавто' : 'Semi-auto';
  if (m === 'auto') return lang === 'ru' ? 'Авто' : 'Auto';
  if (m === 'draft') return lang === 'ru' ? 'Черновик' : 'Draft';
  return m.toUpperCase();
}

export function dialogSettingsSummary(conv: ConversationOut | null | undefined, lang: 'ru' | 'en' = 'ru') {
  const mode = conv?.companion_mode_override ?? conv?.effective_companion_mode ?? 'off';
  const translateOn = !conv?.auto_translate_disabled;
  return companionModeShort(mode, lang) + (translateOn ? '' : (lang === 'ru' ? ' · без перевода' : ' · no translate'));
}
