/** Партнёрская атрибуция pref/src — из URL и sessionStorage между страницами маркетинга. */

const STORAGE_KEY = 'mm_partner_attribution'

export type PartnerAttribution = {
  pref?: string
  src?: string
}

export function readPartnerAttributionFromSearch(params: URLSearchParams): PartnerAttribution {
  const pref = (params.get('pref') || params.get('partner') || '').trim() || undefined
  const src = (params.get('src') || '').trim() || undefined
  return { pref, src }
}

export function loadPartnerAttribution(): PartnerAttribution {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const data = JSON.parse(raw) as PartnerAttribution
    return {
      pref: data.pref || undefined,
      src: data.src || undefined,
    }
  } catch {
    return {}
  }
}

export function savePartnerAttribution(att: PartnerAttribution): void {
  if (!att.pref && !att.src) return
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(att))
  } catch {
    /* ignore quota / private mode */
  }
}

/** URL-параметры имеют приоритет; при наличии — сохраняем в sessionStorage. */
export function mergePartnerAttribution(params: URLSearchParams): PartnerAttribution {
  const fromUrl = readPartnerAttributionFromSearch(params)
  const stored = loadPartnerAttribution()
  const merged: PartnerAttribution = {
    pref: fromUrl.pref || stored.pref,
    src: fromUrl.src || stored.src,
  }
  if (fromUrl.pref || fromUrl.src) savePartnerAttribution(merged)
  return merged
}

export function partnerAttributionSearch(att?: PartnerAttribution): string {
  const a = att || loadPartnerAttribution()
  const p = new URLSearchParams()
  if (a.pref) p.set('pref', a.pref)
  if (a.src) p.set('src', a.src)
  const s = p.toString()
  return s ? `?${s}` : ''
}

export function marketingLoginPath(
  localePath: (p: string) => string,
  opts?: { next?: string; att?: PartnerAttribution },
): string {
  const p = new URLSearchParams()
  const a = opts?.att || loadPartnerAttribution()
  if (a.pref) p.set('pref', a.pref)
  if (a.src) p.set('src', a.src)
  if (opts?.next) p.set('next', opts.next)
  const q = p.toString()
  const base = localePath('/login')
  return q ? `${base}?${q}` : base
}

export function appendPartnerAttributionToLoginPath(loginPath: string, att?: PartnerAttribution): string {
  const a = att || loadPartnerAttribution()
  if (!a.pref && !a.src) return loginPath
  const [path, query = ''] = loginPath.split('?')
  const p = new URLSearchParams(query)
  if (a.pref && !p.has('pref')) p.set('pref', a.pref)
  if (a.src && !p.has('src')) p.set('src', a.src)
  const q = p.toString()
  return q ? `${path}?${q}` : path
}
