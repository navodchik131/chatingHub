import { getApiBaseUrl } from '@/src/api/config';
import { getToken } from '@/src/api/token';

export type RealtimeEvent = {
  type: string;
  conversation_id?: number;
  message?: Record<string, unknown>;
};

function wsBaseUrl(): string {
  const base = getApiBaseUrl();
  const u = new URL(base.includes('://') ? base : `http://${base}`);
  const proto = u.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${u.host}`;
}

export type RealtimeConnection = {
  close: () => void;
};

export async function connectRealtime(onEvent: (ev: RealtimeEvent) => void): Promise<RealtimeConnection | null> {
  const token = await getToken();
  if (!token) return null;

  let closed = false;
  let ws: WebSocket | null = null;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    if (closed) return;
    const url = `${wsBaseUrl()}/api/ws?token=${encodeURIComponent(token)}`;
    ws = new WebSocket(url);
    ws.onmessage = (ev) => {
      try {
        onEvent(JSON.parse(String(ev.data)) as RealtimeEvent);
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => {
      if (!closed) {
        retryTimer = setTimeout(connect, 3000);
      }
    };
    ws.onerror = () => {
      try {
        ws?.close();
      } catch {
        /* ignore */
      }
    };
  };

  connect();

  return {
    close: () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      try {
        ws?.close();
      } catch {
        /* ignore */
      }
    },
  };
}
