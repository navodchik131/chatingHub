import { apiFetch } from '@/src/api/client';
import { formatApiErrorDetail, formatHttpApiError } from '@/src/api/errors';

export type StudioJobAccepted = {
  job_id: number;
  status: string;
  job_type: string;
  generation_id?: number | null;
  message?: string;
};

export type StudioJobStatus = {
  job_id: number;
  job_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  error_message?: string | null;
  result?: Record<string, unknown> | null;
};

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return Promise.reject(new Error('Aborted'));
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new Error('Aborted'));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

export async function postStudioJobStart(
  path: string,
  init: RequestInit & { timeoutMs?: number },
): Promise<StudioJobAccepted> {
  const r = await apiFetch(path, init);
  const data = (await r.json().catch(() => ({}))) as StudioJobAccepted & { detail?: unknown };
  if (r.status === 202) {
    if (!data.job_id) {
      throw new Error(formatApiErrorDetail(data) || 'Не удалось создать задачу студии.');
    }
    return data;
  }
  if (!r.ok) throw new Error(formatHttpApiError(r, data));
  throw new Error('Ожидался ответ 202 (фоновая задача).');
}

export async function fetchStudioJob(jobId: number, signal?: AbortSignal): Promise<StudioJobStatus> {
  const r = await apiFetch(`/api/studio/jobs/${jobId}`, { signal });
  const data = (await r.json().catch(() => ({}))) as StudioJobStatus & { detail?: unknown };
  if (!r.ok) throw new Error(formatHttpApiError(r, data));
  return data;
}

export async function waitForStudioJobResult<T extends Record<string, unknown>>(
  jobId: number,
  opts?: { pollMs?: number; maxWaitMs?: number; onStatus?: (s: StudioJobStatus) => void; signal?: AbortSignal },
): Promise<T> {
  const pollMs = opts?.pollMs ?? 2500;
  const maxWaitMs = opts?.maxWaitMs ?? 20 * 60 * 1000;
  const started = Date.now();

  while (Date.now() - started < maxWaitMs) {
    if (opts?.signal?.aborted) throw new Error('Aborted');
    const status = await fetchStudioJob(jobId, opts?.signal);
    opts?.onStatus?.(status);
    if (status.status === 'completed') {
      if (status.result && typeof status.result === 'object') return status.result as T;
      throw new Error('Задача завершилась без результата.');
    }
    if (status.status === 'failed') {
      throw new Error(status.error_message?.trim() || 'Задача студии не выполнена.');
    }
    await sleep(pollMs, opts?.signal);
  }
  throw new Error('Превышено время ожидания задачи. Проверьте архив.');
}

export async function postStudioJobAndWait<T extends Record<string, unknown>>(
  path: string,
  init: RequestInit & { timeoutMs?: number },
  opts?: Parameters<typeof waitForStudioJobResult<T>>[1],
): Promise<T> {
  const r = await apiFetch(path, init);
  if (r.status === 202) {
    const accepted = (await r.json().catch(() => ({}))) as StudioJobAccepted & { detail?: unknown };
    if (!accepted.job_id) {
      throw new Error(formatApiErrorDetail(accepted) || 'Не удалось создать задачу студии.');
    }
    return waitForStudioJobResult<T>(accepted.job_id, opts);
  }
  const data = (await r.json().catch(() => ({}))) as T & { detail?: unknown };
  if (!r.ok) throw new Error(formatHttpApiError(r, data));
  return data as T;
}
