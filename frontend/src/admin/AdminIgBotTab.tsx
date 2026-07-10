import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { formatDateTimeRu } from './utils'
import type { AdminIgBotStats, AdminIgBotUserDetail, AdminIgBotUserRow } from './types'

export function AdminIgBotTab({
  onError,
}: {
  onError: (msg: string | null) => void
}) {
  const { t } = useTranslation('admin')
  const [stats, setStats] = useState<AdminIgBotStats | null>(null)
  const [users, setUsers] = useState<AdminIgBotUserRow[]>([])
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<AdminIgBotUserDetail | null>(null)

  const loadStats = useCallback(async () => {
    const r = await apiFetch('/api/admin/ig-bot/stats')
    if (r.ok) setStats((await r.json()) as AdminIgBotStats)
    else onError(t('igBot.statsError'))
  }, [onError, t])

  const loadUsers = useCallback(
    async (q: string) => {
      const params = new URLSearchParams()
      params.set('limit', '200')
      if (q.trim()) params.set('q', q.trim())
      const r = await apiFetch(`/api/admin/ig-bot/users?${params}`)
      if (r.ok) setUsers((await r.json()) as AdminIgBotUserRow[])
      else onError(t('igBot.usersError'))
    },
    [onError, t],
  )

  const loadDetail = useCallback(async (id: number) => {
    const r = await apiFetch(`/api/admin/ig-bot/users/${id}`)
    if (r.ok) setDetail((await r.json()) as AdminIgBotUserDetail)
    else onError(t('igBot.detailError'))
  }, [onError, t])

  useEffect(() => {
    setBusy(true)
    onError(null)
    void Promise.all([loadStats(), loadUsers('')]).finally(() => setBusy(false))
  }, [loadStats, loadUsers, onError])

  useEffect(() => {
    if (selectedId == null) {
      setDetail(null)
      return
    }
    void loadDetail(selectedId)
  }, [selectedId, loadDetail])

  const refresh = () => {
    setBusy(true)
    onError(null)
    void Promise.all([loadStats(), loadUsers(search)]).finally(() => setBusy(false))
  }

  return (
    <div className={`admin-users${detail ? ' admin-users--split' : ''}`} role="tabpanel">
      <div className="admin-users__main">
        {stats ? (
          <div className="admin-kpi-grid" style={{ marginBottom: '1.25rem' }}>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('igBot.botUsers')}</span>
              <strong className="admin-kpi__value">{stats.total_users}</strong>
              <span className="admin-kpi__hint">
                {t('igBot.downloadedToday', { count: stats.users_downloaded_today })}
              </span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('igBot.totalDownloads')}</span>
              <strong className="admin-kpi__value">{stats.total_downloads}</strong>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('igBot.todayUtc')}</span>
              <strong className="admin-kpi__value">{stats.downloads_today}</strong>
              <span className="admin-kpi__hint">{t('common.day')} {stats.utc_day}</span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('igBot.limitsPerDay')}</span>
              <strong className="admin-kpi__value">
                {stats.daily_limit_default} / {stats.daily_limit_subscribed}
              </strong>
              <span className="admin-kpi__hint">{t('igBot.limitsHint')}</span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('igBot.active7_30')}</span>
              <strong className="admin-kpi__value">
                {stats.active_users_7d} / {stats.active_users_30d}
              </strong>
              <span className="admin-kpi__hint">{t('igBot.byUpdatedAt')}</span>
            </div>
          </div>
        ) : null}

        <div className="admin-user-toolbar">
          <input
            type="search"
            placeholder={t('igBot.searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="admin-user-search"
          />
          <button type="button" className="ghost-btn" disabled={busy} onClick={() => void loadUsers(search)}>
            {t('common.search')}
          </button>
          <button
            type="button"
            className="ghost-btn"
            disabled={busy}
            onClick={() => {
              setSearch('')
              void loadUsers('')
            }}
          >
            {t('common.reset')}
          </button>
          <button type="button" className="ghost-btn" disabled={busy} onClick={refresh}>
            {t('common.refresh')}
          </button>
        </div>

        {busy && !users.length ? <p className="muted">{t('common.loading')}</p> : null}

        <div className="admin-user-table-wrap">
          <table className="admin-user-table">
            <thead>
              <tr>
                <th>{t('common.id')}</th>
                <th>{t('common.telegram')}</th>
                <th>{t('igBot.totalVideos')}</th>
                <th>{t('common.today')}</th>
                <th>{t('common.registration')}</th>
                <th>{t('common.activity')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.id}
                  className={selectedId === u.id ? 'admin-user-row--active' : ''}
                  onClick={() => setSelectedId(u.id)}
                >
                  <td className="mono">{u.id}</td>
                  <td>
                    <div>{u.display_name}</div>
                    <div className="muted small mono">
                      {u.username ? `@${u.username}` : u.telegram_id}
                    </div>
                  </td>
                  <td className="mono">{u.total_process_count}</td>
                  <td className="mono">{u.daily_process_count}</td>
                  <td className="small">{formatDateTimeRu(u.created_at)}</td>
                  <td className="small">{formatDateTimeRu(u.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!busy && users.length === 0 ? (
            <p className="muted" style={{ padding: '1rem' }}>
              {t('igBot.noUsers')}
            </p>
          ) : null}
        </div>
      </div>

      {detail ? (
        <aside className="admin-panel">
          <header className="admin-panel__head">
            <div>
              <h2 className="admin-panel__title">{detail.display_name}</h2>
              <p className="admin-panel__meta muted">
                Telegram ID {detail.telegram_id}
                {detail.username ? ` · @${detail.username}` : ''}
              </p>
            </div>
            <button type="button" className="ghost-btn" onClick={() => setSelectedId(null)}>
              ✕
            </button>
          </header>

          {detail.telegram_link ? (
            <p style={{ margin: '0 0 1rem' }}>
              <a href={detail.telegram_link} target="_blank" rel="noreferrer">
                {t('common.openInTelegram')}
              </a>
            </p>
          ) : null}

          <dl className="admin-panel__stats">
            <dt>{t('igBot.totalDownloadsDetail')}</dt>
            <dd className="mono">{detail.total_process_count}</dd>
            <dt>{t('igBot.todayUtc')}</dt>
            <dd className="mono">{detail.daily_process_count}</dd>
            {stats ? (
              <>
                <dt>{t('igBot.limitNoSub')}</dt>
                <dd className="mono">{stats.daily_limit_default}{t('common.perDay')}</dd>
                <dt>{t('igBot.limitWithSub')}</dt>
                <dd className="mono">{stats.daily_limit_subscribed}{t('common.perDay')}</dd>
              </>
            ) : null}
            <dt>{t('common.language')}</dt>
            <dd>{detail.language_code ?? '—'}</dd>
            <dt>{t('igBot.counterDay')}</dt>
            <dd className="mono">{detail.daily_process_day ?? '—'}</dd>
            <dt>{t('common.registration')}</dt>
            <dd>{formatDateTimeRu(detail.created_at)}</dd>
            <dt>{t('common.lastActivity')}</dt>
            <dd>{formatDateTimeRu(detail.updated_at)}</dd>
          </dl>
        </aside>
      ) : (
        <div className="admin-users__placeholder muted">
          {t('igBot.placeholder')}
        </div>
      )}
    </div>
  )
}
