import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

function FaqItem({ question, children }: { question: string; children: ReactNode }) {
  return (
    <details className="mkt-details">
      <summary>{question}</summary>
      <div className="mkt-details-body">{children}</div>
    </details>
  )
}

export function FaqPage() {
  return (
    <>
      <header className="mkt-section-head">
        <h1 className="mkt-h1" style={{ fontSize: 'clamp(1.65rem, 4vw, 2.25rem)' }}>
          FAQ: как запустить систему
        </h1>
        <p>
          Короткие ответы по регистрации, переменным окружения, вебхукам Telegram/Fanvue и биллингу. Для Docker и
          полной архитектуры см. также файл README репозитория и{' '}
          <code style={{ fontSize: '0.85em' }}>backend/.env.example</code>.
        </p>
      </header>

      <section className="mkt-faq" aria-label="Вопросы и ответы">
        <FaqItem question="С чего начать после клонирования проекта?">
          <p>
            Задайте секреты <code>JWT_SECRET</code> и <code>FERNET_KEY</code> в <code>backend/.env</code>. Для продакшена с вебхуками Telegram укажите публичный HTTPS —
            переменная <code>PUBLIC_APP_URL</code> — чтобы платформа отдавала корректные URL вебхуков в интерфейсе.
          </p>
          <p>
            Затем поднимите backend и при необходимости соберите фронт: интерфейс доступен либо через Vite в разработке, либо как статика с того же процесса, что и API (папка{' '}
            <code>frontend/dist</code>).
          </p>
        </FaqItem>

        <FaqItem question="Как зарегистрироваться и зайти в кабинет?">
          <p>
            На продакшене откройте страницу входа, создайте владельца пространства (email и пароль не короче 8 символов). После входа все интеграции и оплата настраиваются в кабинете в браузере.
          </p>
          <p>
            Участник команды использует email владельца, свой <strong>логин команды</strong> (латиница, цифры, подчёркивание) и пароль, выданный владельцем.
          </p>
          <p>
            <Link to="/login" className="mkt-link-arrow">
              Перейти к форме входа →
            </Link>
          </p>
        </FaqItem>

        <FaqItem question="Как подключить Telegram (режим SaaS с webhook)?">
          <p>
            Создайте бота в BotFather, добавьте его администратором в чат <strong>Direct messages</strong> канала и выдайте право работать с direct messages. Токен вводится в кабинете в настройках интеграции — сервер сам предложит URL вебхука вида{' '}
            <code>/api/webhooks/telegram/…</code>.
          </p>
          <p>
            Для локальных тестов webhook нужен HTTPS-туннель (например ngrok): см. документацию проекта по Telegram и файл{' '}
            <code>docs/ngrok.md</code>.
          </p>
          <p>
            Если в логах нет входящих <code>telegram.incoming</code>, проверьте доступность <code>api.telegram.org</code>, отсутствие второго процесса с тем же токеном и при необходимости прокси <code>TELEGRAM_PROXY</code>.
          </p>
        </FaqItem>

        <FaqItem question="Что такое Fanvue и как его связать?">
          <p>
            Fanvue подключается через секрет вебхука и учётные данные API из кабинета создателя. В интерфейсе после сохранения отображается URL для сторонней платформы — его нужно указать в настройках вебхука Fanvue.
          </p>
        </FaqItem>

        <FaqItem question="Чем тариф Managed отличается от BYOK?">
          <p>
            <strong>Managed:</strong> студия и связанные модели работают через инфраструктуру платформы; действия студии списывают <strong>кредиты</strong>, которые можно пополнить пакетом.
          </p>
          <p>
            <strong>BYOK (bring your own key):</strong> вы указываете собственные OpenAI-совместимые и другие ключи провайдеров — биллинг на их стороне; условия списания кредитов на платформе смотрите в подсказках кабинета для вашей конфигурации.
          </p>
          <p>
            <Link to="/pricing" className="mkt-link-arrow">
              Подробная страница тарифов →
            </Link>
          </p>
        </FaqItem>

        <FaqItem question="Где включается оплата ЮKassa?">
          <p>
            В <code>backend/.env</code> задаются идентификатор магазина и секрет ЮKassa; вебхук платежной системы должен указывать на ваш экземпляр приложения (endpoint описан в примере env).
          </p>
          <p>
            Если переменные не заданы, блок оплаты в интерфейсе может быть недоступен — это ожидаемо для self-hosted без биллинга.
          </p>
        </FaqItem>

        <FaqItem question="Как проверить, что backend живой и база на месте?">
          <p>
            Откройте <code>GET /api/health</code>: там статус БД, счётчики диалогов, признак связи с Telegram API при необходимости и текущие <strong>публичные</strong> подсказки по ценам подписок и стоимости кредитов студии.
          </p>
        </FaqItem>

        <FaqItem question="Что нужно для студии изображений?">
          <p>
            На стороне сервера задаются ключи и параметры провайдеров студии (см. <code>OPENAI_*</code> и смежные переменные в <code>.env.example</code>). Для пользователя нужна активная подписка, если на инстансе включено требование <code>BILLING_REQUIRE_ACTIVE_SUBSCRIPTION</code>.
          </p>
        </FaqItem>

        <FaqItem question="Docker и один контур для фронта и API">
          <p>
            Из корня репозитория можно поднять <code>docker compose</code>: Postgres и контейнер с API отдаёт собранный фронт единым origin на порту 8080 (см. README).
          </p>
          <p>Последовательность: задать <code>.env</code>, <code>docker compose up --build</code>, зарегистрироваться, затем настроить интеграции.</p>
        </FaqItem>
      </section>

      <section className="mkt-section" style={{ paddingBottom: 0 }}>
        <div className="mkt-hero-panel">
          <h2 style={{ marginBottom: '0.65rem', fontSize: '1rem', textTransform: 'none', letterSpacing: '-0.02em' }}>
            Готовы к работе?
          </h2>
          <p style={{ margin: '0 0 1rem', fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
            Откройте кабинет и следуйте подсказкам мастера интеграций — они совпадают с описанными здесь шагами.
          </p>
          <Link to="/login" className="mkt-nav-cta">
            Войти в ModelMate
          </Link>
        </div>
      </section>
    </>
  )
}
