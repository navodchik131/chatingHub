const STORAGE_KEY = 'mm_device_id';
const COOKIE_KEY = 'mm_device_id';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2;

function readCookieDeviceId(): string | null {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(/(?:^|;\s*)mm_device_id=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : null;
}

function writeCookieDeviceId(id: string): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${COOKIE_KEY}=${encodeURIComponent(id)}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
}

function newDeviceId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `mm-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

/** Стабильный id браузера/PWA для лимита демо на устройство. */
export function getOrCreateDeviceId(): string {
  if (typeof localStorage === 'undefined') return newDeviceId();
  let id = localStorage.getItem(STORAGE_KEY);
  if (!id) id = readCookieDeviceId();
  if (!id) id = newDeviceId();
  localStorage.setItem(STORAGE_KEY, id);
  writeCookieDeviceId(id);
  return id;
}

export const DEVICE_ID_HEADER = 'X-Device-Id';

export function appendDeviceIdHeader(headers: Headers): void {
  headers.set(DEVICE_ID_HEADER, getOrCreateDeviceId());
}
