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
  saveChatTheme,
  saveLocale,
  savePushEnabled,
} from '@/src/i18n/prefs';
import { syncMobilePushEnabled } from '@/src/push/notifications';
import { dict, Strings } from '@/src/i18n/strings';
import type { ChatThemeId } from '@/src/styles/chatThemes';

type AppSettingsValue = {
  ready: boolean;
  locale: AppLocale;
  t: Strings;
  setLocale: (locale: AppLocale) => Promise<void>;
  biometricLock: boolean;
  setBiometricLock: (enabled: boolean) => Promise<void>;
  pushEnabled: boolean;
  pushError: string | null;
  setPushEnabled: (enabled: boolean) => Promise<boolean>;
  chatTheme: ChatThemeId;
  setChatTheme: (theme: ChatThemeId) => Promise<void>;
  syncPushRegistration: () => Promise<boolean>;
};

const AppSettingsContext = createContext<AppSettingsValue | null>(null);

export function AppSettingsProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [locale, setLocaleState] = useState<AppLocale>('ru');
  const [biometricLock, setBiometricLockState] = useState(false);
  const [pushEnabled, setPushEnabledState] = useState(false);
  const [pushError, setPushError] = useState<string | null>(null);
  const [chatTheme, setChatThemeState] = useState<ChatThemeId>('default');

  useEffect(() => {
    void loadAppPrefs().then((prefs) => {
      setLocaleState(prefs.locale);
      setBiometricLockState(prefs.biometricLock);
      setPushEnabledState(prefs.pushEnabled);
      setChatThemeState(prefs.chatTheme);
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
    setPushError(null);
    const result = await syncMobilePushEnabled(enabled);
    if (!result.ok) {
      setPushError(result.reason || 'Не удалось включить уведомления');
      setPushEnabledState(false);
      await savePushEnabled(false);
      return false;
    }
    setPushEnabledState(enabled);
    await savePushEnabled(enabled);
    return true;
  }, []);

  const syncPushRegistration = useCallback(async () => {
    if (!pushEnabled) return true;
    setPushError(null);
    const result = await syncMobilePushEnabled(true);
    if (!result.ok) {
      setPushError(result.reason || 'Не удалось зарегистрировать push');
      return false;
    }
    return true;
  }, [pushEnabled]);

  const setChatTheme = useCallback(async (theme: ChatThemeId) => {
    setChatThemeState(theme);
    await saveChatTheme(theme);
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
      pushError,
      setPushEnabled,
      chatTheme,
      setChatTheme,
      syncPushRegistration,
    }),
    [
      ready,
      locale,
      setLocale,
      biometricLock,
      setBiometricLock,
      pushEnabled,
      pushError,
      setPushEnabled,
      chatTheme,
      setChatTheme,
      syncPushRegistration,
    ],
  );

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings() {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}
