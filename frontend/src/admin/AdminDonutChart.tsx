import { useTranslation } from 'react-i18next'
import type { AdminGenerationTypeShare } from './types'

const PLAN_COLORS = ['#38BDF8', '#D7F452', '#C084FC', '#4ADE80', '#F0A8C8', '#FB923C', '#818CF8']

export function AdminDonutChart({
  items,
  total,
}: {
  items: AdminGenerationTypeShare[]
  total: number
}) {
  const { t } = useTranslation('admin')
  const sum = Math.max(1, items.reduce((s, i) => s + i.count, 0))
  let cursor = 0
  const stops = items
    .map((item) => {
      const start = cursor
      cursor += (item.count / sum) * 100
      return `${item.color} ${start}% ${cursor}%`
    })
    .join(', ')
  const background = items.length ? `conic-gradient(${stops})` : 'rgba(255,255,255,.08)'

  return (
    <div className="admin-card admin-card--chart">
      <h3 className="admin-card__title">{t('overview.charts.genByType')}</h3>
      <div className="admin-donut-wrap">
        <div className="admin-donut" style={{ background }}>
          <div className="admin-donut__hole">
            <span className="admin-donut__total">{total.toLocaleString('ru-RU')}</span>
            <span className="admin-donut__hint">{t('overview.charts.total')}</span>
          </div>
        </div>
        <ul className="admin-donut__legend">
          {items.map((item) => (
            <li key={item.label}>
              <span className="admin-donut__swatch" style={{ background: item.color }} />
              <span className="admin-donut__name">
                {item.label === 'images'
                  ? t('overview.charts.images')
                  : item.label === 'videos'
                    ? t('overview.charts.videos')
                    : item.label}
              </span>
              <span className="admin-donut__val mono">{item.count.toLocaleString('ru-RU')}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export function AdminShareBars({
  title,
  items,
  emptyHint,
}: {
  title: string
  items: { label: string; count: number; pct?: number; color?: string }[]
  emptyHint?: string
}) {
  const max = Math.max(1, ...items.map((i) => i.count))
  if (items.length === 0) {
    return (
      <div className="admin-card admin-card--chart">
        <h3 className="admin-card__title">{title}</h3>
        <p className="admin-card__empty muted">{emptyHint ?? '—'}</p>
      </div>
    )
  }
  return (
    <div className="admin-card admin-card--chart">
      <h3 className="admin-card__title">{title}</h3>
      <ul className="admin-share-bars">
        {items.map((item, idx) => (
          <li key={item.label}>
            <div className="admin-share-bars__row">
              <span className="admin-share-bars__label">{item.label}</span>
              <span className="admin-share-bars__meta mono">
                {item.count}
                {item.pct != null ? ` · ${item.pct}%` : ''}
              </span>
            </div>
            <div className="admin-share-bars__track">
              <span
                className="admin-share-bars__fill"
                style={{
                  width: `${Math.round((item.count / max) * 100)}%`,
                  background: item.color ?? PLAN_COLORS[idx % PLAN_COLORS.length],
                }}
              />
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
