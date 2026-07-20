import { useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import { useAppData } from '@/src/context/AppDataProvider';
import { useAppSettings } from '@/src/context/AppSettingsContext';

/** Регистрирует push-токен после авторизации и обновляет badge непрочитанных. */
export function MobilePushAuthSync() {
  const { ready, authenticated, totalUnread } = useAppData();
  const { pushEnabled, syncPushRegistration } = useAppSettings();

  useEffect(() => {
    if (!ready || !authenticated || !pushEnabled) return;
    void syncPushRegistration();
  }, [ready, authenticated, pushEnabled, syncPushRegistration]);

  useEffect(() => {
    if (!ready || !authenticated) return;
    void Notifications.setBadgeCountAsync(Math.max(0, totalUnread));
  }, [ready, authenticated, totalUnread]);

  return null;
}
