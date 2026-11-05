import { patchUserPreferences } from '@/src/api/actions';
import { getToken } from '@/src/api/token';
import type { AppLocale } from '@/src/i18n/prefs';
import { clearLocaleUserSet, markLocaleUserSet } from '@/src/i18n/prefs';

/** Сохраняет выбранный язык в профиле на сервере. */
export async function persistLocaleToAccount(locale: AppLocale) {
  const token = await getToken();
  if (!token) return;
  await markLocaleUserSet();
  try {
    await patchUserPreferences({ ui_locale: locale });
    await clearLocaleUserSet();
  } catch {
    /* local preference still saved */
  }
}
