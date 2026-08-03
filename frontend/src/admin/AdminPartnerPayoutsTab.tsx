import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { formatAppNumber } from '../i18n'

interface PartnerPayoutRow {
  id: number
  user_id: number
  user_email: string | null
  amount_kopecks: number
  status: string
  wallet_address: string
  payout_currency: string
  payout_asset: string
  network: string
  admin_note: string | null
  requested_at: string | null
  processed_at: string | null
}

function formatKopecks(kopecks: number): string {
  return `${formatAppNumber(kopecks / 100)} ₽`
}

export function AdminPartnerPayoutsTab() {
  const { t } = useTranslation('admin')
  const [rows, setRows] = useState<PartnerPayoutRow[]>([])
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const r = await apiFetch('/api/admin/partner/payout-requests?limit=100')
    if (r.ok) setRows((await r.json()) as PartnerPayoutRow[])
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const updateStatus = async (id: number, status: 'processing' | 'paid' | 'rejected') => {
    const notes =
      status === 'rejected'
        ? window.prompt(t('partners.payouts.rejectNotes'))
        : null
    if (status === 'rejected' && notes === null) return
    setBusy(true)
    try {
      const r = await apiFetch(`/api/admin/partner/payout-requests/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, admin_notes: notes || null }),
      })
      if (r.ok) await load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-donations-payouts">
      <p className="muted admin-section-lead">{t('partners.payouts.lead')}</p>
      {rows.length === 0 ? (
        <p className="muted">{t('partners.payouts.empty')}</p>
      ) : (
        <div className="admin-donation-queue">
          {rows.map((row) => (
            <article key={row.id} className="admin-donation-card">
              <header className="admin-donation-card__header">
                <span className="admin-donation-card__title">
                  #{row.id} · {row.user_email ?? `user #${row.user_id}`}
                </span>
                <span className="admin-donation-card__user">
                  {t(`partners.payoutStatus.${row.status}`, { defaultValue: row.status })}
                </span>
              </header>
              <dl className="admin-donation-meta-grid">
                <div>
                  <dt>{t('partners.payouts.amount')}</dt>
                  <dd>{formatKopecks(row.amount_kopecks)}</dd>
                </div>
                <div>
                  <dt>{t('partners.payouts.wallet')}</dt>
                  <dd className="mono">{row.wallet_address}</dd>
                </div>
                <div>
                  <dt>{t('partners.payouts.asset')}</dt>
                  <dd>
                    {row.payout_asset} · {row.payout_currency} · {row.network}
                  </dd>
                </div>
                <div>
                  <dt>{t('partners.payouts.requested')}</dt>
                  <dd>{row.requested_at ? new Date(row.requested_at).toLocaleString() : '—'}</dd>
                </div>
              </dl>
              {row.admin_note ? <p className="admin-donation-text small muted">{row.admin_note}</p> : null}
              {row.status === 'requested' || row.status === 'processing' ? (
                <div className="admin-donation-actions">
                  {row.status === 'requested' ? (
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={busy}
                      onClick={() => void updateStatus(row.id, 'processing')}
                    >
                      {t('partners.payouts.markProcessing')}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="primary-btn"
                    disabled={busy}
                    onClick={() => void updateStatus(row.id, 'paid')}
                  >
                    {t('partners.payouts.markPaid')}
                  </button>
                  <button
                    type="button"
                    className="ghost-btn"
                    disabled={busy}
                    onClick={() => void updateStatus(row.id, 'rejected')}
                  >
                    {t('partners.payouts.reject')}
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
