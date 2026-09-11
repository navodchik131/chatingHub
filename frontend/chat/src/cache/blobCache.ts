/**
 * Кэш аватарок и медиа в IndexedDB + object URL в памяти.
 * Не качаем повторно при каждом открытии чата.
 */

import { idbDelete, idbGet, idbGetAllKeys, idbSet } from './idb'

const MAX_BLOB_BYTES = 220 * 1024 * 1024
const AVATAR_TTL_MS = 7 * 24 * 60 * 60 * 1000
const MEDIA_TTL_MS = 30 * 24 * 60 * 60 * 1000

interface BlobRecord {
  key: string
  blob: Blob
  mime: string
  size: number
  fetchedAt: number
  kind: 'avatar' | 'media'
}

/** Живые object URL — не создавать дубликаты в рамках сессии. */
const liveUrls = new Map<string, string>()

function isFresh(rec: BlobRecord): boolean {
  const ttl = rec.kind === 'avatar' ? AVATAR_TTL_MS : MEDIA_TTL_MS
  return Date.now() - rec.fetchedAt < ttl
}

async function readRecord(key: string): Promise<BlobRecord | null> {
  const rec = await idbGet<BlobRecord>('blobs', key)
  if (!rec?.blob) return null
  if (!isFresh(rec)) {
    await idbDelete('blobs', key)
    return null
  }
  return rec
}

async function writeRecord(rec: BlobRecord): Promise<void> {
  await idbSet('blobs', rec.key, rec)
  await evictIfNeeded()
}

/** LRU-подобная очистка по размеру. */
async function evictIfNeeded(): Promise<void> {
  const keys = await idbGetAllKeys('blobs')
  if (keys.length < 400) return
  const rows: BlobRecord[] = []
  for (const key of keys) {
    const rec = await idbGet<BlobRecord>('blobs', key)
    if (rec) rows.push(rec)
  }
  rows.sort((a, b) => a.fetchedAt - b.fetchedAt)
  let total = rows.reduce((s, r) => s + (r.size || 0), 0)
  for (const rec of rows) {
    if (total <= MAX_BLOB_BYTES) break
    total -= rec.size || 0
    const live = liveUrls.get(rec.key)
    if (live) {
      URL.revokeObjectURL(live)
      liveUrls.delete(rec.key)
    }
    await idbDelete('blobs', rec.key)
  }
}

export async function getCachedObjectUrl(
  key: string,
  fetcher: () => Promise<Response>,
  kind: 'avatar' | 'media',
): Promise<string | null> {
  const cached = liveUrls.get(key)
  if (cached) return cached

  const rec = await readRecord(key)
  if (rec) {
    const url = URL.createObjectURL(rec.blob)
    liveUrls.set(key, url)
    return url
  }

  try {
    const res = await fetcher()
    if (!res.ok) return null
    const blob = await res.blob()
    if (!blob.size) return null
    const mime = blob.type || res.headers.get('content-type') || 'application/octet-stream'
    await writeRecord({
      key,
      blob,
      mime,
      size: blob.size,
      fetchedAt: Date.now(),
      kind,
    })
    const url = URL.createObjectURL(blob)
    liveUrls.set(key, url)
    return url
  } catch {
    return null
  }
}

export function avatarCacheKey(convId: number): string {
  return `avatar:${convId}`
}

export function mediaCacheKey(url: string): string {
  return `media:${url}`
}
