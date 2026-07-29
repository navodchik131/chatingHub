import { useEffect, useRef } from 'react';
import { patchUserPreferences } from '@/src/api/actions';
import { getToken } from '@/src/api/token';
import { useAppData } from '@/src/context/AppDataProvider';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import type { AppLocale } from '@/src/i18n/prefs';
import {
  clearLocaleUserSet,
  isLocaleUserSet,
  markLocaleUserSet,
  saveLocale,
} from '@/src/i18n/prefs';

function accountLocale(me?: { ui_locale?: string | null } | null): AppLocale | null {
  const raw = me?.ui_locale;
  if (!raw) return null;
  return String(raw).toLowerCase().startsWith('en') ? 'en' : 'ru';
}

/** Подтягивает язык из профиля после входа; при расхождении пушит локальный выбор на сервер. */
export function LocaleAccountSync() {
  const { me, authenticated } = useAppData();
  const { locale, setLocaleStateOnly } = useAppSettings();
  const appliedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!authenticated) {
      appliedRef.current = null;
      return;
    }
    const fromAccount = accountLocale(me);
    if (!fromAccount) return;
    const key = `${me?.id ?? 0}:${fromAccount}:${locale}`;
    if (appliedRef.current === key) return;

    void (async () => {
      const userSet = await isLocaleUserSet();
      if (userSet && locale !== fromAccount) {
        appliedRef.current = key;
        await persistLocaleToAccount(locale);
        await clearLocaleUserSet();
        return;
      }
      appliedRef.current = key;
      if (fromAccount !== locale) {
        setLocaleStateOnly(fromAccount);
        await saveLocale(fromAccount);
      }
      if (fromAccount === locale) await clearLocaleUserSet();
    })();
  }, [authenticated, me?.id, me?.ui_locale, locale, setLocaleStateOnly]);

  return null;
}

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
