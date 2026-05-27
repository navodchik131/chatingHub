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

export async function fetchStudioArchivePage(skip: number, limit: number): Promise<StudioGenerationsPage> {
  const r = await apiFetch(`/api/studio/generations?limit=${limit}&skip=${skip}`)
  const data = (await r.json().catch(() => ({}))) as StudioGenerationsPage & { detail?: unknown }
  if (!r.ok) throw new Error(formatHttpApiError(r, data))
  return {
    items: Array.isArray(data.items) ? data.items : [],
    has_more: Boolean(data.has_more),
  }
}

export async function fetchStudioArchivePending(): Promise<StudioGenerationsPendingPage> {
  const r = await apiFetch('/api/studio/generations/pending')
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

/** Слить pending-статусы в список архива (по id). */
export function mergeStudioArchiveItems(
  current: StudioArchiveItem[],
  pending: StudioArchiveItem[],
): StudioArchiveItem[] {
  if (!pending.length) return current
  const byId = new Map(pending.map((p) => [p.id, p]))
  const merged = current.map((g) => byId.get(g.id) ?? g)
  const seen = new Set(merged.map((g) => g.id))
  for (const p of pending) {
    if (!seen.has(p.id)) merged.unshift(p)
  }
  return merged
}
