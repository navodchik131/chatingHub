import { formatAppCurrency } from '../i18n/appFormat'

export interface CreatorDonationOverviewEvent {
  id: number
  amount_minor: number
  currency: string
  payer_telegram_user_id: number | null
  occurred_at: string
}

export interface CreatorDonationOverview {
  donations_count: number
  active_links: number
  has_donation_setup: boolean
  totals_by_currency: Record<string, number>
  pending_payout_by_currency: Record<string, number>
  latest_event_id: number | null
  latest_event: CreatorDonationOverviewEvent | null
  recent_events: CreatorDonationOverviewEvent[]
}

const SEEN_KEY_PREFIX = 'mm_creator_donation_last_seen_event_'

export function donationSeenStorageKey(userId: number): string {
  return `${SEEN_KEY_PREFIX}${userId}`
}

export function readDonationLastSeenEventId(userId: number): number {
  const raw = localStorage.getItem(donationSeenStorageKey(userId))
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : 0
}

export function writeDonationLastSeenEventId(userId: number, eventId: number): void {
  if (eventId > 0) {
    localStorage.setItem(donationSeenStorageKey(userId), String(eventId))
  }
}

export function formatDonationTotalsLabel(totals: Record<string, number>): string | null {
  const entries = Object.entries(totals).filter(([, v]) => v > 0)
  if (entries.length === 0) return null
  return entries
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([cur, minor]) => formatAppCurrency(minor, cur))
    .join(' · ')
}

export function formatDonationOverviewHint(
  overview: CreatorDonationOverview,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  if (overview.donations_count === 0) {
    if (overview.active_links > 0) {
      return t('platformDonations.hintWaiting')
    }
    if (overview.has_donation_setup) {
      return t('platformDonations.hintSetup')
    }
    return t('platformDonations.hintEmpty')
  }
  const pending = formatDonationTotalsLabel(overview.pending_payout_by_currency)
  if (pending) {
    return t('platformDonations.hintWithPending', {
      count: overview.donations_count,
      pending,
    })
  }
  return t('platformDonations.hintTotal', { count: overview.donations_count })
}
