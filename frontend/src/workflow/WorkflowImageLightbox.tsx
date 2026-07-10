import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createPortal } from 'react-dom'

type Props = {
  imageUrl: string | null
  alt?: string
  onClose: () => void
}

export function WorkflowImageLightbox({ imageUrl, alt, onClose }: Props) {
  const { t } = useTranslation('workflow')
  const resolvedAlt = alt ?? t('nodeUi.lightbox.defaultAlt')
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null)

  useEffect(() => {
    if (!imageUrl) return
    setScale(1)
    setOffset({ x: 0, y: 0 })
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [imageUrl, onClose])

  const zoomBy = useCallback((delta: number) => {
    setScale((s) => Math.min(4, Math.max(0.5, s + delta)))
  }, [])

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? -0.15 : 0.15
    setScale((s) => Math.min(4, Math.max(0.5, s + delta)))
  }, [])

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (scale <= 1) return
      dragRef.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y }
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    },
    [offset.x, offset.y, scale],
  )

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    const d = dragRef.current
    if (!d) return
    setOffset({
      x: d.ox + (e.clientX - d.x),
      y: d.oy + (e.clientY - d.y),
    })
  }, [])

  const onPointerUp = useCallback(() => {
    dragRef.current = null
  }, [])

  if (!imageUrl) return null

  return createPortal(
    <div
      className="workflow-lightbox"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div className="workflow-lightbox__toolbar" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="workflow-lightbox__btn" onClick={() => zoomBy(-0.25)}>
          −
        </button>
        <span className="workflow-lightbox__zoom">{Math.round(scale * 100)}%</span>
        <button type="button" className="workflow-lightbox__btn" onClick={() => zoomBy(0.25)}>
          +
        </button>
        <button type="button" className="workflow-lightbox__btn" onClick={() => setScale(1)}>
          {t('nodeUi.lightbox.reset')}
        </button>
        <button type="button" className="workflow-lightbox__close" onClick={onClose} aria-label={t('nodeUi.lightbox.close')}>
          ×
        </button>
      </div>
      <div
        className="workflow-lightbox__stage"
        onWheel={onWheel}
        onClick={(e) => e.stopPropagation()}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <img
          src={imageUrl}
          alt={resolvedAlt}
          className="workflow-lightbox__img"
          style={{
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
          }}
          draggable={false}
        />
      </div>
    </div>,
    document.body,
  )
}
