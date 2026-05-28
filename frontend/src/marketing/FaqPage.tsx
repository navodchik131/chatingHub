import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { WAVESPEED_REF_URL } from '../billing/planCatalog'
import { MmContainer } from './components/MmUi'

function FaqItem({ question, children }: { question: string; children: ReactNode }) {
  return (
    <details className="mm-details">
      <summary>{question}</summary>
      <div className="mm-details__body">{children}</div>
    </details>
  )
}

export function FaqPage() {
  return (
    <div className="mm-main--page">
      <MmContainer>
        <header className="mm-page-head">
          <h1>Частые вопросы</h1>
          <p>
            Коротко о том, как пользоваться ModelMate: вход, подключение каналов, тарифы и студия.
          </p>
        </header>
        <section className="mm-faq" aria-label="Вопросы и ответы">
          <FaqItem question="С чего начать после регистрации?">
            <p>
              Зайдите в кабинет под email и паролем. Откройте «Подключения» — там WaveSpeed,
              Telegram и Fanvue. На пробном периоде для картинок и видео нужен свой ключ WaveSpeed.
            </p>
          </FaqItem>
          <FaqItem question="Как зарегистрироваться и войти?">
            <p>
              На странице входа выберите регистрацию, укажите email и пароль не короче восьми
              символов.
            </p>
            <p>
              <Link to="/login" className="mm-link-arrow">
                Перейти к входу →
              </Link>
            </p>
          </FaqItem>
          <FaqItem question="Что такое BYOK и почему это выгоднее?">
            <p>
              BYOK — свой API-ключ{' '}
              <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                WaveSpeed
              </a>
              : платите провайдеру напрямую за генерацию без наценки на картинки и видео.
            </p>
          </FaqItem>
          <FaqItem question="Сколько тарифов и что входит?">
            <p>
              Шесть подписок: BYOK и Managed × Solo / Pro / Studio. См.{' '}
              <Link to="/pricing" className="mm-link-arrow">
                страницу тарифов →
              </Link>
              . Годовая оплата со скидкой 25%.
            </p>
          </FaqItem>
          <FaqItem question="Реферальная программа">
            <p>
              В кабинете на вкладке «Тариф и баланс» — ваша ссылка приглашения. Друг получает бонусные
              кредиты при регистрации; вы — после его первой оплаты подписки.
            </p>
          </FaqItem>
          <FaqItem question="Чем тариф Managed отличается от BYOK?">
            <p>
              <strong>Managed</strong> — генерации студии расходуют кредиты с баланса; ключ WaveSpeed
              может подставлять платформа после оплаты.
            </p>
            <p>
              <strong>BYOK</strong> — вы подключаете свой ключ WaveSpeed; кредиты на студию не
              списываются за генерацию у провайдера.
            </p>
          </FaqItem>
          <FaqItem question="Как оплатить подписку или кредиты?">
            <p>
              Владелец аккаунта оформляет подписку или докупку кредитов в кабинете через ЮKassa.
            </p>
          </FaqItem>
          <FaqItem question="Переводы в чате — как это устроено?">
            <p>
              Входящие можно показывать на русском. Вы пишете по-русски — собеседнику уходит текст на
              его языке.
            </p>
          </FaqItem>
          <FaqItem question="Что нужно для студии изображений?">
            <p>
              Доступ к студии, активная подписка (если включён gate) и ключ{' '}
              <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                WaveSpeed
              </a>{' '}
              в интеграциях на пробном Managed или всегда на BYOK.
            </p>
          </FaqItem>
          <FaqItem question="Не открывается страница или не срабатывает кнопка — что сделать?">
            <p>
              Обновите страницу, проверьте HTTPS и отключите блокировщики для домена. Если ошибка
              повторяется — напишите владельцу доступа или в поддержку инстанса.
            </p>
          </FaqItem>
        </section>
        <p className="mm-muted" style={{ marginTop: 'var(--s-8)' }}>
          <Link to="/pricing" className="mm-link-arrow">
            Тарифы →
          </Link>{' '}
          ·{' '}
          <Link to="/" className="mm-link-arrow">
            На главную ↗
          </Link>
        </p>
      </MmContainer>
    </div>
  )
}
