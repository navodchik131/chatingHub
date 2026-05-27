import { useState, type ReactNode } from 'react'
import {
  studioArchiveIsPending,
  studioArchiveThumbUrl,
  type StudioArchiveItem,
} from '../../studioArchive'
import { StudioArchiveMediaModal } from './StudioArchiveMediaModal'

type Props = {
  title?: string
  lead?: ReactNode
  items: StudioArchiveItem[]
  loading?: boolean
  emptyText?: string
  hasMore?: boolean
  loadingMore?: boolean
  onLoadMore?: () => void
  loadMoreLabel?: string
  onDelete: (item: StudioArchiveItem) => void
  onVideoFromImage?: (item: StudioArchiveItem) => void
}

export function StudioGenerationGallery({
  title = 'История',
  lead,
  items,
  loading,
  emptyText = 'Здесь появятся ваши генерации',
  hasMore,
  loadingMore,
  onLoadMore,
  loadMoreLabel = 'Ещё',
  onDelete,
  onVideoFromImage,
}: Props) {
  const [preview, setPreview] = useState<StudioArchiveItem | null>(null)

  return (
    <section className="studio-gallery" aria-labelledby="studio-gallery-heading">
      <header className="studio-gallery__head">
        <h2 id="studio-gallery-heading">{title}</h2>
        {lead ? <p className="studio-gallery__lead">{lead}</p> : null}
      </header>

      {loading ? (
        <p className="muted studio-gallery__status">Загрузка…</p>
      ) : items.length === 0 ? (
        <p className="muted studio-gallery__status">{emptyText}</p>
      ) : (
        <>
          <ul className="studio-gallery__grid">
            {items.map((g) => {
              const pending = studioArchiveIsPending(g)
              const failed = g.status === 'failed'
              const thumb = studioArchiveThumbUrl(g)
              const videoReady = g.media_kind === 'video' && (g.video_url || '').trim()
              const canOpen =
                !pending &&
                !failed &&
                (g.media_kind === 'image'
                  ? Boolean((g.image_url || '').trim())
                  : Boolean(videoReady))

              return (
                <li
                  key={g.id}
                  className={
                    'studio-gen-card' +
                    (pending ? ' studio-gen-card--processing' : '') +
                    (failed ? ' studio-gen-card--failed' : '')
                  }
                >
                  <button
                    type="button"
                    className="studio-gen-card__media"
                    disabled={!canOpen && !pending}
                    aria-label={canOpen ? 'Открыть результат' : undefined}
                    onClick={() => canOpen && setPreview(g)}
                  >
                    {videoReady ? (
                      <video src={videoReady} muted playsInline preload="metadata" />
                    ) : thumb ? (
                      <img src={thumb} alt="" loading="lazy" />
                    ) : (
                      <span className="studio-gen-card__placeholder" />
                    )}
                    {pending ? (
                      <span className="studio-gen-card__overlay">
                        <span className="studio-archive-spinner" aria-hidden />
                        {g.media_kind === 'video' ? 'Видео…' : 'Генерация…'}
                      </span>
                    ) : null}
                    {failed ? (
                      <span className="studio-gen-card__overlay studio-gen-card__overlay--error">
                        Ошибка
                      </span>
                    ) : null}
                    {canOpen && g.media_kind === 'image' ? (
                      <span className="studio-gen-card__play" aria-hidden>
                        ⤢
                      </span>
                    ) : null}
                    {canOpen && g.media_kind === 'video' ? (
                      <span className="studio-gen-card__play" aria-hidden>
                        ▶
                      </span>
                    ) : null}
                  </button>

                  <button
                    type="button"
                    className="studio-gen-card__del"
                    aria-label={pending ? 'Убрать из истории' : 'Удалить'}
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(g)
                    }}
                  >
                    ×
                  </button>

                  <div className="studio-gen-card__foot">
                    <span className="studio-gen-card__model">{g.model_name ?? 'Без модели'}</span>
                    {g.prompt_excerpt ? (
                      <p className="studio-gen-card__prompt">{g.prompt_excerpt}</p>
                    ) : null}
                    <div className="studio-gen-card__tags">
                      {g.output_aspect ? (
                        <span className="studio-gen-card__tag">{g.output_aspect}</span>
                      ) : null}
                      {g.media_kind === 'video' ? (
                        <span className="studio-gen-card__tag">Видео</span>
                      ) : null}
                      {failed && g.error_message ? (
                        <span className="studio-gen-card__tag studio-gen-card__tag--err">
                          {g.error_message.slice(0, 48)}
                        </span>
                      ) : null}
                    </div>
                    {g.media_kind === 'image' && !pending && !failed && onVideoFromImage ? (
                      <button
                        type="button"
                        className="studio-gen-card__link"
                        onClick={() => onVideoFromImage(g)}
                      >
                        → Видео
                      </button>
                    ) : null}
                  </div>
                </li>
              )
            })}
          </ul>
          {hasMore && onLoadMore ? (
            <div className="studio-gallery__more">
              <button
                type="button"
                className="ghost-btn"
                disabled={loadingMore}
                onClick={onLoadMore}
              >
                {loadingMore ? 'Загрузка…' : loadMoreLabel}
              </button>
            </div>
          ) : null}
        </>
      )}
      <StudioArchiveMediaModal item={preview} onClose={() => setPreview(null)} />
    </section>
  )
}
