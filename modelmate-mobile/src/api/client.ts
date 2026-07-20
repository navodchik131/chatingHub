import { apiUrl } from '@/src/api/config';
import { formatHttpApiError } from '@/src/api/errors';
import { getToken } from '@/src/api/token';

export async function apiFetch(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  const { timeoutMs, ...restInit } = init;
  const headers = new Headers(restInit.headers);
  const t = await getToken();
  if (t) headers.set('Authorization', `Bearer ${t}`);
  if (!headers.has('Content-Type') && restInit.body && typeof restInit.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  let ctl: AbortController | undefined;
  let to: ReturnType<typeof setTimeout> | undefined;
  if (typeof timeoutMs === 'number' && timeoutMs > 0 && !restInit.signal) {
    ctl = new AbortController();
    to = setTimeout(() => ctl!.abort(), timeoutMs);
  }

  try {
    return await fetch(apiUrl(path), {
      ...restInit,
      headers,
      signal: ctl?.signal ?? restInit.signal,
    });
  } finally {
    if (to) clearTimeout(to);
  }
}

export async function apiJson<T = unknown>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const res = await apiFetch(path, init);
  let data: unknown = {};
  try {
    data = await res.json();
  } catch {
    /* ignore */
  }
  if (!res.ok) {
    throw new Error(formatHttpApiError(res, data) || `${res.status} ${path}`);
  }
  return data as T;
}

export async function apiJsonOptional<T>(
  path: string,
  init: RequestInit | undefined,
  fallback: T,
): Promise<T> {
  try {
    return await apiJson<T>(path, init);
  } catch {
    return fallback;
  }
}
