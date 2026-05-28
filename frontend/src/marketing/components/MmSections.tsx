import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { WAVESPEED_REF_URL } from '../../billing/planCatalog'
import { parseReferralFromHealth } from '../../billing/referral'
import { usePublicHealth } from '../usePublicHealth'
import {
  MmBadge,
  MmButton,
  MmContainer,
  MmDisplayLg,
  MmEyebrow,
  MmSerifAccent,
} from './MmUi'

const BETA_CREATORS = 19

/** Канал: новости, обсуждения, предложения по продукту */
export const TELEGRAM_CHANNEL_URL = 'https://t.me/ModelMate_app'

const HERO_TILES = [
  { src: '/marketing/hero/hero1.gif', badge: 'VIDEO · 4K', col: '1 / 2', row: '1 / 3', offset: 0 },
  { src: '/marketing/hero/hero2.jpg', badge: 'PHOTO · 15s', col: '2 / 3', row: '1 / 2', offset: 32 },
  { src: '/marketing/hero/hero3.gif', badge: 'VIDEO', col: '2 / 3', row: '2 / 3', offset: 32 },
  { src: '/marketing/hero/hero4.gif', badge: 'VIDEO · I2V', col: '1 / 2', row: '3 / 4', offset: 0 },
] as const

function MediaPair({
  subjectSrc,
  motionSrc,
  subjectLabel,
  motionLabel,
}: {
  subjectSrc: string
  motionSrc: string
  subjectLabel: string
  motionLabel: string
}) {
  return (
    <div className="mm-media-pair">
      <div className="mm-media-pair__tile" style={{ backgroundImage: `url(${subjectSrc})` }}>
        <MmBadge tone="num">{subjectLabel}</MmBadge>
      </div>
      <div className="mm-media-pair__tile" style={{ backgroundImage: `url(${motionSrc})` }}>
        <MmBadge tone="num">{motionLabel}</MmBadge>
      </div>
      <span className="mm-media-pair__mark" aria-hidden>
        ×
      </span>
    </div>
  )
}

export function MmHero() {
  const health = usePublicHealth()
  const signupCredits = health?.signup_bonus_credits ?? 100

  return (
    <section className="mm-hero" aria-labelledby="mm-hero-title">
      <MmContainer>
        <div className="mm-hero__grid">
          <div className="mm-hero__copy">
            <MmEyebrow>Creator OS · Photo · Video · Chat</MmEyebrow>
            <h1 id="mm-hero-title" className="mm-display-xl">
              Создавай <MmSerifAccent>AI-моделей</MmSerifAccent> и общайся с фанами.
            </h1>
            <p className="mm-hero__dek">
              Генерация фото и видео, чат Fanvue и Telegram, авто-перевод и команда — без переключения между
              пятью сервисами.
            </p>
            <div className="mm-hero__actions">
              <MmButton to="/login" size="lg">
                Попробовать бесплатно — {signupCredits} кр.
              </MmButton>
              <MmButton to="/#how" variant="secondary" size="lg">
                Запуск за 5 минут
              </MmButton>
            </div>
            <div className="mm-hero__stats">
              <div>
                <div className="mm-hero__stat-val">{health?.marketing_beta_creators_count ?? BETA_CREATORS}</div>
                <div className="mm-hero__stat-label">в закрытой бете</div>
              </div>
              <div>
                <div className="mm-hero__stat-val">5 мин</div>
                <div className="mm-hero__stat-label">подключение WaveSpeed</div>
              </div>
              <div>
                <div className="mm-hero__stat-val">BYOK</div>
                <div className="mm-hero__stat-label">ключи шифруются</div>
              </div>
            </div>
          </div>
          <div className="mm-hero-collage" aria-hidden>
            {HERO_TILES.map((t) => (
              <div
                key={t.badge}
                className="mm-hero-collage__tile"
                style={{
                  gridColumn: t.col,
                  gridRow: t.row,
                  transform: t.offset ? `translateY(${t.offset}px)` : undefined,
                  backgroundImage: `url(${t.src})`,
                }}
              >
                <MmBadge tone="num">{t.badge}</MmBadge>
              </div>
            ))}
          </div>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmReferralBand() {
  const health = usePublicHealth()
  const ref = parseReferralFromHealth(health)

  return (
    <section id="referral" className="mm-section mm-section--compact mm-referral-section" aria-labelledby="mm-referral-title">
      <MmContainer>
        <div className="mm-referral-band">
          <div className="mm-referral-band__intro">
            <MmEyebrow>Реферальная программа</MmEyebrow>
            <h2 id="mm-referral-title" className="mm-referral-band__title">
              Приглашай креаторов — зарабатывай с каждой оплаты.
            </h2>
            <p className="mm-referral-band__dek">
              Пока друг с нами, вы получаете {ref.referrer_payment_percent}% от каждой его оплаты подписки — в кредитах
              по курсу 1 кр. = {ref.credit_unit_price_rub} ₽. Картой, кредитами или продление — без лимита по времени.
              Приглашённый стартует с +{ref.friend_referral_credits} кр. по вашей ссылке.
            </p>
            <p className="mm-muted mm-referral-band__note">
              Персональная ссылка — в кабинете, раздел «Тариф и баланс». Подписку можно оплатить с баланса кредитов.
            </p>
          </div>
          <div className="mm-referral-grid" role="list">
            <article className="mm-referral-card" role="listitem">
              <span className="mm-referral-card__who">Друг по ссылке</span>
              <strong className="mm-referral-card__value">+{ref.friend_referral_credits} кр.</strong>
              <p className="mm-referral-card__hint">
                Бонус при регистрации по вашей ссылке (плюс стандартный триал {ref.signup_base_credits} кр.).
              </p>
            </article>
            <article className="mm-referral-card mm-referral-card--accent" role="listitem">
              <span className="mm-referral-card__who">Вы — реферер</span>
              <strong className="mm-referral-card__value">{ref.referrer_payment_percent}%</strong>
              <p className="mm-referral-card__hint">
                С каждой оплаты и продления — снова и снова. Пример за платёж: {ref.referrer_reward_example_rub} ₽ →
                ~{ref.referrer_reward_example_credits} кр.
              </p>
            </article>
            <article className="mm-referral-card" role="listitem">
              <span className="mm-referral-card__who">Оплата подписки</span>
              <strong className="mm-referral-card__value">{ref.credit_unit_price_rub} ₽/кр.</strong>
              <p className="mm-referral-card__hint">
                Любой тариф в кабинете можно оплатить кредитами с баланса по тому же курсу.
              </p>
            </article>
          </div>
          <div className="mm-referral-band__actions">
            <MmButton to="/login" size="lg">
              Зарегистрироваться и получить ссылку
            </MmButton>
            <MmButton to="/faq" variant="secondary" size="lg">
              Подробнее в FAQ
            </MmButton>
          </div>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmCommunityBand() {
  return (
    <section className="mm-section mm-section--compact mm-community-section" aria-labelledby="mm-community-title">
      <MmContainer>
        <div className="mm-community-band">
          <div className="mm-community-band__main">
            <MmEyebrow tone="video">Telegram · @ModelMate_app</MmEyebrow>
            <h2 id="mm-community-title" className="mm-community-band__title">
              Общение и новости — в канале.
            </h2>
            <p className="mm-community-band__dek">
              Всё общение, новости и обсуждения проходят в нашем Telegram. Предложения по продукту, обновления
              студии и ответы команды — там же.
            </p>
            <a className="mm-community-band__link" href={TELEGRAM_CHANNEL_URL} target="_blank" rel="noopener noreferrer">
              t.me/ModelMate_app ↗
            </a>
          </div>
          <MmButton href={TELEGRAM_CHANNEL_URL} variant="primary" size="lg">
            Перейти в канал
          </MmButton>
        </div>
      </MmContainer>
    </section>
  )
}

type ToolCardProps = {
  tone: 'photo' | 'video' | 'i2v'
  eyebrow: string
  title: string
  desc: string
  cta: string
  badges: string[]
  img: string
  href: string
}

function MmToolCard({ tone, eyebrow, title, desc, cta, badges, img, href }: ToolCardProps) {
  return (
    <Link to={href} className={`mm-tool-card mm-tool-card--${tone}`}>
      <div className="mm-tool-card__media" style={{ backgroundImage: `url(${img})` }}>
        <div className="mm-tool-card__badges">
          {badges.map((b, i) => (
            <MmBadge key={b} tone={i === 0 ? tone : 'num'}>
              {b}
            </MmBadge>
          ))}
        </div>
      </div>
      <div className="mm-tool-card__body">
        <MmEyebrow tone={tone}>{eyebrow}</MmEyebrow>
        <h3 className="mm-tool-card__title">{title}</h3>
        <p className="mm-tool-card__desc">{desc}</p>
        <span className="mm-tool-card__cta">
          {cta} →
        </span>
      </div>
    </Link>
  )
}

export function MmToolGrid() {
  return (
    <section id="tools" className="mm-section mm-section--tools">
      <MmContainer>
        <div className="mm-section__head-row">
          <div>
            <MmEyebrow>Студия · что внутри</MmEyebrow>
            <MmDisplayLg>
              Три раздела.
              <br />
              Одно окно.
            </MmDisplayLg>
          </div>
          <Link to="/login" className="mm-link-arrow">
            Открыть кабинет ↗
          </Link>
        </div>
        <div className="mm-tool-grid">
          <MmToolCard
            tone="photo"
            eyebrow="Photo · WaveSpeed · профиль модели"
            title="Картинки"
            desc="Модель, референс и промпт — GROK собирает сцену. Nano Banana, Seedance, карусель и доработка в истории."
            cta="Сделать кадр"
            badges={['Photo', '4K']}
            img="/marketing/showcase/image_ref.png"
            href="/login"
          />
          <MmToolCard
            tone="video"
            eyebrow="Video · Seedance · motion"
            title="Видео"
            desc="Реф-ролик, первый кадр и бриф — готовые ролики в архиве. Motion control и сцены под вашу модель."
            cta="Сделать видео"
            badges={['Video', '15s']}
            img="/marketing/showcase/video.gif"
            href="/login"
          />
          <MmToolCard
            tone="i2v"
            eyebrow="Chat · Fanvue · Telegram"
            title="Чат и перевод"
            desc="Один инбокс для фанов. Авто-перевод на десятки языков — оператор пишет по-русски, фан видит свой язык."
            cta="Открыть чаты"
            badges={['Chat', 'New']}
            img="https://picsum.photos/seed/mm-chat-1/800/600"
            href="/login"
          />
        </div>
      </MmContainer>
    </section>
  )
}

export function MmPainSection() {
  const pains = [
    { icon: '↻', title: 'Скачешь между 5 сервисами', text: 'Промпты, генерация, перевод, CRM и таблицы для команды — переключение съедает время.' },
    { icon: '◎', title: 'Каждая генерация с нуля', text: 'Образ модели не запоминается — снова «as before, but…» и снова рандом.' },
    { icon: '◈', title: 'Чаттеры путаются', text: 'Несколько моделей — разные характеры и языки. Фаны чувствуют фальшь.' },
    { icon: '◇', title: 'Иностранные фаны', text: 'Машинный перевод звучит деревянно — доверие и чаевые падают.' },
  ]
  return (
    <section id="problem" className="mm-section mm-section--border">
      <MmContainer>
        <MmEyebrow>Боль · знакомо?</MmEyebrow>
        <MmDisplayLg className="mm-section__title">Пять сервисов. Ноль связности.</MmDisplayLg>
        <div className="mm-pain-grid">
          {pains.map((p) => (
            <article key={p.title} className="mm-pain-card">
              <span className="mm-pain-card__icon" aria-hidden>
                {p.icon}
              </span>
              <h3>{p.title}</h3>
              <p>{p.text}</p>
            </article>
          ))}
        </div>
      </MmContainer>
    </section>
  )
}

function ShowcaseRow({
  eyebrow,
  title,
  dek,
  cta,
  ctaTo,
  reverse,
  pairs,
}: {
  eyebrow: string
  title: ReactNode
  dek: string
  cta: string
  ctaTo: string
  reverse?: boolean
  pairs: { subjectSrc: string; motionSrc: string; subjectLabel: string; motionLabel: string }
}) {
  return (
    <div className={`mm-showcase-row${reverse ? ' mm-showcase-row--reverse' : ''}`}>
      <MmContainer>
        <div className="mm-showcase-row__grid">
          <div className="mm-showcase-row__copy">
            <MmEyebrow>{eyebrow}</MmEyebrow>
            <MmDisplayLg>{title}</MmDisplayLg>
            <p className="mm-showcase-row__dek">{dek}</p>
            <MmButton to={ctaTo} variant="secondary">
              {cta}
            </MmButton>
          </div>
          <MediaPair {...pairs} />
        </div>
      </MmContainer>
    </div>
  )
}

export function MmShowcase() {
  return (
    <div id="showcase" className="mm-showcase">
      <ShowcaseRow
        eyebrow="WaveSpeed · BYOK · Managed"
        title={
          <>
            Один ключ.
            <br />
            Вся студия.
          </>
        }
        dek="На пробном Managed — свой ключ WaveSpeed. На BYOK — всегда ваш. Профиль модели и референсы остаются в кабинете."
        cta="Подключить WaveSpeed"
        ctaTo="/login"
        pairs={{
          subjectSrc: 'https://picsum.photos/seed/mm-face-1/600/750',
          motionSrc: 'https://picsum.photos/seed/mm-result-1/600/750',
          subjectLabel: 'REF',
          motionLabel: 'RESULT',
        }}
      />
      <ShowcaseRow
        reverse
        eyebrow="Fanvue · Telegram · перевод"
        title={
          <>
            Один инбокс.
            <br />
            Любой язык.
          </>
        }
        dek="Диалоги в одном окне. Авто-перевод входящих и исходящих — чаттеры не путают характеры моделей."
        cta="Настроить чаты"
        ctaTo="/login"
        pairs={{
          subjectSrc: 'https://picsum.photos/seed/mm-still-2/600/750',
          motionSrc: 'https://picsum.photos/seed/mm-motion-2/600/750',
          subjectLabel: 'IN',
          motionLabel: 'OUT · LANG',
        }}
      />
      <ShowcaseRow
        eyebrow="GROK · сцены · видео"
        title={
          <>
            Промпт,
            <br />
            который держит образ.
          </>
        }
        dek="Референс → готовый промпт под модель. Раскадровка и motion-бриф для видео — без ручной возни в пяти вкладках."
        cta="Открыть студию"
        ctaTo="/login"
        pairs={{
          subjectSrc: 'https://picsum.photos/seed/mm-still-3/600/750',
          motionSrc: 'https://picsum.photos/seed/mm-result-3/600/750',
          subjectLabel: 'SCENE',
          motionLabel: 'PROMPT',
        }}
      />
    </div>
  )
}

export function MmHowSection() {
  const health = usePublicHealth()
  const signupCredits = health?.signup_bonus_credits ?? 100

  return (
    <section id="how" className="mm-section mm-section--how">
      <MmContainer>
        <MmEyebrow>Onboarding · 5 минут</MmEyebrow>
        <MmDisplayLg className="mm-section__title">
          Запуск без <MmSerifAccent>карты</MmSerifAccent>.
        </MmDisplayLg>
        <div className="mm-how-grid">
          <article className="mm-how-card">
            <span className="mm-how-card__num">1</span>
            <strong>Подключи WaveSpeed</strong>
            <p>
              API-ключ на{' '}
              <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                wavespeed.ai
              </a>{' '}
              — платите провайдеру напрямую.
            </p>
          </article>
          <article className="mm-how-card">
            <span className="mm-how-card__num">2</span>
            <strong>Настрой модель</strong>
            <p>Референсы, стиль, образ — один раз в профиле модели.</p>
          </article>
          <article className="mm-how-card">
            <span className="mm-how-card__num">3</span>
            <strong>Генерируй и общайся</strong>
            <p>Контент, чаты и переводы в одном окне.</p>
          </article>
        </div>
        <div className="mm-how-cta">
          <MmButton to="/login" size="lg">
            Начать бесплатно — {signupCredits} кредитов
          </MmButton>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmModelStrip() {
  const models = [
    { name: 'WaveSpeed', mark: 'W', bg: '#D8FF3D' },
    { name: 'Seedance 2.0', mark: 'S', bg: '#FF7A4D' },
    { name: 'Nano Banana Pro', mark: 'N', bg: '#FFD66E' },
    { name: 'GROK', mark: 'G', bg: '#5BD4FF' },
    { name: 'Wan 2.7', mark: 'W', bg: '#C58CFF' },
    { name: 'Kling Motion', mark: 'K', bg: '#7CE38B' },
    { name: 'Fanvue', mark: 'F', bg: '#F5F5F7' },
    { name: 'Telegram', mark: 'T', bg: '#5BD4FF' },
  ]
  return (
    <section id="models" className="mm-section mm-section--border mm-section--compact">
      <MmContainer>
        <p className="mm-model-strip__eyebrow">
          <MmEyebrow>Интеграции · один баланс</MmEyebrow>
        </p>
        <div className="mm-model-strip">
          {models.map((m) => (
            <span key={m.name} className="mm-model-chip">
              <span className="mm-model-chip__mark" style={{ background: m.bg }}>
                {m.mark}
              </span>
              {m.name}
            </span>
          ))}
        </div>
      </MmContainer>
    </section>
  )
}

export function MmTrialBand() {
  const health = usePublicHealth()
  const betaCount = health?.marketing_beta_creators_count ?? BETA_CREATORS
  const signupCredits = health?.signup_bonus_credits ?? 100

  return (
    <section className="mm-section mm-section--border">
      <MmContainer>
        <div className="mm-trial-band">
          <div>
            <MmEyebrow>Beta · доступ</MmEyebrow>
            <h2 className="mm-trial-band__title">
              {betaCount} креаторов уже внутри
            </h2>
            <p className="mm-trial-band__dek">
              {signupCredits} кредитов при регистрации. Без карты. Кредиты не сгорают по времени.
            </p>
          </div>
          <MmButton to="/login">Получить доступ</MmButton>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmCtaBanner() {
  const health = usePublicHealth()
  const signupCredits = health?.signup_bonus_credits ?? 100

  return (
    <section className="mm-section mm-cta-banner-wrap">
      <MmContainer>
        <div className="mm-cta-banner">
          <MmEyebrow>Студия открыта</MmEyebrow>
          <h2 className="mm-cta-banner__title">
            Хватит прыгать
            <br />
            между сервисами.
          </h2>
          <p className="mm-cta-banner__dek">
            Картинки, видео, чаты и команда — в ModelMate. {signupCredits} кредитов на старт, без привязки карты.
          </p>
          <div className="mm-cta-banner__actions">
            <MmButton to="/login" size="lg">
              Начать сейчас
            </MmButton>
            <MmButton to="/faq" variant="secondary" size="lg">
              Частые вопросы
            </MmButton>
          </div>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmCompareTeaser() {
  return (
    <section className="mm-section mm-section--compact">
      <MmContainer>
        <MmEyebrow>Сравнение</MmEyebrow>
        <MmDisplayLg as="h2" className="mm-section__title--sm">
          Solo · Pro · Studio
        </MmDisplayLg>
        <p className="mm-muted mm-compare-teaser__dek">
          BYOK и Managed — лимиты пользователей, моделей и GROK в одной таблице.
        </p>
        <Link to="/pricing" className="mm-link-arrow">
          Полная таблица тарифов ↗
        </Link>
      </MmContainer>
    </section>
  )
}
