/** HTTP-клиент — тот же JWT, что и кабинет (/workspace/). */

import { formatHttpApiError } from './errors'

const TOKEN_KEY = 'chating_token'

function readCookieToken(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)chating_token=([^;]*)/)
  return m ? decodeURIComponent(m[1]) : null
}

export function getToken(): string | null {
  const ls = localStorage.getItem(TOKEN_KEY)
  if (ls) return ls
  const ck = readCookieToken()
  if (ck) {
    localStorage.setItem(TOKEN_KEY, ck)
    return ck
  }
  return null
}

export function redirectToLogin(): void {
  // На chat.* логин на основном домене, next — полный URL возврата
  const onChatSub = window.location.hostname.startsWith('chat.')
  const nextRaw = onChatSub
    ? window.location.href
    : `${window.location.pathname}${window.location.search}`
  const next = encodeURIComponent(nextRaw)
  const loginBase = onChatSub ? `${window.location.protocol}//${window.location.hostname.replace(/^chat\./, '')}` : ''
  window.location.href = `${loginBase}/login?next=${next}`
}

/** Сессия: всегда проверяем /api/auth/me; stale Bearer не блокирует HttpOnly cookie. */
export async function hasActiveSession(): Promise<boolean> {
  const token = getToken()
  try {
    const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}
    const r = await fetch('/api/auth/me', { credentials: 'include', headers })
    if (r.ok) return true
    // Протухший JWT в localStorage — убираем и пробуем только cookie
    if (token) {
      localStorage.removeItem(TOKEN_KEY)
      const r2 = await fetch('/api/auth/me', { credentials: 'include' })
      return r2.ok
    }
    return false
  } catch {
    return false
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (!headers.has('Content-Type') && init.body && typeof init.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }
  return fetch(path, { ...init, headers, credentials: 'include' })
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init)
  const data = await res.json().catch(() => ({}))
  if (res.status === 401) {
    redirectToLogin()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    throw new Error(formatHttpApiError(res, data))
  }
  return data as T
}
