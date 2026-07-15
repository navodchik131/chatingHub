/**
 * Мост к API текущего бэкенда.
 * Пока макет работает на mock-данных из data-dc-script;
 * сюда постепенно подключаем реальные /api/* без переписывания вёрстки.
 */
export const API_BASE = ''

export async function apiFetch(path, init = {}) {
  const headers = new Headers(init.headers || {})
  if (!headers.has('Accept')) headers.set('Accept', 'application/json')
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...init,
    headers,
  })
  return res
}

export async function getHealth() {
  const r = await apiFetch('/api/health')
  if (!r.ok) throw new Error(`health ${r.status}`)
  return r.json()
}
