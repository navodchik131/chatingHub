import { useId, type ChangeEvent, type ReactNode } from 'react'
import { slotIcon } from './studioIcons'

export type StudioSlotIcon = 'image' | 'video' | 'model' | 'prompt' | 'archive'

type Props = {
  label: string
  hint?: string
  icon?: StudioSlotIcon
  className?: string
  /** Превью поверх слота (URL картинки) */
  previewUrl?: string | null
  busy?: boolean
  emptyLabel?: string
  accept?: string
  onFile?: (file: File | null) => void
  onClear?: () => void
  children?: ReactNode
  fullWidth?: boolean
}

export function StudioMediaSlot({
  label,
  hint,
  icon = 'image',
  className = '',
  previewUrl,
  busy,
  emptyLabel = 'Нажмите или перетащите',
  accept,
  onFile,
  onClear,
  children,
  fullWidth,
}: Props) {
  const inputId = useId()
  const hasPreview = Boolean((previewUrl || '').trim())

  return (
    <div
      className={
        'studio-slot' +
        (fullWidth ? ' studio-slot--wide' : '') +
        (hasPreview ? ' studio-slot--filled' : '') +
        (busy ? ' studio-slot--busy' : '') +
        (className ? ` ${className}` : '')
      }
    >
      <div className="studio-slot__head">
        <span className="studio-slot__icon-wrap">{slotIcon(icon)}</span>
        <div className="studio-slot__titles">
          <span className="studio-slot__label">{label}</span>
          {hint ? <span className="studio-slot__hint">{hint}</span> : null}
        </div>
      </div>

      <div className="studio-slot__body">
        {children ?? (
          <>
            {hasPreview ? (
              <img src={previewUrl!} alt="" className="studio-slot__preview" />
            ) : (
              <span className="studio-slot__empty">{busy ? 'Загрузка…' : emptyLabel}</span>
            )}
            {onFile && accept ? (
              <input
                id={inputId}
                type="file"
                className="studio-slot__file"
                accept={accept}
                disabled={busy}
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  onFile(e.target.files?.[0] ?? null)
                  e.target.value = ''
                }}
              />
            ) : null}
            {onFile && accept ? (
              <label htmlFor={inputId} className="studio-slot__hit" aria-label={label} />
            ) : null}
            {hasPreview && onClear ? (
              <button type="button" className="studio-slot__clear" onClick={onClear} aria-label="Убрать">
                ×
              </button>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}
