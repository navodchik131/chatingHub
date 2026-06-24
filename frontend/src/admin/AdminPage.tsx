import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { apiFetch, getToken } from '../api'
import { AdminBarChart, AdminHBarChart } from './AdminBarChart'
import { AdminDrillableKpi, AdminDrillLink } from './AdminDrillableKpi'
import { AdminSegmentDrill } from './AdminSegmentDrill'
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
  const [drillSegment, setDrillSegment] = useState<string | null>(null)
  const [drillTitle, setDrillTitle] = useState('')

  const openDrill = useCallback((segment: string, title: string) => {
    setDrillSegment(segment)
    setDrillTitle(title)
  }, [])

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

  const onSelectUserFromDrill = useCallback(
    (userId: number) => {
      setDrillSegment(null)
      setTab('users')
      setSelectedId(userId)
      void loadUserDetail(userId)
    },
    [loadUserDetail],
  )

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
            <AdminDrillableKpi
              segment="yookassa_payments"
              title="Оплаты ЮKassa"
              count={stats.yookassa_payments_total}
              onDrill={openDrill}
            >
              <span className="admin-kpi__label">Оплат (ЮKassa)</span>
              <strong className="admin-kpi__value">{stats.yookassa_payments_total}</strong>
              <span className="admin-kpi__hint">клик — кто оплатил и что</span>
            </AdminDrillableKpi>
            <AdminDrillableKpi
              segment="referrals"
              title="Регистрации по рефералке"
              count={stats.referrals_total}
              onDrill={openDrill}
            >
              <span className="admin-kpi__label">По рефералке</span>
              <strong className="admin-kpi__value">{stats.referrals_total}</strong>
              <span className="admin-kpi__hint">зарегистрировались по приглашению</span>
            </AdminDrillableKpi>
          </div>

          {stats.engagement ? (
            <section className="admin-engagement">
              <h2 className="admin-section-title">Вовлечённость владельцев</h2>
              <p className="admin-engagement__dek muted">
                Активность: сообщения в чатах, студия или usage за период. «Зомби» — зарегистрировались, но ни
                разу не пользовались продуктом (без учёта бонусных событий). Оплаченная подписка — status active,
                период не истёк (не trial после регистрации).
              </p>
              <div className="admin-kpi-grid admin-kpi-grid--engagement">
                <AdminDrillableKpi
                  segment="active_7d"
                  title="Активны за 7 дней"
                  count={stats.engagement.active_owners_7d}
                  onDrill={openDrill}
                  className="admin-kpi--highlight"
                >
                  <span className="admin-kpi__label">Активны за 7 дн.</span>
                  <strong className="admin-kpi__value">
                    {stats.engagement.active_owners_7d}
                    <span className="admin-kpi__pct"> ({stats.engagement.active_owners_7d_pct}%)</span>
                  </strong>
                  <span className="admin-kpi__hint">от {stats.workspace_owners} владельцев</span>
                </AdminDrillableKpi>
                <AdminDrillableKpi
                  segment="active_30d"
                  title="Активны за 30 дней"
                  count={stats.engagement.active_owners_30d}
                  onDrill={openDrill}
                  className="admin-kpi--highlight"
                >
                  <span className="admin-kpi__label">Активны за 30 дн.</span>
                  <strong className="admin-kpi__value">
                    {stats.engagement.active_owners_30d}
                    <span className="admin-kpi__pct"> ({stats.engagement.active_owners_30d_pct}%)</span>
                  </strong>
                </AdminDrillableKpi>
                <AdminDrillableKpi
                  segment="paid_active"
                  title="Оплаченная подписка"
                  count={stats.engagement.paid_active_owners}
                  onDrill={openDrill}
                >
                  <span className="admin-kpi__label">Оплаченная подписка</span>
                  <strong className="admin-kpi__value">
                    {stats.engagement.paid_active_owners}
                    <span className="admin-kpi__pct"> ({stats.engagement.paid_active_pct}%)</span>
                  </strong>
                  <span className="admin-kpi__hint">
                    <AdminDrillLink
                      segment="trialing"
                      title="Пробный период"
                      count={stats.engagement.trialing_owners}
                      onDrill={openDrill}
                    >
                      trial {stats.engagement.trialing_owners}
                    </AdminDrillLink>
                    {' · '}
                    <AdminDrillLink
                      segment="past_due"
                      title="Просрочен платёж"
                      count={stats.engagement.past_due_owners}
                      onDrill={openDrill}
                    >
                      past_due {stats.engagement.past_due_owners}
                    </AdminDrillLink>
                  </span>
                </AdminDrillableKpi>
                <AdminDrillableKpi
                  segment="paid_or_trialing"
                  title="Подписка active / trial / past_due"
                  count={stats.engagement.paid_or_trialing_owners}
                  onDrill={openDrill}
                >
                  <span className="admin-kpi__label">Подписка (active / trial / past_due)</span>
                  <strong className="admin-kpi__value">
                    {stats.engagement.paid_or_trialing_owners}
                    <span className="admin-kpi__pct"> ({stats.engagement.paid_or_trialing_pct}%)</span>
                  </strong>
                </AdminDrillableKpi>
                <AdminDrillableKpi
                  segment="zombie"
                  title="Без активности"
                  count={stats.engagement.zombie_owners}
                  onDrill={openDrill}
                  className="admin-kpi--warn"
                >
                  <span className="admin-kpi__label">Зомби (без активности)</span>
                  <strong className="admin-kpi__value">
                    {stats.engagement.zombie_owners}
                    <span className="admin-kpi__pct"> ({stats.engagement.zombie_pct}%)</span>
                  </strong>
                  <span className="admin-kpi__hint">
                    активных хоть раз:{' '}
                    <AdminDrillLink
                      segment="engaged_ever"
                      title="Активны хотя бы раз"
                      count={stats.engagement.engaged_owners_ever}
                      onDrill={openDrill}
                    >
                      {stats.engagement.engaged_owners_ever}
                    </AdminDrillLink>
                  </span>
                </AdminDrillableKpi>
                <AdminDrillableKpi
                  segment="registered_30d"
                  title="Регистрации за 30 дней"
                  count={stats.engagement.registered_owners_30d}
                  onDrill={openDrill}
                >
                  <span className="admin-kpi__label">Регистрации за 30 дн.</span>
                  <strong className="admin-kpi__value">{stats.engagement.registered_owners_30d}</strong>
                  <span className="admin-kpi__hint">
                    из них paid active:{' '}
                    <AdminDrillLink
                      segment="new_paid_active_30d"
                      title="Новые с paid active"
                      count={stats.engagement.new_paid_active_owners_30d}
                      onDrill={openDrill}
                    >
                      {stats.engagement.new_paid_active_owners_30d} ({stats.engagement.new_paid_active_30d_pct}%)
                    </AdminDrillLink>
                  </span>
                </AdminDrillableKpi>
                <AdminDrillableKpi
                  segment="yookassa_credits_buyers"
                  title="Покупали кредиты"
                  count={stats.engagement.owners_yookassa_credits_buyers}
                  onDrill={openDrill}
                >
                  <span className="admin-kpi__label">Покупали кредиты (ЮKassa)</span>
                  <strong className="admin-kpi__value">
                    {stats.engagement.owners_yookassa_credits_buyers}
                  </strong>
                </AdminDrillableKpi>
                <div className="admin-kpi admin-kpi--split">
                  <span className="admin-kpi__label">Студия / чаты</span>
                  <div className="admin-kpi__split-vals">
                    <AdminDrillLink
                      segment="owners_with_studio"
                      title="Пробовали студию"
                      count={stats.engagement.owners_with_studio}
                      onDrill={openDrill}
                    >
                      <strong className="admin-kpi__value">{stats.engagement.owners_with_studio}</strong>
                      <span className="admin-kpi__hint">студия</span>
                    </AdminDrillLink>
                    <span className="admin-kpi__split-sep">/</span>
                    <AdminDrillLink
                      segment="owners_with_chat"
                      title="Писали в чатах"
                      count={stats.engagement.owners_with_chat}
                      onDrill={openDrill}
                    >
                      <strong className="admin-kpi__value">{stats.engagement.owners_with_chat}</strong>
                      <span className="admin-kpi__hint">чаты</span>
                    </AdminDrillLink>
                  </div>
                </div>
              </div>
            </section>
          ) : null}

          {stats?.activation_funnel && stats.activation_funnel.registered > 0 ? (
            <section className="admin-section">
              <h2 className="admin-section-title">
                Воронка активации ({stats.activation_funnel.days} дн.)
              </h2>
              <p className="admin-section-lead muted">
                Только владельцы, зарегистрировавшиеся за выбранный период. Ваши генерации на старом
                аккаунте сюда не попадают. «Первая генерация» — архив studio_generations, события
                onboarding_generation_success / first_generation или списание кредитов за студию.
              </p>
              <div className="admin-funnel">
                {stats.activation_funnel.steps.map((step) => (
                  <div key={step.key} className="admin-funnel__row">
                    <div className="admin-funnel__label">{step.label}</div>
                    <div className="admin-funnel__bar-wrap">
                      <div
                        className="admin-funnel__bar"
                        style={{ width: `${Math.max(step.pct_of_registered, 2)}%` }}
                      />
                    </div>
                    <div className="admin-funnel__meta mono">
                      {step.count}{' '}
                      <span className="admin-kpi__pct">({step.pct_of_registered}%)</span>
                    </div>
                  </div>
                ))}
              </div>
              {Object.keys(stats.activation_funnel.events_by_name).length > 0 ? (
                <ul className="admin-usage-list" style={{ marginTop: '1rem' }}>
                  {Object.entries(stats.activation_funnel.events_by_name)
                    .sort((a, b) => b[1] - a[1])
                    .map(([k, c]) => (
                      <li key={k}>
                        <span>{k}</span>
                        <span className="mono">{c}</span>
                      </li>
                    ))}
                </ul>
              ) : null}
            </section>
          ) : null}

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

      <AdminSegmentDrill
        segment={drillSegment}
        title={drillTitle}
        onClose={() => setDrillSegment(null)}
        onSelectUser={onSelectUserFromDrill}
      />
    </div>
  )
}
