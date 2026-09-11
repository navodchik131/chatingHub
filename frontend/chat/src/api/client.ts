/** HTTP-клиент — тот же JWT, что и кабинет (/workspace/). */

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
  const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`)
  window.location.href = `/login?next=${next}`
}

/** Сессия может жить только в HttpOnly cookie — проверяем через /api/auth/me. */
export async function hasActiveSession(): Promise<boolean> {
  if (getToken()) return true
  try {
    const r = await fetch('/api/auth/me', { credentials: 'include' })
    return r.ok
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
    const detail = typeof data.detail === 'string' ? data.detail : res.statusText
    throw new Error(detail || 'Request failed')
  }
  return data as T
}
