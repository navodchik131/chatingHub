import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { formatDateTimeRu } from './utils'
import type { AdminIgBotStats, AdminIgBotUserDetail, AdminIgBotUserRow } from './types'

export function AdminIgBotTab({
  onError,
}: {
  onError: (msg: string | null) => void
}) {
  const [stats, setStats] = useState<AdminIgBotStats | null>(null)
  const [users, setUsers] = useState<AdminIgBotUserRow[]>([])
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<AdminIgBotUserDetail | null>(null)

  const loadStats = useCallback(async () => {
    const r = await apiFetch('/api/admin/ig-bot/stats')
    if (r.ok) setStats((await r.json()) as AdminIgBotStats)
    else onError('Не удалось загрузить статистику IG-бота')
  }, [onError])

  const loadUsers = useCallback(
    async (q: string) => {
      const params = new URLSearchParams()
      params.set('limit', '200')
      if (q.trim()) params.set('q', q.trim())
      const r = await apiFetch(`/api/admin/ig-bot/users?${params}`)
      if (r.ok) setUsers((await r.json()) as AdminIgBotUserRow[])
      else onError('Не удалось загрузить пользователей IG-бота')
    },
    [onError],
  )

  const loadDetail = useCallback(async (id: number) => {
    const r = await apiFetch(`/api/admin/ig-bot/users/${id}`)
    if (r.ok) setDetail((await r.json()) as AdminIgBotUserDetail)
    else onError('Не удалось загрузить карточку пользователя')
  }, [onError])

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
              <span className="admin-kpi__label">Пользователей бота</span>
              <strong className="admin-kpi__value">{stats.total_users}</strong>
              <span className="admin-kpi__hint">
                скачивали сегодня: {stats.users_downloaded_today}
              </span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Скачиваний всего</span>
              <strong className="admin-kpi__value">{stats.total_downloads}</strong>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Сегодня (UTC)</span>
              <strong className="admin-kpi__value">{stats.downloads_today}</strong>
              <span className="admin-kpi__hint">день {stats.utc_day}</span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Лимиты / сутки</span>
              <strong className="admin-kpi__value">
                {stats.daily_limit_default} / {stats.daily_limit_subscribed}
              </strong>
              <span className="admin-kpi__hint">без подписки / с каналом</span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Активны 7 / 30 дн.</span>
              <strong className="admin-kpi__value">
                {stats.active_users_7d} / {stats.active_users_30d}
              </strong>
              <span className="admin-kpi__hint">по updated_at</span>
            </div>
          </div>
        ) : null}

        <div className="admin-user-toolbar">
          <input
            type="search"
            placeholder="Поиск: @username, имя, telegram id"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="admin-user-search"
          />
          <button type="button" className="ghost-btn" disabled={busy} onClick={() => void loadUsers(search)}>
            Найти
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
            Сброс
          </button>
          <button type="button" className="ghost-btn" disabled={busy} onClick={refresh}>
            Обновить
          </button>
        </div>

        {busy && !users.length ? <p className="muted">Загрузка…</p> : null}

        <div className="admin-user-table-wrap">
          <table className="admin-user-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Telegram</th>
                <th>Всего видео</th>
                <th>Сегодня</th>
                <th>Регистрация</th>
                <th>Активность</th>
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
              Пользователей IG-бота пока нет или бот не включён (IG_BOT_TOKEN).
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
                Открыть в Telegram
              </a>
            </p>
          ) : null}

          <dl className="admin-panel__stats">
            <dt>Всего скачиваний</dt>
            <dd className="mono">{detail.total_process_count}</dd>
            <dt>Сегодня (UTC)</dt>
            <dd className="mono">{detail.daily_process_count}</dd>
            {stats ? (
              <>
                <dt>Лимит без подписки</dt>
                <dd className="mono">{stats.daily_limit_default} / сутки</dd>
                <dt>Лимит с подпиской</dt>
                <dd className="mono">{stats.daily_limit_subscribed} / сутки</dd>
              </>
            ) : null}
            <dt>Язык</dt>
            <dd>{detail.language_code ?? '—'}</dd>
            <dt>День счётчика</dt>
            <dd className="mono">{detail.daily_process_day ?? '—'}</dd>
            <dt>Регистрация</dt>
            <dd>{formatDateTimeRu(detail.created_at)}</dd>
            <dt>Последняя активность</dt>
            <dd>{formatDateTimeRu(detail.updated_at)}</dd>
          </dl>
        </aside>
      ) : (
        <div className="admin-users__placeholder muted">
          Выберите пользователя бота, чтобы увидеть статистику скачиваний.
        </div>
      )}
    </div>
  )
}
