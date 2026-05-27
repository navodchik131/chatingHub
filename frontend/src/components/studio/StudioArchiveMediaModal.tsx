import { useCallback, useEffect, useState } from 'react'
import type { StudioArchiveItem } from '../../studioArchive'

type Props = {
  item: StudioArchiveItem | null
  onClose: () => void
}

function preferNativeShareOnMobile(): boolean {
  if (typeof window === 'undefined') return false
  return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
}

async function downloadArchiveMedia(item: StudioArchiveItem): Promise<string | null> {
  const isVideo = item.media_kind === 'video'
  const url = (isVideo ? item.video_url : item.image_url)?.trim()
  if (!url) return 'Нет файла для скачивания.'

  const defaultName = isVideo
    ? `modelmate-video-${item.id}.mp4`
    : `modelmate-image-${item.id}.png`

  if (
    isVideo &&
    preferNativeShareOnMobile() &&
    typeof navigator.share === 'function'
  ) {
    try {
      await navigator.share({ title: 'Видео ModelMate', url })
      return null
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return null
    }
  }

  let blob: Blob | null = null
  try {
    const res = await fetch(url)
    if (res.ok) blob = await res.blob()
  } catch {
    blob = null
  }

  if (blob) {
    const file = new File([blob], defaultName, {
      type: blob.type || (isVideo ? 'video/mp4' : 'image/png'),
    })
    if (
      preferNativeShareOnMobile() &&
      typeof navigator.share === 'function' &&
      typeof navigator.canShare === 'function' &&
      navigator.canShare({ files: [file] })
    ) {
      try {
        await navigator.share({
          files: [file],
          title: isVideo ? 'Видео ModelMate' : 'Изображение',
        })
        return null
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return null
      }
    }
    const objectUrl = URL.createObjectURL(blob)
    try {
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = defaultName
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } finally {
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    }
    return null
  }

  window.open(url, '_blank', 'noopener,noreferrer')
  return isVideo
    ? 'Открыли видео в новой вкладке — сохраните оттуда, если загрузка не началась.'
    : 'Открыли изображение в новой вкладке — сохраните оттуда, если загрузка не началась.'
}

export function StudioArchiveMediaModal({ item, onClose }: Props) {
  const [busy, setBusy] = useState(false)
  const [hint, setHint] = useState<string | null>(null)

  useEffect(() => {
    if (!item) return
    setHint(null)
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
  }, [item, onClose])

  const handleDownload = useCallback(async () => {
    if (!item || busy) return
    setBusy(true)
    setHint(null)
    try {
      const msg = await downloadArchiveMedia(item)
      if (msg) setHint(msg)
    } catch {
      setHint('Не удалось скачать. Попробуйте «Открыть в новой вкладке».')
    } finally {
      setBusy(false)
    }
  }, [item, busy])

  if (!item) return null

  const isVideo = item.media_kind === 'video'
  const mediaUrl = (isVideo ? item.video_url : item.image_url)?.trim()
  if (!mediaUrl) return null

  return (
    <div
      className="studio-archive-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="studio-archive-modal-title"
      onClick={onClose}
    >
      <div className="studio-archive-modal__panel" onClick={(e) => e.stopPropagation()}>
        <header className="studio-archive-modal__head">
          <div className="studio-archive-modal__titles">
            <h3 id="studio-archive-modal-title">{item.model_name ?? 'Результат'}</h3>
            {item.prompt_excerpt ? (
              <p className="studio-archive-modal__prompt">{item.prompt_excerpt}</p>
            ) : null}
          </div>
          <button
            type="button"
            className="studio-archive-modal__close"
            aria-label="Закрыть"
            onClick={onClose}
          >
            ×
          </button>
        </header>

        <div className="studio-archive-modal__media">
          {isVideo ? (
            <video src={mediaUrl} controls autoPlay playsInline />
          ) : (
            <img src={mediaUrl} alt="" />
          )}
        </div>

        <footer className="studio-archive-modal__actions">
          <button
            type="button"
            className="send-btn"
            disabled={busy}
            onClick={() => void handleDownload()}
          >
            {busy ? 'Сохранение…' : 'Скачать'}
          </button>
          <a
            className="ghost-btn"
            href={mediaUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            В новой вкладке
          </a>
        </footer>
        {hint ? <p className="studio-archive-modal__hint muted">{hint}</p> : null}
      </div>
    </div>
  )
}
