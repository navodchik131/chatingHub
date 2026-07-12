import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { formatAppNumber } from '../i18n'

interface DonationEventRow {
  id: number
  user_id: number
  user_email: string | null
  link_title: string
  amount_minor: number
  currency: string
  platform_fee_minor: number
  net_amount_minor: number
  payer_telegram_user_id: number | null
  payout_status: string
  occurred_at: string
}

function formatMinor(minor: number, currency: string): string {
  const sym = currency === 'RUB' ? '₽' : currency === 'EUR' ? '€' : '$'
  return `${formatAppNumber(minor / 100)} ${sym}`
}

export function AdminCreatorDonationsEventsTab() {
  const { t } = useTranslation('admin')
  const [rows, setRows] = useState<DonationEventRow[]>([])

  const load = useCallback(async () => {
    const r = await apiFetch('/api/admin/creator-donations/events?limit=200')
    if (r.ok) setRows((await r.json()) as DonationEventRow[])
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="admin-donations-events">
      {rows.length === 0 ? (
        <p className="muted">{t('creatorDonations.events.empty')}</p>
      ) : (
        <div className="admin-donations-summary-table-wrap">
          <table className="admin-donations-table">
            <thead>
              <tr>
                <th>{t('creatorDonations.events.date')}</th>
                <th>{t('creatorDonations.events.creator')}</th>
                <th>{t('creatorDonations.events.donation')}</th>
                <th>{t('creatorDonations.events.amount')}</th>
                <th>{t('creatorDonations.events.fee')}</th>
                <th>{t('creatorDonations.events.net')}</th>
                <th>{t('creatorDonations.events.payer')}</th>
                <th>{t('creatorDonations.events.status')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{new Date(row.occurred_at).toLocaleString()}</td>
                  <td>
                    {row.user_email ?? `#${row.user_id}`}
                  </td>
                  <td>{row.link_title}</td>
                  <td>{formatMinor(row.amount_minor, row.currency)}</td>
                  <td>{formatMinor(row.platform_fee_minor, row.currency)}</td>
                  <td>{formatMinor(row.net_amount_minor, row.currency)}</td>
                  <td className="mono">
                    {row.payer_telegram_user_id != null ? `tg:${row.payer_telegram_user_id}` : '—'}
                  </td>
                  <td>{t(`creatorDonations.payoutStatus.${row.payout_status}`, { defaultValue: row.payout_status })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
