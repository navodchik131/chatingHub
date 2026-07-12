import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { formatAppNumber } from '../i18n'

interface PayoutRequestRow {
  id: number
  user_id: number
  user_email: string | null
  source_currency: string
  amount_minor: number
  platform_fee_minor: number
  net_amount_minor: number
  wallet_address: string
  payout_currency: string
  network: string
  status: string
  admin_notes: string | null
  requested_at: string
}

function formatMinor(minor: number, currency: string): string {
  const sym = currency === 'RUB' ? '₽' : currency === 'EUR' ? '€' : '$'
  return `${formatAppNumber(minor / 100)} ${sym}`
}

export function AdminCreatorDonationsPayoutsTab() {
  const { t } = useTranslation('admin')
  const [rows, setRows] = useState<PayoutRequestRow[]>([])
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const r = await apiFetch('/api/admin/creator-donations/payout-requests?limit=100')
    if (r.ok) setRows((await r.json()) as PayoutRequestRow[])
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const updateStatus = async (id: number, status: 'processing' | 'paid' | 'rejected') => {
    const notes =
      status === 'rejected'
        ? window.prompt(t('creatorDonations.payouts.rejectNotes'))
        : null
    if (status === 'rejected' && notes === null) return
    setBusy(true)
    try {
      const r = await apiFetch(`/api/admin/creator-donations/payout-requests/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, admin_notes: notes || null }),
      })
      if (r.ok) await load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-donations-payouts">
      {rows.length === 0 ? (
        <p className="muted">{t('creatorDonations.payouts.empty')}</p>
      ) : (
        <div className="admin-donation-queue">
          {rows.map((row) => (
            <article key={row.id} className="admin-donation-card">
              <header className="admin-donation-card__header">
                <span className="admin-donation-card__title">
                  #{row.id} · {row.user_email ?? `user #${row.user_id}`}
                </span>
                <span className="admin-donation-card__user">
                  {t(`creatorDonations.payoutStatus.${row.status}`, { defaultValue: row.status })}
                </span>
              </header>
              <dl className="admin-donation-meta-grid">
                <div>
                  <dt>{t('creatorDonations.payouts.amount')}</dt>
                  <dd>{formatMinor(row.amount_minor, row.source_currency)}</dd>
                </div>
                <div>
                  <dt>{t('creatorDonations.payouts.fee')}</dt>
                  <dd>{formatMinor(row.platform_fee_minor, row.source_currency)}</dd>
                </div>
                <div>
                  <dt>{t('creatorDonations.payouts.net')}</dt>
                  <dd>{formatMinor(row.net_amount_minor, row.source_currency)}</dd>
                </div>
                <div>
                  <dt>{t('creatorDonations.payouts.wallet')}</dt>
                  <dd className="mono">{row.wallet_address}</dd>
                </div>
                <div>
                  <dt>{t('creatorDonations.payouts.asset')}</dt>
                  <dd>
                    {row.payout_currency} · {row.network}
                  </dd>
                </div>
                <div>
                  <dt>{t('creatorDonations.payouts.requested')}</dt>
                  <dd>{new Date(row.requested_at).toLocaleString()}</dd>
                </div>
              </dl>
              {row.admin_notes ? <p className="admin-donation-text small muted">{row.admin_notes}</p> : null}
              {row.status === 'requested' || row.status === 'processing' ? (
                <div className="admin-donation-actions">
                  {row.status === 'requested' ? (
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={busy}
                      onClick={() => void updateStatus(row.id, 'processing')}
                    >
                      {t('creatorDonations.payouts.markProcessing')}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="primary-btn"
                    disabled={busy}
                    onClick={() => void updateStatus(row.id, 'paid')}
                  >
                    {t('creatorDonations.payouts.markPaid')}
                  </button>
                  <button
                    type="button"
                    className="ghost-btn"
                    disabled={busy}
                    onClick={() => void updateStatus(row.id, 'rejected')}
                  >
                    {t('creatorDonations.payouts.reject')}
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
