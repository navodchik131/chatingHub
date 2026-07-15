const TOKEN_KEY = 'chating_token'
const COOKIE_MAX_AGE = 60 * 60 * 24 * 90

function readCookieToken(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)chating_token=([^;]*)/)
  return m ? decodeURIComponent(m[1]) : null
}

function writeCookieToken(token: string | null): void {
  if (token) {
    document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`
  } else {
    document.cookie = `${TOKEN_KEY}=; path=/; max-age=0; SameSite=Lax`
  }
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

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
    writeCookieToken(token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
    writeCookieToken(null)
  }
}

export async function apiFetch(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  const { timeoutMs, ...restInit } = init
  const headers = new Headers(restInit.headers)
  const t = getToken()
  if (t) headers.set('Authorization', `Bearer ${t}`)
  if (!headers.has('Content-Type') && restInit.body && typeof restInit.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }
  let ctl: AbortController | undefined
  let to: ReturnType<typeof setTimeout> | undefined
  if (typeof timeoutMs === 'number' && timeoutMs > 0 && !restInit.signal) {
    ctl = new AbortController()
    to = setTimeout(() => ctl!.abort(), timeoutMs)
  }
  try {
    return await fetch(path, {
      ...restInit,
      headers,
      signal: ctl?.signal ?? restInit.signal,
    })
  } finally {
    if (to) clearTimeout(to)
  }
}
