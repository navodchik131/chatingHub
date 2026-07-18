import { apiFetch } from './api'
import { formatApiErrorDetail, formatHttpApiError } from './apiErrors'

export interface StudioJobAccepted {
  job_id: number
  status: string
  job_type: string
  generation_id?: number | null
  message?: string
}

export function coerceJobGenerationId(accepted: StudioJobAccepted | null | undefined): number | null {
  const raw = accepted?.generation_id
  if (typeof raw === 'number' && Number.isFinite(raw) && raw > 0) return raw
  if (typeof raw === 'string' && raw.trim()) {
    const n = Number(raw)
    if (Number.isFinite(n) && n > 0) return n
  }
  return null
}

/** POST студии: 202 — задача в фоне, без ожидания WaveSpeed. */
export async function postStudioJobStart(
  path: string,
  init: RequestInit & { timeoutMs?: number },
): Promise<StudioJobAccepted> {
  const r = await apiFetch(path, init)
  const data = (await r.json().catch(() => ({}))) as StudioJobAccepted & { detail?: unknown }
  if (r.status === 202) {
    if (!data.job_id) {
      throw new Error(formatApiErrorDetail(data) || 'Не удалось создать задачу студии.')
    }
    return data
  }
  if (!r.ok) {
    throw new Error(formatHttpApiError(r, data))
  }
  throw new Error('Ожидался ответ 202 (фоновая задача). Обновите страницу.')
}

export interface StudioJobStatus {
  job_id: number
  job_type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  error_message?: string | null
  result?: Record<string, unknown> | null
  created_at?: string
  started_at?: string | null
  completed_at?: string | null
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return Promise.reject(new DOMException('Aborted', 'AbortError'))
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    const onAbort = () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError')
  }
}

function parseStudioGenerationId(raw: unknown): number | null {
  if (typeof raw === 'number' && Number.isFinite(raw) && raw > 0) return raw
  if (typeof raw === 'string' && raw.trim() !== '') {
    const n = Number(raw)
    if (Number.isFinite(n) && n > 0) return n
  }
  return null
}

export async function fetchStudioJob(jobId: number, signal?: AbortSignal): Promise<StudioJobStatus> {
  const r = await apiFetch(`/api/studio/jobs/${jobId}`, { signal })
  const data = (await r.json().catch(() => ({}))) as StudioJobStatus & { detail?: unknown }
  if (!r.ok) {
    throw new Error(formatHttpApiError(r, data))
  }
  return data
}

export async function waitForStudioJobResult<T extends Record<string, unknown>>(
  jobId: number,
  opts?: {
    pollMs?: number
    maxWaitMs?: number
    onStatus?: (status: StudioJobStatus) => void
    signal?: AbortSignal
  },
): Promise<T> {
  const pollMs = opts?.pollMs ?? 2500
  const maxWaitMs = opts?.maxWaitMs ?? 20 * 60 * 1000
  const started = Date.now()

  while (Date.now() - started < maxWaitMs) {
    throwIfAborted(opts?.signal)
    const status = await fetchStudioJob(jobId, opts?.signal)
    opts?.onStatus?.(status)
    if (status.status === 'completed') {
      if (status.result && typeof status.result === 'object') {
        return status.result as T
      }
      throw new Error('Задача завершилась без результата.')
    }
    if (status.status === 'failed') {
      throw new Error(status.error_message?.trim() || 'Задача студии не выполнена.')
    }
    await sleep(pollMs, opts?.signal)
  }

  throw new Error(
    'Превышено время ожидания задачи. Обновите страницу — результат мог уже сохраниться в «Сохранённые» или «Последние видео».',
  )
}

/**
 * POST в студию: при 202 опрашивает /api/studio/jobs/{id}, при 200 возвращает JSON как раньше.
 */
export async function postStudioJobAndWait<T extends Record<string, unknown>>(
  path: string,
  init: RequestInit & { timeoutMs?: number },
  opts?: Parameters<typeof waitForStudioJobResult<T>>[1],
): Promise<T> {
  throwIfAborted(opts?.signal)
  const r = await apiFetch(path, init)
  throwIfAborted(opts?.signal)
  if (r.status === 202) {
    const accepted = (await r.json().catch(() => ({}))) as StudioJobAccepted & { detail?: unknown }
    if (!accepted.job_id) {
      throw new Error(formatApiErrorDetail(accepted) || 'Не удалось создать задачу студии.')
    }
    const placeholderGenerationId = parseStudioGenerationId(accepted.generation_id)
    const result = await waitForStudioJobResult<T>(accepted.job_id, opts)
    if (parseStudioGenerationId(result.generation_id) == null && placeholderGenerationId != null) {
      return { ...result, generation_id: placeholderGenerationId }
    }
    return result
  }
  const data = (await r.json().catch(() => ({}))) as T & { detail?: unknown }
  if (!r.ok) {
    throw new Error(formatHttpApiError(r, data))
  }
  return data as T
}
