/** Базовый путь Unibox: /chat/ на основном домене или / на chat.* */

export function chatBasePath(): string {
  if (typeof window === 'undefined') return import.meta.env.BASE_URL || '/chat/'
  if (window.location.hostname.startsWith('chat.')) return '/'
  if (window.location.pathname.startsWith('/chat/')) return '/chat/'
  return import.meta.env.BASE_URL || '/chat/'
}

export function chatScopePath(): string {
  const base = chatBasePath()
  return base.endsWith('/') ? base : `${base}/`
}
