/** Минимальные пороги выплат Tribute (minor units). @see https://wiki.tribute.tg/ru/for-content-creators/payouts */
export const TRIBUTE_PAYOUT_MIN_MINOR: Record<string, number> = {
  RUB: 300_000,
  EUR: 10_000,
  USD: 10_000,
}

export interface DonationEventForPayout {
  amount_minor: number
  currency: string
  payout_status: string
  occurred_at: string
}

export interface DonationPayoutSummary {
  totalByCurrency: Record<string, number>
  availableByCurrency: Record<string, number>
  heldByCurrency: Record<string, number>
  paidByCurrency: Record<string, number>
  eligibleCurrencies: string[]
  canRequestPayout: boolean
}

/** Донаты 1–15 → доступны с 16-го; 16–конец месяца → с 1-го следующего. */
export function donationAvailableAtUtc(occurredAt: Date): Date {
  const y = occurredAt.getUTCFullYear()
  const m = occurredAt.getUTCMonth()
  const d = occurredAt.getUTCDate()
  if (d <= 15) return new Date(Date.UTC(y, m, 16))
  return new Date(Date.UTC(y, m + 1, 1))
}

export function isDonationAvailableForPayout(occurredAt: Date, now = new Date()): boolean {
  return now.getTime() >= donationAvailableAtUtc(occurredAt).getTime()
}

export function tributePayoutMinimumMinor(currency: string): number | null {
  return TRIBUTE_PAYOUT_MIN_MINOR[currency.toUpperCase()] ?? null
}

export function summarizeDonationPayouts(
  events: DonationEventForPayout[],
  now = new Date(),
): DonationPayoutSummary {
  const totalByCurrency: Record<string, number> = {}
  const availableByCurrency: Record<string, number> = {}
  const heldByCurrency: Record<string, number> = {}
  const paidByCurrency: Record<string, number> = {}

  for (const ev of events) {
    if (ev.amount_minor <= 0) continue
    const cur = ev.currency.toUpperCase()
    totalByCurrency[cur] = (totalByCurrency[cur] ?? 0) + ev.amount_minor

    if (ev.payout_status === 'paid') {
      paidByCurrency[cur] = (paidByCurrency[cur] ?? 0) + ev.amount_minor
      continue
    }

    const at = new Date(ev.occurred_at)
    if (isDonationAvailableForPayout(at, now)) {
      availableByCurrency[cur] = (availableByCurrency[cur] ?? 0) + ev.amount_minor
    } else {
      heldByCurrency[cur] = (heldByCurrency[cur] ?? 0) + ev.amount_minor
    }
  }

  const eligibleCurrencies = Object.entries(availableByCurrency)
    .filter(([cur, amount]) => {
      const min = tributePayoutMinimumMinor(cur)
      return min != null && amount >= min
    })
    .map(([cur]) => cur)

  return {
    totalByCurrency,
    availableByCurrency,
    heldByCurrency,
    paidByCurrency,
    eligibleCurrencies,
    canRequestPayout: eligibleCurrencies.length > 0,
  }
}
