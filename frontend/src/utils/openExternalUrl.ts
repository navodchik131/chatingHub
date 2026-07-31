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

/**
 * Открыть Telegram-бота, не уходя со страницы входа (polling должен продолжаться).
 * location.assign убивает страницу — в PWA после возврата UI зависает.
 */
function telegramTargets(webUrl: string): { href: string; tgScheme: string | null } {
  const href = webUrl.trim()
  if (!href) return { href: '', tgScheme: null }
  const tgMatch = href.match(/^https?:\/\/t\.me\/([^/?#]+)(?:\?(.*))?$/i)
  const tgScheme = tgMatch
    ? `tg://resolve?domain=${encodeURIComponent(tgMatch[1])}${tgMatch[2] ? `&${tgMatch[2]}` : ''}`
    : null
  return { href, tgScheme }
}

export function navigatePopupToTelegram(popup: Window | null, webUrl: string): boolean {
  const { href, tgScheme } = telegramTargets(webUrl)
  if (!href || !popup || popup.closed) return false
  const urls: string[] = []
  if (isMobileLikeClient() && tgScheme) urls.push(tgScheme)
  urls.push(href)
  for (const target of urls) {
    try {
      popup.location.href = target
      return true
    } catch {
      /* try next */
    }
  }
  try {
    popup.close()
  } catch {
    /* ignore */
  }
  return false
}

export function openTelegramBotUrl(webUrl: string): void {
  const { href, tgScheme } = telegramTargets(webUrl)
  if (!href) return

  const tryAnchor = (target: string) => {
    const link = document.createElement('a')
    link.href = target
    link.target = '_blank'
    link.rel = 'noopener noreferrer'
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  if (isMobileLikeClient() && tgScheme) {
    tryAnchor(tgScheme)
  }
  tryAnchor(href)

  const popup = window.open(href, '_blank')
  if (!popup && isMobileLikeClient() && tgScheme) {
    window.open(tgScheme, '_blank')
  }
}

/**
 * Синхронно открыть пустую вкладку в обработчике клика для последующей навигации после async.
 * Нельзя передавать noopener — браузер вернёт null, вкладка about:blank останется пустой.
 */
export function openBlankPopupForDeferredNav(): Window | null {
  try {
    return window.open('about:blank', '_blank')
  } catch {
    return null
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
      try {
        popup.close()
      } catch {
        /* ignore */
      }
    }
  }

  openExternalUrl(href)
}

/** Desktop Telegram: popup сразу по клику. */
export function openTelegramBotUrlDeferred(
  webUrl: string,
  popup: Window | null,
): void {
  if (navigatePopupToTelegram(popup, webUrl)) return
  openTelegramBotUrl(webUrl)
}
