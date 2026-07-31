/** Открыть внешний URL (Telegram, оплата): в PWA popup после async часто блокируется. */
export function isMobileLikeClient(): boolean {
  return (
    window.matchMedia('(pointer: coarse)').matches ||
    window.matchMedia('(max-width: 768px)').matches ||
    window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  )
}

export function openExternalUrl(url: string): void {
  const href = url.trim()
  if (!href) return

  if (isMobileLikeClient()) {
    window.location.assign(href)
    return
  }

  const popup = window.open(href, '_blank', 'noopener,noreferrer')
  if (!popup) {
    window.location.assign(href)
  }
}

/** Desktop: popup сразу по клику, URL — после async (обходит блокировку). */
export function openExternalUrlDeferred(
  url: string,
  popup: Window | null,
): void {
  const href = url.trim()
  if (!href) return

  if (popup && !popup.closed) {
    try {
      popup.location.href = href
      return
    } catch {
      /* cross-origin or blocked — fallback below */
    }
  }

  openExternalUrl(href)
}
