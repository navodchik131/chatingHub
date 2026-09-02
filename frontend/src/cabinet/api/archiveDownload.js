/** Append download=1 for tokenized studio video URLs (forces attachment on backend). */
export function withVideoDownloadParam(url) {
  const src = String(url || '').trim()
  if (!src) return ''
  if (!src.includes('public-generation-video')) return src
  if (/[?&]download=/.test(src)) return src
  return `${src}${src.includes('?') ? '&' : '?'}download=1`
}

/** iOS / iPadOS WebKit (PWA и Safari). */
export function isIosWebKit() {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  const platform = navigator.platform || ''
  const touchPoints = Number(navigator.maxTouchPoints || 0)
  const iosDevice = /iPhone|iPad|iPod/i.test(ua) || (platform === 'MacIntel' && touchPoints > 1)
  return iosDevice && /WebKit/i.test(ua)
}

/** Мобильные браузеры/PWA — Web Share с files даёт «Сохранить в Фото» одним жестом. */
export function preferNativeShareForDownload() {
  if (typeof navigator === 'undefined') return false
  return isIosWebKit() || /Android/i.test(navigator.userAgent || '')
}

function guessMime(filename, blobType) {
  const t = String(blobType || '').trim()
  if (t && t !== 'application/octet-stream') return t
  const lower = String(filename || '').toLowerCase()
  if (lower.endsWith('.mp4') || lower.endsWith('.mov')) return 'video/mp4'
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg'
  if (lower.endsWith('.png')) return 'image/png'
  if (lower.endsWith('.webp')) return 'image/webp'
  return 'application/octet-stream'
}

/** Пробуем системный share-sheet (iOS/Android) — лучший UX для PWA. */
async function tryShareFileBlob(blob, filename) {
  if (!preferNativeShareForDownload()) return false
  if (typeof navigator.share !== 'function' || typeof navigator.canShare !== 'function') return false
  const file = new File([blob], filename, { type: guessMime(filename, blob.type) })
  if (!navigator.canShare({ files: [file] })) return false
  try {
    await navigator.share({ files: [file], title: filename })
    return true
  } catch (err) {
    if (err?.name === 'AbortError') return true
    return false
  }
}

function triggerBlobAnchorDownload(blob, filename) {
  const objectUrl = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
  }
}

function triggerDirectUrlClick(url) {
  const directLink = document.createElement('a')
  directLink.href = url
  directLink.rel = 'noopener noreferrer'
  document.body.appendChild(directLink)
  directLink.click()
  document.body.removeChild(directLink)
}

/** Скачивание blob: share на мобилках → anchor download на десктопе. */
export async function downloadBlobAsFile(blob, filename) {
  if (!blob) throw new Error('Файл недоступен для скачивания')
  if (await tryShareFileBlob(blob, filename)) return
  triggerBlobAnchorDownload(blob, filename)
}

export async function downloadArchiveBlob(url, filename) {
  const src = withVideoDownloadParam(url)
  if (!src) throw new Error('Файл недоступен для скачивания')

  let blob = null
  try {
    const res = await fetch(src, { credentials: 'include' })
    if (res.ok) blob = await res.blob()
  } catch {
    /* fallback below */
  }

  if (blob) {
    await downloadBlobAsFile(blob, filename)
    return
  }

  if (isIosWebKit()) {
    window.location.assign(src)
    return
  }

  const opened = window.open(src, '_blank', 'noopener,noreferrer')
  if (!opened) {
    throw new Error('Не удалось скачать файл. Разрешите всплывающие окна или попробуйте ещё раз.')
  }
}
