import { apiFetch } from './api'
import { formatHttpApiError } from './apiErrors'

export type StudioArchiveMediaKind = 'image' | 'video'

export type StudioArchiveItem = {
  id: number
  created_at: string
  output_aspect: string | null
  studio_model_id: number | null
  model_name: string | null
  prompt_excerpt: string | null
  status: string
  media_kind: StudioArchiveMediaKind
  error_message: string | null
  job_id: number | null
  image_url: string
  video_url: string | null
}

export type StudioGenerationsPage = {
  items: StudioArchiveItem[]
  has_more: boolean
}

export type StudioGenerationsPendingPage = {
  items: StudioArchiveItem[]
  poll_after_seconds: number
}

export function studioArchiveIsPending(item: StudioArchiveItem): boolean {
  const st = (item.status || '').trim()
  if (st === 'processing' || st === 'archiving') return true
  if (st === 'failed' || st === 'ready') return false
  if (st === 'provider_ready') {
    if (item.media_kind === 'video') return !(item.video_url || '').trim()
    return !(item.image_url || '').trim()
  }
  return false
}

export function studioArchiveThumbUrl(item: StudioArchiveItem): string | null {
  if (item.media_kind === 'video') {
    if ((item.video_url || '').trim()) return null
    return (item.image_url || '').trim() || null
  }
  return (item.image_url || '').trim() || null
}

export async function fetchStudioArchivePage(
  skip: number,
  limit: number,
  mediaKind?: StudioArchiveMediaKind,
): Promise<StudioGenerationsPage> {
  const qs = new URLSearchParams({ limit: String(limit), skip: String(skip) })
  if (mediaKind) qs.set('media_kind', mediaKind)
  const r = await apiFetch(`/api/studio/generations?${qs}`)
  const data = (await r.json().catch(() => ({}))) as StudioGenerationsPage & { detail?: unknown }
  if (!r.ok) throw new Error(formatHttpApiError(r, data))
  return {
    items: Array.isArray(data.items) ? data.items : [],
    has_more: Boolean(data.has_more),
  }
}

export async function fetchStudioArchivePending(
  mediaKind?: StudioArchiveMediaKind,
): Promise<StudioGenerationsPendingPage> {
  const qs = mediaKind ? `?media_kind=${encodeURIComponent(mediaKind)}` : ''
  const r = await apiFetch(`/api/studio/generations/pending${qs}`)
  const data = (await r.json().catch(() => ({}))) as StudioGenerationsPendingPage & { detail?: unknown }
  if (!r.ok) throw new Error(formatHttpApiError(r, data))
  return {
    items: Array.isArray(data.items) ? data.items : [],
    poll_after_seconds:
      typeof data.poll_after_seconds === 'number' && data.poll_after_seconds > 0
        ? data.poll_after_seconds
        : 12,
  }
}

export type MotionRenderArchiveSource = {
  id: number
  created_at: string
  studio_generation_id: number | null
  studio_model_id?: number | null
  video_url: string
  frame_image_url: string
}

const OPTIMISTIC_STUDIO_ARCHIVE_ID_FLOOR = -1_000_000_000

/** Временная карточка «Генерация…» до ответа API (отрицательный id ниже порога). */
export function isOptimisticStudioArchiveId(id: number): boolean {
  return id <= OPTIMISTIC_STUDIO_ARCHIVE_ID_FLOOR
}

/** Отрицательный id — запись только из motion/renders (нет video-строки в архиве). */
export function isMotionRenderArchiveId(id: number): boolean {
  return id < 0 && id > OPTIMISTIC_STUDIO_ARCHIVE_ID_FLOOR
}

let optimisticStudioArchiveSeq = 0

export function createOptimisticStudioArchiveItem(opts: {
  mediaKind: StudioArchiveMediaKind
  promptExcerpt?: string | null
  studioModelId?: number | null
  modelName?: string | null
  outputAspect?: string | null
}): { item: StudioArchiveItem; tempId: number } {
  optimisticStudioArchiveSeq += 1
  const tempId = OPTIMISTIC_STUDIO_ARCHIVE_ID_FLOOR - optimisticStudioArchiveSeq
  return {
    tempId,
    item: {
      id: tempId,
      created_at: new Date().toISOString(),
      output_aspect: opts.outputAspect ?? null,
      studio_model_id: opts.studioModelId ?? null,
      model_name: opts.modelName ?? null,
      prompt_excerpt: (opts.promptExcerpt ?? '').trim().slice(0, 200) || 'Генерация…',
      status: 'processing',
      media_kind: opts.mediaKind,
      error_message: null,
      job_id: null,
      image_url: '',
      video_url: null,
    },
  }
}

export function prependOptimisticStudioArchive(
  current: StudioArchiveItem[],
  item: StudioArchiveItem,
): StudioArchiveItem[] {
  return dedupeStudioArchiveById([item, ...current])
}

export function replaceOptimisticStudioArchiveId(
  current: StudioArchiveItem[],
  tempId: number,
  realId: number,
  patch?: Partial<StudioArchiveItem>,
): StudioArchiveItem[] {
  return dedupeStudioArchiveById(
    current.map((g) => (g.id === tempId ? { ...g, id: realId, ...patch } : g)),
  )
}

export function removeOptimisticStudioArchive(
  current: StudioArchiveItem[],
  tempId: number,
): StudioArchiveItem[] {
  return current.filter((g) => g.id !== tempId)
}

export function motionRenderArchiveId(renderId: number): number {
  return -renderId
}

/**
 * Дополняет список video-архива роликами из /studio/motion/renders
 * (как на главной), если их ещё нет в generations.
 */
export function mergeVideoArchiveWithMotionRenders(
  generations: StudioArchiveItem[],
  motionRenders: MotionRenderArchiveSource[],
): StudioArchiveItem[] {
  const seenUrls = new Set(
    generations
      .map((g) => (g.video_url || '').trim())
      .filter(Boolean),
  )
  const enriched = generations.map((g) => ({ ...g }))

  const extra: StudioArchiveItem[] = []
  for (const r of motionRenders) {
    const url = (r.video_url || '').trim()
    if (!url) continue
    const frame = (r.frame_image_url || '').trim()
    const gid = r.studio_generation_id

    if (gid != null) {
      const idx = enriched.findIndex((g) => g.id === gid && g.media_kind === 'video')
      if (idx >= 0) {
        const cur = enriched[idx]
        if (frame && !(cur.image_url || '').trim()) {
          enriched[idx] = { ...cur, image_url: frame }
        }
        if (!(cur.video_url || '').trim()) {
          enriched[idx] = { ...enriched[idx], video_url: url, status: 'ready' }
        }
        seenUrls.add(url)
        continue
      }
    }

    if (seenUrls.has(url)) continue
    seenUrls.add(url)

    extra.push({
      id: motionRenderArchiveId(r.id),
      created_at: r.created_at,
      output_aspect: null,
      studio_model_id: r.studio_model_id ?? null,
      model_name: null,
      prompt_excerpt: `Видео #${r.id}`,
      status: 'ready',
      media_kind: 'video',
      error_message: null,
      job_id: null,
      image_url: frame || url,
      video_url: url,
    })
  }

  const merged = [...enriched, ...extra]
  merged.sort((a, b) => {
    const ta = Date.parse(a.created_at) || 0
    const tb = Date.parse(b.created_at) || 0
    return tb - ta || Math.abs(b.id) - Math.abs(a.id)
  })
  return merged
}

/** Убрать дубликаты по id (первая запись в списке сохраняется). */
export function dedupeStudioArchiveById(items: StudioArchiveItem[]): StudioArchiveItem[] {
  const seen = new Set<number>()
  const out: StudioArchiveItem[] = []
  for (const g of items) {
    if (seen.has(g.id)) continue
    seen.add(g.id)
    out.push(g)
  }
  return out
}

/** Keep prior signed media URL when only the JWT query changed (browser cache). */
export function preferStableArchiveMediaUrl(prev: string | null | undefined, next: string | null | undefined): string {
  const p = (prev || '').trim()
  const n = (next || '').trim()
  if (!n) return p
  if (!p) return n
  if (p === n) return p
  const pBase = p.split('?')[0]
  const nBase = n.split('?')[0]
  if (
    pBase === nBase &&
    (pBase.includes('/api/studio/public-generation-image') ||
      pBase.includes('/api/studio/public-generation-video'))
  ) {
    return p
  }
  return n
}

export function mergeArchiveItemPreserveMedia(
  prev: StudioArchiveItem,
  next: StudioArchiveItem,
): StudioArchiveItem {
  return {
    ...prev,
    ...next,
    image_url: preferStableArchiveMediaUrl(prev.image_url, next.image_url),
    video_url: preferStableArchiveMediaUrl(prev.video_url, next.video_url) || null,
  }
}

/** Слить pending-статусы в список архива (по id). */
export function mergeStudioArchiveItems(
  current: StudioArchiveItem[],
  pending: StudioArchiveItem[],
): StudioArchiveItem[] {
  if (!pending.length) return dedupeStudioArchiveById(current)
  const byId = new Map(pending.map((p) => [p.id, p]))
  const merged = current.map((g) => {
    const upd = byId.get(g.id)
    return upd ? mergeArchiveItemPreserveMedia(g, upd) : g
  })
  const seen = new Set(merged.map((g) => g.id))
  for (const p of pending) {
    if (!seen.has(p.id)) merged.unshift(p)
  }
  return dedupeStudioArchiveById(merged)
}

function sleepMs(ms: number, signal?: AbortSignal): Promise<void> {
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

/** Ждёт готовности картинки в архиве (после отложенного WaveSpeed). */
export async function waitForStudioGenerationImage(
  generationId: number,
  opts?: { maxWaitMs?: number; pollMs?: number; signal?: AbortSignal },
): Promise<string> {
  const maxWaitMs = opts?.maxWaitMs ?? 20 * 60 * 1000
  const started = Date.now()

  while (Date.now() - started < maxWaitMs) {
    if (opts?.signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    const pending = await fetchStudioArchivePending('image')
    const pollMs = (pending.poll_after_seconds ?? 12) * 1000
    const fromPending = pending.items.find((g) => g.id === generationId)
    if (fromPending) {
      if (fromPending.status === 'failed') {
        throw new Error(fromPending.error_message?.trim() || 'Генерация не выполнена')
      }
      const url = (fromPending.image_url || '').trim()
      if (url && !studioArchiveIsPending(fromPending)) return url
    } else {
      const page = await fetchStudioArchivePage(0, 40, 'image')
      const ready = page.items.find((g) => g.id === generationId)
      if (ready) {
        if (ready.status === 'failed') {
          throw new Error(ready.error_message?.trim() || 'Генерация не выполнена')
        }
        const url = (ready.image_url || '').trim()
        if (url && !studioArchiveIsPending(ready)) return url
      }
    }
    await sleepMs(Math.min(pollMs, maxWaitMs - (Date.now() - started)), opts?.signal)
  }

  throw new Error(
    'Превышено время ожидания WaveSpeed. Результат может появиться в «Сохранённые» через минуту.',
  )
}
