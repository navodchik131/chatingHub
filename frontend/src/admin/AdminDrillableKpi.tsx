import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export function AdminDrillableKpi({
  segment,
  title,
  count,
  onDrill,
  className = '',
  children,
}: {
  segment: string
  title: string
  count: number
  onDrill: (segment: string, title: string) => void
  className?: string
  children: ReactNode
}) {
  const { t } = useTranslation('admin')
  const clickable = count > 0
  if (!clickable) {
    return <div className={`admin-kpi ${className}`}>{children}</div>
  }
  return (
    <button
      type="button"
      className={`admin-kpi admin-kpi--clickable ${className}`}
      onClick={() => onDrill(segment, title)}
      title={t('drill.showList')}
    >
      {children}
    </button>
  )
}

export function AdminDrillLink({
  segment,
  title,
  count,
  onDrill,
  children,
}: {
  segment: string
  title: string
  count: number
  onDrill: (segment: string, title: string) => void
  children: ReactNode
}) {
  if (count <= 0) return <span>{children}</span>
  return (
    <button
      type="button"
      className="admin-drill-link"
      onClick={(e) => {
        e.stopPropagation()
        onDrill(segment, title)
      }}
    >
      {children}
    </button>
  )
}
