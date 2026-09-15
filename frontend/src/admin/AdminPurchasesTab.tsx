import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { formatAppNumber } from '../i18n'

interface PurchaseRow {
  id: number
  user_id: number
  user_email: string | null
  created_at: string
  purchase_type: string
  product_label: string
  payment_provider: string
  amount_rub: number
  credits_quantity: number | null
  credits_granted: number | null
  payment_ref: string | null
}

interface PurchasesResponse {
  items: PurchaseRow[]
  has_more: boolean
  skip: number
  summary: {
    total_count: number
    total_amount_rub: number
    subscription_count: number
    credits_count: number
  }
}

function defaultFromDate(): string {
  const d = new Date()
  d.setDate(d.getDate() - 30)
  return d.toISOString().slice(0, 10)
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

const PAGE = 100

export function AdminPurchasesTab() {
  const { t } = useTranslation('admin')
  const [fromDate, setFromDate] = useState(defaultFromDate)
  const [toDate, setToDate] = useState(todayIso)
  const [rows, setRows] = useState<PurchaseRow[]>([])
  const [summary, setSummary] = useState<PurchasesResponse['summary'] | null>(null)
  const [skip, setSkip] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(
    async (nextSkip: number, replace: boolean) => {
      setLoading(true)
      setError(null)
      const q = new URLSearchParams()
      q.set('from', fromDate)
      q.set('to', toDate)
      q.set('skip', String(nextSkip))
      q.set('limit', String(PAGE))
      const r = await apiFetch(`/api/admin/purchases?${q}`)
      setLoading(false)
      if (!r.ok) {
        setError(t('purchases.loadFailed'))
        return
      }
      const data = (await r.json()) as PurchasesResponse
      setSummary(data.summary)
      setHasMore(data.has_more)
      setSkip(nextSkip)
      setRows((prev) => (replace ? data.items : [...prev, ...data.items]))
    },
    [fromDate, toDate, t],
  )

  useEffect(() => {
    void load(0, true)
  }, [load])

  const typeLabel = useCallback(
    (pt: string) => t(`purchases.types.${pt}`, { defaultValue: pt }),
    [t],
  )

  const providerLabel = useCallback(
    (p: string) => t(`purchases.providers.${p}`, { defaultValue: p }),
    [t],
  )

  const kpi = useMemo(() => {
    if (!summary) return null
    return [
      { label: t('purchases.summaryCount'), value: String(summary.total_count) },
      {
        label: t('purchases.summaryAmount'),
        value: `${formatAppNumber(summary.total_amount_rub)} ₽`,
      },
      { label: t('purchases.summarySubscriptions'), value: String(summary.subscription_count) },
      { label: t('purchases.summaryCredits'), value: String(summary.credits_count) },
    ]
  }, [summary, t])

  return (
    <div className="admin-purchases admin-fade-in">
      <div className="admin-user-toolbar" style={{ marginBottom: 16 }}>
        <label className="admin-purchases__date-label">
          <span className="muted small">{t('purchases.from')}</span>
          <input
            type="date"
            className="admin-user-search"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
          />
        </label>
        <label className="admin-purchases__date-label">
          <span className="muted small">{t('purchases.to')}</span>
          <input
            type="date"
            className="admin-user-search"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="ghost-btn"
          disabled={loading}
          onClick={() => void load(0, true)}
        >
          {t('purchases.apply')}
        </button>
      </div>

      {error ? (
        <div className="admin-banner admin-banner--error" role="alert">
          {error}
        </div>
      ) : null}

      {kpi ? (
        <div className="admin-kpi-grid" style={{ marginBottom: 16 }}>
          {kpi.map((k) => (
            <div key={k.label} className="admin-card admin-kpi">
              <div className="muted small">{k.label}</div>
              <div style={{ fontWeight: 700, fontSize: 18, marginTop: 4 }}>{k.value}</div>
            </div>
          ))}
        </div>
      ) : null}

      {rows.length === 0 && !loading ? (
        <p className="muted">{t('purchases.empty')}</p>
      ) : (
        <div className="admin-donations-summary-table-wrap admin-card">
          <table className="admin-donations-table">
            <thead>
              <tr>
                <th>{t('purchases.colDate')}</th>
                <th>{t('purchases.colUser')}</th>
                <th>{t('purchases.colType')}</th>
                <th>{t('purchases.colProduct')}</th>
                <th>{t('purchases.colProvider')}</th>
                <th>{t('purchases.colAmount')}</th>
                <th>{t('purchases.colCredits')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{new Date(row.created_at).toLocaleString()}</td>
                  <td>{row.user_email || `#${row.user_id}`}</td>
                  <td>{typeLabel(row.purchase_type)}</td>
                  <td>{row.product_label}</td>
                  <td>{providerLabel(row.payment_provider)}</td>
                  <td>
                    {row.amount_rub > 0
                      ? `${formatAppNumber(row.amount_rub)} ₽`
                      : '—'}
                  </td>
                  <td className="mono">
                    {row.credits_granted != null
                      ? formatAppNumber(row.credits_granted)
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasMore ? (
        <div style={{ marginTop: 12, textAlign: 'center' }}>
          <button
            type="button"
            className="ghost-btn"
            disabled={loading}
            onClick={() => void load(skip + PAGE, false)}
          >
            {t('purchases.loadMore')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
