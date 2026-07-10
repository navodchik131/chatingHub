import i18n, { COMMON_NS } from './i18n'

/** Разбор detail / message из ответа FastAPI и похожих JSON. */
export function formatApiErrorDetail(data: unknown): string {
  if (!data || typeof data !== 'object') return ''
  const o = data as Record<string, unknown>
  if (typeof o.message === 'string' && o.message.trim()) {
    const m = o.message.trim()
    if (/invalid user uuid/i.test(m)) {
      return i18n.t('errors.fanvueInvalidUser', { ns: COMMON_NS })
    }
    return m
  }
  const d = o.detail
  if (typeof d === 'string') {
    const trimmed = d.trim()
    if (trimmed.startsWith('{')) {
      try {
        const parsed = JSON.parse(trimmed) as Record<string, unknown>
        if (
          typeof parsed.message === 'string' &&
          /invalid user uuid/i.test(parsed.message)
        ) {
          return i18n.t('errors.fanvueInvalidUser', { ns: COMMON_NS })
        }
      } catch {
        /* not JSON */
      }
    }
    return d
  }
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
    const m = (d as { message: string }).message.trim()
    if (m) return m
  }
  return ''
}

function formatHttpStatusFallback(status: number, statusText: string): string {
  const st = (statusText || '').trim()
  const statusTextSuffix = st ? ` ${st}` : ''
  if (status === 502 || status === 504) {
    return i18n.t('errors.gatewayTimeout', { ns: COMMON_NS })
  }
  if (status === 503) {
    return i18n.t('errors.serviceUnavailable', { ns: COMMON_NS })
  }
  if (status === 413) {
    return i18n.t('errors.payloadTooLarge', { ns: COMMON_NS })
  }
  if (status === 401) return i18n.t('errors.sessionExpired', { ns: COMMON_NS })
  if (status === 403) return i18n.t('errors.forbidden', { ns: COMMON_NS })
  if (status >= 500) {
    return i18n.t('errors.serverError', {
      ns: COMMON_NS,
      status,
      statusText: statusTextSuffix,
    })
  }
  if (status >= 400) {
    return i18n.t('errors.clientError', {
      ns: COMMON_NS,
      status,
      statusText: statusTextSuffix,
    })
  }
  return st || `HTTP ${status}`
}

/** Текст ошибки по ответу API, если в теле нет detail — по коду статуса. */
export function formatHttpApiError(response: Response, data: unknown): string {
  const fromBody = formatApiErrorDetail(data).trim()
  if (fromBody) return fromBody
  return formatHttpStatusFallback(response.status, response.statusText)
}

/**
 * Сообщение для catch вокруг fetch: таймаут AbortController, обрыв сети, прочее.
 * `longOperation` — студия (видео/картинки), где обрыв клиента не значит «ничего не произошло».
 */
export function formatClientFetchError(error: unknown, longOperation = false): string {
  if (error instanceof DOMException && error.name === 'AbortError') {
    const hint = longOperation
      ? i18n.t('errors.abortHintLong', { ns: COMMON_NS })
      : i18n.t('errors.abortHintShort', { ns: COMMON_NS })
    return i18n.t('errors.abortTimeout', { ns: COMMON_NS }) + hint
  }
  if (error instanceof TypeError && error.message === 'Failed to fetch') {
    return i18n.t('errors.networkFailed', { ns: COMMON_NS })
  }
  if (error instanceof Error) {
    const m = error.message?.trim()
    if (m && m !== 'Failed to fetch') return m
  }
  const tail = longOperation
    ? i18n.t('errors.genericTailLong', { ns: COMMON_NS })
    : i18n.t('errors.genericTail', { ns: COMMON_NS })
  return i18n.t('errors.generic', { ns: COMMON_NS }) + tail
}
