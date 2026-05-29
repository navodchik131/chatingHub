import { formatShortDate } from './utils'

export function AdminBarChart({
  title,
  series,
  emptyHint = 'Нет данных за период',
}: {
  title: string
  series: { date: string; count: number }[]
  emptyHint?: string
}) {
  const max = Math.max(1, ...series.map((p) => p.count))
  const total = series.reduce((s, p) => s + p.count, 0)
  if (total === 0) {
    return (
      <div className="admin-chart">
        <h3 className="admin-chart__title">{title}</h3>
        <p className="admin-chart__empty muted">{emptyHint}</p>
      </div>
    )
  }
  return (
    <div className="admin-chart">
      <h3 className="admin-chart__title">
        {title}
        <span className="admin-chart__total muted"> · {total} за период</span>
      </h3>
      <div className="admin-chart__bars" role="img" aria-label={title}>
        {series.map((p) => (
          <div key={p.date} className="admin-chart__bar-wrap" title={`${formatShortDate(p.date)}: ${p.count}`}>
            <div
              className="admin-chart__bar"
              style={{ height: `${Math.max(4, Math.round((p.count / max) * 100))}%` }}
            />
            <span className="admin-chart__bar-val">{p.count > 0 ? p.count : ''}</span>
          </div>
        ))}
      </div>
      <div className="admin-chart__axis">
        <span>{formatShortDate(series[0]?.date ?? '')}</span>
        <span>{formatShortDate(series[Math.floor(series.length / 2)]?.date ?? '')}</span>
        <span>{formatShortDate(series[series.length - 1]?.date ?? '')}</span>
      </div>
    </div>
  )
}

export function AdminHBarChart({
  title,
  items,
}: {
  title: string
  items: { label: string; count: number }[]
}) {
  const max = Math.max(1, ...items.map((i) => i.count))
  if (items.length === 0) {
    return (
      <div className="admin-chart admin-chart--h">
        <h3 className="admin-chart__title">{title}</h3>
        <p className="admin-chart__empty muted">Нет данных</p>
      </div>
    )
  }
  return (
    <div className="admin-chart admin-chart--h">
      <h3 className="admin-chart__title">{title}</h3>
      <ul className="admin-hbars">
        {items.map((item) => (
          <li key={item.label} className="admin-hbars__row">
            <span className="admin-hbars__label" title={item.label}>
              {item.label}
            </span>
            <span className="admin-hbars__track">
              <span
                className="admin-hbars__fill"
                style={{ width: `${Math.round((item.count / max) * 100)}%` }}
              />
            </span>
            <span className="admin-hbars__count mono">{item.count}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
