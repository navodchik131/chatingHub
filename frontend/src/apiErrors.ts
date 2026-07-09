/** Разбор detail / message из ответа FastAPI и похожих JSON. */
export function formatApiErrorDetail(data: unknown): string {
  if (!data || typeof data !== 'object') return ''
  const o = data as Record<string, unknown>
  if (typeof o.message === 'string' && o.message.trim()) {
    const m = o.message.trim()
    if (/invalid user uuid/i.test(m)) {
      return 'Пользователь Fanvue недоступен: аккаунт удалён или заблокирован на платформе.'
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
          return 'Пользователь Fanvue недоступен: аккаунт удалён или заблокирован на платформе.'
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
  if (status === 502 || status === 504) {
    return (
      'Шлюз или прокси не дождались ответа от сервера (таймаут). ' +
      'Долгая генерация могла всё равно завершиться — обновите страницу и проверьте «Сохранённые» / «Последние видео».'
    )
  }
  if (status === 503) {
    return 'Сервис временно недоступен (503). Попробуйте через минуту.'
  }
  if (status === 413) {
    return 'Файл слишком большой для загрузки (413).'
  }
  if (status === 401) return 'Сессия истекла — войдите снова.'
  if (status === 403) return 'Нет доступа к этой операции (403).'
  if (status >= 500) {
    return `Ошибка сервера (${status}${st ? ` ${st}` : ''}). Повторите позже или обновите страницу.`
  }
  if (status >= 400) {
    return `Запрос отклонён (${status}${st ? ` ${st}` : ''}).`
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
      ? ' Долгая генерация могла завершиться на сервере — обновите страницу и проверьте «Сохранённые» и «Последние видео».'
      : ' Повторите запрос или обновите страницу.'
    return 'Превышено время ожидания ответа (таймаут).' + hint
  }
  if (error instanceof TypeError && error.message === 'Failed to fetch') {
    return (
      'Нет ответа от сервера (сеть, VPN, блокировка или перезапуск бэкенда). ' +
      'Проверьте соединение. Если только что запускали генерацию — после восстановления связи обновите страницу и посмотрите архив.'
    )
  }
  if (error instanceof Error) {
    const m = error.message?.trim()
    if (m && m !== 'Failed to fetch') return m
  }
  const tail = longOperation
    ? ' Обновите страницу — готовое видео или кадр могли уже попасть в раздел истории.'
    : ' Обновите страницу и повторите при необходимости.'
  return 'Ошибка запроса.' + tail
}
