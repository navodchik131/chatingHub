import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'

interface AgentRule {
  id: number
  code: string | null
  title: string
  prompt_zh: string
  prompt_en: string
  enabled: boolean
  locked: boolean
  sort: number
}

type Draft = Pick<AgentRule, 'title' | 'prompt_zh' | 'prompt_en' | 'enabled' | 'sort'>

const EMPTY: Draft = { title: '', prompt_zh: '', prompt_en: '', enabled: true, sort: 100 }

async function readDetail(r: Response): Promise<string> {
  const d = (await r.json().catch(() => ({}))) as { detail?: string | { msg?: string }[] }
  if (typeof d.detail === 'string') return d.detail
  if (Array.isArray(d.detail) && d.detail[0]?.msg) return d.detail[0].msg
  return `${r.status} ${r.statusText}`
}

function RuleForm({ initial, busy, onSave, onCancel }: {
  initial: Draft
  busy: boolean
  onSave: (d: Draft) => void
  onCancel: () => void
}) {
  const { t } = useTranslation('admin')
  const [d, setD] = useState<Draft>(initial)
  return (
    <div className="admin-rule__form">
      <label className="admin-rule__label">
        {t('agentRules.fieldTitle')}
        <textarea className="admin-rule__input" rows={3} value={d.title} onChange={(e) => setD({ ...d, title: e.target.value })} />
      </label>
      <label className="admin-rule__label">
        {t('agentRules.fieldZh')}
        <textarea className="admin-rule__input" rows={2} value={d.prompt_zh} onChange={(e) => setD({ ...d, prompt_zh: e.target.value })} />
      </label>
      <label className="admin-rule__label">
        {t('agentRules.fieldEn')}
        <textarea className="admin-rule__input" rows={2} value={d.prompt_en} onChange={(e) => setD({ ...d, prompt_en: e.target.value })} />
      </label>
      <div className="admin-rule__row">
        <label className="admin-rule__check">
          <input type="checkbox" checked={d.enabled} onChange={(e) => setD({ ...d, enabled: e.target.checked })} />
          {t('agentRules.enabled')}
        </label>
        <label className="admin-rule__check">
          {t('agentRules.sort')}
          <input className="admin-rule__num" type="number" value={d.sort} onChange={(e) => setD({ ...d, sort: Number(e.target.value) || 0 })} />
        </label>
        <span style={{ flex: 1 }} />
        <button type="button" className="admin-btn admin-btn--ghost" disabled={busy} onClick={onCancel}>{t('agentRules.cancel')}</button>
        <button type="button" className="admin-btn admin-btn--primary" disabled={busy || d.title.trim().length < 3} onClick={() => onSave(d)}>
          {t('agentRules.save')}
        </button>
      </div>
    </div>
  )
}

export function AdminAgentRulesTab({ onError }: { onError: (msg: string | null) => void }) {
  const { t } = useTranslation('admin')
  const [rows, setRows] = useState<AgentRule[]>([])
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<number | 'new' | null>(null)

  const load = useCallback(async () => {
    onError(null)
    const r = await apiFetch('/api/admin/agent-rules')
    if (!r.ok) {
      onError(await readDetail(r))
      return
    }
    setRows((await r.json()) as AgentRule[])
  }, [onError])

  useEffect(() => {
    void load()
  }, [load])

  const run = async (fn: () => Promise<Response>) => {
    setBusy(true)
    onError(null)
    try {
      const r = await fn()
      if (!r.ok) {
        onError(await readDetail(r))
        return false
      }
      await load()
      return true
    } finally {
      setBusy(false)
    }
  }

  const save = async (id: number | 'new', d: Draft) => {
    const ok = await run(() =>
      id === 'new'
        ? apiFetch('/api/admin/agent-rules', { method: 'POST', body: JSON.stringify(d) })
        : apiFetch(`/api/admin/agent-rules/${id}`, { method: 'PATCH', body: JSON.stringify(d) }),
    )
    if (ok) setEditing(null)
  }

  const toggle = (row: AgentRule) =>
    run(() => apiFetch(`/api/admin/agent-rules/${row.id}`, { method: 'PATCH', body: JSON.stringify({ enabled: !row.enabled }) }))

  const remove = (row: AgentRule) => {
    if (!window.confirm(t('agentRules.confirmDelete'))) return
    void run(() => apiFetch(`/api/admin/agent-rules/${row.id}`, { method: 'DELETE' }))
  }

  const reset = (row: AgentRule) => {
    if (!row.code || !window.confirm(t('agentRules.confirmReset'))) return
    void run(() => apiFetch(`/api/admin/agent-rules/reset/${row.code}`, { method: 'POST' }))
  }

  return (
    <div className="admin-ref">
      <div className="admin-ref__head">
        <div>
          <h2 className="admin-ref__title">{t('agentRules.title')}</h2>
          <p className="admin-ref__hint muted">{t('agentRules.hint')}</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" className="admin-btn admin-btn--ghost" disabled={busy} onClick={() => void load()}>
            {t('common.refresh')}
          </button>
          <button type="button" className="admin-btn admin-btn--primary" disabled={busy || editing === 'new'} onClick={() => setEditing('new')}>
            {t('agentRules.add')}
          </button>
        </div>
      </div>

      {editing === 'new' ? (
        <div className="admin-rule">
          <RuleForm initial={EMPTY} busy={busy} onSave={(d) => void save('new', d)} onCancel={() => setEditing(null)} />
        </div>
      ) : null}

      <div className="admin-rule__list">
        {rows.map((row) => (
          <article key={row.id} className={`admin-rule ${row.enabled ? '' : 'admin-rule--off'}`}>
            {editing === row.id ? (
              <RuleForm
                initial={{ title: row.title, prompt_zh: row.prompt_zh, prompt_en: row.prompt_en, enabled: row.enabled, sort: row.sort }}
                busy={busy}
                onSave={(d) => void save(row.id, d)}
                onCancel={() => setEditing(null)}
              />
            ) : (
              <>
                <div className="admin-rule__top">
                  <span className="admin-rule__badge">{row.locked ? t('agentRules.locked') : row.enabled ? t('agentRules.on') : t('agentRules.off')}</span>
                  <span className="muted">#{row.id}{row.code ? ` · ${row.code}` : ''}</span>
                </div>
                <p className="admin-rule__title">{row.title}</p>
                {row.prompt_zh ? <p className="admin-rule__prompt muted"><b>Seedream:</b> {row.prompt_zh}</p> : null}
                {row.prompt_en ? <p className="admin-rule__prompt muted"><b>GPT:</b> {row.prompt_en}</p> : null}
                {row.locked ? (
                  <p className="admin-rule__prompt muted">{t('agentRules.lockedHint')}</p>
                ) : (
                  <div className="admin-rule__row">
                    <button type="button" className="admin-btn admin-btn--ghost" disabled={busy} onClick={() => setEditing(row.id)}>{t('agentRules.edit')}</button>
                    <button type="button" className="admin-btn admin-btn--ghost" disabled={busy} onClick={() => void toggle(row)}>
                      {row.enabled ? t('agentRules.disable') : t('agentRules.enable')}
                    </button>
                    {row.code ? (
                      <button type="button" className="admin-btn admin-btn--ghost" disabled={busy} onClick={() => reset(row)}>{t('agentRules.reset')}</button>
                    ) : null}
                    <span style={{ flex: 1 }} />
                    <button type="button" className="admin-btn admin-btn--danger" disabled={busy} onClick={() => remove(row)}>{t('agentRules.delete')}</button>
                  </div>
                )}
              </>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}
