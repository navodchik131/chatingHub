/** Append download=1 for tokenized studio video URLs (forces attachment on backend). */
export function withVideoDownloadParam(url) {
  const src = String(url || '').trim()
  if (!src) return ''
  if (!src.includes('public-generation-video')) return src
  if (/[?&]download=/.test(src)) return src
  return `${src}${src.includes('?') ? '&' : '?'}download=1`
}

function isIosWebKit() {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  const platform = navigator.platform || ''
  const touchPoints = Number(navigator.maxTouchPoints || 0)
  const iosDevice = /iPhone|iPad|iPod/i.test(ua) || (platform === 'MacIntel' && touchPoints > 1)
  return iosDevice && /WebKit/i.test(ua)
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
    if (isIosWebKit()) {
      const directLink = document.createElement('a')
      directLink.href = src
      directLink.rel = 'noopener noreferrer'
      document.body.appendChild(directLink)
      directLink.click()
      document.body.removeChild(directLink)
      return
    }

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
    return
  }

  if (isIosWebKit()) {
    window.location.assign(src)
    return
  }

  window.open(src, '_blank', 'noopener,noreferrer')
}
