import { useTranslation } from 'react-i18next'
import type { AdminMonthRevenue } from './types'
import { formatRub } from './utils'

export function AdminRevenueChart({ series }: { series: AdminMonthRevenue[] }) {
  const { t } = useTranslation('admin')
  const max = Math.max(1, ...series.map((p) => p.amount_rub))
  const total = series.reduce((s, p) => s + p.amount_rub, 0)

  return (
    <div className="admin-card admin-card--chart">
      <div className="admin-card__head">
        <h3 className="admin-card__title">{t('overview.charts.revenueByMonth')}</h3>
        <span className="admin-card__meta">{t('overview.charts.last12mo')}</span>
      </div>
      {total === 0 ? (
        <p className="admin-card__empty muted">{t('overview.charts.noDataPeriod')}</p>
      ) : (
        <div className="admin-revenue-bars" role="img" aria-label={t('overview.charts.revenueByMonth')}>
          {series.map((p) => (
            <div key={p.month} className="admin-revenue-bars__col" title={`${p.label}: ${formatRub(p.amount_rub)}`}>
              <span className="admin-revenue-bars__label">{p.label}</span>
              <div
                className="admin-revenue-bars__bar"
                style={{ height: `${Math.max(6, Math.round((p.amount_rub / max) * 100))}%` }}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
