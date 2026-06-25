import { useCallback, useEffect, useState } from 'react'
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
  const [config, setConfig] = useState<AdminEmailConfig | null>(null)
  const [templates, setTemplates] = useState<AdminEmailTemplate[]>([])
  const [campaigns, setCampaigns] = useState<AdminEmailCampaign[]>([])
  const [busy, setBusy] = useState(false)

  const [segment, setSegment] = useState('zombie')
  const [templateId, setTemplateId] = useState('')
  const [subject, setSubject] = useState('')
  const [bodyHtml, setBodyHtml] = useState('')
  const [preview, setPreview] = useState<AdminEmailSegmentPreview | null>(null)

  const loadAll = useCallback(async () => {
    const [cfgR, tplR, campR] = await Promise.all([
      apiFetch('/api/admin/email/config'),
      apiFetch('/api/admin/email/templates'),
      apiFetch('/api/admin/email/campaigns'),
    ])
    if (cfgR.ok) setConfig((await cfgR.json()) as AdminEmailConfig)
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
    const tpl = templates.find((t) => t.id === templateId)
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
          subject: subject || 'Тест ModelMate',
          body_html: bodyHtml || '<p>Тестовое письмо</p>',
        }),
      })
      if (!r.ok) {
        const d = (await r.json().catch(() => ({}))) as { detail?: string }
        throw new Error(d.detail ?? r.statusText)
      }
      onError(null)
      alert(`Тестовое письмо отправлено на ${meEmail}`)
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Ошибка отправки теста')
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
      alert(sendNow ? 'Кампания поставлена в очередь' : 'Черновик сохранён')
    } catch (e) {
      onError(e instanceof Error ? e.message : 'Ошибка кампании')
    } finally {
      setBusy(false)
    }
  }

  if (!config) {
    return <p className="muted">Загрузка настроек email…</p>
  }

  return (
    <div className="admin-email" role="tabpanel">
      {!config.smtp_configured ? (
        <div className="admin-banner admin-banner--error" style={{ marginBottom: '1rem' }}>
          SMTP не настроен. Добавьте в .env на сервере: SMTP_HOST, SMTP_FROM_EMAIL и при необходимости
          SMTP_USER / SMTP_PASSWORD. Можно свой Postfix на localhost:587 или relay (Yandex, Mailgun).
        </div>
      ) : (
        <p className="admin-section-lead muted">
          Отправитель: {config.from_name} &lt;{config.from_email}&gt;. Письма уходят пачками в фоне.
        </p>
      )}

      <div className="admin-email-grid">
        <section className="admin-section admin-email-form">
          <h2 className="admin-section-title">Новая рассылка</h2>

          <label className="admin-field">
            <span>Сегмент</span>
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
              В сегменте: {preview.segment_total} · получат:{' '}
              <strong>{preview.eligible}</strong>
              {preview.opted_out > 0 ? ` · отписались ${preview.opted_out}` : ''}
              {preview.inactive > 0 ? ` · неактивны ${preview.inactive}` : ''}
            </p>
          ) : null}

          <label className="admin-field">
            <span>Шаблон</span>
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="admin-user-search"
            >
              <option value="">— свой текст —</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>

          <label className="admin-field">
            <span>Тема</span>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="admin-user-search"
              placeholder="Тема письма"
            />
          </label>

          <label className="admin-field">
            <span>HTML-тело</span>
            <textarea
              value={bodyHtml}
              onChange={(e) => setBodyHtml(e.target.value)}
              className="admin-email-textarea"
              rows={12}
              placeholder="<p>Текст…</p>  Переменные: {{email}}, {{app_url}}"
            />
          </label>

          <div className="admin-email-actions">
            <button type="button" className="ghost-btn" disabled={busy || !config.smtp_configured} onClick={() => void sendTest()}>
              Тест на {meEmail || 'мой email'}
            </button>
            <button
              type="button"
              className="ghost-btn"
              disabled={busy || !config.smtp_configured}
              onClick={() => void launchCampaign(false)}
            >
              Сохранить черновик
            </button>
            <button
              type="button"
              className="primary-btn"
              disabled={busy || !config.smtp_configured || !preview?.eligible}
              onClick={() => {
                if (
                  !window.confirm(
                    `Отправить ${preview?.eligible ?? '?'} писем сегменту «${preview?.title ?? segment}»?`,
                  )
                ) {
                  return
                }
                void launchCampaign(true)
              }}
            >
              Отправить кампанию
            </button>
          </div>
        </section>

        <section className="admin-section">
          <h2 className="admin-section-title">История кампаний</h2>
          {campaigns.length === 0 ? (
            <p className="muted">Пока нет кампаний</p>
          ) : (
            <div className="admin-user-table-wrap">
              <table className="admin-user-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Сегмент</th>
                    <th>Тема</th>
                    <th>Статус</th>
                    <th>Отправлено</th>
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
