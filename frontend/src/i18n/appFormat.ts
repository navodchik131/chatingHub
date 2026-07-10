import { appLocale } from './index'

function localeTag(): string {
  return appLocale() === 'en' ? 'en-US' : 'ru-RU'
}

export function formatDateTimeApp(iso: string | undefined | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString(localeTag(), { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return String(iso)
  }
}

export function formatNoteUpdatedAtApp(iso: string | undefined | null): string {
  if (!iso) return '—'
  try {
    const updated = new Date(iso)
    const now = new Date()
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const startOfUpdated = new Date(updated.getFullYear(), updated.getMonth(), updated.getDate())
    const dayDiff = Math.round((startOfToday.getTime() - startOfUpdated.getTime()) / 86_400_000)
    const time = updated.toLocaleTimeString(localeTag(), { hour: '2-digit', minute: '2-digit' })
    if (appLocale() === 'en') {
      if (dayDiff === 0) return `today, ${time}`
      if (dayDiff === 1) return `yesterday, ${time}`
      if (dayDiff > 1 && dayDiff < 7) return `${dayDiff} days ago`
      return formatDateTimeApp(iso)
    }
    if (dayDiff === 0) return `сегодня, ${time}`
    if (dayDiff === 1) return `вчера, ${time}`
    if (dayDiff > 1 && dayDiff < 7) return `${dayDiff} дн. назад`
    return formatDateTimeApp(iso)
  } catch {
    return String(iso)
  }
}

export function formatAppCurrency(amountMinor: number, currency: string): string {
  const cur = (currency || 'USD').toUpperCase()
  try {
    return new Intl.NumberFormat(localeTag(), {
      style: 'currency',
      currency: cur,
      maximumFractionDigits: 2,
    }).format(amountMinor / 100)
  } catch {
    return `${(amountMinor / 100).toFixed(2)} ${cur}`
  }
}
