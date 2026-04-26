/** Разбор detail из ответа FastAPI (422 и др.) */
export function formatApiErrorDetail(data: unknown): string {
  if (!data || typeof data !== 'object') return 'Ошибка запроса'
  const d = (data as { detail?: unknown }).detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d
      .map((item) => {
        if (typeof item === 'string') return item
        const o = item as { loc?: unknown[]; msg?: string; type?: string }
        const loc = Array.isArray(o.loc) ? o.loc.filter((x) => x !== 'body').join('.') : ''
        const msg = o.msg ?? o.type ?? ''
        return loc ? `${loc}: ${msg}` : msg
      })
      .filter(Boolean)
      .join('; ')
  }
  return 'Ошибка запроса'
}
