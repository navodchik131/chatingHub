import { useTranslation } from 'react-i18next'
import {
  studioArchiveIsPending,
  studioArchiveThumbUrl,
  type StudioArchiveItem,
} from '../../studioArchive'

type Props = {
  label: string
  hint?: string
  items: StudioArchiveItem[]
  value: number | null
  onChange: (id: number | null, item: StudioArchiveItem | null) => void
  /** Только готовые картинки (не видео, не processing) */
  imagesOnly?: boolean
}

export function StudioArchiveThumbPicker({
  label,
  hint,
  items,
  value,
  onChange,
  imagesOnly = true,
}: Props) {
  const { t } = useTranslation('studio')

  const pickable = items.filter((g) => {
    if (imagesOnly && g.media_kind !== 'image') return false
    if (studioArchiveIsPending(g) || g.status === 'failed') return false
    const thumb = studioArchiveThumbUrl(g) || g.image_url
    return Boolean((thumb || '').trim())
  })

  return (
    <div className="studio-archive-picker">
      <div className="studio-slot__head">
        <span className="studio-slot__icon-wrap">
          <svg className="studio-slot__icon-svg" width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path
              d="M4 7h16v12H4V7zM8 3h8v4H8V3z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <div className="studio-slot__titles">
          <span className="studio-slot__label">{label}</span>
          {hint ? <span className="studio-slot__hint">{hint}</span> : null}
        </div>
      </div>

      {pickable.length === 0 ? (
        <p className="studio-archive-picker__empty">{t('archivePicker.empty')}</p>
      ) : (
        <ul className="studio-archive-picker__grid" role="listbox" aria-label={label}>
          <li>
            <button
              type="button"
              role="option"
              aria-selected={value == null}
              className={
                'studio-archive-picker__item studio-archive-picker__item--none' +
                (value == null ? ' is-selected' : '')
              }
              onClick={() => onChange(null, null)}
            >
              <span>—</span>
            </button>
          </li>
          {pickable.map((g) => {
            const thumb = studioArchiveThumbUrl(g) || g.image_url
            const selected = value === g.id
            return (
              <li key={g.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={'studio-archive-picker__item' + (selected ? ' is-selected' : '')}
                  title={g.prompt_excerpt?.trim() || g.model_name || `#${g.id}`}
                  onClick={() => onChange(g.id, g)}
                >
                  <img src={thumb} alt="" loading="lazy" />
                  {g.model_name ? (
                    <span className="studio-archive-picker__cap">{g.model_name}</span>
                  ) : null}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
