import { Link } from 'react-router-dom'
import { formatRub, usePublicHealth } from './usePublicHealth'

const FALLBACK_MANAGED = 1299
const FALLBACK_BYOK = 499
const FALLBACK_CREDITS_MIN = 50
const FALLBACK_CREDITS_BULK_FROM = 200
const FALLBACK_UNIT = 3
const FALLBACK_BULK_UNIT = 2.7

export function PricingPage() {
  const health = usePublicHealth()
  const managed = health?.billing_price_managed_month_rub ?? FALLBACK_MANAGED
  const byok = health?.billing_price_byok_month_rub ?? FALLBACK_BYOK
  const creditsMin = health?.billing_credits_min_purchase ?? FALLBACK_CREDITS_MIN
  const creditsBulkFrom = health?.billing_credits_bulk_from ?? FALLBACK_CREDITS_BULK_FROM
  const creditsUnit = health?.billing_credits_unit_price_rub ?? FALLBACK_UNIT
  const creditsBulkUnit = health?.billing_credits_bulk_unit_price_rub ?? FALLBACK_BULK_UNIT
  const promptCost = health?.studio_prompt_credit_cost
  const upscaleCost = health?.studio_upscale_credit_cost
  const carouselCost = health?.studio_carousel_credit_cost

  return (
    <>
      <header className="mkt-section-head">
        <h1 className="mkt-h1" style={{ fontSize: 'clamp(1.65rem, 4vw, 2.25rem)' }}>
          Тарифы и за что вы платите
        </h1>
        <p>
          Подписка открывает доступ к кабинету и студии согласно выбранному плану. Ниже — смысл каждого тарифа; суммы
          берутся из настроек сервера (или показаны ориентиры, если API временно недоступен).
        </p>
      </header>

      <section className="mkt-section" style={{ paddingTop: 0 }} aria-labelledby="plans-heading">
        <h2 id="plans-heading" className="visually-hidden">
          Планы
        </h2>
        <div className="mkt-price-row">
          <article className="mkt-price-card featured">
            <span className="badge">Managed</span>
            <h3>Платформа ведёт AI</h3>
            <div className="amount">{formatRub(managed)}</div>
            <div className="period">ежемесячно · оплата в кабинете через ЮKassa</div>
            <ul>
              <li>
                <strong>За что платите:</strong> доступ к приложению, инфраструктура переводов и студии на стороне
                сервиса.
              </li>
              <li>
                <strong>Кредиты:</strong> операции студии (уточнение промпта, апскейл, кадры карусели и т.д.)
                списывают баланс кредитов; его можно пополнить пакетами.
              </li>
              <li>
                <strong>Кому подходит:</strong> быстрый старт без настройки своих ключей OpenAI-совместимых API.
              </li>
            </ul>
            <Link to="/login" className="mkt-nav-cta" style={{ textAlign: 'center', width: 'fit-content' }}>
              Оформить в кабинете
            </Link>
          </article>

          <article className="mkt-price-card">
            <span className="badge" style={{ background: 'var(--bg-subtle)', color: 'var(--text-secondary)' }}>
              BYOK
            </span>
            <h3>Свои ключи</h3>
            <div className="amount">{formatRub(byok)}</div>
            <div className="period">ежемесячно · вы подключаете LLM и провайдеров студии</div>
            <ul>
              <li>
                <strong>За что платите:</strong> доступ к кабинету и использование ваших ключей для текстовой модели и
                студии — расходы у провайдеров AI на вашей стороне.
              </li>
              <li>
                <strong>Кредиты платформы:</strong> на типичном BYOK-сценарии не расходуются на ваш API-текст (см.
                подсказки в кабинете для вашей конфигурации).
              </li>
              <li>
                <strong>Кому подходит:</strong> команды с лимитами, договорами или политиками на своих поставщиков AI.
              </li>
            </ul>
            <Link to="/login" className="mkt-nav-cta secondary" style={{ textAlign: 'center', width: 'fit-content' }}>
              Выбрать BYOK в кабинете
            </Link>
          </article>
        </div>
      </section>

      <section className="mkt-section" aria-labelledby="credits-heading">
        <div className="mkt-section-head">
          <h2 id="credits-heading">Покупка кредитов (Managed)</h2>
          <p>
            На тарифе Managed студийные действия переводятся в кредиты. Пополнить баланс можно на любую сумму: от{' '}
            {creditsMin.toLocaleString('ru-RU')} кредитов и выше — в кабинете вы вводите количество, сумма считается по
            правилам ниже.
          </p>
        </div>
        <article className="mkt-price-card" style={{ maxWidth: 420 }}>
          <h3>Правила цены</h3>
          <ul style={{ margin: 0, paddingLeft: '1.15rem' }}>
            <li>
              <strong>Базовая ставка:</strong>{' '}
              {creditsUnit.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} ₽ за один
              кредит.
            </li>
            <li>
              <strong>От {creditsBulkFrom.toLocaleString('ru-RU')} кредитов:</strong>{' '}
              {creditsBulkUnit.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} ₽ за
              кредит.
            </li>
            <li>
              <strong>Минимальная покупка:</strong> {creditsMin.toLocaleString('ru-RU')} кредитов.
            </li>
          </ul>
          <p className="period" style={{ marginTop: '1rem' }}>
            Оформление — в разделе оплаты в кабинете (ЮKassa).
          </p>
        </article>
      </section>

      {(promptCost != null || upscaleCost != null || carouselCost != null) && (
        <section className="mkt-section" aria-labelledby="studio-cost-heading">
          <div className="mkt-section-head">
            <h2 id="studio-cost-heading">Ориентиры по кредитам студии</h2>
            <p>Ниже значения из текущей конфигурации сервера (могут меняться администратором платформы).</p>
          </div>
          <div className="mkt-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
            {promptCost != null ? (
              <article className="mkt-card">
                <h3>Уточнение промпта</h3>
                <p>{promptCost} кр.</p>
              </article>
            ) : null}
            {upscaleCost != null ? (
              <article className="mkt-card">
                <h3>Апскейл</h3>
                <p>{upscaleCost} кр.</p>
              </article>
            ) : null}
            {carouselCost != null ? (
              <article className="mkt-card">
                <h3>Кадр карусели</h3>
                <p>{carouselCost} кр.</p>
              </article>
            ) : null}
          </div>
        </section>
      )}

      <section className="mkt-section" aria-labelledby="compare-heading">
        <div className="mkt-section-head">
          <h2 id="compare-heading">Сводка «за что платёж»</h2>
        </div>
        <div className="mkt-card" style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.875rem',
            }}
          >
            <caption className="visually-hidden">
              Сравнение строк затрат по тарифам
            </caption>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th scope="col" style={{ textAlign: 'left', padding: '0.65rem 0.5rem 0.65rem 0' }}>
                  Статья
                </th>
                <th scope="col" style={{ textAlign: 'left', padding: '0.65rem 0.5rem' }}>
                  Managed
                </th>
                <th scope="col" style={{ textAlign: 'left', padding: '0.65rem 0.5rem' }}>
                  BYOK
                </th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th scope="row" style={{ padding: '0.65rem 0.5rem 0.65rem 0', fontWeight: 700 }}>
                  Подписка
                </th>
                <td style={{ padding: '0.65rem 0.5rem', color: 'var(--text-secondary)' }}>
                  Доступ к сервису и студии через кредиты
                </td>
                <td style={{ padding: '0.65rem 0.5rem', color: 'var(--text-secondary)' }}>
                  Доступ к сервису + ваши ключи API
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th scope="row" style={{ padding: '0.65rem 0.5rem 0.65rem 0', fontWeight: 700 }}>
                  LLM / студия
                </th>
                <td style={{ padding: '0.65rem 0.5rem', color: 'var(--text-secondary)' }}>
                  Расход кредитов платформы по тарификации студии
                </td>
                <td style={{ padding: '0.65rem 0.5rem', color: 'var(--text-secondary)' }}>
                  Оплата провайдерам по вашим ключам
                </td>
              </tr>
              <tr>
                <th scope="row" style={{ padding: '0.65rem 0.5rem 0.65rem 0', fontWeight: 700 }}>
                  Переводы
                </th>
                <td style={{ padding: '0.65rem 0.5rem', color: 'var(--text-secondary)' }}>
                  Включены в работу сервиса (DeepL/LibreTranslate по настройке сервера)
                </td>
                <td style={{ padding: '0.65rem 0.5rem', color: 'var(--text-secondary)' }}>
                  То же, пока включено на инстансе
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p style={{ marginTop: '1rem', fontSize: '0.8125rem', color: 'var(--muted)' }}>
          Итоговая касса — через ЮKassa при включённом биллинге. Если платёжный модуль выключен на вашем инстансе,
          уточните условия у администратора.
        </p>
      </section>

      <p style={{ fontSize: '0.875rem' }}>
        Остались вопросы?{' '}
        <Link to="/faq" className="mkt-link-arrow" style={{ display: 'inline' }}>
          Раздел FAQ и запуск →
        </Link>
      </p>
    </>
  )
}
