import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import type {
  AdminEmailCampaign,
  AdminEmailConfig,
  AdminEmailSegmentPreview,
  AdminEmailTemplate,
} from './types'

interface Props {
  meEmail: string
  onError: (msg: string | null) => void
}

export function AdminEmailTab({ meEmail, onError }: Props) {
  const { t } = useTranslation('admin')
  const [config, setConfig] = useState<AdminEmailConfig | null>(null)
  const [templates, setTemplates] = useState<AdminEmailTemplate[]>([])
  const [campaigns, setCampaigns] = useState<AdminEmailCampaign[]>([])
  const [busy, setBusy] = useState(false)

  const [segment, setSegment] = useState('zombie')
  const [templateId, setTemplateId] = useState('')
  const [subject, setSubject] = useState('')
  const [bodyHtml, setBodyHtml] = useState('')
  const [preview, setPreview] = useState<AdminEmailSegmentPreview | null>(null)
  const [smtpCheck, setSmtpCheck] = useState<{ ok: boolean; error?: string; hint?: string } | null>(
    null,
  )

  const loadAll = useCallback(async () => {
    const [cfgR, tplR, campR] = await Promise.all([
      apiFetch('/api/admin/email/config'),
      apiFetch('/api/admin/email/templates'),
      apiFetch('/api/admin/email/campaigns'),
    ])
    if (cfgR.ok) {
      const cfg = (await cfgR.json()) as AdminEmailConfig
      setConfig(cfg)
      if (cfg.smtp_configured) {
        const chk = await apiFetch('/api/admin/email/smtp-check')
        if (chk.ok) setSmtpCheck((await chk.json()) as { ok: boolean; error?: string; hint?: string })
      }
    }
    if (tplR.ok) setTemplates((await tplR.json()) as AdminEmailTemplate[])
    if (campR.ok) setCampaigns((await campR.json()) as AdminEmailCampaign[])
  }, [])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    if (!segment) return
    void (async () => {
      const r = await apiFetch(
        `/api/admin/email/segment-preview?segment=${encodeURIComponent(segment)}`,
      )
      if (r.ok) setPreview((await r.json()) as AdminEmailSegmentPreview)
    })()
  }, [segment])

  useEffect(() => {
    if (!templateId) return
    const tpl = templates.find((tplItem) => tplItem.id === templateId)
    if (!tpl) return
    setSubject(tpl.subject)
    setBodyHtml(tpl.body_html)
  }, [templateId, templates])

  const sendTest = async () => {
    if (!meEmail) return
    setBusy(true)
    onError(null)
    try {
      const r = await apiFetch('/api/admin/email/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_email: meEmail,
          subject: subject || t('email.testSubject'),
          body_html: bodyHtml || t('email.testBody'),
        }),
      })
      if (!r.ok) {
        const d = (await r.json().catch(() => ({}))) as { detail?: string }
        throw new Error(d.detail ?? r.statusText)
      }
      onError(null)
      alert(t('email.testSent', { email: meEmail }))
    } catch (e) {
      onError(e instanceof Error ? e.message : t('email.testError'))
    } finally {
      setBusy(false)
    }
  }

  const launchCampaign = async (sendNow: boolean) => {
    setBusy(true)
    onError(null)
    try {
      const r = await apiFetch('/api/admin/email/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          segment,
          subject,
          body_html: bodyHtml,
          template_id: templateId || null,
          use_template_body: Boolean(templateId),
          send_now: sendNow,
        }),
      })
      if (!r.ok) {
        const d = (await r.json().catch(() => ({}))) as { detail?: string }
        throw new Error(d.detail ?? r.statusText)
      }
      await loadAll()
      alert(sendNow ? t('email.campaignQueued') : t('email.draftSaved'))
    } catch (e) {
      onError(e instanceof Error ? e.message : t('email.campaignError'))
    } finally {
      setBusy(false)
    }
  }

  if (!config) {
    return <p className="muted">{t('email.loading')}</p>
  }

  return (
    <div className="admin-email" role="tabpanel">
      {!config.smtp_configured ? (
        <div className="admin-banner admin-banner--error" style={{ marginBottom: '1rem' }}>
          {t('email.smtpNotConfigured')}
        </div>
      ) : (
        <>
          <p className="admin-section-lead muted">
            {t('email.senderInfo', { fromName: config.from_name, fromEmail: config.from_email })}
          </p>
          {smtpCheck && !smtpCheck.ok ? (
            <div className="admin-banner admin-banner--error" style={{ marginBottom: '1rem' }}>
              <div>
                <strong>{t('email.smtpNoConnection')}</strong>
                {smtpCheck.error ? `: ${smtpCheck.error}` : ''}
              </div>
              {smtpCheck.hint ? <div className="small" style={{ marginTop: '0.35rem' }}>{smtpCheck.hint}</div> : null}
            </div>
          ) : null}
          {smtpCheck?.ok ? (
            <p className="muted small" style={{ marginBottom: '1rem' }}>
              {t('email.smtpAvailable')}
            </p>
          ) : null}
        </>
      )}

      <div className="admin-email-grid">
        <section className="admin-section admin-email-form">
          <h2 className="admin-section-title">{t('email.newCampaign')}</h2>

          <label className="admin-field">
            <span>{t('common.segment')}</span>
            <select
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              className="admin-user-search"
            >
              {config.segments.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
          </label>

          {preview ? (
            <p className="muted small">
              {t('email.segmentIn', { total: preview.segment_total })} · {t('email.segmentEligible', { eligible: preview.eligible })}
              {preview.opted_out > 0 ? ` · ${t('email.segmentOptedOut', { count: preview.opted_out })}` : ''}
              {preview.inactive > 0 ? ` · ${t('email.segmentInactive', { count: preview.inactive })}` : ''}
            </p>
          ) : null}

          <label className="admin-field">
            <span>{t('email.template')}</span>
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="admin-user-search"
            >
              <option value="">{t('email.customText')}</option>
              {templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name}
                </option>
              ))}
            </select>
          </label>

          <label className="admin-field">
            <span>{t('common.subject')}</span>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="admin-user-search"
              placeholder={t('email.subjectPlaceholder')}
            />
          </label>

          <label className="admin-field">
            <span>{t('email.bodyLabel')}</span>
            <textarea
              value={bodyHtml}
              onChange={(e) => setBodyHtml(e.target.value)}
              className="admin-email-textarea"
              rows={12}
              placeholder={t('email.bodyPlaceholder')}
            />
          </label>

          <div className="admin-email-actions">
            <button type="button" className="ghost-btn" disabled={busy || !config.smtp_configured} onClick={() => void sendTest()}>
              {t('email.testOn', { email: meEmail || t('email.myEmail') })}
            </button>
            <button
              type="button"
              className="ghost-btn"
              disabled={busy || !config.smtp_configured}
              onClick={() => void launchCampaign(false)}
            >
              {t('email.saveDraft')}
            </button>
            <button
              type="button"
              className="primary-btn"
              disabled={busy || !config.smtp_configured || !preview?.eligible}
              onClick={() => {
                if (
                  !window.confirm(
                    t('email.confirmSend', {
                      count: preview?.eligible ?? '?',
                      title: preview?.title ?? segment,
                    }),
                  )
                ) {
                  return
                }
                void launchCampaign(true)
              }}
            >
              {t('email.sendCampaign')}
            </button>
          </div>
        </section>

        <section className="admin-section">
          <h2 className="admin-section-title">{t('email.history')}</h2>
          {campaigns.length === 0 ? (
            <p className="muted">{t('email.noCampaigns')}</p>
          ) : (
            <div className="admin-user-table-wrap">
              <table className="admin-user-table">
                <thead>
                  <tr>
                    <th>{t('common.id')}</th>
                    <th>{t('common.segment')}</th>
                    <th>{t('common.subject')}</th>
                    <th>{t('common.status')}</th>
                    <th>{t('common.sent')}</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c) => (
                    <tr key={c.id}>
                      <td className="mono">{c.id}</td>
                      <td>{c.segment_title}</td>
                      <td>{c.subject}</td>
                      <td>{c.status}</td>
                      <td className="mono">
                        {c.sent_count}/{c.recipient_count}
                        {c.failed_count > 0 ? ` · err ${c.failed_count}` : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
