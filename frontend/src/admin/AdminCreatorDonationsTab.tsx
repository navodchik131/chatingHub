import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import '../styles/donations-ui.css'

interface AdminDonationLink {
  id: number
  user_id: number
  title: string
  description: string | null
  button_text: string | null
  cover_image_url: string | null
  has_cover?: boolean
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

interface TributeProduct {
  id: number
  type: string | null
  name: string | null
  amount: number | null
  currency: string | null
  web_link: string | null
  telegram_link: string | null
  status: string | null
}

function DonationCoverPreview({ linkId, hasCover }: { linkId: number; hasCover: boolean }) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!hasCover) {
      setUrl(null)
      return undefined
    }
    let objectUrl: string | null = null
    let cancelled = false
    void apiFetch(`/api/admin/creator-donations/${linkId}/cover`).then(async (r) => {
      if (!r.ok || cancelled) return
      objectUrl = URL.createObjectURL(await r.blob())
      if (!cancelled) setUrl(objectUrl)
    })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [hasCover, linkId])

  if (!hasCover || !url) return null
  return <img src={url} alt="" />
}

export function AdminCreatorDonationsTab() {
  const { t } = useTranslation('admin')
  const [rows, setRows] = useState<AdminDonationLink[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [products, setProducts] = useState<TributeProduct[]>([])
  const [productsNote, setProductsNote] = useState<string | null>(null)
  const [productsOpen, setProductsOpen] = useState(false)
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

  const loadTributeProducts = async () => {
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch('/api/admin/creator-donations/tribute-products?size=50')
      if (!r.ok) {
        setError(t('creatorDonations.errors.productsFailed'))
        return
      }
      const data = (await r.json()) as { rows: TributeProduct[]; note?: string }
      setProducts(data.rows ?? [])
      setProductsNote(data.note ?? null)
      setProductsOpen(true)
    } finally {
      setBusy(false)
    }
  }

  const downloadCover = async (linkId: number) => {
    const r = await apiFetch(`/api/admin/creator-donations/${linkId}/cover`)
    if (!r.ok) return
    const blob = await r.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `donation-cover-${linkId}.jpg`
    a.click()
    URL.revokeObjectURL(url)
  }

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

  const formatAmount = (minor: number | null, currency: string) => {
    if (minor == null) return '—'
    return `${(minor / 100).toFixed(2)} ${currency}`
  }

  return (
    <div className="admin-panel admin-donations-panel">
      <h2>{t('creatorDonations.title')}</h2>
      <p className="muted">{t('creatorDonations.intro')}</p>

      <div className="admin-donations-toolbar">
        <button type="button" className="primary-btn" disabled={busy} onClick={() => void loadTributeProducts()}>
          {t('creatorDonations.loadTributeProducts')}
        </button>
        {productsOpen ? (
          <button type="button" className="ghost-btn" onClick={() => setProductsOpen(false)}>
            {t('creatorDonations.hideProducts')}
          </button>
        ) : null}
      </div>

      {productsOpen && products.length > 0 ? (
        <div className="admin-tribute-products">
          {productsNote ? <p className="admin-tribute-products__note">{productsNote}</p> : null}
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>{t('creatorDonations.productName')}</th>
                <th>{t('creatorDonations.fields.currency')}</th>
                <th>{t('creatorDonations.productAmount')}</th>
                <th>Web</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id}>
                  <td className="mono">{p.id}</td>
                  <td>{p.name ?? '—'}</td>
                  <td>{p.currency ?? '—'}</td>
                  <td>{formatAmount(p.amount, p.currency ?? '')}</td>
                  <td className="mono" style={{ maxWidth: 180, wordBreak: 'break-all' }}>
                    {p.web_link ? p.web_link.slice(0, 48) + (p.web_link.length > 48 ? '…' : '') : '—'}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ghost-btn"
                      onClick={() => {
                        try {
                          void navigator.clipboard.writeText(String(p.id))
                        } catch {
                          /* ignore */
                        }
                      }}
                    >
                      {t('creatorDonations.copyId')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {error ? <p className="admin-error">{error}</p> : null}

      {rows.length === 0 ? (
        <p className="muted">{t('creatorDonations.empty')}</p>
      ) : (
        <div className="admin-donation-queue">
          {rows.map((row) => {
            const form = activateForms[row.id] ?? { tributeId: '', webLink: '', tgLink: '' }
            return (
              <article key={row.id} className="admin-donation-card">
                <header className="admin-donation-card__header">
                  <span className="admin-donation-card__title">{row.title}</span>
                  <span className="admin-donation-card__user">user #{row.user_id}</span>
                </header>

                <dl className="admin-donation-meta-grid">
                  <div>
                    <dt>{t('creatorDonations.fields.currency')}</dt>
                    <dd>{row.currency}</dd>
                  </div>
                  <div>
                    <dt>{t('creatorDonations.fields.min')}</dt>
                    <dd>{formatAmount(row.min_amount_minor, row.currency)}</dd>
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

                {row.description ? <p className="admin-donation-text">{row.description}</p> : null}
                {row.button_text ? (
                  <p className="admin-donation-text small muted">
                    {t('creatorDonations.buttonLabel')}: {row.button_text}
                  </p>
                ) : null}

                {row.has_cover ? (
                  <div className="admin-donation-cover-block">
                    <DonationCoverPreview linkId={row.id} hasCover={Boolean(row.has_cover)} />
                    <button type="button" className="ghost-btn" onClick={() => void downloadCover(row.id)}>
                      {t('creatorDonations.downloadCover')}
                    </button>
                  </div>
                ) : null}

                <div className="admin-donation-activate-grid">
                  <label>
                    {t('creatorDonations.fields.tributeId')}
                    <input
                      value={form.tributeId}
                      onChange={(e) => setFormField(row.id, 'tributeId', e.target.value)}
                      placeholder="12345"
                    />
                  </label>
                  <label>
                    {t('creatorDonations.fields.webLink')}
                    <input
                      value={form.webLink}
                      onChange={(e) => setFormField(row.id, 'webLink', e.target.value)}
                      placeholder="https://..."
                    />
                  </label>
                  <label>
                    {t('creatorDonations.fields.tgLink')}
                    <input
                      value={form.tgLink}
                      onChange={(e) => setFormField(row.id, 'tgLink', e.target.value)}
                      placeholder="https://t.me/..."
                    />
                  </label>
                </div>

                {products.length > 0 ? (
                  <p className="small muted">{t('creatorDonations.pickProductHint')}</p>
                ) : null}

                <div className="admin-donation-actions">
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
