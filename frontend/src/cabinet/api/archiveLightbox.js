import { mergeArchiveItemPreserveMedia } from '../../studioArchive'

/** Снимок кадра при открытии lightbox — не теряется при инкрементальном poll архива. */
export function archiveLightboxPayload(item) {
  if (!item || item.id == null) return null
  const id = Number(item.id)
  if (!Number.isFinite(id)) return null
  return { id, item: { ...item } }
}

function findArchiveItemById(id, archiveImages, archiveVideos) {
  if (!Number.isFinite(id)) return null
  return (
    (archiveImages || []).find((x) => Number(x.id) === id)
    || (archiveVideos || []).find((x) => Number(x.id) === id)
    || null
  )
}

/** Разрешает кадр для lightbox: snapshot + live merge, если карточка ещё в списке. */
export function resolveArchiveLightboxItem(lightbox, archiveImages = [], archiveVideos = []) {
  if (lightbox == null) return null

  if (typeof lightbox === 'object' && lightbox.item && typeof lightbox.item === 'object') {
    const snap = lightbox.item
    const id = Number(lightbox.id ?? snap.id)
    const live = findArchiveItemById(id, archiveImages, archiveVideos)
    return live ? mergeArchiveItemPreserveMedia(snap, live) : snap
  }

  if (typeof lightbox === 'object' && lightbox.id != null && (lightbox.image_url != null || lightbox.video_url != null)) {
    const id = Number(lightbox.id)
    const live = findArchiveItemById(id, archiveImages, archiveVideos)
    return live ? mergeArchiveItemPreserveMedia(lightbox, live) : lightbox
  }

  const numeric = Number(lightbox)
  if (Number.isFinite(numeric) && numeric > 0) {
    return findArchiveItemById(numeric, archiveImages, archiveVideos)
  }

  const idx = Number(lightbox)
  if (Number.isFinite(idx) && idx >= 0) {
    return (archiveImages || [])[idx] || null
  }

  return null
}
