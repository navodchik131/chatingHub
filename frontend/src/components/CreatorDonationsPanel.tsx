import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { formatAppNumber } from '../i18n'
import '../styles/donations-ui.css'

export interface StudioModelOption {
  id: number
  name: string
}

export interface CreatorDonationLink {
  id: number
  studio_model_id: number | null
  title: string
  description: string | null
  button_text: string | null
  cover_image_url: string | null
  has_cover?: boolean
  currency: 'EUR' | 'RUB' | 'USD'
  min_amount_minor: number | null
  allow_one_time: boolean
  allow_recurring: boolean
  status: 'draft' | 'pending' | 'awaiting_id' | 'active' | 'rejected' | 'disabled'
  tribute_donation_request_id: number | null
  web_link: string | null
  telegram_link: string | null
  admin_notes: string | null
  created_at: string
  updated_at: string
  activated_at: string | null
  donations_count?: number
  totals_by_currency?: Record<string, number>
  pending_payout_by_currency?: Record<string, number>
}

export interface CreatorDonationEvent {
  id: number
  creator_donation_link_id: number
  studio_model_id: number | null
  event_name: string
  amount_minor: number
  currency: string
  payer_telegram_user_id: number | null
  payout_status: string
  occurred_at: string
}

const EMPTY_FORM = {
  title: '',
  description: '',
  button_text: '',
  currency: 'EUR' as 'EUR' | 'RUB' | 'USD',
  min_amount_major: '',
  allow_one_time: true,
  allow_recurring: true,
  studio_model_id: '' as string,
}

function minorToMajor(minor: number | null): string {
  if (minor == null) return ''
  return String(minor / 100)
}

function majorToMinor(raw: string): number | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const num = Number(trimmed.replace(',', '.'))
  if (!Number.isFinite(num) || num <= 0) return null
  return Math.round(num * 100)
}

function formatMoney(minor: number, currency: string): string {
  const major = minor / 100
  const sym = currency === 'RUB' ? '₽' : currency === 'EUR' ? '€' : '$'
  return `${formatAppNumber(major)} ${sym}`
}

function statusClass(status: CreatorDonationLink['status']): string {
  if (status === 'active') return 'is-ok'
  if (status === 'pending' || status === 'awaiting_id') return 'is-warn'
  if (status === 'rejected') return 'is-bad'
  return 'is-muted'
}

async function uploadCoverFile(linkId: number, file: File): Promise<boolean> {
  const fd = new FormData()
  fd.append('cover', file)
  const r = await apiFetch(`/api/creator-donations/${linkId}/cover`, { method: 'POST', body: fd })
  return r.ok
}

export interface CreatorDonationsPanelProps {
  studioModels: StudioModelOption[]
  platformConfigured?: boolean
}

export function CreatorDonationsPanel({
  studioModels,
  platformConfigured = true,
}: CreatorDonationsPanelProps) {
  const { t } = useTranslation('workspace')
  const [links, setLinks] = useState<CreatorDonationLink[]>([])
  const [events, setEvents] = useState<CreatorDonationEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [coverPreview, setCoverPreview] = useState<string | null>(null)
  const [existingCover, setExistingCover] = useState(false)
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null)

  const loadCoverPreview = useCallback(async (linkId: number) => {
    const r = await apiFetch(`/api/creator-donations/${linkId}/cover`)
    if (!r.ok) return null
    const blob = await r.blob()
    return URL.createObjectURL(blob)
  }, [])

  const load = useCallback(async () => {
    const [linksRes, eventsRes] = await Promise.all([
      apiFetch('/api/creator-donations'),
      apiFetch('/api/creator-donations/events?limit=50'),
    ])
    if (linksRes.ok) setLinks((await linksRes.json()) as CreatorDonationLink[])
    if (eventsRes.ok) setEvents((await eventsRes.json()) as CreatorDonationEvent[])
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (coverFile) {
      const url = URL.createObjectURL(coverFile)
      setCoverPreview(url)
      return () => URL.revokeObjectURL(url)
    }
    if (existingCover && editingId) {
      let cancelled = false
      void loadCoverPreview(editingId).then((url) => {
        if (!cancelled && url) setCoverPreview(url)
      })
      return () => {
        cancelled = true
      }
    }
    setCoverPreview(null)
    return undefined
  }, [coverFile, existingCover, editingId, loadCoverPreview])

  const resetForm = () => {
    setEditingId(null)
    setForm({ ...EMPTY_FORM })
    setCoverFile(null)
    setExistingCover(false)
    setCoverPreview(null)
    setError(null)
  }

  const fillForm = (link: CreatorDonationLink) => {
    setEditingId(link.id)
    setForm({
      title: link.title,
      description: link.description ?? '',
      button_text: link.button_text ?? '',
      currency: link.currency,
      min_amount_major: minorToMajor(link.min_amount_minor),
      allow_one_time: link.allow_one_time,
      allow_recurring: link.allow_recurring,
      studio_model_id: link.studio_model_id != null ? String(link.studio_model_id) : '',
    })
    setCoverFile(null)
    setExistingCover(Boolean(link.has_cover))
    setSelectedLinkId(link.id)
  }

  const payloadFromForm = (submit: boolean) => ({
    title: form.title.trim(),
    description: form.description.trim() || null,
    button_text: form.button_text.trim() || null,
    currency: form.currency,
    min_amount_minor: majorToMinor(form.min_amount_major),
    allow_one_time: form.allow_one_time,
    allow_recurring: form.allow_recurring,
    studio_model_id: form.studio_model_id ? Number(form.studio_model_id) : null,
    submit,
  })

  const save = async (submit: boolean) => {
    setBusy(true)
    setError(null)
    try {
      const body = payloadFromForm(submit)
      const url = editingId ? `/api/creator-donations/${editingId}` : '/api/creator-donations'
      const r = await apiFetch(url, {
        method: editingId ? 'PATCH' : 'POST',
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const data = (await r.json().catch(() => ({}))) as { detail?: string }
        setError(data.detail ?? t('donationsExt.errors.saveFailed'))
        return
      }
      const data = (await r.json()) as CreatorDonationLink
      if (coverFile) {
        const ok = await uploadCoverFile(data.id, coverFile)
        if (!ok) {
          setError(t('donationsExt.errors.coverFailed'))
          await load()
          return
        }
      }
      resetForm()
      await load()
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: number) => {
    if (!window.confirm(t('donationsExt.confirmDelete'))) return
    setBusy(true)
    try {
      const r = await apiFetch(`/api/creator-donations/${id}`, { method: 'DELETE' })
      if (!r.ok) {
        setError(t('donationsExt.errors.deleteFailed'))
        return
      }
      if (editingId === id) resetForm()
      await load()
    } finally {
      setBusy(false)
    }
  }

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      /* ignore */
    }
  }

  const activeLink = useMemo(
    () => links.find((l) => l.id === selectedLinkId) ?? links.find((l) => l.status === 'active') ?? null,
    [links, selectedLinkId],
  )

  const filteredEvents = useMemo(() => {
    if (!activeLink) return events
    return events.filter((e) => e.creator_donation_link_id === activeLink.id)
  }, [events, activeLink])

  return (
    <div className="account-cabinet-pane cabinet-donations" role="tabpanel">
      <p className="cabinet-lead muted">{t('donationsExt.intro')}</p>

      {!platformConfigured ? (
        <p className="cabinet-banner cabinet-banner--warn">{t('donationsExt.platformNotConfigured')}</p>
      ) : null}

      <section className="cabinet-module">
        <div className="cabinet-module-head">
          <h4 className="cabinet-module-title">
            {editingId ? t('donationsExt.editTitle') : t('donationsExt.createTitle')}
          </h4>
        </div>

        <div className="donations-form-grid">
          <label className="donations-field-full">
            {t('donationsExt.fields.title')}
            <input
              value={form.title}
              maxLength={128}
              disabled={busy}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder={t('donationsExt.placeholders.title')}
            />
          </label>

          <label className="donations-field-full">
            {t('donationsExt.fields.description')}
            <textarea
              rows={3}
              maxLength={2000}
              value={form.description}
              disabled={busy}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder={t('donationsExt.placeholders.description')}
            />
          </label>

          <label>
            {t('donationsExt.fields.buttonText')}
            <input
              value={form.button_text}
              maxLength={64}
              disabled={busy}
              onChange={(e) => setForm((f) => ({ ...f, button_text: e.target.value }))}
              placeholder={t('donationsExt.placeholders.buttonText')}
            />
          </label>

          <label>
            {t('donationsExt.fields.currency')}
            <select
              value={form.currency}
              disabled={busy}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  currency: e.target.value as 'EUR' | 'RUB' | 'USD',
                }))
              }
            >
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
              <option value="RUB">RUB</option>
            </select>
          </label>

          <label>
            {t('donationsExt.fields.minAmount')}
            <input
              value={form.min_amount_major}
              inputMode="decimal"
              disabled={busy}
              onChange={(e) => setForm((f) => ({ ...f, min_amount_major: e.target.value }))}
              placeholder={t('donationsExt.placeholders.minAmount')}
            />
            <span className="small muted">{t('donationsExt.hints.minAmount')}</span>
          </label>

          {studioModels.length > 0 ? (
            <label>
              {t('cabinet.integrations.model')}
              <select
                value={form.studio_model_id}
                disabled={busy}
                onChange={(e) => setForm((f) => ({ ...f, studio_model_id: e.target.value }))}
              >
                <option value="">{t('cabinet.integrations.modelUnassigned')}</option>
                {studioModels.map((m) => (
                  <option key={m.id} value={String(m.id)}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <div aria-hidden />
          )}

          <div className="donations-field-full donations-cover-field">
            <span>{t('donationsExt.fields.coverUpload')}</span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null
                setCoverFile(file)
                if (file) setExistingCover(false)
              }}
            />
            {(coverPreview || coverFile) && (
              <div className="donations-cover-preview">
                {coverPreview ? <img src={coverPreview} alt="" /> : null}
                {coverFile ? <span className="donations-cover-name">{coverFile.name}</span> : null}
              </div>
            )}
            <span className="small muted">{t('donationsExt.hints.coverUpload')}</span>
          </div>

          <fieldset className="donations-frequency">
            <legend>{t('donationsExt.fields.frequency')}</legend>
            <div className="donations-frequency-row">
              <label>
                <input
                  type="checkbox"
                  checked={form.allow_one_time}
                  disabled={busy}
                  onChange={(e) => setForm((f) => ({ ...f, allow_one_time: e.target.checked }))}
                />
                {t('donationsExt.fields.allowOneTime')}
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={form.allow_recurring}
                  disabled={busy}
                  onChange={(e) => setForm((f) => ({ ...f, allow_recurring: e.target.checked }))}
                />
                {t('donationsExt.fields.allowRecurring')}
              </label>
            </div>
          </fieldset>

          {error ? <p className="cabinet-form-error donations-field-full">{error}</p> : null}

          <div className="donations-form-actions">
            <button type="button" className="ghost-btn" disabled={busy} onClick={() => void save(false)}>
              {t('donationsExt.saveDraft')}
            </button>
            <button
              type="button"
              className="primary-btn"
              disabled={busy || !form.title.trim()}
              onClick={() => void save(true)}
            >
              {busy ? '…' : t('donationsExt.submitForReview')}
            </button>
            {editingId ? (
              <button type="button" className="ghost-btn" disabled={busy} onClick={resetForm}>
                {t('donationsExt.cancelEdit')}
              </button>
            ) : null}
          </div>
        </div>
      </section>

      <section className="cabinet-module">
        <div className="cabinet-module-head">
          <h4 className="cabinet-module-title">{t('donationsExt.myLinks')}</h4>
        </div>
        {links.length === 0 ? (
          <p className="muted cabinet-module-body">{t('donationsExt.emptyLinks')}</p>
        ) : (
          <div className="cabinet-donation-links">
            {links.map((link) => (
              <article key={link.id} className="cabinet-donation-card">
                <div className="cabinet-donation-card__head">
                  <strong>{link.title}</strong>
                  <span className={`cabinet-module-badge ${statusClass(link.status)}`}>
                    {t(`donationsExt.status.${link.status}`)}
                  </span>
                </div>
                <p className="small muted">
                  {link.currency}
                  {link.min_amount_minor != null ? ` · min ${formatMoney(link.min_amount_minor, link.currency)}` : ''}
                  {link.donations_count ? ` · ${t('donationsExt.donationsCount', { count: link.donations_count })}` : ''}
                  {link.has_cover ? ` · ${t('donationsExt.hasCover')}` : ''}
                </p>
                {link.status === 'rejected' && link.admin_notes ? (
                  <p className="small cabinet-form-error">{link.admin_notes}</p>
                ) : null}
                {link.status === 'active' && link.web_link ? (
                  <div className="cabinet-donation-card__links">
                    <label>
                      {t('donationsExt.paymentLink')}
                      <div className="cabinet-link-row">
                        <input readOnly value={link.web_link} />
                        <button type="button" className="ghost-btn" onClick={() => void copyText(link.web_link!)}>
                          {t('donationsExt.copy')}
                        </button>
                      </div>
                    </label>
                    {link.telegram_link ? (
                      <label>
                        Telegram
                        <div className="cabinet-link-row">
                          <input readOnly value={link.telegram_link} />
                          <button type="button" className="ghost-btn" onClick={() => void copyText(link.telegram_link!)}>
                            {t('donationsExt.copy')}
                          </button>
                        </div>
                      </label>
                    ) : null}
                  </div>
                ) : null}
                {link.status === 'pending' || link.status === 'awaiting_id' ? (
                  <p className="small muted">{t('donationsExt.pendingHint')}</p>
                ) : null}
                <div className="cabinet-donation-card__actions">
                  {(link.status === 'draft' || link.status === 'pending' || link.status === 'rejected') && (
                    <button type="button" className="ghost-btn" onClick={() => fillForm(link)}>
                      {t('donationsExt.edit')}
                    </button>
                  )}
                  {link.status === 'active' && (
                    <button type="button" className="ghost-btn" onClick={() => setSelectedLinkId(link.id)}>
                      {t('donationsExt.viewAnalytics')}
                    </button>
                  )}
                  {link.status !== 'active' && (
                    <button type="button" className="ghost-btn" disabled={busy} onClick={() => void remove(link.id)}>
                      {t('donationsExt.delete')}
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {activeLink?.status === 'active' ? (
        <section className="cabinet-module">
          <div className="cabinet-module-head">
            <h4 className="cabinet-module-title">{t('donationsExt.analyticsTitle', { title: activeLink.title })}</h4>
          </div>
          {Object.keys(activeLink.totals_by_currency ?? {}).length > 0 ? (
            <div className="cabinet-dashboard-grid">
              {Object.entries(activeLink.totals_by_currency ?? {}).map(([cur, total]) => (
                <div key={cur} className="cabinet-dash-card">
                  <div className="cabinet-dash-label">{t('donationsExt.totalReceived')}</div>
                  <div className="cabinet-dash-value">{formatMoney(total, cur)}</div>
                  <p className="cabinet-dash-hint muted">
                    {t('donationsExt.pendingPayout')}:{' '}
                    {formatMoney(activeLink.pending_payout_by_currency?.[cur] ?? 0, cur)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted cabinet-module-body">{t('donationsExt.noDonationsYet')}</p>
          )}

          {filteredEvents.length > 0 ? (
            <div className="cabinet-table-wrap">
              <table className="cabinet-table">
                <thead>
                  <tr>
                    <th>{t('donationsExt.table.date')}</th>
                    <th>{t('donationsExt.table.amount')}</th>
                    <th>{t('donationsExt.table.payer')}</th>
                    <th>{t('donationsExt.table.payout')}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEvents.map((ev) => (
                    <tr key={ev.id}>
                      <td>{new Date(ev.occurred_at).toLocaleString()}</td>
                      <td>{formatMoney(ev.amount_minor, ev.currency)}</td>
                      <td className="mono">
                        {ev.payer_telegram_user_id != null ? `tg:${ev.payer_telegram_user_id}` : '—'}
                      </td>
                      <td>{t(`donationsExt.payoutStatus.${ev.payout_status}`, { defaultValue: ev.payout_status })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}
