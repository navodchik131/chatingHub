/** Static asset URL with Vite base path (/workspace/ on production). */
export function assetUrl(path) {
  const base = (typeof import.meta !== 'undefined' && import.meta.env?.BASE_URL) || '/'
  return `${base.replace(/\/?$/, '/')}${String(path || '').replace(/^\//, '')}`
}
