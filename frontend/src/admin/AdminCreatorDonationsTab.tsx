import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'

interface AdminDonationLink {
  id: number
  user_id: number
  title: string
  description: string | null
  button_text: string | null
  cover_image_url: string | null
  currency: string
  min_amount_minor: number | null
  allow_one_time: boolean
  allow_recurring: boolean
  status: string
  tribute_donation_request_id: number | null
  web_link: string | null
  telegram_link: string | null
  admin_notes_internal: string | null
  created_at: string
  updated_at: string
}

export function AdminCreatorDonationsTab() {
  const { t } = useTranslation('admin')
  const [rows, setRows] = useState<AdminDonationLink[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activateForms, setActivateForms] = useState<
    Record<number, { tributeId: string; webLink: string; tgLink: string }>
  >({})

  const load = useCallback(async () => {
    const r = await apiFetch('/api/admin/creator-donations?status=pending')
    if (r.ok) setRows((await r.json()) as AdminDonationLink[])
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const reject = async (id: number) => {
    const notes = window.prompt(t('creatorDonations.rejectNotesPrompt'))
    if (notes === null) return
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/admin/creator-donations/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ admin_notes: notes || null }),
      })
      if (!r.ok) {
        setError(t('creatorDonations.errors.actionFailed'))
        return
      }
      await load()
    } finally {
      setBusy(false)
    }
  }

  const activate = async (id: number) => {
    const form = activateForms[id] ?? { tributeId: '', webLink: '', tgLink: '' }
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/admin/creator-donations/${id}/activate`, {
        method: 'POST',
        body: JSON.stringify({
          tribute_donation_request_id: Number(form.tributeId),
          web_link: form.webLink.trim(),
          telegram_link: form.tgLink.trim() || null,
        }),
      })
      if (!r.ok) {
        setError(t('creatorDonations.errors.actionFailed'))
        return
      }
      await load()
    } finally {
      setBusy(false)
    }
  }

  const setFormField = (id: number, key: 'tributeId' | 'webLink' | 'tgLink', value: string) => {
    setActivateForms((prev) => ({
      ...prev,
      [id]: {
        tributeId: prev[id]?.tributeId ?? '',
        webLink: prev[id]?.webLink ?? '',
        tgLink: prev[id]?.tgLink ?? '',
        [key]: value,
      },
    }))
  }

  return (
    <div className="admin-panel">
      <h2>{t('creatorDonations.title')}</h2>
      <p className="muted">{t('creatorDonations.intro')}</p>
      {error ? <p className="admin-error">{error}</p> : null}
      {rows.length === 0 ? (
        <p className="muted">{t('creatorDonations.empty')}</p>
      ) : (
        <div className="admin-donation-queue">
          {rows.map((row) => {
            const form = activateForms[row.id] ?? { tributeId: '', webLink: '', tgLink: '' }
            return (
              <article key={row.id} className="admin-donation-card">
                <header>
                  <strong>{row.title}</strong>
                  <span className="mono">user #{row.user_id}</span>
                </header>
                <dl className="admin-donation-meta">
                  <div>
                    <dt>{t('creatorDonations.fields.currency')}</dt>
                    <dd>{row.currency}</dd>
                  </div>
                  <div>
                    <dt>{t('creatorDonations.fields.min')}</dt>
                    <dd>{row.min_amount_minor ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>{t('creatorDonations.fields.oneTime')}</dt>
                    <dd>{row.allow_one_time ? '✓' : '—'}</dd>
                  </div>
                  <div>
                    <dt>{t('creatorDonations.fields.recurring')}</dt>
                    <dd>{row.allow_recurring ? '✓' : '—'}</dd>
                  </div>
                </dl>
                {row.description ? <p>{row.description}</p> : null}
                {row.button_text ? <p className="small muted">Button: {row.button_text}</p> : null}
                {row.cover_image_url ? (
                  <p className="small mono">{row.cover_image_url}</p>
                ) : null}
                <div className="admin-donation-activate">
                  <label>
                    {t('creatorDonations.fields.tributeId')}
                    <input
                      value={form.tributeId}
                      onChange={(e) => setFormField(row.id, 'tributeId', e.target.value)}
                    />
                  </label>
                  <label>
                    {t('creatorDonations.fields.webLink')}
                    <input
                      value={form.webLink}
                      onChange={(e) => setFormField(row.id, 'webLink', e.target.value)}
                    />
                  </label>
                  <label>
                    {t('creatorDonations.fields.tgLink')}
                    <input
                      value={form.tgLink}
                      onChange={(e) => setFormField(row.id, 'tgLink', e.target.value)}
                    />
                  </label>
                </div>
                <div className="admin-actions">
                  <button
                    type="button"
                    className="primary-btn"
                    disabled={busy || !form.tributeId || !form.webLink.trim()}
                    onClick={() => void activate(row.id)}
                  >
                    {t('creatorDonations.activate')}
                  </button>
                  <button type="button" className="ghost-btn" disabled={busy} onClick={() => void reject(row.id)}>
                    {t('creatorDonations.reject')}
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
