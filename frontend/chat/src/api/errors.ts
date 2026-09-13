/** Разбор ошибок FastAPI для Unibox — чтобы не показывать голый «Request failed». */

export function formatApiErrorDetail(data: unknown): string {
  if (!data || typeof data !== 'object') return ''
  const o = data as Record<string, unknown>
  if (typeof o.message === 'string' && o.message.trim()) return o.message.trim()
  if (typeof o.error === 'string' && o.error.trim()) return o.error.trim()
  const d = o.detail
  if (typeof d === 'string' && d.trim()) return d.trim()
  if (Array.isArray(d)) {
    return d
      .map((item) => {
        if (typeof item === 'string') return item
        const row = item as { loc?: unknown[]; msg?: string; type?: string }
        const loc = Array.isArray(row.loc) ? row.loc.filter((x) => x !== 'body').join('.') : ''
        const msg = row.msg ?? row.type ?? ''
        return loc ? `${loc}: ${msg}` : msg
      })
      .filter(Boolean)
      .join('; ')
  }
  if (d && typeof d === 'object' && typeof (d as { message?: unknown }).message === 'string') {
    return (d as { message: string }).message.trim()
  }
  return ''
}

export function formatHttpApiError(res: Response, data: unknown): string {
  const fromBody = formatApiErrorDetail(data).trim()
  if (fromBody) return fromBody
  if (res.status === 502 || res.status === 504) return 'Сервер не дождался ответа Telegram/Fanvue. Попробуйте позже.'
  if (res.status === 503) return 'Сервис временно недоступен — проверьте подключения в кабинете.'
  if (res.status === 429) return 'Слишком много отправок — Telegram просит подождать.'
  if (res.status === 410) return 'Пользователь недоступен на платформе.'
  if (res.status === 401) return 'Сессия истекла — войдите снова.'
  if (res.status === 403) return 'Нет доступа к этому диалогу.'
  if (res.status >= 500) return `Ошибка сервера (${res.status}). Откройте логи api или повторите позже.`
  if (res.status >= 400) return `Ошибка запроса (${res.status}${res.statusText ? `: ${res.statusText}` : ''})`
  return res.statusText || 'Request failed'
}
