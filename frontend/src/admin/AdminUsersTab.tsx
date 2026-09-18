import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import {
  billingPlanLabel,
  planTierLabel,
  subscriptionStatusLabel,
} from './constants'
import { AdminUserPanel } from './AdminUserPanel'
import type { AdminUserDetail, AdminUserRow } from './types'
import { formatDateTimeRu } from './utils'

const MOBILE_MAX = 1099

function useAdminUsersMobileLayout() {
  const [mobile, setMobile] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(`(max-width: ${MOBILE_MAX}px)`).matches,
  )

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MOBILE_MAX}px)`)
    const sync = () => setMobile(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])

  return mobile
}

function UserListCard({
  user,
  active,
  onOpen,
}: {
  user: AdminUserRow
  active: boolean
  onOpen: () => void
}) {
  const { t } = useTranslation('admin')
  const isOwner = user.parent_user_id == null

  return (
    <button
      type="button"
      className={`admin-user-card${active ? ' admin-user-card--active' : ''}`}
      onClick={onOpen}
    >
      <div className="admin-user-card__top">
        <span className="admin-user-card__email">{user.email}</span>
        <span className="admin-user-card__id mono">#{user.id}</span>
      </div>
      <div className="admin-user-badges">
        {!user.is_active ? (
          <span className="admin-badge admin-badge--off">{t('roles.disabled')}</span>
        ) : null}
        {user.is_partner && isOwner ? (
          <span className="admin-badge admin-badge--partner">{t('users.partnerBadge')}</span>
        ) : null}
      </div>
      <div className="admin-user-card__meta muted small">
        {isOwner ? t('roles.owner') : user.member_login ?? t('roles.member')}
        {' · '}
        {subscriptionStatusLabel(user.subscription_status)}
        {' · '}
        {billingPlanLabel(user.billing_plan)}
      </div>
      <div className="admin-user-card__foot">
        <span className="mono admin-kpi__value--accent">{user.credits_balance} cr</span>
        <span className="muted small">
          {t('common.generations')}: {user.studio_generations_count ?? 0}
        </span>
      </div>
    </button>
  )
}

export function AdminUsersTab({
  users,
  userSearch,
  onUserSearchChange,
  partnersOnly,
  onPartnersOnlyChange,
  busy,
  userPage,
  userPageCount,
  userRangeFrom,
  userRangeTo,
  userTotal,
  selectedId,
  onSelectId,
  selectedDetail,
  detailLoading,
  detailError,
  onRunSearch,
  onResetSearch,
  onUserUpdated,
  onDetailError,
  onBusy,
}: {
  users: AdminUserRow[]
  userSearch: string
  onUserSearchChange: (v: string) => void
  partnersOnly: boolean
  onPartnersOnlyChange: (v: boolean) => void
  busy: boolean
  userPage: number
  userPageCount: number
  userRangeFrom: number
  userRangeTo: number
  userTotal: number
  selectedId: number | null
  onSelectId: (id: number | null) => void
  selectedDetail: AdminUserDetail | null
  detailLoading: boolean
  detailError: string | null
  onRunSearch: (page?: number) => void
  onResetSearch: () => void
  onUserUpdated: (row: AdminUserRow) => void
  onDetailError: (msg: string | null) => void
  onBusy: (v: boolean) => void
}) {
  const { t } = useTranslation('admin')
  const mobile = useAdminUsersMobileLayout()

  useEffect(() => {
    if (!mobile || selectedId == null) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [mobile, selectedId])

  const closeDetail = () => onSelectId(null)

  const detailBody = (
    <>
      {detailLoading && !selectedDetail ? (
        <div className="admin-user-detail-state muted">{t('common.loading')}</div>
      ) : null}
      {detailError && !selectedDetail ? (
        <div className="admin-user-detail-state admin-user-detail-state--error">
          <p>{detailError}</p>
          <button type="button" className="ghost-btn" onClick={closeDetail}>
            {t('users.backToList')}
          </button>
        </div>
      ) : null}
      {selectedDetail ? (
        <AdminUserPanel
          user={selectedDetail}
          busy={busy}
          onBusy={onBusy}
          onUpdated={onUserUpdated}
          onClose={closeDetail}
          onError={onDetailError}
        />
      ) : null}
    </>
  )

  const mobileSheet =
    mobile && selectedId != null
      ? createPortal(
          <div className="admin-user-mobile-sheet" role="dialog" aria-modal="true">
            <header className="admin-user-mobile-sheet__head">
              <button type="button" className="admin-user-mobile-sheet__back" onClick={closeDetail}>
                ← {t('users.backToList')}
              </button>
            </header>
            <div className="admin-user-mobile-sheet__body">{detailBody}</div>
          </div>,
          document.body,
        )
      : null

  return (
    <>
      <div
        className={`admin-users admin-fade-in${!mobile && selectedDetail ? ' admin-users--split' : ''}`}
      >
        <div className="admin-users__main">
          <div className="admin-user-toolbar">
            <input
              type="search"
              placeholder={t('users.searchPlaceholder')}
              value={userSearch}
              onChange={(e) => onUserSearchChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onRunSearch(0)
              }}
              className="admin-user-search"
            />
            <select
              className="admin-user-filter"
              value={partnersOnly ? 'partners' : 'all'}
              onChange={(e) => onPartnersOnlyChange(e.target.value === 'partners')}
            >
              <option value="all">{t('users.filterAll')}</option>
              <option value="partners">{t('users.filterPartners')}</option>
            </select>
            <button type="button" className="ghost-btn" disabled={busy} onClick={() => onRunSearch(0)}>
              {t('common.search')}
            </button>
            <button type="button" className="ghost-btn" disabled={busy} onClick={onResetSearch}>
              {t('common.reset')}
            </button>
          </div>

          <div className="admin-user-cards" aria-label={t('users.listAria')}>
            {users.map((u) => (
              <UserListCard
                key={u.id}
                user={u}
                active={selectedId === u.id}
                onOpen={() => onSelectId(u.id)}
              />
            ))}
            {!users.length && !busy ? (
              <p className="muted admin-user-cards__empty">{t('common.noRecords')}</p>
            ) : null}
          </div>

          <div className="admin-user-table-desktop">
            <div className="admin-user-table-scroller admin-card">
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
                  {users.map((u) => {
                    const isOwner = u.parent_user_id == null
                    const active = selectedId === u.id
                    return (
                      <tr
                        key={u.id}
                        className={active ? 'admin-user-row--active' : ''}
                        onClick={() => onSelectId(u.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            onSelectId(u.id)
                          }
                        }}
                        tabIndex={0}
                        role="button"
                      >
                        <td className="mono">{u.id}</td>
                        <td>
                          <div>{u.email}</div>
                          <div className="admin-user-badges">
                            {!u.is_active ? (
                              <span className="admin-badge admin-badge--off">{t('roles.disabled')}</span>
                            ) : null}
                            {u.is_partner && isOwner ? (
                              <span className="admin-badge admin-badge--partner">{t('users.partnerBadge')}</span>
                            ) : null}
                          </div>
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
                  {!users.length && !busy ? (
                    <tr>
                      <td colSpan={7} className="muted admin-user-table__empty">
                        {t('common.noRecords')}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <div className="admin-user-pagination">
            <span className="muted small">
              {userTotal
                ? t('users.paginationRange', { from: userRangeFrom, to: userRangeTo, total: userTotal })
                : t('users.paginationEmpty')}
            </span>
            <div className="admin-user-pagination__controls">
              <button
                type="button"
                className="ghost-btn"
                disabled={busy || userPage <= 0}
                onClick={() => onRunSearch(userPage - 1)}
              >
                {t('users.prevPage')}
              </button>
              <span className="muted small">
                {t('users.pageOf', { page: userPage + 1, total: userPageCount })}
              </span>
              <button
                type="button"
                className="ghost-btn"
                disabled={busy || userPage + 1 >= userPageCount}
                onClick={() => onRunSearch(userPage + 1)}
              >
                {t('users.nextPage')}
              </button>
            </div>
          </div>
        </div>

        {!mobile ? (
          <div className="admin-users__detail">
            {selectedId == null ? (
              <div className="admin-users__placeholder muted">{t('users.placeholder')}</div>
            ) : (
              detailBody
            )}
          </div>
        ) : null}
      </div>
      {mobileSheet}
    </>
  )
}
