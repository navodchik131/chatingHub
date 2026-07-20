import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { apiJson } from '@/src/api/client';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

let registeredToken: string | null = null;

export type PushSetupResult = {
  ok: boolean;
  permissionGranted: boolean;
  tokenRegistered: boolean;
  reason?: string;
  token?: string;
};

export async function ensureNotificationChannel() {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('messages', {
      name: 'Сообщения',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 120, 250],
      lightColor: '#D7F452',
      sound: 'default',
    });
  }
}

export async function isPushPermissionGranted(): Promise<boolean> {
  const { status } = await Notifications.getPermissionsAsync();
  return status === 'granted';
}

export async function registerMobilePush(): Promise<PushSetupResult> {
  await ensureNotificationChannel();

  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;
  if (existing !== 'granted') {
    const req = await Notifications.requestPermissionsAsync({
      ios: { allowAlert: true, allowBadge: true, allowSound: true },
    });
    finalStatus = req.status;
  }

  const permissionGranted = finalStatus === 'granted';
  if (!permissionGranted) {
    return {
      ok: false,
      permissionGranted: false,
      tokenRegistered: false,
      reason: 'Разрешите уведомления в настройках телефона.',
    };
  }

  if (!Device.isDevice) {
    return {
      ok: true,
      permissionGranted: true,
      tokenRegistered: false,
      reason: 'Разрешение получено. Доставка push работает только на физическом устройстве, не в эмуляторе.',
    };
  }

  const projectId =
    Constants.expoConfig?.extra?.eas?.projectId ||
    Constants.easConfig?.projectId ||
    Constants.expoConfig?.extra?.projectId;

  if (!projectId) {
    return {
      ok: false,
      permissionGranted: true,
      tokenRegistered: false,
      reason: 'Не найден EAS projectId. Пересоберите приложение через EAS.',
    };
  }

  try {
    const tokenData = await Notifications.getExpoPushTokenAsync({ projectId });
    const expoToken = tokenData.data;
    if (!expoToken) {
      return {
        ok: false,
        permissionGranted: true,
        tokenRegistered: false,
        reason: 'Не удалось получить push-токен Expo.',
      };
    }

    await apiJson('/api/push/mobile/register', {
      method: 'POST',
      body: JSON.stringify({
        expo_token: expoToken,
        platform: Platform.OS,
        device_name: Device.modelName || undefined,
      }),
    });

    registeredToken = expoToken;
    return { ok: true, permissionGranted: true, tokenRegistered: true, token: expoToken };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return {
      ok: false,
      permissionGranted: true,
      tokenRegistered: false,
      reason: msg.includes('401') || msg.includes('403')
        ? 'Войдите в аккаунт, затем включите уведомления снова.'
        : msg.includes('Firebase') || msg.includes('googleServicesFile')
          ? 'Нужна настройка Firebase (FCM): добавьте google-services.json и пересоберите APK. См. README → Push-уведомления.'
          : `Не удалось зарегистрировать push: ${msg}`,
    };
  }
}

export async function unregisterMobilePush(): Promise<void> {
  if (!registeredToken) return;
  try {
    await apiJson('/api/push/mobile/unregister', {
      method: 'POST',
      body: JSON.stringify({ expo_token: registeredToken }),
    });
  } catch {
    /* ignore */
  }
  registeredToken = null;
}

export async function syncMobilePushEnabled(enabled: boolean): Promise<PushSetupResult> {
  if (enabled) {
    return registerMobilePush();
  }
  await unregisterMobilePush();
  return { ok: true, permissionGranted: false, tokenRegistered: false };
}
