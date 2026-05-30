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

/** Отрицательный id — запись только из motion/renders (нет video-строки в архиве). */
export function isMotionRenderArchiveId(id: number): boolean {
  return id < 0
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
  const videoGenIds = new Set(
    generations.filter((g) => g.media_kind === 'video').map((g) => g.id),
  )

  const extra: StudioArchiveItem[] = []
  for (const r of motionRenders) {
    const url = (r.video_url || '').trim()
    if (!url || seenUrls.has(url)) continue
    const gid = r.studio_generation_id
    if (gid != null && videoGenIds.has(gid)) continue
    seenUrls.add(url)

    const frame = (r.frame_image_url || '').trim()
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

  const merged = [...generations, ...extra]
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

/** Слить pending-статусы в список архива (по id). */
export function mergeStudioArchiveItems(
  current: StudioArchiveItem[],
  pending: StudioArchiveItem[],
): StudioArchiveItem[] {
  if (!pending.length) return dedupeStudioArchiveById(current)
  const byId = new Map(pending.map((p) => [p.id, p]))
  const merged = current.map((g) => byId.get(g.id) ?? g)
  const seen = new Set(merged.map((g) => g.id))
  for (const p of pending) {
    if (!seen.has(p.id)) merged.unshift(p)
  }
  return dedupeStudioArchiveById(merged)
}
