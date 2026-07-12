import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { formatAppNumber } from '../i18n'

interface StatsData {
  totals_by_currency: Record<string, number>
  pending_transfer_by_currency: Record<string, number>
  platform_fee_by_currency: Record<string, number>
  net_to_transfer_by_currency: Record<string, number>
  events_count: number
  active_links: number
  open_payout_requests: number
  platform_fee_percent: number
  creators: Array<{
    user_id: number
    email: string
    totals_by_currency: Record<string, number>
    pending_by_currency: Record<string, number>
    platform_fee_by_currency: Record<string, number>
    net_to_transfer_by_currency: Record<string, number>
  }>
}

function formatMinor(minor: number, currency: string): string {
  const sym = currency === 'RUB' ? '₽' : currency === 'EUR' ? '€' : '$'
  return `${formatAppNumber(minor / 100)} ${sym}`
}

export function AdminCreatorDonationsStatsTab() {
  const { t } = useTranslation('admin')
  const [stats, setStats] = useState<StatsData | null>(null)

  const load = useCallback(async () => {
    const r = await apiFetch('/api/admin/creator-donations/stats')
    if (r.ok) setStats((await r.json()) as StatsData)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (!stats) return <p className="muted">{t('creatorDonations.stats.loading')}</p>

  const currencies = Object.keys(stats.totals_by_currency)

  return (
    <div className="admin-donations-stats">
      <div className="admin-donations-kpi-grid">
        <div className="admin-donations-kpi">
          <span>{t('creatorDonations.stats.events')}</span>
          <strong>{stats.events_count}</strong>
        </div>
        <div className="admin-donations-kpi">
          <span>{t('creatorDonations.stats.activeLinks')}</span>
          <strong>{stats.active_links}</strong>
        </div>
        <div className="admin-donations-kpi">
          <span>{t('creatorDonations.stats.openPayouts')}</span>
          <strong>{stats.open_payout_requests}</strong>
        </div>
        <div className="admin-donations-kpi">
          <span>{t('creatorDonations.stats.platformFee')}</span>
          <strong>{stats.platform_fee_percent}%</strong>
        </div>
      </div>

      {currencies.length > 0 ? (
        <div className="admin-donations-summary-table-wrap">
          <table className="admin-donations-table">
            <thead>
              <tr>
                <th>{t('creatorDonations.stats.currency')}</th>
                <th>{t('creatorDonations.stats.total')}</th>
                <th>{t('creatorDonations.stats.toTransfer')}</th>
                <th>{t('creatorDonations.stats.fee')}</th>
                <th>{t('creatorDonations.stats.net')}</th>
              </tr>
            </thead>
            <tbody>
              {currencies.map((cur) => (
                <tr key={cur}>
                  <td>{cur}</td>
                  <td>{formatMinor(stats.totals_by_currency[cur] ?? 0, cur)}</td>
                  <td>{formatMinor(stats.pending_transfer_by_currency[cur] ?? 0, cur)}</td>
                  <td>{formatMinor(stats.platform_fee_by_currency[cur] ?? 0, cur)}</td>
                  <td>{formatMinor(stats.net_to_transfer_by_currency[cur] ?? 0, cur)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <h3>{t('creatorDonations.stats.byCreator')}</h3>
      {stats.creators.length === 0 ? (
        <p className="muted">{t('creatorDonations.stats.noCreators')}</p>
      ) : (
        <div className="admin-donations-summary-table-wrap">
          <table className="admin-donations-table">
            <thead>
              <tr>
                <th>{t('creatorDonations.stats.creator')}</th>
                <th>{t('creatorDonations.stats.total')}</th>
                <th>{t('creatorDonations.stats.toTransfer')}</th>
                <th>{t('creatorDonations.stats.net')}</th>
              </tr>
            </thead>
            <tbody>
              {stats.creators.map((c) => (
                <tr key={c.user_id}>
                  <td>
                    {c.email} <span className="muted">#{c.user_id}</span>
                  </td>
                  <td>
                    {Object.entries(c.totals_by_currency)
                      .map(([cur, v]) => formatMinor(v, cur))
                      .join(' · ') || '—'}
                  </td>
                  <td>
                    {Object.entries(c.pending_by_currency)
                      .map(([cur, v]) => formatMinor(v, cur))
                      .join(' · ') || '—'}
                  </td>
                  <td>
                    {Object.entries(c.net_to_transfer_by_currency)
                      .map(([cur, v]) => formatMinor(v, cur))
                      .join(' · ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
