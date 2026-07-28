import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import type {
  AdminLoginBotBroadcastResult,
  AdminLoginBotConfig,
  AdminLoginBotStats,
} from './types'

function insertAtCursor(
  value: string,
  insertion: string,
  setValue: (next: string) => void,
  textareaRef: HTMLTextAreaElement | null,
) {
  if (!textareaRef) {
    setValue(value ? `${value}\n${insertion}` : insertion)
    return
  }
  const start = textareaRef.selectionStart
  const end = textareaRef.selectionEnd
  const next = `${value.slice(0, start)}${insertion}${value.slice(end)}`
  setValue(next)
  requestAnimationFrame(() => {
    const pos = start + insertion.length
    textareaRef.focus()
    textareaRef.setSelectionRange(pos, pos)
  })
}

export function AdminLoginBotTab({ onError }: { onError: (msg: string | null) => void }) {
  const { t } = useTranslation('admin')
  const [config, setConfig] = useState<AdminLoginBotConfig | null>(null)
  const [stats, setStats] = useState<AdminLoginBotStats | null>(null)
  const [busy, setBusy] = useState(false)
  const [text, setText] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [lastResult, setLastResult] = useState<AdminLoginBotBroadcastResult | null>(null)
  const [textareaEl, setTextareaEl] = useState<HTMLTextAreaElement | null>(null)

  const loadAll = useCallback(async () => {
    onError(null)
    const [cfgR, statsR] = await Promise.all([
      apiFetch('/api/admin/login-bot/config'),
      apiFetch('/api/admin/login-bot/stats'),
    ])

    const readDetail = async (r: Response) => {
      const d = (await r.json().catch(() => ({}))) as { detail?: string | { msg?: string }[] }
      if (typeof d.detail === 'string') return d.detail
      if (Array.isArray(d.detail) && d.detail[0]?.msg) return d.detail[0].msg
      return `${r.status} ${r.statusText}`
    }

    if (cfgR.ok) {
      setConfig((await cfgR.json()) as AdminLoginBotConfig)
    } else {
      onError(await readDetail(cfgR))
    }

    if (statsR.ok) {
      setStats((await statsR.json()) as AdminLoginBotStats)
    } else if (cfgR.ok) {
      onError(await readDetail(statsR))
    }
  }, [onError])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    if (!templateId || !config) return
    const tpl = config.templates.find((item) => item.id === templateId)
    if (tpl) setText(tpl.text)
  }, [templateId, config])

  const sendTest = async () => {
    if (!text.trim()) return
    setBusy(true)
    onError(null)
    try {
      const r = await apiFetch('/api/admin/login-bot/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.trim() }),
      })
      if (!r.ok) {
        const d = (await r.json().catch(() => ({}))) as { detail?: string }
        throw new Error(d.detail ?? r.statusText)
      }
      alert(t('loginBot.testSent'))
    } catch (e) {
      onError(e instanceof Error ? e.message : t('loginBot.testError'))
    } finally {
      setBusy(false)
    }
  }

  const broadcast = async () => {
    if (!text.trim()) return
    const recipients = stats?.reachable_contacts ?? config?.recipient_count ?? 0
    const ok = window.confirm(t('loginBot.confirmBroadcast', { count: recipients }))
    if (!ok) return

    setBusy(true)
    onError(null)
    setLastResult(null)
    try {
      const r = await apiFetch('/api/admin/login-bot/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text.trim(),
          template_id: templateId || null,
          use_template_body: Boolean(templateId),
          confirm: true,
        }),
      })
      if (!r.ok) {
        const d = (await r.json().catch(() => ({}))) as { detail?: string }
        throw new Error(d.detail ?? r.statusText)
      }
      const result = (await r.json()) as AdminLoginBotBroadcastResult
      setLastResult(result)
      await loadAll()
    } catch (e) {
      onError(e instanceof Error ? e.message : t('loginBot.broadcastError'))
    } finally {
      setBusy(false)
    }
  }

  if (!config) {
    return <p className="muted">{t('loginBot.loading')}</p>
  }

  const channelUrl = config.channel_url ?? 'https://t.me/ModelMate_app'
  const botUrl = config.bot_url ?? `https://t.me/${config.bot_username ?? ''}`

  return (
    <div className="admin-email admin-fade-in" role="tabpanel">
      {!config.bot_configured ? (
        <div className="admin-banner admin-banner--error" style={{ marginBottom: '1rem' }}>
          {t('loginBot.botNotConfigured')}
        </div>
      ) : (
        <p className="admin-section-lead muted">
          {t('loginBot.botInfo', {
            username: config.bot_username ? `@${config.bot_username}` : '—',
            count: stats?.reachable_contacts ?? config.recipient_count,
          })}
        </p>
      )}

      {stats ? (
        <div className="admin-kpi-grid" style={{ marginBottom: '1.25rem' }}>
          <div className="admin-kpi">
            <span className="admin-kpi__label">{t('loginBot.totalContacts')}</span>
            <strong className="admin-kpi__value">{stats.total_contacts}</strong>
          </div>
          <div className="admin-kpi">
            <span className="admin-kpi__label">{t('loginBot.reachable')}</span>
            <strong className="admin-kpi__value admin-kpi__value--accent">{stats.reachable_contacts}</strong>
            {stats.blocked_contacts > 0 ? (
              <span className="admin-kpi__hint">{t('loginBot.blockedHint', { count: stats.blocked_contacts })}</span>
            ) : null}
          </div>
          <div className="admin-kpi">
            <span className="admin-kpi__label">{t('loginBot.active7d')}</span>
            <strong className="admin-kpi__value">{stats.active_contacts_7d}</strong>
          </div>
          <div className="admin-kpi">
            <span className="admin-kpi__label">{t('loginBot.active30d')}</span>
            <strong className="admin-kpi__value">{stats.active_contacts_30d}</strong>
          </div>
        </div>
      ) : null}

      <div className="admin-email-grid">
        <section className="admin-section admin-email-form">
          <h2 className="admin-section-title">{t('loginBot.newBroadcast')}</h2>

          <label className="admin-field">
            <span>{t('loginBot.template')}</span>
            <select
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              className="admin-user-search"
            >
              <option value="">{t('loginBot.customText')}</option>
              {config.templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name}
                </option>
              ))}
            </select>
          </label>

          <div className="admin-field">
            <span>{t('loginBot.quickInsert')}</span>
            <div className="admin-email-actions" style={{ flexWrap: 'wrap' }}>
              <button
                type="button"
                className="ghost-btn"
                disabled={busy}
                onClick={() => insertAtCursor(text, channelUrl, setText, textareaEl)}
              >
                {t('loginBot.insertChannel', { label: config.channel_label ?? 'канал' })}
              </button>
              <button
                type="button"
                className="ghost-btn"
                disabled={busy || !config.bot_username}
                onClick={() => insertAtCursor(text, botUrl, setText, textareaEl)}
              >
                {t('loginBot.insertBot')}
              </button>
            </div>
          </div>

          <label className="admin-field">
            <span>{t('loginBot.messageLabel')}</span>
            <textarea
              ref={setTextareaEl}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="admin-email-textarea"
              rows={10}
              placeholder={t('loginBot.messagePlaceholder')}
            />
            <span className="muted small">{t('loginBot.htmlHint')}</span>
          </label>

          <div className="admin-email-actions">
            <button type="button" className="ghost-btn" disabled={busy || !text.trim()} onClick={() => void sendTest()}>
              {t('loginBot.sendTest')}
            </button>
            <button
              type="button"
              className="admin-primary-btn"
              disabled={busy || !config.bot_configured || !text.trim()}
              onClick={() => void broadcast()}
            >
              {t('loginBot.sendAll')}
            </button>
          </div>
        </section>

        <section className="admin-section">
          <h2 className="admin-section-title">{t('loginBot.helpTitle')}</h2>
          <ul className="muted small" style={{ lineHeight: 1.6, paddingLeft: '1.1rem' }}>
            <li>{t('loginBot.helpReachable')}</li>
            <li>{t('loginBot.helpBackfill')}</li>
            <li>{t('loginBot.helpRate')}</li>
          </ul>

          {lastResult ? (
            <div className="admin-card" style={{ marginTop: '1rem', padding: '1rem' }}>
              <h3 className="admin-section-title" style={{ fontSize: '1rem' }}>
                {t('loginBot.lastResult')}
              </h3>
              <p className="small">
                {t('loginBot.resultSummary', {
                  total: lastResult.total,
                  sent: lastResult.sent,
                  failed: lastResult.failed,
                  blocked: lastResult.blocked,
                })}
              </p>
              {lastResult.errors.length > 0 ? (
                <ul className="mono small muted" style={{ marginTop: '0.5rem' }}>
                  {lastResult.errors.slice(0, 5).map((err) => (
                    <li key={String(err.telegram_id)}>
                      {err.telegram_id}: {err.error}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  )
}
