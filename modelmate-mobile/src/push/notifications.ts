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

export async function registerMobilePush(): Promise<{ ok: boolean; reason?: string; token?: string }> {
  if (!Device.isDevice) {
    return { ok: false, reason: 'Push работает только на реальном устройстве, не в эмуляторе.' };
  }

  await ensureNotificationChannel();

  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;
  if (existing !== 'granted') {
    const req = await Notifications.requestPermissionsAsync();
    finalStatus = req.status;
  }
  if (finalStatus !== 'granted') {
    return { ok: false, reason: 'Разрешите уведомления в настройках телефона.' };
  }

  const projectId =
    Constants.expoConfig?.extra?.eas?.projectId ||
    Constants.easConfig?.projectId ||
    Constants.expoConfig?.extra?.projectId;

  if (!projectId) {
    return { ok: false, reason: 'Не найден EAS projectId для push-токена.' };
  }

  const tokenData = await Notifications.getExpoPushTokenAsync({ projectId });
  const expoToken = tokenData.data;
  if (!expoToken) {
    return { ok: false, reason: 'Не удалось получить push-токен.' };
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
  return { ok: true, token: expoToken };
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

export async function syncMobilePushEnabled(enabled: boolean): Promise<{ ok: boolean; reason?: string }> {
  if (enabled) {
    const result = await registerMobilePush();
    return { ok: result.ok, reason: result.reason };
  }
  await unregisterMobilePush();
  return { ok: true };
}
