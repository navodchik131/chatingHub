import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'

interface AdminReferenceRow {
  id: number
  user_id: number
  title: string | null
  tags: string[]
  upload_batch_id: string | null
  media_type: string
  moderation_status: string
  admin_notes: string | null
  preview_url: string
  created_at: string
}

function ReferencePreview({ row }: { row: AdminReferenceRow }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    let cancelled = false
    void apiFetch(row.preview_url).then(async (r) => {
      if (!r.ok || cancelled) return
      objectUrl = URL.createObjectURL(await r.blob())
      if (!cancelled) setUrl(objectUrl)
    })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [row.preview_url])

  if (!url) {
    return <div className="admin-ref-card__placeholder muted">…</div>
  }
  if (row.media_type === 'video') {
    return <video src={url} controls muted playsInline className="admin-ref-card__media" />
  }
  return <img src={url} alt="" className="admin-ref-card__media" />
}

export function AdminReferencesTab() {
  const { t } = useTranslation('admin')
  const [rows, setRows] = useState<AdminReferenceRow[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const r = await apiFetch('/api/admin/references?status=pending')
    if (r.ok) setRows((await r.json()) as AdminReferenceRow[])
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const approve = async (id: number) => {
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/admin/references/${id}/approve`, { method: 'POST' })
      if (!r.ok) {
        setError(t('references.errors.actionFailed'))
        return
      }
      await load()
    } finally {
      setBusy(false)
    }
  }

  const reject = async (id: number) => {
    const notes = window.prompt(t('references.rejectNotesPrompt'))
    if (notes === null) return
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/admin/references/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ admin_notes: notes || null }),
      })
      if (!r.ok) {
        setError(t('references.errors.actionFailed'))
        return
      }
      await load()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-ref">
      <div className="admin-ref__head">
        <div>
          <h2 className="admin-ref__title">{t('references.title')}</h2>
          <p className="admin-ref__hint muted">{t('references.hint')}</p>
        </div>
        <button type="button" className="admin-btn admin-btn--ghost" disabled={busy} onClick={() => void load()}>
          {t('common.refresh')}
        </button>
      </div>

      {error ? <div className="admin-alert admin-alert--error">{error}</div> : null}

      {!rows.length ? (
        <div className="admin-ref__empty muted">{t('references.empty')}</div>
      ) : (
        <div className="admin-ref__grid">
          {rows.map((row) => (
            <article key={row.id} className="admin-ref-card">
              <ReferencePreview row={row} />
              <div className="admin-ref-card__body">
                <div className="admin-ref-card__meta">
                  <span>#{row.id}</span>
                  <span>{t('references.user')} #{row.user_id}</span>
                  <span>{row.media_type}</span>
                </div>
                {!!row.tags?.length && (
                  <div className="admin-ref-card__tags">
                    {row.tags.map((tag) => (
                      <span key={tag} className="admin-ref-card__tag">{tag}</span>
                    ))}
                  </div>
                )}
                <div className="admin-ref-card__actions">
                  <button type="button" className="admin-btn admin-btn--primary" disabled={busy} onClick={() => void approve(row.id)}>
                    {t('references.approve')}
                  </button>
                  <button type="button" className="admin-btn admin-btn--danger" disabled={busy} onClick={() => void reject(row.id)}>
                    {t('references.reject')}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
