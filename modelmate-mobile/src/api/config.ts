import Constants from 'expo-constants';

const DEFAULT_DEV = 'http://10.0.2.2:8080';

export function getApiBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/$/, '');

  const extra = Constants.expoConfig?.extra as { apiUrl?: string } | undefined;
  if (extra?.apiUrl) return extra.apiUrl.replace(/\/$/, '');

  return DEFAULT_DEV;
}

/** Публичный сайт (статика, Telegram OAuth bridge). По умолчанию = API host. */
export function getSiteBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_SITE_URL?.trim();
  if (fromEnv) return fromEnv.replace(/\/$/, '');
  return getApiBaseUrl().replace(/\/api\/?$/, '');
}

export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const base = getApiBaseUrl();
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
}

const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '[::1]']);

/** Переписывает host локальных медиа-URL на EXPO_PUBLIC_API_URL (эмулятор не видит 127.0.0.1). */
export function resolveMediaUrl(raw: string | null | undefined): string {
  const path = (raw || '').trim();
  if (!path) return '';
  if (!/^https?:\/\//i.test(path)) return apiUrl(path);
  try {
    const media = new URL(path);
    if (!LOOPBACK_HOSTS.has(media.hostname)) return path;
    const base = getApiBaseUrl();
    const baseUrl = new URL(base.includes('://') ? base : `http://${base}`);
    media.protocol = baseUrl.protocol;
    media.host = baseUrl.host;
    return media.toString();
  } catch {
    return path;
  }
}
