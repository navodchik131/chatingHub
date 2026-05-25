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

  const sectionTitle: Record<WorkspaceSection, string> = {
    overview: 'Обзор',
    chat: 'Диалоги',
    studio: 'Студия · Картинки',
    studio_video: 'Студия · Видео',
  }

  return (
    <div className="workspace-shell">
      <aside className="workspace-sidebar" aria-label="Навигация">
        <div className="workspace-sidebar-brand">
          <span className="workspace-logo-mark" aria-hidden>
            M
          </span>
          <div>
            <strong>ModelMate</strong>
            <span className="workspace-logo-sub">Creator OS</span>
          </div>
        </div>

        <nav className="workspace-nav">
          {nav
            .filter((x) => x.show)
            .map((item) => (
              <button
                key={item.id}
                type="button"
                className={
                  appSection === item.id ? 'workspace-nav-item is-active' : 'workspace-nav-item'
                }
                onClick={() => onSectionChange(item.id)}
                aria-current={appSection === item.id ? 'page' : undefined}
              >
                <span className="workspace-nav-icon" aria-hidden>
                  {item.icon}
                </span>
                <span className="workspace-nav-label">{item.label}</span>
                {item.badge != null && item.badge > 0 ? (
                  <span className="workspace-nav-badge">{item.badge > 99 ? '99+' : item.badge}</span>
                ) : null}
              </button>
            ))}
        </nav>

        <div className="workspace-sidebar-plan panel-glass">
          <div className="workspace-plan-row">
            <span className="muted">Кредиты</span>
            <strong>{creditsBalance ?? '—'}</strong>
          </div>
          <div className="workspace-plan-row">
            <span className="muted">Тариф</span>
            <span>{billingPlanLabel}</span>
          </div>
          <button type="button" className="workspace-plan-btn" onClick={onAccountOpen}>
            Кабинет и оплата
          </button>
        </div>

        <div className="workspace-sidebar-user">
          <div className="workspace-user-avatar" aria-hidden>
            {userTitle.slice(0, 1).toUpperCase()}
          </div>
          <div className="workspace-user-text">
            <span className="workspace-user-name">{userTitle}</span>
            <span className="workspace-user-meta">{userMeta}</span>
          </div>
        </div>
      </aside>

      <div className="workspace-main">
        <header className="workspace-topbar">
          <div className="workspace-topbar-title">
            <h1>{sectionTitle[appSection]}</h1>
          </div>
          <div className="workspace-topbar-actions">
            <Link to="/" className="ghost-btn workspace-topbar-link">
              Сайт
            </Link>
            <button type="button" className="ghost-btn" onClick={onAccountOpen}>
              Настройки
            </button>
            <button type="button" className="ghost-btn" onClick={onLogout}>
              Выйти
            </button>
          </div>
        </header>

        <div className="workspace-content">{children}</div>
      </div>

      <nav className="workspace-mobile-nav" aria-label="Разделы (мобильный)">
        {nav
          .filter((x) => x.show)
          .map((item) => (
            <button
              key={item.id}
              type="button"
              className={
                appSection === item.id
                  ? 'workspace-mobile-nav-item is-active'
                  : 'workspace-mobile-nav-item'
              }
              onClick={() => onSectionChange(item.id)}
            >
              <span aria-hidden>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
      </nav>
    </div>
  )
}
