import { useEffect, useReducer, useState } from 'react'
import { NavLink, Outlet, useSearchParams } from 'react-router-dom'
import { getToken } from '../api'
import { billingReturnCopy } from '../billingReturnCopy'
import { MmButton, MmContainer } from './components/MmUi'
import './mm-tokens.css'
import './mm-site.css'

export function MarketingLayout() {
  const [, bump] = useReducer((x: number) => x + 1, 0)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === 'chating_token') bump()
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const hasToken = Boolean(getToken())
  const [searchParams, setSearchParams] = useSearchParams()
  const billingParam = searchParams.get('billing')
  const billingCopy = billingReturnCopy(billingParam)

  const dismissBillingBanner = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('billing')
    setSearchParams(next, { replace: true })
  }

  return (
    <div className="mm-root">
      <a className="mm-skip" href="#main-content">
        К содержимому
      </a>
      <header className={`mm-header${scrolled ? ' is-scrolled' : ''}`}>
        <MmContainer className="mm-header__inner">
          <NavLink to="/" className="mm-wordmark" end>
            MODELMATE
            <span className="mm-wordmark__dot" aria-hidden />
          </NavLink>
          <nav className="mm-nav" aria-label="Разделы сайта">
            <NavLink to="/" end className="mm-nav__link">
              Главная
            </NavLink>
            <NavLink to="/#tools" className="mm-nav__link">
              Студия
            </NavLink>
            <NavLink to="/#showcase" className="mm-nav__link">
              Примеры
            </NavLink>
            <NavLink to="/pricing" className="mm-nav__link">
              Тарифы
            </NavLink>
            <NavLink to="/faq" className="mm-nav__link">
              FAQ
            </NavLink>
          </nav>
          <div className="mm-header__actions">
            {hasToken ? (
              <NavLink to="/workspace" className="mm-header__login">
                Кабинет
              </NavLink>
            ) : (
              <NavLink to="/login" className="mm-header__login">
                Войти
              </NavLink>
            )}
            <MmButton to={hasToken ? '/workspace' : '/login'} size="sm">
              {hasToken ? 'Открыть студию' : 'Открыть студию'}
            </MmButton>
          </div>
        </MmContainer>
      </header>
      <main id="main-content" className="mm-main">
        {billingCopy ? (
          <div
            className={`billing-return-banner billing-return-banner--${billingCopy.variant}`}
            role="status"
          >
            <div className="billing-return-banner__text">
              <h2 className="billing-return-banner__title">{billingCopy.title}</h2>
              <p className="billing-return-banner__body">{billingCopy.body}</p>
            </div>
            <div className="billing-return-banner__actions">
              {hasToken ? (
                <MmButton to="/workspace" size="sm">
                  В кабинет
                </MmButton>
              ) : (
                <MmButton to="/login" size="sm">
                  Войти
                </MmButton>
              )}
              <button type="button" className="mm-btn mm-btn--ghost mm-btn--sm" onClick={dismissBillingBanner}>
                Закрыть
              </button>
            </div>
          </div>
        ) : null}
        <Outlet />
      </main>
      <footer className="mm-footer">
        <MmContainer>
          <div className="mm-footer__grid">
            <div className="mm-footer__brand">
              <NavLink to="/" className="mm-wordmark" end>
                MODELMATE
                <span className="mm-wordmark__dot" aria-hidden />
              </NavLink>
              <p>Студия для ИИ фото и видео. Чаты Fanvue и Telegram, команда и биллинг в одном окне.</p>
            </div>
            <div className="mm-footer__col">
              <h4>Студия</h4>
              <ul>
                <li>
                  <a href="/#tools">Картинки</a>
                </li>
                <li>
                  <a href="/#tools">Видео</a>
                </li>
                <li>
                  <a href="/#tools">Чат</a>
                </li>
              </ul>
            </div>
            <div className="mm-footer__col">
              <h4>Тарифы</h4>
              <ul>
                <li>
                  <NavLink to="/pricing">BYOK и Managed</NavLink>
                </li>
                <li>
                  <NavLink to="/faq">Триал и кредиты</NavLink>
                </li>
              </ul>
            </div>
            <div className="mm-footer__col">
              <h4>Помощь</h4>
              <ul>
                <li>
                  <NavLink to="/faq">FAQ</NavLink>
                </li>
                <li>
                  <NavLink to="/login">Вход</NavLink>
                </li>
              </ul>
            </div>
            <div className="mm-footer__col">
              <h4>Юр.</h4>
              <ul>
                <li>
                  <NavLink to="/terms">Соглашение</NavLink>
                </li>
                <li>
                  <NavLink to="/privacy">Конфиденциальность</NavLink>
                </li>
              </ul>
            </div>
          </div>
          <div className="mm-footer__bottom">
            <span>© {new Date().getFullYear()} ModelMate · model-mate.online</span>
            <span>BYOK · Managed · без сгорающих кредитов</span>
          </div>
        </MmContainer>
      </footer>
    </div>
  )
}
