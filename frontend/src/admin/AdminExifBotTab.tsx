import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api'
import { formatDateTimeRu } from './utils'
import type { AdminExifBotStats, AdminExifBotUserDetail, AdminExifBotUserRow } from './types'

export function AdminExifBotTab({
  onError,
}: {
  onError: (msg: string | null) => void
}) {
  const { t } = useTranslation('admin')
  const [stats, setStats] = useState<AdminExifBotStats | null>(null)
  const [users, setUsers] = useState<AdminExifBotUserRow[]>([])
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<AdminExifBotUserDetail | null>(null)

  const loadStats = useCallback(async () => {
    const r = await apiFetch('/api/admin/exif-bot/stats')
    if (r.ok) setStats((await r.json()) as AdminExifBotStats)
    else onError(t('exifBot.statsError'))
  }, [onError, t])

  const loadUsers = useCallback(
    async (q: string) => {
      const params = new URLSearchParams()
      params.set('limit', '200')
      if (q.trim()) params.set('q', q.trim())
      const r = await apiFetch(`/api/admin/exif-bot/users?${params}`)
      if (r.ok) setUsers((await r.json()) as AdminExifBotUserRow[])
      else onError(t('exifBot.usersError'))
    },
    [onError, t],
  )

  const loadDetail = useCallback(async (id: number) => {
    const r = await apiFetch(`/api/admin/exif-bot/users/${id}`)
    if (r.ok) setDetail((await r.json()) as AdminExifBotUserDetail)
    else onError(t('exifBot.detailError'))
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
              <span className="admin-kpi__label">{t('exifBot.botUsers')}</span>
              <strong className="admin-kpi__value">{stats.total_users}</strong>
              <span className="admin-kpi__hint">{t('exifBot.withProfiles', { count: stats.users_with_profiles })}</span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('exifBot.totalProcesses')}</span>
              <strong className="admin-kpi__value">{stats.total_processes}</strong>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('exifBot.todayUtc')}</span>
              <strong className="admin-kpi__value">{stats.processes_today}</strong>
              <span className="admin-kpi__hint">{t('common.day')} {stats.utc_day}</span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('exifBot.phoneProfiles')}</span>
              <strong className="admin-kpi__value">{stats.total_profiles}</strong>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">{t('exifBot.active7_30')}</span>
              <strong className="admin-kpi__value">
                {stats.active_users_7d} / {stats.active_users_30d}
              </strong>
              <span className="admin-kpi__hint">{t('exifBot.byUpdatedAt')}</span>
            </div>
          </div>
        ) : null}

        <div className="admin-user-toolbar">
          <input
            type="search"
            placeholder={t('exifBot.searchPlaceholder')}
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
                <th>{t('exifBot.profiles')}</th>
                <th>{t('exifBot.totalPhotos')}</th>
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
                  <td className="mono">{u.profiles_count}</td>
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
              {t('exifBot.noUsers')}
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
            <dt>{t('exifBot.totalProcessesDetail')}</dt>
            <dd className="mono">{detail.total_process_count}</dd>
            <dt>{t('exifBot.todayUtc')}</dt>
            <dd className="mono">{detail.daily_process_count}</dd>
            <dt>{t('exifBot.profilesCount')}</dt>
            <dd className="mono">{detail.profiles_count}</dd>
            <dt>{t('common.language')}</dt>
            <dd>{detail.language_code ?? '—'}</dd>
            <dt>{t('common.registration')}</dt>
            <dd>{formatDateTimeRu(detail.created_at)}</dd>
            <dt>{t('common.lastActivity')}</dt>
            <dd>{formatDateTimeRu(detail.updated_at)}</dd>
          </dl>

          <section className="admin-panel__section">
            <h3>{t('exifBot.phoneProfilesSection')}</h3>
            {detail.profiles.length === 0 ? (
              <p className="muted">{t('exifBot.noProfiles')}</p>
            ) : (
              <ul className="admin-usage-list">
                {detail.profiles.map((p) => (
                  <li key={p.id}>
                    <strong>{p.title || `#${p.id}`}</strong>
                    <div className="muted small">
                      {p.camera_preset_id ?? t('exifBot.noPreset')}
                      {p.is_ready ? ` · ${t('exifBot.ready')}` : ` · ${t('exifBot.draft')}`}
                      {p.has_gps ? ' · GPS' : ''}
                    </div>
                    <div className="muted small">
                      selfie {p.has_selfie_ref ? '✓' : '—'} · main {p.has_main_ref ? '✓' : '—'}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      ) : (
        <div className="admin-users__placeholder muted">
          {t('exifBot.placeholder')}
        </div>
      )}
    </div>
  )
}
