/** Открыть страницу оплаты: на мобильных/PWA popup после async часто блокируется. */
export function openPaymentUrl(
  url: string,
  options?: { telegramDeepLink?: string | null },
): void {
  const href = url.trim()
  if (!href) return

  const tg = options?.telegramDeepLink?.trim()
  const isMobileLike =
    window.matchMedia('(pointer: coarse)').matches ||
    window.matchMedia('(max-width: 768px)').matches ||
    window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true

  const target = isMobileLike && tg ? tg : href

  if (isMobileLike) {
    window.location.assign(target)
    return
  }

  const popup = window.open(target, '_blank', 'noopener,noreferrer')
  if (!popup) {
    window.location.assign(target)
  }
}
