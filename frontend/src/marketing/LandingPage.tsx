import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { formatRub, usePublicHealth } from './usePublicHealth'

const DEFAULT_MANAGED = 1299
const DEFAULT_BYOK = 499

function CheckItem({ children }: { children: ReactNode }) {
  return (
    <li>
      <span className="mkt-check-ico" aria-hidden>
        ✓
      </span>
      <span>{children}</span>
    </li>
  )
}

export function LandingPage() {
  const health = usePublicHealth()
  const managed = health?.billing_price_managed_month_rub ?? DEFAULT_MANAGED
  const byok = health?.billing_price_byok_month_rub ?? DEFAULT_BYOK

  return (
    <>
      <section className="mkt-hero" aria-labelledby="hero-title">
        <div>
          <p className="mkt-hero-kicker">SaaS для команд создателей</p>
          <h1 id="hero-title" className="mkt-h1">
            Единый кабинет для диалогов, студии изображений и управления подпиской
          </h1>
          <p className="mkt-lead">
            ModelMate объединяет входящие из Telegram и Fanvue с переводом, ролями операторов и студией
            генерации — с понятным биллингом через ЮKassa и выбором тарифа под ваш сценарий.
          </p>
          <div className="mkt-hero-actions">
            <Link to="/login" className="mkt-nav-cta">
              Войти или зарегистрироваться
            </Link>
            <Link to="/pricing" className="mkt-nav-cta secondary">
              Смотреть тарифы
            </Link>
          </div>
          <div className="mkt-hero-metrics">
            <div className="mkt-metric">
              <div className="mkt-metric-val">Telegram + Fanvue</div>
              <div className="mkt-metric-label">Интеграции на владельце пространства</div>
            </div>
            <div className="mkt-metric">
              <div className="mkt-metric-val">Managed / BYOK</div>
              <div className="mkt-metric-label">Платформа или ваши ключи к AI</div>
            </div>
          </div>
        </div>
        <aside className="mkt-hero-panel" aria-label="Ключевые возможности">
          <h2>Что внутри</h2>
          <ul className="mkt-checklist">
            <CheckItem>Перевод переписки: входящие на русский, ответы — на язык собеседника</CheckItem>
            <CheckItem>Мультитенантность: владелец, операторы с правами, общий биллинг</CheckItem>
            <CheckItem>Студия изображений с учётом кредитов на тарифе Managed</CheckItem>
            <CheckItem>Web Push и реальное время для оперативной работы из браузера</CheckItem>
          </ul>
        </aside>
      </section>

      <section className="mkt-section" aria-labelledby="benefits-title">
        <div className="mkt-section-head">
          <h2 id="benefits-title">Зачем командам ModelMate</h2>
          <p>
            Меньше переключений между сервисами: диалоги, настройки каналов и студия доступны из одного интерфейса
            с предсказуемой моделью оплаты.
          </p>
        </div>
        <div className="mkt-grid">
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              💬
            </div>
            <h3>Один инбокс</h3>
            <p>Сообщения из подключённых каналов попадают в список диалогов с превью и статусом прочтения.</p>
          </article>
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              🌐
            </div>
            <h3>Языки без барьера</h3>
            <p>
              DeepL или LibreTranslate — перевод прозрачен для оператора: видно оригинал и локализованный текст.
            </p>
          </article>
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              🎨
            </div>
            <h3>Студия и кредиты</h3>
            <p>
              На тарифе Managed генерации списывают кредиты; при BYOK вы подключаете свои ключи и экономите на
              студии по своей политике.
            </p>
          </article>
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              👥
            </div>
            <h3>Команда и права</h3>
            <p>Владелец управляет участниками и доступом к чату, интеграциям и студии через маску разрешений.</p>
          </article>
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              💳
            </div>
            <h3>ЮKassa</h3>
            <p>Подписка и пакеты кредитов оформляются в кабинете; статус периода виден сразу после оплаты.</p>
          </article>
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              🔒
            </div>
            <h3>Изоляция данных</h3>
            <p>Каждое пространство работает со своими секретами интеграций; секреты хранятся в зашифрованном виде.</p>
          </article>
        </div>
      </section>

      <section className="mkt-section" aria-labelledby="pricing-preview-title">
        <div className="mkt-section-head">
          <h2 id="pricing-preview-title">Стоимость</h2>
          <p>
            Два основных тарифа подписки — с инфраструктурой платформы или со своими ключами. Точные суммы
            подтягиваются с сервера при оплате.
          </p>
        </div>
        <div className="mkt-price-row">
          <article className="mkt-price-card featured">
            <span className="badge">Популярный</span>
            <h3>Managed</h3>
            <div className="amount">{formatRub(managed)}</div>
            <div className="period">в месяц · студия по кредитам платформы</div>
            <ul>
              <li>Диалоги и переводы в общей связке</li>
              <li>Студия списывает кредиты по действиям (промпт, апскейл и др.)</li>
              <li>Подходит, если не хотите заводить свои ключи API</li>
            </ul>
            <Link to="/pricing" className="mkt-link-arrow">
              Подробнее о тарифах →
            </Link>
          </article>
          <article className="mkt-price-card">
            <h3>BYOK</h3>
            <div className="amount">{formatRub(byok)}</div>
            <div className="period">в месяц · свои ключи LLM и провайдеров студии</div>
            <ul>
              <li>Гибкая модель расходов на стороне вашего аккаунта у провайдера</li>
              <li>Кредиты студии на платформе не расходуются на ваш BYOK-текст</li>
              <li>Для команд с уже настроенными контрактами на AI</li>
            </ul>
            <Link to="/pricing" className="mkt-link-arrow">
              Сравнить с Managed →
            </Link>
          </article>
        </div>
      </section>

      <section className="mkt-section">
        <div className="mkt-hero-panel">
          <h2 style={{ marginBottom: '0.65rem', fontSize: '1rem', textTransform: 'none', letterSpacing: '-0.02em' }}>
            Готовы подключить каналы?
          </h2>
          <p style={{ margin: '0 0 1rem', fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
            После регистрации откройте кабинет: там же оплата, интеграции Telegram/Fanvue и студия. По шагам — в разделе{' '}
            <Link to="/faq" className="mkt-link-arrow" style={{ display: 'inline' }}>
              FAQ
            </Link>
            .
          </p>
          <Link to="/login" className="mkt-nav-cta">
            Перейти ко входу
          </Link>
        </div>
      </section>
    </>
  )
}
