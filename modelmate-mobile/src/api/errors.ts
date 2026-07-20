export function formatApiErrorDetail(data: unknown): string {
  if (!data || typeof data !== 'object') return '';
  const o = data as Record<string, unknown>;
  if (typeof o.message === 'string' && o.message.trim()) return o.message.trim();
  const d = o.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d
      .map((item) => {
        if (typeof item === 'string') return item;
        const row = item as { loc?: unknown[]; msg?: string; type?: string };
        const loc = Array.isArray(row.loc) ? row.loc.filter((x) => x !== 'body').join('.') : '';
        const msg = row.msg ?? row.type ?? '';
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter(Boolean)
      .join('; ');
  }
  if (d && typeof d === 'object' && typeof (d as { message?: unknown }).message === 'string') {
    return (d as { message: string }).message.trim();
  }
  return '';
}

function formatHttpStatusFallback(status: number, statusText: string): string {
  if (status === 401) return 'Сессия истекла — войдите снова';
  if (status === 403) return 'Недостаточно прав';
  if (status === 502 || status === 504) return 'Сервер не отвечает — попробуйте позже';
  if (status === 503) return 'Сервис временно недоступен';
  if (status >= 500) return `Ошибка сервера (${status})`;
  if (status >= 400) return statusText || `Ошибка запроса (${status})`;
  return statusText || `HTTP ${status}`;
}

export function formatHttpApiError(response: Response, data: unknown): string {
  const fromBody = formatApiErrorDetail(data).trim();
  if (fromBody) return fromBody;
  return formatHttpStatusFallback(response.status, response.statusText);
}

export function formatClientFetchError(error: unknown, longOperation = false): string {
  if (error instanceof Error && error.name === 'AbortError') {
    return longOperation
      ? 'Превышено время ожидания. Результат мог уже сохраниться в архиве.'
      : 'Превышено время ожидания запроса';
  }
  if (error instanceof TypeError && error.message === 'Network request failed') {
    return 'Нет связи с сервером. Проверьте API URL и сеть.';
  }
  if (error instanceof Error && error.message?.trim()) return error.message.trim();
  return 'Не удалось выполнить запрос';
}
