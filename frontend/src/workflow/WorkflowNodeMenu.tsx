import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

type Props = {
  disabled: boolean
  onToggleDisabled: () => void
  onDelete: () => void
}

export function WorkflowNodeMenu({ disabled, onToggleDisabled, onDelete }: Props) {
  const { t } = useTranslation('workflow')
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  const close = useCallback(() => setOpen(false), [])

  useEffect(() => {
    if (!open) return
    const onDocClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close()
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [close, open])

  return (
    <div className="workflow-node-menu nodrag" ref={rootRef}>
      <button
        type="button"
        className="workflow-node-menu__trigger"
        aria-label={t('menu.aria')}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        ⋮
      </button>
      {open ? (
        <div className="workflow-node-menu__dropdown" role="menu">
          <button
            type="button"
            className="workflow-node-menu__item"
            role="menuitem"
            onClick={() => {
              onToggleDisabled()
              close()
            }}
          >
            {disabled ? t('menu.enable') : t('menu.disable')}
          </button>
          <button
            type="button"
            className="workflow-node-menu__item workflow-node-menu__item--danger"
            role="menuitem"
            onClick={() => {
              onDelete()
              close()
            }}
          >
            {t('menu.delete')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
