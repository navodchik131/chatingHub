import * as SecureStore from 'expo-secure-store';
import type { ChatThemeId } from '@/src/styles/chatThemes';

export type AppLocale = 'ru' | 'en';

const LOCALE_KEY = 'mm_locale';
const BIOMETRIC_LOCK_KEY = 'mm_biometric_lock';
const PUSH_ENABLED_KEY = 'mm_push_enabled';
const CHAT_THEME_KEY = 'mm_chat_theme';

export type AppPrefs = {
  locale: AppLocale;
  biometricLock: boolean;
  pushEnabled: boolean;
  chatTheme: ChatThemeId;
};

const VALID_THEMES: ChatThemeId[] = ['default', 'ocean', 'emerald', 'sunset', 'mono'];

function parseTheme(raw: string | null): ChatThemeId {
  if (raw && VALID_THEMES.includes(raw as ChatThemeId)) return raw as ChatThemeId;
  return 'default';
}

export async function loadAppPrefs(): Promise<AppPrefs> {
  try {
    const [localeRaw, biometricRaw, pushRaw, themeRaw] = await Promise.all([
      SecureStore.getItemAsync(LOCALE_KEY),
      SecureStore.getItemAsync(BIOMETRIC_LOCK_KEY),
      SecureStore.getItemAsync(PUSH_ENABLED_KEY),
      SecureStore.getItemAsync(CHAT_THEME_KEY),
    ]);
    return {
      locale: localeRaw === 'en' ? 'en' : 'ru',
      biometricLock: biometricRaw === '1',
      pushEnabled: pushRaw === '1',
      chatTheme: parseTheme(themeRaw),
    };
  } catch {
    return { locale: 'ru', biometricLock: false, pushEnabled: false, chatTheme: 'default' };
  }
}

export async function saveLocale(locale: AppLocale): Promise<void> {
  try {
    await SecureStore.setItemAsync(LOCALE_KEY, locale);
  } catch {
    /* ignore */
  }
}

export async function saveBiometricLock(enabled: boolean): Promise<void> {
  try {
    if (enabled) {
      await SecureStore.setItemAsync(BIOMETRIC_LOCK_KEY, '1');
    } else {
      await SecureStore.deleteItemAsync(BIOMETRIC_LOCK_KEY);
    }
  } catch {
    /* ignore */
  }
}

export async function savePushEnabled(enabled: boolean): Promise<void> {
  try {
    if (enabled) {
      await SecureStore.setItemAsync(PUSH_ENABLED_KEY, '1');
    } else {
      await SecureStore.deleteItemAsync(PUSH_ENABLED_KEY);
    }
  } catch {
    /* ignore */
  }
}

export async function saveChatTheme(theme: ChatThemeId): Promise<void> {
  try {
    await SecureStore.setItemAsync(CHAT_THEME_KEY, theme);
  } catch {
    /* ignore */
  }
}
