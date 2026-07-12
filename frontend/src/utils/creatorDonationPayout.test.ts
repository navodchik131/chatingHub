import { describe, expect, it } from 'vitest'
import {
  donationAvailableAtUtc,
  isDonationAvailableForPayout,
  summarizeDonationPayouts,
} from './creatorDonationPayout'

describe('creatorDonationPayout', () => {
  it('releases donations from 1-15 on the 16th', () => {
    const occurred = new Date('2026-07-10T12:00:00Z')
    expect(donationAvailableAtUtc(occurred).toISOString()).toBe('2026-07-16T00:00:00.000Z')
    expect(isDonationAvailableForPayout(occurred, new Date('2026-07-15T23:59:59Z'))).toBe(false)
    expect(isDonationAvailableForPayout(occurred, new Date('2026-07-16T00:00:00Z'))).toBe(true)
  })

  it('releases donations from 16-end on the 1st of next month', () => {
    const occurred = new Date('2026-07-20T12:00:00Z')
    expect(donationAvailableAtUtc(occurred).toISOString()).toBe('2026-08-01T00:00:00.000Z')
  })

  it('enables payout request when available exceeds tribute minimum', () => {
    const summary = summarizeDonationPayouts(
      [
        {
          amount_minor: 100_000,
          currency: 'RUB',
          payout_status: 'pending',
          occurred_at: '2026-06-01T10:00:00Z',
        },
        {
          amount_minor: 250_000,
          currency: 'RUB',
          payout_status: 'pending',
          occurred_at: '2026-06-02T10:00:00Z',
        },
      ],
      new Date('2026-07-20T12:00:00Z'),
    )
    expect(summary.availableByCurrency.RUB).toBe(350_000)
    expect(summary.canRequestPayout).toBe(true)
    expect(summary.eligibleCurrencies).toContain('RUB')
  })
})
