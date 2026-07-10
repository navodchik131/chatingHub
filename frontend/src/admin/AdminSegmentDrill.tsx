import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { billingPlanLabel, planTierLabel, subscriptionStatusLabel } from './constants'
import type { AdminSegmentItem, AdminSegmentResponse } from './types'
import { formatDateTimeRu } from './utils'

interface AdminSegmentDrillProps {
  segment: string | null
  title: string
  onClose: () => void
  onSelectUser: (userId: number) => void
}

export function AdminSegmentDrill({ segment, title, onClose, onSelectUser }: AdminSegmentDrillProps) {
  const { t } = useTranslation('admin')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<AdminSegmentResponse | null>(null)

  useEffect(() => {
    if (!segment) {
      setData(null)
      setError(null)
      return
    }
    setLoading(true)
    setError(null)
    void (async () => {
      const r = await apiFetch(
        `/api/admin/stats/segment?segment=${encodeURIComponent(segment)}&limit=200`,
      )
      if (!r.ok) {
        const err = (await r.json().catch(() => ({}))) as { detail?: string }
        setError(typeof err.detail === 'string' ? err.detail : t('drill.error', { status: r.status }))
        setData(null)
        setLoading(false)
        return
      }
      setData((await r.json()) as AdminSegmentResponse)
      setLoading(false)
    })()
  }, [segment, t])

  if (!segment) return null

  return (
    <div className="admin-drill-backdrop" role="presentation" onClick={onClose}>
      <div
        className="admin-drill"
        role="dialog"
        aria-labelledby="admin-drill-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="admin-drill__header">
          <div>
            <h2 id="admin-drill-title" className="admin-drill__title">
              {data?.title ?? title}
            </h2>
            {data ? (
              <p className="admin-drill__sub muted">
                {data.total !== data.items.length
                  ? t('drill.shownOf', { shown: data.items.length, total: data.total })
                  : t('drill.shownSimple', { shown: data.items.length })}
              </p>
            ) : null}
          </div>
          <button type="button" className="admin-drill__close" onClick={onClose} aria-label={t('common.close')}>
            ✕
          </button>
        </header>

        {loading ? <p className="admin-drill__loading muted">{t('common.loading')}</p> : null}
        {error ? (
          <p className="admin-drill__error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && !error && data && data.items.length === 0 ? (
          <p className="muted">{t('common.noRecords')}</p>
        ) : null}

        {!loading && !error && data && data.items.length > 0 ? (
          <div className="admin-drill__table-wrap">
            <table className="admin-drill__table">
              <thead>
                <tr>
                  <th>{t('common.id')}</th>
                  <th>{t('common.email')}</th>
                  <th>{t('common.subscription')}</th>
                  <th>{t('common.details')}</th>
                  <th>{t('common.date')}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row, idx) => (
                  <SegmentRow
                    key={row.payment_id ? `pay-${row.payment_id}` : `u-${row.user_id ?? idx}`}
                    row={row}
                    onSelectUser={onSelectUser}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function SegmentRow({
  row,
  onSelectUser,
}: {
  row: AdminSegmentItem
  onSelectUser: (userId: number) => void
}) {
  const clickable = row.user_id != null
  const sub =
    row.subscription_status != null
      ? `${subscriptionStatusLabel(row.subscription_status)} · ${billingPlanLabel(row.billing_plan ?? 'managed')} · ${planTierLabel(row.plan_tier)}`
      : '—'

  return (
    <tr
      className={clickable ? 'admin-drill__row--clickable' : ''}
      onClick={() => {
        if (row.user_id != null) onSelectUser(row.user_id)
      }}
    >
      <td className="mono">{row.user_id ?? '—'}</td>
      <td>
        {row.email ?? '—'}
        {row.payment_id ? (
          <div className="muted small mono">pay {row.payment_id.slice(0, 12)}…</div>
        ) : null}
      </td>
      <td className="small">{sub}</td>
      <td className="small">{row.detail ?? '—'}</td>
      <td className="small muted">{formatDateTimeRu(row.occurred_at ?? row.user_created_at)}</td>
    </tr>
  )
}
