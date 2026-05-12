const TOKEN_KEY = 'chating_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
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
