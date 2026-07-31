import { useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import { useAppData } from '@/src/context/AppDataProvider';
import { useNav } from '@/src/context/NavigationContext';

function ticketIdFromNotification(data: unknown): number | null {
  if (!data || typeof data !== 'object') return null;
  const raw = (data as { ticket_id?: unknown }).ticket_id;
  const id = Number(raw);
  return id > 0 ? id : null;
}

/** Deep link из push: открыть тикет поддержки или админку. */
export function MobilePushNavigation() {
  const { authenticated, me } = useAppData();
  const { resetTo, push } = useNav();

  useEffect(() => {
    if (!authenticated) return;

    const openFromNotification = (response: Notifications.NotificationResponse | null) => {
      if (!response) return;
      const data = response.notification.request.content.data;
      const ticketId = ticketIdFromNotification(data);
      if (!ticketId) return;

      const kind = String((data as { kind?: string })?.kind || '');

      if (kind === 'support_new' && me?.is_platform_admin) {
        resetTo('admin');
        return;
      }

      resetTo('profile');
      push('support');
      push(`ticket:${ticketId}`);
    };

    const sub = Notifications.addNotificationResponseReceivedListener(openFromNotification);
    void Notifications.getLastNotificationResponseAsync().then(openFromNotification);

    return () => sub.remove();
  }, [authenticated, me?.is_platform_admin, resetTo, push]);

  return null;
}
