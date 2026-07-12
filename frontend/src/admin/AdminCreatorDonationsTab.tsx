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

interface WebhookInboxRow {
  id: number
  donation_request_id: number
  event_name: string
  amount_minor: number
  currency: string
  payer_telegram_user_id: number | null
  received_at: string
  resolved_link_id: number | null
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

function formatAmount(minor: number | null, currency: string): string {
  if (minor == null) return '—'
  return `${(minor / 100).toFixed(2)} ${currency}`
}

function buildTributeDonationBrief(row: AdminDonationLink, t: (key: string) => string): string {
  const lines = [
    `${t('creatorDonations.copyBrief.title')}: ${row.title}`,
    row.description ? `${t('creatorDonations.copyBrief.description')}: ${row.description}` : null,
    row.button_text ? `${t('creatorDonations.copyBrief.button')}: ${row.button_text}` : null,
    `${t('creatorDonations.fields.currency')}: ${row.currency}`,
    `${t('creatorDonations.fields.min')}: ${formatAmount(row.min_amount_minor, row.currency)}`,
    `${t('creatorDonations.fields.oneTime')}: ${row.allow_one_time ? 'yes' : 'no'}`,
    `${t('creatorDonations.fields.recurring')}: ${row.allow_recurring ? 'yes' : 'no'}`,
    `${t('creatorDonations.copyBrief.user')}: #${row.user_id}`,
    `${t('creatorDonations.copyBrief.request')}: #${row.id}`,
  ]
  return lines.filter(Boolean).join('\n')
}

export function AdminCreatorDonationsTab() {
  const { t } = useTranslation('admin')
  const [rows, setRows] = useState<AdminDonationLink[]>([])
  const [inbox, setInbox] = useState<WebhookInboxRow[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [activateForms, setActivateForms] = useState<
    Record<number, { donationRequestId: string; webLink: string; tgLink: string }>
  >({})

  const load = useCallback(async () => {
    const [linksRes, inboxRes] = await Promise.all([
      apiFetch('/api/admin/creator-donations?status=moderation'),
      apiFetch('/api/admin/creator-donations/webhook-inbox'),
    ])
    if (linksRes.ok) setRows((await linksRes.json()) as AdminDonationLink[])
    if (inboxRes.ok) setInbox((await inboxRes.json()) as WebhookInboxRow[])
  }, [])

  useEffect(() => {
    void load()
  }, [load])

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

  const copyDonationBrief = async (row: AdminDonationLink) => {
    try {
      await navigator.clipboard.writeText(buildTributeDonationBrief(row, t))
      setCopiedId(row.id)
      window.setTimeout(() => setCopiedId((cur) => (cur === row.id ? null : cur)), 2000)
    } catch {
      setError(t('creatorDonations.errors.copyFailed'))
    }
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

  const saveLinks = async (id: number) => {
    const form = activateForms[id] ?? { donationRequestId: '', webLink: '', tgLink: '' }
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/admin/creator-donations/${id}/activate`, {
        method: 'POST',
        body: JSON.stringify({
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

  const readApiError = async (r: Response, fallback: string): Promise<string> => {
    try {
      const data = (await r.json()) as { detail?: string | { msg?: string }[] }
      if (typeof data.detail === 'string' && data.detail.trim()) return data.detail
      if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg
    } catch {
      /* ignore */
    }
    return fallback
  }

  const bindDonationId = async (linkId: number, donationRequestId: number, inboxId?: number) => {
    const row = rows.find((r) => r.id === linkId)
    const form = activateForms[linkId] ?? {
      donationRequestId: String(donationRequestId),
      webLink: row?.web_link ?? '',
      tgLink: row?.telegram_link ?? '',
    }
    const webLink = form.webLink.trim()
    if (!webLink) {
      setError(t('creatorDonations.errors.webLinkRequired'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/admin/creator-donations/${linkId}/bind-donation-id`, {
        method: 'POST',
        body: JSON.stringify({
          tribute_donation_request_id: donationRequestId,
          inbox_id: inboxId ?? null,
          web_link: webLink,
          telegram_link: form.tgLink.trim() || null,
        }),
      })
      if (!r.ok) {
        setError(await readApiError(r, t('creatorDonations.errors.actionFailed')))
        return
      }
      await load()
    } finally {
      setBusy(false)
    }
  }

  const activateWithId = async (id: number) => {
    const form = activateForms[id] ?? { donationRequestId: '', webLink: '', tgLink: '' }
    setBusy(true)
    setError(null)
    try {
      const r = await apiFetch(`/api/admin/creator-donations/${id}/activate`, {
        method: 'POST',
        body: JSON.stringify({
          tribute_donation_request_id: Number(form.donationRequestId),
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

  const setFormField = (
    id: number,
    key: 'donationRequestId' | 'webLink' | 'tgLink',
    value: string,
  ) => {
    setActivateForms((prev) => ({
      ...prev,
      [id]: {
        donationRequestId: prev[id]?.donationRequestId ?? '',
        webLink: prev[id]?.webLink ?? '',
        tgLink: prev[id]?.tgLink ?? '',
        [key]: value,
      },
    }))
  }

  const applyInboxIdToForm = (linkId: number, donationRequestId: number) => {
    setFormField(linkId, 'donationRequestId', String(donationRequestId))
  }

  return (
    <div className="admin-panel admin-donations-panel">
      <h2>{t('creatorDonations.title')}</h2>
      <p className="muted">{t('creatorDonations.intro')}</p>
      <p className="admin-donation-api-note">{t('creatorDonations.noDonationsApi')}</p>
      <p className="admin-donation-api-note admin-donation-id-note">{t('creatorDonations.idFromWebhook')}</p>

      {error ? <p className="admin-error">{error}</p> : null}

      {inbox.length > 0 ? (
        <section className="admin-donation-inbox">
          <div className="admin-donation-inbox__head">
            <h3>{t('creatorDonations.inboxTitle')}</h3>
            <button type="button" className="ghost-btn" disabled={busy} onClick={() => void load()}>
              {t('creatorDonations.refreshInbox')}
            </button>
          </div>
          <p className="small muted">{t('creatorDonations.inboxHint')}</p>
          <div className="admin-donation-inbox-list">
            {inbox.map((item) => (
              <div key={item.id} className="admin-donation-inbox-row">
                <div className="admin-donation-inbox-row__main">
                  <strong className="mono">donation_request_id = {item.donation_request_id}</strong>
                  <span className="muted">
                    {formatAmount(item.amount_minor, item.currency)} · {item.event_name}
                  </span>
                </div>
                {rows.length === 1 ? (
                  <button
                    type="button"
                    className="primary-btn"
                    disabled={busy}
                    onClick={() => void bindDonationId(rows[0].id, item.donation_request_id, item.id)}
                  >
                    {t('creatorDonations.bindToRequest', { id: rows[0].id })}
                  </button>
                ) : (
                  rows.map((row) =>
                    row.status === 'awaiting_id' ? (
                      <button
                        key={`${item.id}-${row.id}`}
                        type="button"
                        className="ghost-btn"
                        disabled={busy}
                        onClick={() => void bindDonationId(row.id, item.donation_request_id, item.id)}
                      >
                        {t('creatorDonations.bindToRequest', { id: row.id })}
                      </button>
                    ) : null,
                  )
                )}
              </div>
            ))}
          </div>
        </section>
      ) : rows.some((r) => r.status === 'awaiting_id') ? (
        <section className="admin-donation-inbox admin-donation-inbox--empty">
          <div className="admin-donation-inbox__head">
            <h3>{t('creatorDonations.inboxTitle')}</h3>
            <button type="button" className="ghost-btn" disabled={busy} onClick={() => void load()}>
              {t('creatorDonations.refreshInbox')}
            </button>
          </div>
          <p className="small muted">{t('creatorDonations.inboxEmpty')}</p>
        </section>
      ) : null}

      {rows.length === 0 ? (
        <p className="muted">{t('creatorDonations.empty')}</p>
      ) : (
        <div className="admin-donation-queue">
          {rows.map((row) => {
            const form = activateForms[row.id] ?? {
              donationRequestId: row.tribute_donation_request_id
                ? String(row.tribute_donation_request_id)
                : '',
              webLink: row.web_link ?? '',
              tgLink: row.telegram_link ?? '',
            }
            const awaitingId = row.status === 'awaiting_id'
            return (
              <article key={row.id} className="admin-donation-card">
                <header className="admin-donation-card__header">
                  <span className="admin-donation-card__title">{row.title}</span>
                  <span className="admin-donation-card__user">
                    user #{row.user_id}
                    {awaitingId ? ` · ${t('creatorDonations.awaitingIdBadge')}` : ''}
                  </span>
                </header>

                <ol className="admin-donation-steps">
                  <li>{t('creatorDonations.steps.openTribute')}</li>
                  <li>{t('creatorDonations.steps.copyFields')}</li>
                  <li>{t('creatorDonations.steps.createDonation')}</li>
                  <li>{t('creatorDonations.steps.pasteLinks')}</li>
                  <li>{t('creatorDonations.steps.testDonation')}</li>
                  <li>{t('creatorDonations.steps.bindFromInbox')}</li>
                </ol>

                <button
                  type="button"
                  className="ghost-btn admin-donation-copy-btn"
                  onClick={() => void copyDonationBrief(row)}
                >
                  {copiedId === row.id
                    ? t('creatorDonations.copiedBrief')
                    : t('creatorDonations.copyBriefButton')}
                </button>

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

                <h5 className="admin-donation-activate-title">{t('creatorDonations.afterCreateTitle')}</h5>
                <div className="admin-donation-activate-grid">
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
                  <label>
                    {t('creatorDonations.fields.donationRequestId')}
                    <input
                      value={form.donationRequestId}
                      onChange={(e) => setFormField(row.id, 'donationRequestId', e.target.value)}
                      placeholder={t('creatorDonations.idPlaceholder')}
                      inputMode="numeric"
                    />
                  </label>
                </div>

                {inbox.length > 0 && !form.donationRequestId ? (
                  <div className="admin-donation-inbox-pick">
                    {inbox.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className="ghost-btn"
                        onClick={() => applyInboxIdToForm(row.id, item.donation_request_id)}
                      >
                        {t('creatorDonations.useInboxId', { id: item.donation_request_id })}
                      </button>
                    ))}
                  </div>
                ) : null}

                <div className="admin-donation-actions">
                  {!awaitingId ? (
                    <button
                      type="button"
                      className="primary-btn"
                      disabled={busy || !form.webLink.trim()}
                      onClick={() => void saveLinks(row.id)}
                    >
                      {t('creatorDonations.saveLinks')}
                    </button>
                  ) : null}
                  {awaitingId && form.donationRequestId ? (
                    <button
                      type="button"
                      className="primary-btn"
                      disabled={busy}
                      onClick={() =>
                        void bindDonationId(row.id, Number(form.donationRequestId))
                      }
                    >
                      {t('creatorDonations.bindAndActivate')}
                    </button>
                  ) : null}
                  {!awaitingId && form.donationRequestId && form.webLink.trim() ? (
                    <button
                      type="button"
                      className="ghost-btn"
                      disabled={busy}
                      onClick={() => void activateWithId(row.id)}
                    >
                      {t('creatorDonations.activateWithId')}
                    </button>
                  ) : null}
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
