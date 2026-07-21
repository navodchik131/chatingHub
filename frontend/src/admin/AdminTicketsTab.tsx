import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'

interface TicketReply {
  id: number
  is_staff: boolean
  message: string
  created_at: string
}

interface TicketListItem {
  id: number
  user_id: number
  user_email: string
  type: string
  subject: string
  status: string
  created_at: string
  updated_at: string
}

interface TicketDetail extends TicketListItem {
  message: string
  replies: TicketReply[]
}

interface Props {
  onError: (msg: string | null) => void
}

const TYPE_LABELS: Record<string, { ru: string; en: string }> = {
  general: { ru: 'Общие вопросы', en: 'General' },
  technical: { ru: 'Технические проблемы', en: 'Technical issues' },
  payment: { ru: 'Оплата', en: 'Payment' },
  subscription: { ru: 'Подписки', en: 'Subscriptions' },
}

const STATUS_OPTIONS = ['submitted', 'in_review', 'answered', 'closed'] as const

export function AdminTicketsTab({ onError }: Props) {
  const { t, i18n } = useTranslation('admin')
  const lang = i18n.language?.startsWith('ru') ? 'ru' : 'en'
  const [tickets, setTickets] = useState<TicketListItem[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [reply, setReply] = useState('')
  const [busy, setBusy] = useState(false)

  const loadTickets = useCallback(async () => {
    const q = new URLSearchParams()
    q.set('limit', '200')
    if (statusFilter) q.set('status', statusFilter)
    const r = await apiFetch(`/api/admin/tickets?${q}`)
    if (r.ok) setTickets((await r.json()) as TicketListItem[])
    else onError(t('tickets.loadFailed'))
  }, [statusFilter, onError, t])

  const loadDetail = useCallback(async (id: number) => {
    const r = await apiFetch(`/api/admin/tickets/${id}`)
    if (r.ok) setDetail((await r.json()) as TicketDetail)
    else onError(t('tickets.loadFailed'))
  }, [onError, t])

  useEffect(() => {
    void loadTickets()
  }, [loadTickets])

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null)
      return
    }
    void loadDetail(selectedId)
  }, [selectedId, loadDetail])

  const typeLabel = (type: string) => {
    const hit = TYPE_LABELS[type]
    return hit ? hit[lang] : type
  }

  const statusLabel = (status: string) => t(`tickets.status.${status}`, status)

  const sendReply = async () => {
    if (!selectedId || !reply.trim()) return
    setBusy(true)
    onError(null)
    try {
      const r = await apiFetch(`/api/admin/tickets/${selectedId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: reply.trim() }),
      })
      if (!r.ok) throw new Error(t('tickets.replyFailed'))
      setReply('')
      await loadDetail(selectedId)
      await loadTickets()
    } catch (e) {
      onError(e instanceof Error ? e.message : t('tickets.replyFailed'))
    } finally {
      setBusy(false)
    }
  }

  const patchStatus = async (status: string) => {
    if (!selectedId) return
    setBusy(true)
    onError(null)
    try {
      const r = await apiFetch(`/api/admin/tickets/${selectedId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      if (!r.ok) throw new Error(t('tickets.statusFailed'))
      await loadDetail(selectedId)
      await loadTickets()
    } catch (e) {
      onError(e instanceof Error ? e.message : t('tickets.statusFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-tickets">
      <div className="admin-tickets__toolbar">
        <label className="admin-field">
          <span className="admin-field__label">{t('common.status')}</span>
          <select
            className="admin-input"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">{t('tickets.allStatuses')}</option>
            {STATUS_OPTIONS.map((st) => (
              <option key={st} value={st}>{statusLabel(st)}</option>
            ))}
          </select>
        </label>
        <button type="button" className="admin-refresh-btn" onClick={() => void loadTickets()}>
          ↻ {t('common.refresh')}
        </button>
      </div>

      <div className="admin-tickets__grid">
        <div className="admin-card admin-tickets__list">
          <div className="admin-card__title">{t('tickets.listTitle')}</div>
          {tickets.length ? (
            <div className="admin-tickets__rows">
              {tickets.map((tk) => (
                <button
                  key={tk.id}
                  type="button"
                  className={`admin-tickets__row${selectedId === tk.id ? ' is-active' : ''}`}
                  onClick={() => setSelectedId(tk.id)}
                >
                  <div className="admin-tickets__row-head">
                    <span className="admin-tickets__subject">{tk.subject}</span>
                    <span className="admin-badge">{statusLabel(tk.status)}</span>
                  </div>
                  <div className="muted small">
                    {tk.user_email} · {typeLabel(tk.type)}
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="muted">{t('tickets.empty')}</div>
          )}
        </div>

        <div className="admin-card admin-tickets__detail">
          {!detail ? (
            <div className="muted">{t('tickets.selectHint')}</div>
          ) : (
            <>
              <div className="admin-tickets__detail-head">
                <div>
                  <div className="admin-card__title">{detail.subject}</div>
                  <div className="muted small">
                    {detail.user_email} · {typeLabel(detail.type)} · #{detail.id}
                  </div>
                </div>
                <select
                  className="admin-input admin-input--compact"
                  value={detail.status}
                  disabled={busy}
                  onChange={(e) => void patchStatus(e.target.value)}
                >
                  {STATUS_OPTIONS.map((st) => (
                    <option key={st} value={st}>{statusLabel(st)}</option>
                  ))}
                </select>
              </div>

              <div className="admin-tickets__thread">
                <div className={`admin-tickets__msg${detail.replies?.length ? '' : ' is-user'}`}>
                  <div className="admin-tickets__msg-meta muted small">{t('tickets.initial')}</div>
                  <div>{detail.message}</div>
                </div>
                {(detail.replies || []).map((r) => (
                  <div key={r.id} className={`admin-tickets__msg${r.is_staff ? ' is-staff' : ' is-user'}`}>
                    <div className="admin-tickets__msg-meta muted small">
                      {r.is_staff ? t('tickets.staff') : t('tickets.user')}
                    </div>
                    <div>{r.message}</div>
                  </div>
                ))}
              </div>

              <div className="admin-tickets__reply">
                <textarea
                  className="admin-input admin-input--textarea"
                  rows={4}
                  value={reply}
                  placeholder={t('tickets.replyPlaceholder')}
                  onChange={(e) => setReply(e.target.value)}
                />
                <button type="button" className="admin-btn admin-btn--primary" disabled={busy || !reply.trim()} onClick={() => void sendReply()}>
                  {t('tickets.sendReply')}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
