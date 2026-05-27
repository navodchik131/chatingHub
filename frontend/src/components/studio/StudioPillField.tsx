import type { ReactNode } from 'react'

export type PillOption<T extends string | number> = {
  value: T
  label: string
  title?: string
}

type Props<T extends string | number> = {
  label: string
  hint?: string
  icon?: ReactNode
  options: PillOption<T>[]
  value: T | null
  onChange: (v: T | null) => void
  allowEmpty?: boolean
  emptyLabel?: string
  /** Горизонтальная прокрутка вместо переноса (формат, много моделей) */
  scrollRow?: boolean
}

export function StudioPillField<T extends string | number>({
  label,
  hint,
  icon,
  options,
  value,
  onChange,
  allowEmpty,
  emptyLabel = '—',
  scrollRow,
}: Props<T>) {
  return (
    <div className="studio-pill-field">
      <div className="studio-slot__head">
        {icon ? <span className="studio-slot__icon-wrap">{icon}</span> : null}
        <div className="studio-slot__titles">
          <span className="studio-slot__label">{label}</span>
          {hint ? <span className="studio-slot__hint">{hint}</span> : null}
        </div>
      </div>
      <div
        className={
          'studio-pill-field__row' + (scrollRow ? ' studio-pill-field__row--scroll' : '')
        }
        role="group"
        aria-label={label}
      >
        {allowEmpty ? (
          <button
            type="button"
            className={'studio-pill' + (value == null ? ' is-active' : '')}
            onClick={() => onChange(null)}
          >
            {emptyLabel}
          </button>
        ) : null}
        {options.map((o) => (
          <button
            key={String(o.value)}
            type="button"
            className={'studio-pill' + (value === o.value ? ' is-active' : '')}
            title={o.title ?? o.label}
            onClick={() => onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}
