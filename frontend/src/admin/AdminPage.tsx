import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { apiFetch, getToken } from '../api'
import { AdminBarChart, AdminHBarChart } from './AdminBarChart'
import { AdminUserPanel } from './AdminUserPanel'
import {
  SUBSCRIPTION_STATUS_LABELS,
  USAGE_KIND_LABELS,
  billingPlanLabel,
  planTierLabel,
} from './constants'
import type { AdminStats, AdminUserDetail, AdminUserRow } from './types'
import { formatDateTimeRu } from './utils'
import './admin.css'

interface UserMe {
  is_platform_admin?: boolean
  email?: string
}

export function AdminPage() {
  const [gate, setGate] = useState<'loading' | 'ok' | 'denied' | 'anon'>('loading')
  const [meEmail, setMeEmail] = useState('')
  const [tab, setTab] = useState<'overview' | 'users'>('overview')
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [users, setUsers] = useState<AdminUserRow[]>([])
  const [userSearch, setUserSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<AdminUserDetail | null>(null)

  const loadStats = useCallback(async () => {
    const r = await apiFetch('/api/admin/stats?chart_days=30')
    if (r.ok) setStats((await r.json()) as AdminStats)
  }, [])

  const loadUsers = useCallback(async (search: string) => {
    const q = new URLSearchParams()
    q.set('limit', '200')
    if (search.trim()) q.set('q', search.trim())
    const r = await apiFetch(`/api/admin/users?${q}`)
    if (r.ok) setUsers((await r.json()) as AdminUserRow[])
  }, [])

  const loadUserDetail = useCallback(async (id: number) => {
    const r = await apiFetch(`/api/admin/users/${id}`)
    if (r.ok) setSelectedDetail((await r.json()) as AdminUserDetail)
  }, [])

  useEffect(() => {
    if (!getToken()) {
      setGate('anon')
      return
    }
    void (async () => {
      const r = await apiFetch('/api/auth/me')
      if (!r.ok) {
        setGate('anon')
        return
      }
      const me = (await r.json()) as UserMe
      if (!me.is_platform_admin) {
        setGate('denied')
        return
      }
      setMeEmail(me.email ?? '')
      setGate('ok')
    })()
  }, [])

  useEffect(() => {
    if (gate !== 'ok') return
    setBusy(true)
    void Promise.all([loadStats(), loadUsers('')]).finally(() => setBusy(false))
  }, [gate, loadStats, loadUsers])

  useEffect(() => {
    if (selectedId == null) {
      setSelectedDetail(null)
      return
    }
    void loadUserDetail(selectedId)
  }, [selectedId, loadUserDetail])

  const refreshAll = () => {
    setBusy(true)
    void Promise.all([loadStats(), loadUsers(userSearch)]).finally(() => setBusy(false))
  }

  const onUserUpdated = (row: AdminUserRow) => {
    setUsers((prev) => prev.map((u) => (u.id === row.id ? { ...u, ...row } : u)))
    if (selectedDetail?.id === row.id) {
      setSelectedDetail((prev) => (prev ? { ...prev, ...row } : prev))
      void loadUserDetail(row.id)
    }
  }

  if (gate === 'loading') {
    return (
      <div className="admin-page admin-page--center">
        <p className="muted">Проверка доступа…</p>
      </div>
    )
  }
  if (gate === 'anon') {
    return <Navigate to="/login" replace />
  }
  if (gate === 'denied') {
    return (
      <div className="admin-page admin-page--center">
        <h1>Нет доступа</h1>
        <p className="muted">Админ-панель только для администраторов платформы.</p>
        <Link to="/workspace" className="admin-back-link">
          В рабочее пространство
        </Link>
      </div>
    )
  }

  const statusItems =
    stats?.subscriptions_by_status.map((s) => ({
      label: SUBSCRIPTION_STATUS_LABELS[s.label] ?? s.label,
      count: s.count,
    })) ?? []

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div>
          <p className="admin-header__eyebrow">ModelMate · платформа</p>
          <h1 className="admin-header__title">Админ-панель</h1>
          {meEmail ? <p className="admin-header__sub muted">{meEmail}</p> : null}
        </div>
        <div className="admin-header__actions">
          <button type="button" className="ghost-btn" disabled={busy} onClick={refreshAll}>
            Обновить
          </button>
          <Link to="/workspace" className="ghost-btn">
            ← Кабинет
          </Link>
        </div>
      </header>

      {error ? (
        <div className="admin-banner admin-banner--error" role="alert">
          {error}
          <button type="button" className="admin-banner__close" onClick={() => setError(null)}>
            ✕
          </button>
        </div>
      ) : null}

      <nav className="admin-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'overview'}
          className={tab === 'overview' ? 'admin-tabs__btn active' : 'admin-tabs__btn'}
          onClick={() => setTab('overview')}
        >
          Обзор
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'users'}
          className={tab === 'users' ? 'admin-tabs__btn active' : 'admin-tabs__btn'}
          onClick={() => setTab('users')}
        >
          Пользователи
        </button>
      </nav>

      {tab === 'overview' && stats ? (
        <div className="admin-overview" role="tabpanel">
          <div className="admin-kpi-grid">
            <div className="admin-kpi">
              <span className="admin-kpi__label">Пользователей</span>
              <strong className="admin-kpi__value">{stats.total_users}</strong>
              <span className="admin-kpi__hint">
                владельцев {stats.workspace_owners} · в команде {stats.workspace_members}
              </span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Кредитов на балансах</span>
              <strong className="admin-kpi__value">{stats.total_credits_balance}</strong>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Моделей студии</span>
              <strong className="admin-kpi__value">{stats.studio_models_total}</strong>
              <span className="admin-kpi__hint">фото {stats.studio_model_images_total}</span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Контент в архиве</span>
              <strong className="admin-kpi__value">{stats.studio_generations_total}</strong>
              <span className="admin-kpi__hint">
                картинки {stats.studio_images_total} · видео {stats.studio_videos_total} · motion{' '}
                {stats.studio_motion_renders_total}
              </span>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Диалоги</span>
              <strong className="admin-kpi__value">{stats.conversations_total}</strong>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">Оплат (ЮKassa)</span>
              <strong className="admin-kpi__value">{stats.yookassa_payments_total}</strong>
            </div>
            <div className="admin-kpi">
              <span className="admin-kpi__label">По рефералке</span>
              <strong className="admin-kpi__value">{stats.referrals_total}</strong>
              <span className="admin-kpi__hint">зарегистрировались по приглашению</span>
            </div>
          </div>

          <div className="admin-charts-grid">
            <AdminBarChart title="Регистрации владельцев (30 дн.)" series={stats.registrations_by_day} />
            <AdminBarChart title="Генерации в архиве (30 дн.)" series={stats.generations_by_day} />
            <AdminHBarChart title="Подписки по статусу" items={statusItems} />
            <AdminHBarChart title="Оплачиваемые тарифы (active / trialing / past_due)" items={stats.subscriptions_by_plan} />
          </div>

          {Object.keys(stats.usage_by_kind).length > 0 ? (
            <section className="admin-usage">
              <h2 className="admin-section-title">События usage (топ)</h2>
              <ul className="admin-usage-list">
                {Object.entries(stats.usage_by_kind)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 20)
                  .map(([k, c]) => (
                    <li key={k}>
                      <span>{USAGE_KIND_LABELS[k] ?? k}</span>
                      <span className="mono">{c}</span>
                    </li>
                  ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}

      {tab === 'overview' && !stats && busy ? <p className="muted">Загрузка аналитики…</p> : null}

      {tab === 'users' ? (
        <div className={`admin-users${selectedDetail ? ' admin-users--split' : ''}`} role="tabpanel">
          <div className="admin-users__main">
            <div className="admin-user-toolbar">
              <input
                type="search"
                placeholder="Поиск по email"
                value={userSearch}
                onChange={(e) => setUserSearch(e.target.value)}
                className="admin-user-search"
              />
              <button type="button" className="ghost-btn" disabled={busy} onClick={() => void loadUsers(userSearch)}>
                Найти
              </button>
              <button
                type="button"
                className="ghost-btn"
                disabled={busy}
                onClick={() => {
                  setUserSearch('')
                  void loadUsers('')
                }}
              >
                Сброс
              </button>
            </div>

            <div className="admin-user-table-wrap">
              <table className="admin-user-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Email</th>
                    <th>Роль</th>
                    <th>Подписка</th>
                    <th>Тариф</th>
                    <th>Кредиты</th>
                    <th>Модели</th>
                    <th>Генерации</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    const isOwner = u.parent_user_id == null
                    const active = selectedId === u.id
                    return (
                      <tr
                        key={u.id}
                        className={active ? 'admin-user-row--active' : ''}
                        onClick={() => setSelectedId(u.id)}
                      >
                        <td className="mono">{u.id}</td>
                        <td>
                          <div>{u.email}</div>
                          {!u.is_active ? <span className="admin-badge admin-badge--off">выкл</span> : null}
                        </td>
                        <td>{isOwner ? 'владелец' : u.member_login ?? 'участник'}</td>
                        <td>{SUBSCRIPTION_STATUS_LABELS[u.subscription_status] ?? u.subscription_status}</td>
                        <td>
                          {billingPlanLabel(u.billing_plan)} · {planTierLabel(u.plan_tier)}
                          <div className="muted small">{formatDateTimeRu(u.subscription_period_end)}</div>
                        </td>
                        <td className="mono">{u.credits_balance}</td>
                        <td className="mono">{u.studio_models_count ?? 0}</td>
                        <td className="mono">{u.studio_generations_count ?? 0}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {selectedDetail ? (
            <AdminUserPanel
              user={selectedDetail}
              busy={busy}
              onBusy={setBusy}
              onUpdated={onUserUpdated}
              onClose={() => setSelectedId(null)}
              onError={setError}
            />
          ) : (
            <div className="admin-users__placeholder muted">
              Выберите пользователя в таблице, чтобы изменить подписку, кредиты и доступ.
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
