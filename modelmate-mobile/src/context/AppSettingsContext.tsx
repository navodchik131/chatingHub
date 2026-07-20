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
import {
  isPushPermissionGranted,
  syncMobilePushEnabled,
} from '@/src/push/notifications';
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
  pushRegistered: boolean;
  pushError: string | null;
  pushBusy: boolean;
  setPushEnabled: (enabled: boolean) => Promise<boolean>;
  chatTheme: ChatThemeId;
  setChatTheme: (theme: ChatThemeId) => Promise<void>;
  syncPushRegistration: () => Promise<boolean>;
  refreshPushStatus: () => Promise<void>;
};

const AppSettingsContext = createContext<AppSettingsValue | null>(null);

export function AppSettingsProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [locale, setLocaleState] = useState<AppLocale>('ru');
  const [biometricLock, setBiometricLockState] = useState(false);
  const [pushEnabled, setPushEnabledState] = useState(false);
  const [pushRegistered, setPushRegisteredState] = useState(false);
  const [pushError, setPushError] = useState<string | null>(null);
  const [pushBusy, setPushBusy] = useState(false);
  const [chatTheme, setChatThemeState] = useState<ChatThemeId>('default');

  const refreshPushStatus = useCallback(async () => {
    const granted = await isPushPermissionGranted();
    if (granted && !pushEnabled) {
      setPushEnabledState(true);
      await savePushEnabled(true);
    }
    if (!granted && pushEnabled) {
      setPushEnabledState(false);
      setPushRegisteredState(false);
      await savePushEnabled(false);
    }
  }, [pushEnabled]);

  useEffect(() => {
    void loadAppPrefs().then(async (prefs) => {
      setLocaleState(prefs.locale);
      setBiometricLockState(prefs.biometricLock);
      setChatThemeState(prefs.chatTheme);
      const granted = await isPushPermissionGranted();
      const enabled = prefs.pushEnabled && granted;
      setPushEnabledState(enabled);
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
    setPushBusy(true);
    setPushError(null);
    try {
      if (!enabled) {
        await syncMobilePushEnabled(false);
        setPushEnabledState(false);
        setPushRegisteredState(false);
        await savePushEnabled(false);
        return true;
      }

      const result = await syncMobilePushEnabled(true);
      if (!result.permissionGranted) {
        setPushError(result.reason || 'Не удалось получить разрешение на уведомления');
        setPushEnabledState(false);
        setPushRegisteredState(false);
        await savePushEnabled(false);
        return false;
      }

      setPushEnabledState(true);
      await savePushEnabled(true);

      if (result.tokenRegistered) {
        setPushRegisteredState(true);
        setPushError(null);
        return true;
      }

      setPushRegisteredState(false);
      setPushError(result.reason || 'Разрешение есть, но push-токен не зарегистрирован');
      return true;
    } finally {
      setPushBusy(false);
    }
  }, []);

  const syncPushRegistration = useCallback(async () => {
    if (!pushEnabled) return true;
    setPushError(null);
    const result = await syncMobilePushEnabled(true);
    if (result.tokenRegistered) {
      setPushRegisteredState(true);
      setPushError(null);
      return true;
    }
    setPushRegisteredState(false);
    if (result.reason) setPushError(result.reason);
    return result.tokenRegistered;
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
      pushRegistered,
      pushError,
      pushBusy,
      setPushEnabled,
      chatTheme,
      setChatTheme,
      syncPushRegistration,
      refreshPushStatus,
    }),
    [
      ready,
      locale,
      setLocale,
      biometricLock,
      setBiometricLock,
      pushEnabled,
      pushRegistered,
      pushError,
      pushBusy,
      setPushEnabled,
      chatTheme,
      setChatTheme,
      syncPushRegistration,
      refreshPushStatus,
    ],
  );

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings() {
  const ctx = useContext(AppSettingsContext);
  if (!ctx) throw new Error('useAppSettings must be used within AppSettingsProvider');
  return ctx;
}
