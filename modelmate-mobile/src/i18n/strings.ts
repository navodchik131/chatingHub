import type { AppLocale } from '@/src/i18n/prefs';

export type Strings = {
  navOverview: string;
  navDialogs: string;
  navStudio: string;
  navCharacters: string;
  navProfile: string;
  navBilling: string;
  navDonations: string;
  navConnections: string;
  navTeam: string;
  profileTitle: string;
  owner: string;
  member: string;
  sectionWorkspace: string;
  sectionSystem: string;
  settingsTitle: string;
  settingsLanguage: string;
  settingsLanguageRu: string;
  settingsLanguageEn: string;
  settingsLanguageHint: string;
  settingsBiometric: string;
  settingsBiometricHint: string;
  settingsBiometricTest: string;
  settingsBiometricUnavailable: string;
  settingsBiometricLock: string;
  settingsBiometricLockHint: string;
  settingsPush: string;
  settingsPushHint: string;
  settingsPushEnabled: string;
  settingsPushDisabled: string;
  settingsSaved: string;
  adminPanel: string;
};

const RU: Strings = {
  navOverview: 'Обзор',
  navDialogs: 'Диалоги',
  navStudio: 'Студия',
  navCharacters: 'Персонажи',
  navProfile: 'Профиль',
  navBilling: 'Тариф и баланс',
  navDonations: 'Донаты и выплаты',
  navConnections: 'Подключения',
  navTeam: 'Команда',
  profileTitle: 'Профиль',
  owner: 'Владелец',
  member: 'Участник',
  sectionWorkspace: 'WORKSPACE',
  sectionSystem: 'СИСТЕМА',
  settingsTitle: 'Настройки',
  settingsLanguage: 'Язык',
  settingsLanguageRu: 'Русский',
  settingsLanguageEn: 'English',
  settingsLanguageHint: 'Интерфейс приложения. Диалоги с фанами переводятся отдельно.',
  settingsBiometric: 'Face ID / биометрия',
  settingsBiometricHint: 'Проверка отпечатка или Face ID при входе в приложение.',
  settingsBiometricTest: 'Проверить сейчас',
  settingsBiometricUnavailable: 'Биометрия недоступна на этом устройстве.',
  settingsBiometricLock: 'Запрашивать при открытии',
  settingsBiometricLockHint: 'После фона — экран блокировки с биометрией.',
  settingsPush: 'Push-уведомления',
  settingsPushHint: 'Новые сообщения, донаты и статус генераций.',
  settingsPushEnabled: 'Уведомления включены',
  settingsPushDisabled: 'Уведомления выключены',
  settingsSaved: 'Сохранено',
  adminPanel: 'Admin-панель',
};

const EN: Strings = {
  navOverview: 'Overview',
  navDialogs: 'Dialogs',
  navStudio: 'Studio',
  navCharacters: 'Characters',
  navProfile: 'Profile',
  navBilling: 'Plan & balance',
  navDonations: 'Donations & payouts',
  navConnections: 'Connections',
  navTeam: 'Team',
  profileTitle: 'Profile',
  owner: 'Owner',
  member: 'Member',
  sectionWorkspace: 'WORKSPACE',
  sectionSystem: 'SYSTEM',
  settingsTitle: 'Settings',
  settingsLanguage: 'Language',
  settingsLanguageRu: 'Russian',
  settingsLanguageEn: 'English',
  settingsLanguageHint: 'App UI language. Fan chat translation is separate.',
  settingsBiometric: 'Face ID / biometrics',
  settingsBiometricHint: 'Use fingerprint or Face ID when opening the app.',
  settingsBiometricTest: 'Test now',
  settingsBiometricUnavailable: 'Biometrics are not available on this device.',
  settingsBiometricLock: 'Require on app open',
  settingsBiometricLockHint: 'After backgrounding — lock screen with biometrics.',
  settingsPush: 'Push notifications',
  settingsPushHint: 'New messages, donations and generation status.',
  settingsPushEnabled: 'Notifications enabled',
  settingsPushDisabled: 'Notifications disabled',
  settingsSaved: 'Saved',
  adminPanel: 'Admin panel',
};

export const dict: Record<AppLocale, Strings> = { ru: RU, en: EN };

export function languageLabel(locale: AppLocale, t: Strings): string {
  return locale === 'en' ? t.settingsLanguageEn : t.settingsLanguageRu;
}

export function settingsLanguageRow(locale: AppLocale, t: Strings): string {
  return `${t.settingsLanguage} — ${languageLabel(locale, t)}`;
}
