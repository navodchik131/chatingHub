import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { resolveWorkspaceUrl, WORKSPACE_URL } from '../marketing/workspaceEntry'

export type AdminTabId =
  | 'overview'
  | 'users'
  | 'email'
  | 'exif_bot'
  | 'ig_bot'
  | 'creator_donations'

type NavItem = {
  id: AdminTabId
  label: string
  icon: ReactNode
}

function NavIcon({ children }: { children: ReactNode }) {
  return (
    <span className="admin-nav__icon" aria-hidden>
      {children}
    </span>
  )
}

const NAV_ICONS: Record<AdminTabId, ReactNode> = {
  overview: (
    <NavIcon>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="3" width="7.5" height="7.5" rx="2" />
        <rect x="13.5" y="3" width="7.5" height="7.5" rx="2" />
        <rect x="3" y="13.5" width="7.5" height="7.5" rx="2" />
        <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2" />
      </svg>
    </NavIcon>
  ),
  users: (
    <NavIcon>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="9" cy="9" r="3.2" />
        <path d="M3.5 19.5c.6-2.9 2.9-4.6 5.5-4.6s4.9 1.7 5.5 4.6" />
        <circle cx="17" cy="10" r="2.5" />
        <path d="M16 15.2c2.3.2 4 1.7 4.5 4.3" />
      </svg>
    </NavIcon>
  ),
  email: (
    <NavIcon>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="5" width="18" height="14" rx="3" />
        <path d="M4 7l8 6 8-6" />
      </svg>
    </NavIcon>
  ),
  exif_bot: (
    <NavIcon>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="7" width="18" height="13" rx="3" />
        <path d="M8.5 7L10 4h4l1.5 3" />
        <circle cx="12" cy="13" r="3.4" />
      </svg>
    </NavIcon>
  ),
  ig_bot: (
    <NavIcon>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="4" y="4" width="16" height="16" rx="5" />
        <circle cx="12" cy="12" r="3.6" />
        <circle cx="16.5" cy="7.5" r="1" fill="currentColor" stroke="none" />
      </svg>
    </NavIcon>
  ),
  creator_donations: (
    <NavIcon>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="4" y="9" width="16" height="11" rx="2" />
        <path d="M12 9v11M4 13.5h16" />
        <path d="M12 9c-1.5-2.5-4-3.8-5.5-2.3S7.5 9 9.5 9zM12 9c1.5-2.5 4-3.8 5.5-2.3S16.5 9 14.5 9z" />
      </svg>
    </NavIcon>
  ),
}

export function AdminShell({
  tab,
  onTabChange,
  pageTitle,
  meEmail,
  busy,
  onRefresh,
  children,
}: {
  tab: AdminTabId
  onTabChange: (tab: AdminTabId) => void
  pageTitle: string
  meEmail: string
  busy: boolean
  onRefresh: () => void
  children: ReactNode
}) {
  const { t } = useTranslation('admin')
  const [mobile, setMobile] = useState(false)

  useEffect(() => {
    const onResize = () => setMobile(window.innerWidth < 900)
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const navItems: NavItem[] = [
    { id: 'overview', label: t('tabs.overview'), icon: NAV_ICONS.overview },
    { id: 'users', label: t('tabs.users'), icon: NAV_ICONS.users },
    { id: 'email', label: t('tabs.email'), icon: NAV_ICONS.email },
    { id: 'exif_bot', label: t('tabs.exifBot'), icon: NAV_ICONS.exif_bot },
    { id: 'ig_bot', label: t('tabs.igBot'), icon: NAV_ICONS.ig_bot },
    { id: 'creator_donations', label: t('tabs.creatorDonations'), icon: NAV_ICONS.creator_donations },
  ]

  const initial = (meEmail || '?').trim().charAt(0).toUpperCase()

  return (
    <div className="admin-app">
      {!mobile ? (
        <aside className="admin-sidebar">
          <div className="admin-sidebar__brand">
            <img src="/admin-logo.png" alt="" className="admin-sidebar__logo" />
            <div>
              <div className="admin-sidebar__name">ModelMate</div>
              <div className="admin-sidebar__badge">{t('shell.adminAccess')}</div>
            </div>
          </div>
          <nav className="admin-sidebar__nav" aria-label={t('shell.navAria')}>
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`admin-sidebar__link${tab === item.id ? ' is-active' : ''}`}
                onClick={() => onTabChange(item.id)}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
          <div className="admin-sidebar__foot">
            <a href={resolveWorkspaceUrl(WORKSPACE_URL)} className="admin-sidebar__cabinet">
              ← {t('header.backToCabinet')}
            </a>
            <div className="admin-sidebar__user">
              <span className="admin-sidebar__avatar">{initial}</span>
              <span className="admin-sidebar__email">{meEmail}</span>
            </div>
          </div>
        </aside>
      ) : null}

      <div className="admin-main">
        <header className="admin-topbar">
          {mobile ? <img src="/admin-logo.png" alt="" className="admin-topbar__logo" /> : null}
          <div className="admin-topbar__titles">
            <div className="admin-topbar__eyebrow">{t('shell.topEyebrow')}</div>
            <h1 className="admin-topbar__title">{pageTitle}</h1>
          </div>
          <div className="admin-topbar__actions">
            <span className="admin-live">{t('shell.live')}</span>
            <button type="button" className="admin-refresh-btn" disabled={busy} onClick={onRefresh}>
              ↻ {t('header.refresh')}
            </button>
          </div>
        </header>

        {mobile ? (
          <div className="admin-mobile-tabs" role="tablist">
            {navItems.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={`admin-mobile-tabs__chip${tab === item.id ? ' is-active' : ''}`}
                onClick={() => onTabChange(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        ) : null}

        <div className="admin-content">{children}</div>
      </div>
    </div>
  )
}
