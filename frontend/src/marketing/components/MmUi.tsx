import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function MmContainer({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`mm-container ${className}`.trim()}>{children}</div>
}

export function MmEyebrow({ children, tone }: { children: ReactNode; tone?: 'photo' | 'video' | 'i2v' }) {
  const toneClass = tone ? ` mm-eyebrow--${tone}` : ''
  return <span className={`mm-eyebrow${toneClass}`}>{children}</span>
}

type BtnProps = {
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  to?: string
  href?: string
  className?: string
  onClick?: () => void
}

export function MmButton({ children, variant = 'primary', size = 'md', to, href, className = '', onClick }: BtnProps) {
  const cls = `mm-btn mm-btn--${variant} mm-btn--${size} ${className}`.trim()
  const icon = variant === 'primary' && size !== 'sm' ? <MmArrowRight /> : null
  if (to) {
    return (
      <Link to={to} className={cls}>
        {children}
        {icon}
      </Link>
    )
  }
  if (href) {
    return (
      <a href={href} className={cls} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    )
  }
  return (
    <button type="button" className={cls} onClick={onClick}>
      {children}
      {icon}
    </button>
  )
}

export function MmBadge({ children, tone = 'default' }: { children: ReactNode; tone?: string }) {
  return <span className={`mm-badge mm-badge--${tone}`}>{children}</span>
}

export function MmArrowRight({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden className="mm-icon-arrow">
      <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function MmSerifAccent({ children }: { children: ReactNode }) {
  return <span className="mm-serif-accent">{children}</span>
}

export function MmDisplayLg({
  children,
  as: Tag = 'h2',
  className = '',
  id,
}: {
  children: ReactNode
  as?: 'h1' | 'h2' | 'h3'
  className?: string
  id?: string
}) {
  return (
    <Tag id={id} className={`mm-display-lg ${className}`.trim()}>
      {children}
    </Tag>
  )
}
