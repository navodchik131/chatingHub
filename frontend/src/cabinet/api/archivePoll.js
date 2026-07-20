import { apiJsonOptional } from './helpers'
import { isArchivePending, refreshArchiveVideos } from './actions'
import { isOptimisticStudioArchiveId, mergeStudioArchiveItems } from '../../studioArchive'

function archiveItemPollKey(item) {
  if (!item) return ''
  return [
    item.id,
    item.status || '',
    item.image_url || '',
    item.video_url || '',
    item.error_message || '',
    item.job_id || '',
  ].join('|')
}

function dedupeById(items) {
  const seen = new Set()
  return items.filter((g) => {
    if (seen.has(g.id)) return false
    seen.add(g.id)
    return true
  })
}

/** Инкрементальный опрос pending-картинок (как mm-os-bridge refreshPendingArchiveOnly). */
export async function refreshPendingArchiveImages(current) {
  const tracked = current.filter((g) => isArchivePending(g) || isOptimisticStudioArchiveId(g.id))
  const hasOptimistic = current.some((g) => isOptimisticStudioArchiveId(g.id))
  if (!tracked.length && !hasOptimistic) return { items: current, changed: false }

  const pending = await apiJsonOptional('/api/studio/generations/pending?media_kind=image', {}, { items: [] })
  const pendingItems = pending.items || []
  const pendingById = new Map(pendingItems.map((p) => [p.id, p]))
  let changed = false
  const maybeCompletedIds = []

  let next = current.map((g) => {
    if (isOptimisticStudioArchiveId(g.id)) {
      const byJob = g.job_id != null ? pendingItems.find((p) => p.job_id === g.job_id) : null
      if (byJob) {
        const merged = { ...g, ...byJob, id: byJob.id }
        if (archiveItemPollKey(g) !== archiveItemPollKey(merged)) changed = true
        return merged
      }
      return g
    }
    if (!isArchivePending(g)) return g
    const upd = pendingById.get(g.id)
    if (upd) {
      const merged = { ...g, ...upd }
      if (archiveItemPollKey(g) !== archiveItemPollKey(merged)) changed = true
      return merged
    }
    maybeCompletedIds.push(g.id)
    return g
  })

  if (maybeCompletedIds.length || hasOptimistic) {
    const page = await apiJsonOptional(
      '/api/studio/generations?limit=40&skip=0&media_kind=image',
      {},
      { items: [] },
    )
    const freshItems = page.items || []
    const freshById = new Map(freshItems.map((p) => [p.id, p]))

    if (maybeCompletedIds.length) {
      next = next.map((g) => {
        if (!maybeCompletedIds.includes(g.id)) return g
        const fresh = freshById.get(g.id)
        if (!fresh) return g
        const merged = { ...g, ...fresh }
        if (archiveItemPollKey(g) !== archiveItemPollKey(merged)) changed = true
        return merged
      })
    }

    const known = new Set(next.map((g) => g.id))
    const newcomers = freshItems.filter((p) => !known.has(p.id) && !isArchivePending(p))
    if (newcomers.length) {
      let images = [...next]
      for (const nr of newcomers) {
        const optIdx = images.findIndex((g) => isOptimisticStudioArchiveId(g.id))
        if (optIdx >= 0) images.splice(optIdx, 1)
        images.unshift(nr)
        known.add(nr.id)
        changed = true
      }
      next = dedupeById(images)
    }
  }

  return { items: dedupeById(next), changed }
}

export async function refreshPendingArchiveVideos(current) {
  const tracked = current.filter((g) => isArchivePending(g) || isOptimisticStudioArchiveId(g.id))
  const hasOptimistic = current.some((g) => isOptimisticStudioArchiveId(g.id))
  if (!tracked.length && !hasOptimistic) return { items: current, changed: false }

  const pending = await apiJsonOptional('/api/studio/generations/pending?media_kind=video', {}, { items: [] })
  const pendingItems = pending.items || []
  const pendingById = new Map(pendingItems.map((p) => [p.id, p]))
  let changed = false
  const maybeCompletedIds = []

  let next = current.map((g) => {
    if (isOptimisticStudioArchiveId(g.id)) {
      const byJob = g.job_id != null ? pendingItems.find((p) => p.job_id === g.job_id) : null
      if (byJob) {
        const merged = { ...g, ...byJob, id: byJob.id }
        if (archiveItemPollKey(g) !== archiveItemPollKey(merged)) changed = true
        return merged
      }
      return g
    }
    if (!isArchivePending(g)) return g
    const upd = pendingById.get(g.id)
    if (upd) {
      const merged = { ...g, ...upd }
      if (archiveItemPollKey(g) !== archiveItemPollKey(merged)) changed = true
      return merged
    }
    if (!isOptimisticStudioArchiveId(g.id)) maybeCompletedIds.push(g.id)
    return g
  })

  if (maybeCompletedIds.length || hasOptimistic) {
    const freshList = await refreshArchiveVideos()
    const freshById = new Map(freshList.map((p) => [p.id, p]))

    if (maybeCompletedIds.length) {
      next = next.map((g) => {
        if (!maybeCompletedIds.includes(g.id)) return g
        const fresh = freshById.get(g.id)
        if (!fresh) return g
        const merged = { ...g, ...fresh }
        if (archiveItemPollKey(g) !== archiveItemPollKey(merged)) changed = true
        return merged
      })
    }

    const known = new Set(next.map((g) => g.id))
    const newcomers = freshList.filter((p) => !known.has(p.id) && !isArchivePending(p))
    if (newcomers.length) {
      let videos = [...next]
      for (const nr of newcomers) {
        const optIdx = videos.findIndex((g) => isOptimisticStudioArchiveId(g.id))
        if (optIdx >= 0) videos.splice(optIdx, 1)
        videos.unshift(nr)
        known.add(nr.id)
        changed = true
      }
      next = dedupeById(videos)
    } else if (changed) {
      next = mergeStudioArchiveItems(next, freshList.filter((p) => !isArchivePending(p)))
      changed = true
    }
  }

  return { items: dedupeById(next), changed }
}
