const STORAGE_KEY = 'mm_ui_locale';
const USER_SET_KEY = 'mm_ui_locale_user_set';

export function readStoredLocale() {
  if (typeof localStorage === 'undefined') return 'ru';
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === 'en') return 'en';
  const legacy = localStorage.getItem('i18nextLng');
  if (legacy?.startsWith('en')) return 'en';
  return 'ru';
}

export function writeStoredLocale(lang) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, lang === 'en' ? 'en' : 'ru');
}

export function markLocaleUserSet() {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem(USER_SET_KEY, '1');
}

export function clearLocaleUserSet() {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(USER_SET_KEY);
}

export function isLocaleUserSet() {
  if (typeof localStorage === 'undefined') return false;
  return localStorage.getItem(USER_SET_KEY) === '1';
}

export function localeFromMe(me) {
  const raw = me?.ui_locale;
  if (!raw) return null;
  return String(raw).toLowerCase().startsWith('en') ? 'en' : 'ru';
}