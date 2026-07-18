import { useCallback, useEffect, useMemo, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { resolveWorkspaceUrl, WORKSPACE_URL } from '../marketing/workspaceEntry'
import { apiFetch, getToken, setToken } from '../api'
import { AdminCreatorDonationsTab } from './AdminCreatorDonationsTab'
import { AdminEmailTab } from './AdminEmailTab'
import { AdminExifBotTab } from './AdminExifBotTab'
import { AdminIgBotTab } from './AdminIgBotTab'
import { AdminOverview } from './AdminOverview'
import { AdminSegmentDrill } from './AdminSegmentDrill'
import { AdminShell, type AdminTabId } from './AdminShell'
import { AdminUserPanel } from './AdminUserPanel'
import {
  billingPlanLabel,
  planTierLabel,
  subscriptionStatusLabel,
} from './constants'
import type { AdminStats, AdminUserDetail, AdminUserRow } from './types'
import { formatDateTimeRu } from './utils'
import './admin.css'

interface UserMe {
  is_platform_admin?: boolean
  email?: string
}

const TAB_TITLES: Record<AdminTabId, string> = {
  overview: 'overviewTitle',
  users: 'usersTitle',
  email: 'emailTitle',
  exif_bot: 'exifBotTitle',
  ig_bot: 'igBotTitle',
  creator_donations: 'creatorDonationsTitle',
}

export function AdminPage() {
  const { t } = useTranslation('admin')
  const [gate, setGate] = useState<'loading' | 'ok' | 'denied' | 'anon'>('loading')
  const [meEmail, setMeEmail] = useState('')
  const [tab, setTab] = useState<AdminTabId>('overview')
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [users, setUsers] = useState<AdminUserRow[]>([])
  const [userSearch, setUserSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<AdminUserDetail | null>(null)
  const [drillSegment, setDrillSegment] = useState<string | null>(null)
  const [drillTitle, setDrillTitle] = useState('')

  const pageTitle = t(`shell.${TAB_TITLES[tab]}`)

  const openDrill = useCallback((segment: string, title: string) => {
    setDrillSegment(segment)
    setDrillTitle(title)
  }, [])

  const loadStats = useCallback(async () => {
    const r = await apiFetch('/api/admin/stats?chart_days=30')
    if (r.ok) {
      setStats((await r.json()) as AdminStats)
      return
    }
    setError(t('gate.statsLoadFailed'))
  }, [t])

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
        setToken(null)
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

  const filteredUsers = useMemo(() => {
    const q = userSearch.trim().toLowerCase()
    if (!q) return users
    return users.filter((u) => u.email.toLowerCase().includes(q))
  }, [users, userSearch])

  if (gate === 'loading') {
    return (
      <div className="admin-page admin-page--center">
        <p className="muted">{t('gate.checking')}</p>
      </div>
    )
  }
  if (gate === 'anon') {
    return <Navigate to="/login?next=%2Fadmin" replace />
  }
  if (gate === 'denied') {
    return (
      <div className="admin-page admin-page--center">
        <h1>{t('gate.deniedTitle')}</h1>
        <p className="muted">{t('gate.deniedHint')}</p>
        <a href={resolveWorkspaceUrl(WORKSPACE_URL)} className="admin-back-link">
          {t('gate.backToWorkspace')}
        </a>
      </div>
    )
  }

  return (
    <>
      <AdminShell
        tab={tab}
        onTabChange={setTab}
        pageTitle={pageTitle}
        meEmail={meEmail}
        busy={busy}
        onRefresh={refreshAll}
      >
        {error ? (
          <div className="admin-banner admin-banner--error" role="alert">
            {error}
            <button type="button" className="admin-banner__close" onClick={() => setError(null)}>
              ✕
            </button>
          </div>
        ) : null}

        {tab === 'overview' && stats ? (
          <AdminOverview stats={stats} onDrill={openDrill} />
        ) : null}
        {tab === 'overview' && !stats && busy ? (
          <p className="muted admin-fade-in">{t('overview.loadingAnalytics')}</p>
        ) : null}
        {tab === 'overview' && !stats && !busy ? (
          <p className="muted admin-fade-in">{error || t('gate.statsLoadFailed')}</p>
        ) : null}

        {tab === 'users' ? (
          <div className={`admin-users admin-fade-in${selectedDetail ? ' admin-users--split' : ''}`}>
            <div className="admin-users__main">
              <div className="admin-user-toolbar">
                <input
                  type="search"
                  placeholder={t('users.searchPlaceholder')}
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  className="admin-user-search"
                />
                <button type="button" className="ghost-btn" disabled={busy} onClick={() => void loadUsers(userSearch)}>
                  {t('common.search')}
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
                  {t('common.reset')}
                </button>
              </div>

              <div className="admin-user-table-wrap admin-card">
                <table className="admin-user-table">
                  <thead>
                    <tr>
                      <th>{t('common.id')}</th>
                      <th>{t('common.email')}</th>
                      <th>{t('common.role')}</th>
                      <th>{t('common.subscription')}</th>
                      <th>{t('common.plan')}</th>
                      <th>{t('common.credits')}</th>
                      <th>{t('common.generations')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((u) => {
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
                            {!u.is_active ? (
                              <span className="admin-badge admin-badge--off">{t('roles.disabled')}</span>
                            ) : null}
                          </td>
                          <td>{isOwner ? t('roles.owner') : u.member_login ?? t('roles.member')}</td>
                          <td>{subscriptionStatusLabel(u.subscription_status)}</td>
                          <td>
                            {billingPlanLabel(u.billing_plan)} · {planTierLabel(u.plan_tier)}
                            <div className="muted small">{formatDateTimeRu(u.subscription_period_end)}</div>
                          </td>
                          <td className="mono admin-kpi__value--accent">{u.credits_balance}</td>
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
              <div className="admin-users__placeholder muted">{t('users.placeholder')}</div>
            )}
          </div>
        ) : null}

        {tab === 'email' ? <AdminEmailTab meEmail={meEmail} onError={setError} /> : null}
        {tab === 'exif_bot' ? <AdminExifBotTab onError={setError} /> : null}
        {tab === 'ig_bot' ? <AdminIgBotTab onError={setError} /> : null}
        {tab === 'creator_donations' ? <AdminCreatorDonationsTab /> : null}
      </AdminShell>

      <AdminSegmentDrill
        segment={drillSegment}
        title={drillTitle}
        onClose={() => setDrillSegment(null)}
        onSelectUser={onSelectUserFromDrill}
      />
    </>
  )
}
