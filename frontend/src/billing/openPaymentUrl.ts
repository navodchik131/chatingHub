/** Открыть страницу оплаты: на мобильных/PWA popup после async часто блокируется. */
import { isMobileLikeClient, openExternalUrl } from '../utils/openExternalUrl'

export function openPaymentUrl(
  url: string,
  options?: { telegramDeepLink?: string | null },
): void {
  const href = url.trim()
  if (!href) return

  const tg = options?.telegramDeepLink?.trim()
  const target = isMobileLikeClient() && tg ? tg : href
  openExternalUrl(target)
}
