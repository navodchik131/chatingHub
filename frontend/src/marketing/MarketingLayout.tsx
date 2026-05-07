import { useEffect, useReducer } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { getToken } from '../api'
import '../App.css'
import './marketing.css'

export function MarketingLayout() {
  const [, bump] = useReducer((x: number) => x + 1, 0)

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'chating_token') bump()
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const hasToken = Boolean(getToken())

  return (
    <div className="mkt-root">
      <div className="app-bg" aria-hidden />
      <a className="mkt-skip" href="#main-content">
        К содержимому
      </a>
      <header className="mkt-header">
        <NavLink to="/" className="mkt-brand">
          <img src="/brand-icon.svg" alt="" width={36} height={36} />
          <span className="mkt-brand-text">
            <span className="mkt-brand-name">ModelMate</span>
            <span className="mkt-brand-tag">Студия AI-моделей</span>
          </span>
        </NavLink>
        <nav className="mkt-nav" aria-label="Разделы сайта">
          <NavLink to="/" end className="mkt-nav-link">
            Главная
          </NavLink>
          <NavLink to="/pricing" className="mkt-nav-link">
            Тарифы
          </NavLink>
          <NavLink to="/faq" className="mkt-nav-link">
            FAQ
          </NavLink>
          {hasToken ? (
            <NavLink to="/workspace" className="mkt-nav-cta">
              Кабинет
            </NavLink>
          ) : (
            <NavLink to="/login" className="mkt-nav-cta">
              Войти
            </NavLink>
          )}
        </nav>
      </header>
      <main id="main-content" className="mkt-main">
        <Outlet />
      </main>
      <footer className="mkt-footer">
        <div className="mkt-footer-inner">
          <span>© {new Date().getFullYear()} ModelMate · чаты, студия, биллинг в одном пространстве.</span>
          <div className="mkt-footer-links">
            <NavLink to="/pricing">Тарифы</NavLink>
            <NavLink to="/faq">FAQ и запуск</NavLink>
            <NavLink to="/login">{hasToken ? 'Кабинет' : 'Вход'}</NavLink>
          </div>
        </div>
      </footer>
    </div>
  )
}
