import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export type WorkspaceSection = 'overview' | 'chat' | 'studio' | 'studio_video'

type NavItem = {
  id: WorkspaceSection
  label: string
  icon: string
  show: boolean
  badge?: number
}

export interface AppShellProps {
  appSection: WorkspaceSection
  onSectionChange: (section: WorkspaceSection) => void
  canChat: boolean
  canStudioAny: boolean
  unreadTotal: number
  creditsBalance: number | null
  billingPlanLabel: string
  userTitle: string
  userMeta: string
  onAccountOpen: () => void
  onLogout: () => void
  children: ReactNode
}

export function AppShell({
  appSection,
  onSectionChange,
  canChat,
  canStudioAny,
  unreadTotal,
  creditsBalance,
  billingPlanLabel,
  userTitle,
  userMeta,
  onAccountOpen,
  onLogout,
  children,
}: AppShellProps) {
  const nav: NavItem[] = [
    { id: 'overview', label: 'Обзор', icon: '◆', show: true },
    { id: 'chat', label: 'Диалоги', icon: '💬', show: canChat, badge: unreadTotal },
    { id: 'studio', label: 'Картинки', icon: '🎨', show: canStudioAny },
    { id: 'studio_video', label: 'Видео', icon: '🎬', show: canStudioAny },
  ]

  const visibleNav = nav.filter((x) => x.show)

  const topNavButton = (item: NavItem) => (
    <button
      key={item.id}
      type="button"
      className={
        appSection === item.id ? 'workspace-topnav-item is-active' : 'workspace-topnav-item'
      }
      onClick={() => onSectionChange(item.id)}
      aria-current={appSection === item.id ? 'page' : undefined}
    >
      <span className="workspace-topnav-icon" aria-hidden>
        {item.icon}
      </span>
      <span className="workspace-topnav-label">{item.label}</span>
      {item.badge != null && item.badge > 0 ? (
        <span className="workspace-topnav-badge">
          {item.badge > 99 ? '99+' : item.badge}
        </span>
      ) : null}
    </button>
  )

  const mobileNavButton = (item: NavItem) => (
    <button
      key={item.id}
      type="button"
      className={
        appSection === item.id
          ? 'workspace-mobile-nav-item is-active'
          : 'workspace-mobile-nav-item'
      }
      onClick={() => onSectionChange(item.id)}
      aria-current={appSection === item.id ? 'page' : undefined}
    >
      <span aria-hidden>{item.icon}</span>
      <span>{item.label}</span>
      {item.badge != null && item.badge > 0 ? (
        <span className="workspace-mobile-nav-badge">
          {item.badge > 99 ? '99+' : item.badge}
        </span>
      ) : null}
    </button>
  )

  return (
    <div className="workspace-shell workspace-shell--topnav">
      <div className="workspace-main">
        <header className="workspace-topbar">
          <div className="workspace-topbar-start">
            <div className="workspace-topbar-brand">
              <span className="workspace-logo-mark" aria-hidden>
                M
              </span>
              <div className="workspace-topbar-brand-text">
                <strong>ModelMate</strong>
                <span className="workspace-logo-sub workspace-logo-sub--desktop">
                  Creator OS
                </span>
              </div>
            </div>

            <nav className="workspace-topnav workspace-topnav--desktop" aria-label="Разделы">
              {visibleNav.map((item) => topNavButton(item))}
            </nav>
          </div>

          <div className="workspace-topbar-end">
            <button
              type="button"
              className="workspace-credits-chip"
              onClick={onAccountOpen}
              title={`${creditsBalance ?? '—'} кр. · ${billingPlanLabel}`}
            >
              <span className="workspace-credits-value">{creditsBalance ?? '—'}</span>
              <span className="workspace-credits-label">кр.</span>
            </button>
            <div className="workspace-topbar-end-desktop">
              <button type="button" className="ghost-btn workspace-topbar-btn" onClick={onAccountOpen}>
                Кабинет
              </button>
              <Link to="/" className="ghost-btn workspace-topbar-link workspace-topbar-btn">
                Сайт
              </Link>
              <button type="button" className="ghost-btn workspace-topbar-btn" onClick={onLogout}>
                Выйти
              </button>
            </div>
            <button
              type="button"
              className="workspace-user-chip"
              onClick={onAccountOpen}
              title={userMeta}
              aria-label="Личный кабинет"
            >
              <span className="workspace-user-avatar" aria-hidden>
                {userTitle.slice(0, 1).toUpperCase()}
              </span>
              <span className="workspace-user-name">{userTitle}</span>
            </button>
          </div>
        </header>

        <div className="workspace-content">{children}</div>

        <nav className="workspace-mobile-nav" aria-label="Разделы приложения">
          {visibleNav.map((item) => mobileNavButton(item))}
        </nav>
      </div>
    </div>
  )
}
