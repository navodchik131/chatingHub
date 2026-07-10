import type { ReactNode } from 'react'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { AppLanguageSwitcher } from '../i18n/AppLanguageSwitcher'
import { formatAppNumber } from '../i18n'
import { TelegramChannelBanner } from './TelegramChannelBanner'
import { WorkspaceNavIcon, type NavIconName } from './WorkspaceNavIcon'

export type WorkspaceSection =
  | 'overview'
  | 'chat'
  | 'studio'
  | 'studio_bootstrap'
  | 'studio_video'

type NavItem = {
  id?: WorkspaceSection
  href?: string
  label: string
  icon: NavIconName
  show: boolean
  badge?: number
  beta?: boolean
}

export interface AppShellProps {
  appSection: WorkspaceSection
  onSectionChange: (section: WorkspaceSection) => void
  canChat: boolean
  canStudioAny: boolean
  unreadTotal: number
  creditsBalance: number | null
  billingPlanLabel: string
  demoGenerationsRemaining?: number
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
  demoGenerationsRemaining = 0,
  userTitle,
  userMeta,
  onAccountOpen,
  onLogout,
  children,
}: AppShellProps) {
  const { t } = useTranslation('workspace')
  const location = useLocation()
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    contentRef.current?.scrollTo({ top: 0, left: 0 })
  }, [appSection, location.pathname])

  const nav: NavItem[] = [
    { id: 'overview', label: t('nav.overview'), icon: 'overview', show: true },
    { id: 'chat', label: t('nav.chat'), icon: 'chat', show: canChat, badge: unreadTotal },
    { id: 'studio', label: t('nav.studio'), icon: 'studio', show: canStudioAny },
    {
      id: 'studio_bootstrap',
      label: t('nav.modelBootstrap'),
      icon: 'model',
      show: canStudioAny,
    },
    { id: 'studio_video', label: t('nav.video'), icon: 'video', show: canStudioAny },
    {
      href: '/workspace/workflow',
      label: t('nav.workflow'),
      icon: 'workflow',
      show: canStudioAny,
      beta: true,
    },
  ]

  const visibleNav = nav.filter((x) => x.show)

  const navItemActive = (item: NavItem) =>
    item.href
      ? location.pathname.startsWith(item.href)
      : appSection === item.id

  const navItemKey = (item: NavItem) => item.href ?? item.id ?? item.label

  const topNavButton = (item: NavItem) => {
    const className = navItemActive(item)
      ? 'workspace-topnav-item is-active'
      : 'workspace-topnav-item'
    const content = (
      <>
        <span className="workspace-topnav-icon" aria-hidden>
          <WorkspaceNavIcon name={item.icon} />
        </span>
        <span className="workspace-topnav-label">{item.label}</span>
        {item.beta ? <span className="workspace-topnav-beta">beta</span> : null}
        {item.badge != null && item.badge > 0 ? (
          <span className="workspace-topnav-badge">
            {item.badge > 99 ? '99+' : item.badge}
          </span>
        ) : null}
      </>
    )

    if (item.href) {
      return (
        <Link
          key={navItemKey(item)}
          to={item.href}
          className={className}
          aria-current={navItemActive(item) ? 'page' : undefined}
        >
          {content}
        </Link>
      )
    }

    return (
      <button
        key={navItemKey(item)}
        type="button"
        className={className}
        onClick={() => item.id && onSectionChange(item.id)}
        aria-current={navItemActive(item) ? 'page' : undefined}
      >
        {content}
      </button>
    )
  }

  const mobileNavButton = (item: NavItem) => {
    const className = navItemActive(item)
      ? 'workspace-mobile-nav-item is-active'
      : 'workspace-mobile-nav-item'
    const content = (
      <>
        <span className="workspace-mobile-nav-icon" aria-hidden>
          <WorkspaceNavIcon name={item.icon} />
        </span>
        <span>{item.label}</span>
        {item.beta ? <span className="workspace-mobile-nav-beta">beta</span> : null}
        {item.badge != null && item.badge > 0 ? (
          <span className="workspace-mobile-nav-badge">
            {item.badge > 99 ? '99+' : item.badge}
          </span>
        ) : null}
      </>
    )

    if (item.href) {
      return (
        <Link
          key={navItemKey(item)}
          to={item.href}
          className={className}
          aria-current={navItemActive(item) ? 'page' : undefined}
        >
          {content}
        </Link>
      )
    }

    return (
      <button
        key={navItemKey(item)}
        type="button"
        className={className}
        onClick={() => item.id && onSectionChange(item.id)}
        aria-current={navItemActive(item) ? 'page' : undefined}
      >
        {content}
      </button>
    )
  }

  return (
    <div className="workspace-shell workspace-shell--topnav">
      <TelegramChannelBanner />
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

            <nav className="workspace-topnav workspace-topnav--desktop" aria-label={t('nav.sectionsAria')}>
              {visibleNav.map((item) => topNavButton(item))}
            </nav>
          </div>

          <div className="workspace-topbar-end">
            <AppLanguageSwitcher className="mm-lang-switch mm-lang-switch--compact workspace-lang-switch" />
            <button
              type="button"
              className="workspace-credits-chip"
              onClick={onAccountOpen}
              title={t('shell.creditsTitle', {
                plan: billingPlanLabel,
                credits: creditsBalance != null ? formatAppNumber(creditsBalance) : '—',
                demo:
                  demoGenerationsRemaining > 0
                    ? ` · ${demoGenerationsRemaining} ${t('shell.demo')}`
                    : '',
              })}
            >
              <span className="workspace-billing-plan">{billingPlanLabel}</span>
              <span className="workspace-credits-sep" aria-hidden>
                ·
              </span>
              <span className="workspace-credits-value">{creditsBalance ?? '—'}</span>
              <span className="workspace-credits-label">{t('shell.credits')}</span>
              {demoGenerationsRemaining > 0 ? (
                <span className="workspace-demo-pill">
                  {demoGenerationsRemaining} {t('shell.demo')}
                </span>
              ) : null}
            </button>
            <div className="workspace-topbar-end-desktop">
              <button type="button" className="ghost-btn workspace-topbar-btn" onClick={onAccountOpen}>
                {t('shell.cabinet')}
              </button>
              <Link to="/" className="ghost-btn workspace-topbar-link workspace-topbar-btn">
                {t('shell.site')}
              </Link>
              <button type="button" className="ghost-btn workspace-topbar-btn" onClick={onLogout}>
                {t('shell.logout')}
              </button>
            </div>
            <button
              type="button"
              className="workspace-user-chip"
              onClick={onAccountOpen}
              title={userMeta}
              aria-label={t('shell.accountAria')}
            >
              <span className="workspace-user-avatar" aria-hidden>
                {userTitle.slice(0, 1).toUpperCase()}
              </span>
              <span className="workspace-user-name">{userTitle}</span>
            </button>
          </div>
        </header>

        <div className="workspace-content" ref={contentRef}>
          {children}
        </div>

        <nav className="workspace-mobile-nav" aria-label={t('nav.mobileSectionsAria')}>
          {visibleNav.map((item) => mobileNavButton(item))}
        </nav>
      </div>
    </div>
  )
}
