import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  AppLocale,
  loadAppPrefs,
  saveBiometricLock,
  saveLocale,
  savePushEnabled,
} from '@/src/i18n/prefs';
import { dict, Strings } from '@/src/i18n/strings';

type AppSettingsValue = {
  ready: boolean;
  locale: AppLocale;
  t: Strings;
  setLocale: (locale: AppLocale) => Promise<void>;
  biometricLock: boolean;
  setBiometricLock: (enabled: boolean) => Promise<void>;
  pushEnabled: boolean;
  setPushEnabled: (enabled: boolean) => Promise<void>;
};

const AppSettingsContext = createContext<AppSettingsValue | null>(null);

export function AppSettingsProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [locale, setLocaleState] = useState<AppLocale>('ru');
  const [biometricLock, setBiometricLockState] = useState(false);
  const [pushEnabled, setPushEnabledState] = useState(false);

  useEffect(() => {
    void loadAppPrefs().then((prefs) => {
      setLocaleState(prefs.locale);
      setBiometricLockState(prefs.biometricLock);
      setPushEnabledState(prefs.pushEnabled);
      setReady(true);
    });
  }, []);

  const setLocale = useCallback(async (next: AppLocale) => {
    setLocaleState(next);
    await saveLocale(next);
  }, []);

  const setBiometricLock = useCallback(async (enabled: boolean) => {
    setBiometricLockState(enabled);
    await saveBiometricLock(enabled);
  }, []);

  const setPushEnabled = useCallback(async (enabled: boolean) => {
    setPushEnabledState(enabled);
    await savePushEnabled(enabled);
  }, []);

  const value = useMemo<AppSettingsValue>(
    () => ({
      ready,
      locale,
      t: dict[locale],
      setLocale,
      biometricLock,
      setBiometricLock,
      pushEnabled,
      setPushEnabled,
    }),
    [ready, locale, setLocale, biometricLock, setBiometricLock, pushEnabled, setPushEnabled],
  );

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings() {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}
