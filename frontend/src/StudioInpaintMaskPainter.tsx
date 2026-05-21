import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  type PointerEvent,
} from 'react'

/** PNG-маска: чёрное = сохранить, белое = зона inpaint (совпадает с пикселями превью). */

export type StudioInpaintMaskPainterRef = {
  getMaskFile: () => Promise<File | null>
  clearMask: () => void
  hasPaint: () => boolean
}

type Props = {
  imageSrc: string | null
  enabled: boolean
  brushSize: 's' | 'm' | 'l'
  onPaintStateChange?: (hasPaint: boolean) => void
}

const BRUSH_MUL: Record<Props['brushSize'], number> = { s: 0.011, m: 0.02, l: 0.035 }

function noopPaint(_has: boolean) {}

function fillCanvasBlack(ctx: CanvasRenderingContext2D, w: number, h: number) {
  ctx.save()
  ctx.globalCompositeOperation = 'source-over'
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, w, h)
  ctx.restore()
}

export const StudioInpaintMaskPainter = forwardRef<StudioInpaintMaskPainterRef, Props>(
  function StudioInpaintMaskPainter(
    { imageSrc, enabled, brushSize: brushPreset, onPaintStateChange = noopPaint },
    ref,
  ) {
    const wrapRef = useRef<HTMLDivElement>(null)
    const imgRef = useRef<HTMLImageElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const paintingRef = useRef(false)
    const hasPaintRef = useRef(false)
    const lastRef = useRef<{ x: number; y: number } | null>(null)
    const brushRadiusRef = useRef(12)
    /** Смена этого ключа сбрасывает буфер маски (новый файл / другой архивный снимок / другой размер). */
    const bufferKeyRef = useRef<string>('')

    const matchCanvasCssToImg = useCallback(() => {
      const img = imgRef.current
      const canvas = canvasRef.current
      if (!img || !canvas) return
      canvas.style.width = `${img.clientWidth}px`
      canvas.style.height = `${img.clientHeight}px`
    }, [])

    /** После загрузки / смены imageSrc или реальных px картинки. */
    const initBufferIfNeeded = useCallback(() => {
      const img = imgRef.current
      const canvas = canvasRef.current
      if (!img || !canvas || !img.complete || !img.naturalWidth || !img.naturalHeight)
        return

      const nw = img.naturalWidth
      const nh = img.naturalHeight
      const key = `${imageSrc ?? ''}@${nw}x${nh}`
      brushRadiusRef.current = Math.max(6, Math.round(Math.min(nw, nh) * BRUSH_MUL[brushPreset]))

      if (bufferKeyRef.current !== key) {
        bufferKeyRef.current = key
        canvas.width = nw
        canvas.height = nh
        const ctx = canvas.getContext('2d')
        if (!ctx) return
        fillCanvasBlack(ctx, nw, nh)
        hasPaintRef.current = false
        lastRef.current = null
        onPaintStateChange(false)
      }
      matchCanvasCssToImg()
    }, [brushPreset, imageSrc, matchCanvasCssToImg, onPaintStateChange])

    const notifyPaint = useCallback(() => {
      if (!hasPaintRef.current) {
        hasPaintRef.current = true
        onPaintStateChange(true)
      }
    }, [onPaintStateChange])

    const strokeTo = useCallback(
      (x: number, y: number) => {
        const canvas = canvasRef.current
        if (!canvas || !canvas.width) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return

        ctx.save()
        ctx.globalCompositeOperation = 'source-over'
        ctx.strokeStyle = '#ffffff'
        ctx.fillStyle = '#ffffff'
        ctx.lineWidth = brushRadiusRef.current * 2
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'

        const last = lastRef.current
        if (last != null) {
          ctx.beginPath()
          ctx.moveTo(last.x, last.y)
          ctx.lineTo(x, y)
          ctx.stroke()
        } else {
          ctx.beginPath()
          ctx.arc(x, y, brushRadiusRef.current, 0, Math.PI * 2)
          ctx.fill()
        }
        lastRef.current = { x, y }
        ctx.restore()
        notifyPaint()
      },
      [notifyPaint],
    )

    const eventToCanvas = useCallback((e: PointerEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current
      if (!canvas) return null
      const rect = canvas.getBoundingClientRect()
      if (rect.width < 1 || rect.height < 1) return null
      const sx = canvas.width / rect.width
      const sy = canvas.height / rect.height
      return {
        x: (e.clientX - rect.left) * sx,
        y: (e.clientY - rect.top) * sy,
      }
    }, [])

    const clearMask = useCallback(() => {
      const canvas = canvasRef.current
      if (!canvas || !canvas.width) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      fillCanvasBlack(ctx, canvas.width, canvas.height)
      hasPaintRef.current = false
      lastRef.current = null
      onPaintStateChange(false)
    }, [onPaintStateChange])

    useImperativeHandle(
      ref,
      () => ({
        clearMask,
        hasPaint: () => hasPaintRef.current,
        getMaskFile: () =>
          new Promise((resolve) => {
            const canvas = canvasRef.current
            if (!canvas || !canvas.width || !hasPaintRef.current) {
              resolve(null)
              return
            }
            canvas.toBlob(
              (blob) => {
                if (!blob) {
                  resolve(null)
                  return
                }
                resolve(new File([blob], 'inpaint-mask.png', { type: 'image/png' }))
              },
              'image/png',
              1,
            )
          }),
      }),
      [clearMask],
    )

    /** Сменили толщину кисти — пересчитать радиус, буфер не трогаем. */
    useEffect(() => {
      const canvas = canvasRef.current
      if (!canvas?.width || !canvas.height) return
      const nw = canvas.width
      const nh = canvas.height
      brushRadiusRef.current = Math.max(
        6,
        Math.round(Math.min(nw, nh) * BRUSH_MUL[brushPreset]),
      )
    }, [brushPreset])

      if (!enabled || !imageSrc) return
      const wrap = wrapRef.current
      if (!wrap || typeof ResizeObserver === 'undefined') return
      const ro = new ResizeObserver(() => matchCanvasCssToImg())
      ro.observe(wrap)
      return () => ro.disconnect()
    }, [enabled, imageSrc, matchCanvasCssToImg])

    useEffect(() => {
      if (!enabled) {
        paintingRef.current = false
        lastRef.current = null
      }
    }, [enabled])

    if (!imageSrc) return null

    return (
      <div
        ref={wrapRef}
        className={`studio-inpaint-mask-painter${enabled ? ' is-enabled' : ''}`}
      >
        <p className="muted studio-mask-painter-hint">
          Белым закрасьте участок, который нужно заменить по описанию ниже; чёрное на маске (всё вокруг) не
          трогаем. Если что-то сбились — «Очистить маску».
        </p>
        <div className="studio-mask-painter-frame">
          <img
            ref={imgRef}
            src={imageSrc}
            alt=""
            className="studio-mask-painter-img"
            draggable={false}
            decoding="async"
            onLoad={initBufferIfNeeded}
          />
          <canvas
            ref={canvasRef}
            className="studio-mask-painter-canvas"
            width={1}
            height={1}
            aria-label="Область рисования маски inpaint"
            style={{
              visibility: enabled ? 'visible' : 'hidden',
              pointerEvents: enabled ? 'auto' : 'none',
            }}
            onPointerDown={(e) => {
              if (!enabled) return
              e.preventDefault()
              ;(e.currentTarget as HTMLCanvasElement).setPointerCapture(e.pointerId)
              paintingRef.current = true
              lastRef.current = null
              const p = eventToCanvas(e)
              if (p) strokeTo(p.x, p.y)
            }}
            onPointerMove={(e) => {
              if (!enabled || !paintingRef.current) return
              e.preventDefault()
              const p = eventToCanvas(e)
              if (p) strokeTo(p.x, p.y)
            }}
            onPointerUp={(e) => {
              if (!enabled) return
              paintingRef.current = false
              lastRef.current = null
              try {
                ;(e.currentTarget as HTMLCanvasElement).releasePointerCapture(e.pointerId)
              } catch {
                /* noop */
              }
            }}
            onPointerCancel={(e) => {
              paintingRef.current = false
              lastRef.current = null
              try {
                ;(e.currentTarget as HTMLCanvasElement).releasePointerCapture(e.pointerId)
              } catch {
                /* noop */
              }
            }}
          />
        </div>
      </div>
    )
  }
)
