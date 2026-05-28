import { Link } from 'react-router-dom'
import { parseCatalogFromHealth, WAVESPEED_REF_URL } from '../billing/planCatalog'
import { PricingSection } from './PricingSection'
import { formatRub, usePublicHealth } from './usePublicHealth'

const BETA_CREATORS = 19

export function LandingPage() {
  const health = usePublicHealth()
  const plans = parseCatalogFromHealth(health)
  const signupCredits = health?.signup_bonus_credits ?? 100
  const betaCount = health?.marketing_beta_creators_count ?? BETA_CREATORS

  return (
    <>
      <section className="mkt-hero" aria-labelledby="hero-title">
        <div>
          <p className="mkt-hero-kicker">ModelMate · для креаторов AI-моделей</p>
          <h1 id="hero-title" className="mkt-h1 mkt-h1--hero">
            Создавай AI-моделей и общайся с фанами в одном окне
          </h1>
          <p className="mkt-lead">
            Генерация фото и видео, чат Fanvue и Telegram, авто-перевод, командная работа — без
            переключения между пятью сервисами.
          </p>
          <div className="mkt-hero-actions">
            <Link to="/login" className="mkt-nav-cta">
              Попробовать бесплатно — {signupCredits} кредитов
            </Link>
            <a href="#how" className="mkt-nav-cta secondary">
              Посмотреть, как работает
            </a>
          </div>
          <p className="mkt-hero-fine muted">
            Без привязки карты · Кредиты не сгорают · Настройка за 5 минут
          </p>
          <div className="mkt-hero-metrics">
            <div className="mkt-metric">
              <div className="mkt-metric-val">🔥 {betaCount} в бете</div>
              <div className="mkt-metric-label">Креаторы уже в закрытом доступе</div>
            </div>
            <div className="mkt-metric">
              <div className="mkt-metric-val">⚡ 5 минут</div>
              <div className="mkt-metric-label">Подключение ключа WaveSpeed</div>
            </div>
            <div className="mkt-metric">
              <div className="mkt-metric-val">🔐 BYOK</div>
              <div className="mkt-metric-label">Ключи хранятся в зашифрованном виде</div>
            </div>
          </div>
        </div>
        <aside className="mkt-hero-panel" aria-label="Интерфейс">
          <div className="mkt-hero-mockup-placeholder">
            <p className="muted">Скриншот или короткое демо кабинета</p>
          </div>
        </aside>
      </section>

      <section className="mkt-section mkt-section--alt" id="problem" aria-labelledby="problem-title">
        <div className="mkt-section-head">
          <h2 id="problem-title">Знакомо?</h2>
        </div>
        <div className="mkt-grid mkt-grid--4">
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              🔄
            </div>
            <h3>Скачешь между 5 сервисами</h3>
            <p>
              Промпты, генерация, перевод, CRM для чатов, таблицы для команды — бесконечное
              переключение съедает время.
            </p>
          </article>
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              🎨
            </div>
            <h3>Каждая генерация с нуля</h3>
            <p>Образ модели не запоминается — снова «as before, but…» и снова рандом.</p>
          </article>
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              💬
            </div>
            <h3>Чаттеры путаются</h3>
            <p>Несколько моделей — разные характеры и языки. Фаны чувствуют фальшь.</p>
          </article>
          <article className="mkt-card">
            <div className="mkt-card-icon" aria-hidden>
              🌍
            </div>
            <h3>Иностранные фаны</h3>
            <p>Машинный перевод звучит деревянно — доверие и чаевые падают.</p>
          </article>
        </div>
      </section>

      <section className="mkt-section" id="solution" aria-labelledby="solution-title">
        <div className="mkt-section-head">
          <h2 id="solution-title">Одна платформа закрывает всё</h2>
        </div>
        <div className="mkt-grid">
          <article className="mkt-card">
            <h3>🎨 Фото и видео</h3>
            <p>
              Свой ключ{' '}
              <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                WaveSpeed
              </a>{' '}
              без наценки на генерацию. Профиль модели и референсы сохраняются в кабинете.
            </p>
          </article>
          <article className="mkt-card">
            <h3>🧠 GROK для промптов</h3>
            <p>Референс → готовый промпт под модель. Раскадровка и сцены для видео.</p>
          </article>
          <article className="mkt-card">
            <h3>💬 Чат + перевод</h3>
            <p>Fanvue и Telegram в одном инбоксе. Авто-перевод на десятки языков.</p>
          </article>
          <article className="mkt-card">
            <h3>👥 Команда</h3>
            <p>Креатор и чаттеры с ролями, доступ к моделям, общий биллинг владельца.</p>
          </article>
        </div>
      </section>

      <section className="mkt-section mkt-section--alt" id="how" aria-labelledby="how-title">
        <div className="mkt-section-head">
          <h2 id="how-title">Запуск за 5 минут</h2>
        </div>
        <ol className="mkt-steps">
          <li>
            <strong>🔑 Подключи WaveSpeed</strong>
            <p>
              API-ключ на{' '}
              <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                wavespeed.ai
              </a>{' '}
              — платите провайдеру напрямую.
            </p>
          </li>
          <li>
            <strong>🎨 Настрой модель</strong>
            <p>Референсы, стиль, образ — один раз в профиле модели.</p>
          </li>
          <li>
            <strong>🚀 Генерируй и общайся</strong>
            <p>Контент, чаты и переводы в одном окне.</p>
          </li>
        </ol>
        <p style={{ marginTop: '1.25rem' }}>
          <Link to="/login" className="mkt-nav-cta">
            Начать бесплатно — {signupCredits} кредитов
          </Link>
        </p>
      </section>

      <PricingSection plans={plans} />

      <section className="mkt-section" aria-labelledby="compare-title">
        <div className="mkt-section-head">
          <h2 id="compare-title">Сравни тарифы</h2>
        </div>
        <div className="mkt-table-wrap">
          <table className="mkt-table">
            <thead>
              <tr>
                <th>Функция</th>
                <th>BYOK Solo</th>
                <th>BYOK Pro</th>
                <th>BYOK Studio</th>
                <th>Managed Pro</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Цена / мес</td>
                <td>{formatRub(990)}</td>
                <td>{formatRub(2490)}</td>
                <td>{formatRub(5990)}</td>
                <td>{formatRub(4990)}</td>
              </tr>
              <tr>
                <td>Пользователей</td>
                <td>1</td>
                <td>3</td>
                <td>10</td>
                <td>3</td>
              </tr>
              <tr>
                <td>Моделей</td>
                <td>1</td>
                <td>3</td>
                <td>10</td>
                <td>3</td>
              </tr>
              <tr>
                <td>Свой ключ WaveSpeed</td>
                <td>✓</td>
                <td>✓</td>
                <td>✓</td>
                <td>—</td>
              </tr>
              <tr>
                <td>Кредиты в подписке</td>
                <td>—</td>
                <td>—</td>
                <td>—</td>
                <td>400 / мес</td>
              </tr>
              <tr>
                <td>Чат + перевод</td>
                <td>✓</td>
                <td>✓</td>
                <td>✓</td>
                <td>✓</td>
              </tr>
              <tr>
                <td>GROK</td>
                <td>✓</td>
                <td>✓</td>
                <td>✓</td>
                <td>✓</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="muted" style={{ marginTop: '0.75rem' }}>
          <Link to="/pricing">Полная таблица и детали →</Link>
        </p>
      </section>

      <section className="mkt-section mkt-section--alt" aria-labelledby="beta-title">
        <div className="mkt-section-head">
          <h2 id="beta-title">Уже в закрытой бете</h2>
          <p>
            <strong>{betaCount} креаторов</strong> активно используют ModelMate. Каждую неделю
            открываем новые места.
          </p>
        </div>
        <p className="muted">Fanvue · Telegram · WaveSpeed</p>
        <Link to="/login" className="mkt-nav-cta" style={{ marginTop: '1rem' }}>
          Получить доступ
        </Link>
      </section>

      <section className="mkt-section" aria-labelledby="faq-teaser">
        <div className="mkt-section-head">
          <h2 id="faq-teaser">Вопросы</h2>
          <p>
            <Link to="/faq">Частые вопросы о BYOK, триале и оплате →</Link>
          </p>
        </div>
      </section>

      <section className="mkt-cta-final" aria-labelledby="final-cta">
        <h2 id="final-cta">Готов попробовать?</h2>
        <p>{signupCredits} кредитов бесплатно. Без карты. Без срока на триал.</p>
        <Link to="/login" className="mkt-nav-cta">
          Начать сейчас
        </Link>
      </section>
    </>
  )
}
