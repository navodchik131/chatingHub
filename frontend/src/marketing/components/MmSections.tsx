import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { renderWithWavespeedRef } from '../../billing/wavespeedRefLink'
import { parseReferralFromHealth } from '../../billing/referral'
import { usePublicHealth } from '../usePublicHealth'
import { useMarketingPath } from '../i18n/useMarketingPath'
import {
  MmBadge,
  MmButton,
  MmContainer,
  MmDisplayLg,
  MmEyebrow,
  MmSerifAccent,
} from './MmUi'

const BETA_CREATORS = 19

export const TELEGRAM_CHANNEL_URL = 'https://t.me/ModelMate_app'

const HERO_TILES = [
  { src: '/marketing/hero/hero1.gif', badge: 'VIDEO · 4K', col: '1 / 2', row: '1 / 3', offset: 0 },
  { src: '/marketing/hero/hero2.jpg', badge: 'PHOTO · 15s', col: '2 / 3', row: '1 / 2', offset: 32 },
  { src: '/marketing/hero/hero3.gif', badge: 'VIDEO', col: '2 / 3', row: '2 / 3', offset: 32 },
  { src: '/marketing/hero/hero4.gif', badge: 'VIDEO · I2V', col: '1 / 2', row: '3 / 4', offset: 0 },
] as const

const SHOWCASE_MEDIA = [
  {
    subjectSrc: '/marketing/tools/img_ref.jpg',
    motionSrc: '/marketing/tools/img_result.jpg',
  },
  {
    subjectSrc: 'https://picsum.photos/seed/mm-still-2/600/750',
    motionSrc: 'https://picsum.photos/seed/mm-motion-2/600/750',
  },
  {
    subjectSrc: 'https://picsum.photos/seed/mm-still-3/600/750',
    motionSrc: 'https://picsum.photos/seed/mm-result-3/600/750',
  },
] as const

const TOOL_IMAGES = [
  '/marketing/showcase/image_ref.png',
  '/marketing/showcase/video.gif',
  'https://picsum.photos/seed/mm-chat-1/800/600',
] as const

const PAIN_ICONS = ['↻', '◎', '◈', '◇'] as const

const MODEL_CHIPS = [
  { name: 'WaveSpeed', mark: 'W', bg: '#D8FF3D' },
  { name: 'Seedance 2.0', mark: 'S', bg: '#FF7A4D' },
  { name: 'Nano Banana Pro', mark: 'N', bg: '#FFD66E' },
  { name: 'Scene AI', mark: 'A', bg: '#5BD4FF' },
  { name: 'Wan 2.7', mark: 'W', bg: '#C58CFF' },
  { name: 'Kling Motion', mark: 'K', bg: '#7CE38B' },
  { name: 'Fanvue', mark: 'F', bg: '#F5F5F7' },
  { name: 'Telegram', mark: 'T', bg: '#5BD4FF' },
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
  const { t } = useTranslation('marketing')
  const health = usePublicHealth()
  const demoGenerations = health?.demo_generations_grant ?? 3

  return (
    <section className="mm-hero" aria-labelledby="mm-hero-title">
      <MmContainer>
        <div className="mm-hero__grid">
          <div className="mm-hero__copy">
            <MmEyebrow>{t('hero.eyebrow')}</MmEyebrow>
            <h1 id="mm-hero-title" className="mm-display-xl">
              {t('hero.titleBefore')}
              <MmSerifAccent>{t('hero.titleAccent')}</MmSerifAccent>
              {t('hero.titleAfter')}
            </h1>
            <p className="mm-hero__dek">{t('hero.dek')}</p>
            <div className="mm-hero__actions">
              <MmButton to="/login" size="lg">
                {t('hero.ctaPrimary', { demoGenerations })}
              </MmButton>
            </div>
            <div className="mm-hero__stats">
              <div>
                <div className="mm-hero__stat-val">{t('hero.statDemoValue', { demoGenerations })}</div>
                <div className="mm-hero__stat-label">{t('hero.statDemoLabel')}</div>
              </div>
              <div>
                <div className="mm-hero__stat-val">{t('hero.statStartValue')}</div>
                <div className="mm-hero__stat-label">{t('hero.statStartLabel')}</div>
              </div>
              <div>
                <div className="mm-hero__stat-val">{t('hero.statPlansValue')}</div>
                <div className="mm-hero__stat-label">{t('hero.statPlansLabel')}</div>
              </div>
            </div>
          </div>
          <div className="mm-hero-collage" aria-hidden>
            {HERO_TILES.map((tile) => (
              <div
                key={tile.badge}
                className="mm-hero-collage__tile"
                style={{
                  gridColumn: tile.col,
                  gridRow: tile.row,
                  transform: tile.offset ? `translateY(${tile.offset}px)` : undefined,
                  backgroundImage: `url(${tile.src})`,
                }}
              >
                <MmBadge tone="num">{tile.badge}</MmBadge>
              </div>
            ))}
          </div>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmReferralBand() {
  const { t } = useTranslation('marketing')
  const health = usePublicHealth()
  const ref = parseReferralFromHealth(health)

  return (
    <section id="referral" className="mm-section mm-section--compact mm-referral-section" aria-labelledby="mm-referral-title">
      <MmContainer>
        <div className="mm-referral-band">
          <div className="mm-referral-band__intro">
            <MmEyebrow>{t('referral.eyebrow')}</MmEyebrow>
            <h2 id="mm-referral-title" className="mm-referral-band__title">
              {t('referral.title')}
            </h2>
            <p className="mm-referral-band__dek">{t('referral.dek', { ref })}</p>
            <p className="mm-muted mm-referral-band__note">{t('referral.note')}</p>
          </div>
          <div className="mm-referral-grid" role="list">
            <article className="mm-referral-card" role="listitem">
              <span className="mm-referral-card__who">{t('referral.cardFriendWho')}</span>
              <strong className="mm-referral-card__value">{t('referral.cardFriendValue', { ref })}</strong>
              <p className="mm-referral-card__hint">{t('referral.cardFriendHint', { ref })}</p>
            </article>
            <article className="mm-referral-card mm-referral-card--accent" role="listitem">
              <span className="mm-referral-card__who">{t('referral.cardReferrerWho')}</span>
              <strong className="mm-referral-card__value">{t('referral.cardReferrerValue', { ref })}</strong>
              <p className="mm-referral-card__hint">{t('referral.cardReferrerHint', { ref })}</p>
            </article>
            <article className="mm-referral-card" role="listitem">
              <span className="mm-referral-card__who">{t('referral.cardPayWho')}</span>
              <strong className="mm-referral-card__value">{t('referral.cardPayValue', { ref })}</strong>
              <p className="mm-referral-card__hint">{t('referral.cardPayHint')}</p>
            </article>
          </div>
          <div className="mm-referral-band__actions">
            <MmButton to="/login" size="lg">
              {t('referral.ctaPrimary')}
            </MmButton>
            <MmButton to="/faq" variant="secondary" size="lg">
              {t('referral.ctaSecondary')}
            </MmButton>
          </div>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmCommunityBand() {
  const { t } = useTranslation('marketing')

  return (
    <section className="mm-section mm-section--compact mm-community-section" aria-labelledby="mm-community-title">
      <MmContainer>
        <div className="mm-community-band">
          <div className="mm-community-band__main">
            <MmEyebrow tone="video">{t('community.eyebrow')}</MmEyebrow>
            <h2 id="mm-community-title" className="mm-community-band__title">
              {t('community.title')}
            </h2>
            <p className="mm-community-band__dek">{t('community.dek')}</p>
            <a className="mm-community-band__link" href={TELEGRAM_CHANNEL_URL} target="_blank" rel="noopener noreferrer">
              {t('community.link')}
            </a>
          </div>
          <MmButton href={TELEGRAM_CHANNEL_URL} variant="primary" size="lg">
            {t('community.cta')}
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
}

function MmToolCard({ tone, eyebrow, title, desc, cta, badges, img }: ToolCardProps) {
  const { path } = useMarketingPath()
  return (
    <Link to={path('/login')} className={`mm-tool-card mm-tool-card--${tone}`}>
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
        <span className="mm-tool-card__cta">{cta} →</span>
      </div>
    </Link>
  )
}

export function MmToolGrid() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()
  const cards = t('tools.cards', { returnObjects: true }) as ToolCardProps[]

  return (
    <section id="tools" className="mm-section mm-section--tools">
      <MmContainer>
        <div className="mm-section__head-row">
          <div>
            <MmEyebrow>{t('tools.eyebrow')}</MmEyebrow>
            <MmDisplayLg>
              {t('tools.titleLine1')}
              <br />
              {t('tools.titleLine2')}
            </MmDisplayLg>
          </div>
          <Link to={path('/login')} className="mm-link-arrow">
            {t('tools.linkCabinet')}
          </Link>
        </div>
        <div className="mm-tool-grid">
          {Array.isArray(cards)
            ? cards.map((card, i) => (
                <MmToolCard key={card.title} {...card} img={TOOL_IMAGES[i] ?? TOOL_IMAGES[0]} />
              ))
            : null}
        </div>
      </MmContainer>
    </section>
  )
}

export function MmPainSection() {
  const { t } = useTranslation('marketing')
  const items = t('pain.items', { returnObjects: true }) as Array<{ title: string; text: string }>

  return (
    <section id="problem" className="mm-section mm-section--border">
      <MmContainer>
        <MmEyebrow>{t('pain.eyebrow')}</MmEyebrow>
        <MmDisplayLg className="mm-section__title">{t('pain.title')}</MmDisplayLg>
        <div className="mm-pain-grid">
          {Array.isArray(items)
            ? items.map((p, i) => (
                <article key={p.title} className="mm-pain-card">
                  <span className="mm-pain-card__icon" aria-hidden>
                    {PAIN_ICONS[i] ?? '·'}
                  </span>
                  <h3>{p.title}</h3>
                  <p>{p.text}</p>
                </article>
              ))
            : null}
        </div>
      </MmContainer>
    </section>
  )
}

function ShowcaseRow({
  eyebrow,
  titleLine1,
  titleLine2,
  dek,
  cta,
  reverse,
  pairs,
}: {
  eyebrow: string
  titleLine1: string
  titleLine2: string
  dek: string
  cta: string
  reverse?: boolean
  pairs: { subjectSrc: string; motionSrc: string; subjectLabel: string; motionLabel: string }
}) {
  return (
    <div className={`mm-showcase-row${reverse ? ' mm-showcase-row--reverse' : ''}`}>
      <MmContainer>
        <div className="mm-showcase-row__grid">
          <div className="mm-showcase-row__copy">
            <MmEyebrow>{eyebrow}</MmEyebrow>
            <MmDisplayLg>
              {titleLine1}
              <br />
              {titleLine2}
            </MmDisplayLg>
            <p className="mm-showcase-row__dek">{dek}</p>
            <MmButton to="/login" variant="secondary">
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
  const { t } = useTranslation('marketing')
  const health = usePublicHealth()
  const demoGenerations = health?.demo_generations_grant ?? 3
  const rows = t('showcase.rows', { returnObjects: true, demoGenerations }) as Array<{
    eyebrow: string
    titleLine1: string
    titleLine2: string
    dek: string
    cta: string
    subjectLabel: string
    motionLabel: string
  }>

  return (
    <div id="showcase" className="mm-showcase">
      {Array.isArray(rows)
        ? rows.map((row, i) => (
            <ShowcaseRow
              key={row.eyebrow}
              {...row}
              reverse={i === 1}
              pairs={{
                ...SHOWCASE_MEDIA[i],
                subjectLabel: row.subjectLabel,
                motionLabel: row.motionLabel,
              }}
            />
          ))
        : null}
    </div>
  )
}

export function MmHowSection() {
  const { t } = useTranslation('marketing')
  const health = usePublicHealth()
  const demoGenerations = health?.demo_generations_grant ?? 3
  const steps = t('how.steps', { returnObjects: true, demoGenerations }) as Array<{ title: string; text: string }>

  return (
    <section id="how" className="mm-section mm-section--how">
      <MmContainer>
        <MmEyebrow>{t('how.eyebrow')}</MmEyebrow>
        <MmDisplayLg className="mm-section__title">
          {t('how.titleBefore')}
          <MmSerifAccent>{t('how.titleAccent')}</MmSerifAccent>
          {t('how.titleAfter')}
        </MmDisplayLg>
        <div className="mm-how-grid">
          {Array.isArray(steps)
            ? steps.map((step, i) => (
                <article key={step.title} className="mm-how-card">
                  <span className="mm-how-card__num">{i + 1}</span>
                  <strong>{renderWithWavespeedRef(step.title)}</strong>
                  <p>{renderWithWavespeedRef(step.text)}</p>
                </article>
              ))
            : null}
        </div>
        <div className="mm-how-cta">
          <MmButton to="/login" size="lg">
            {t('how.cta', { demoGenerations })}
          </MmButton>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmModelStrip() {
  const { t } = useTranslation('marketing')

  return (
    <section id="models" className="mm-section mm-section--border mm-section--compact">
      <MmContainer>
        <p className="mm-model-strip__eyebrow">
          <MmEyebrow>{t('modelsStrip.eyebrow')}</MmEyebrow>
        </p>
        <div className="mm-model-strip">
          {MODEL_CHIPS.map((m) => (
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
  const { t } = useTranslation('marketing')
  const health = usePublicHealth()
  const betaCount = health?.marketing_beta_creators_count ?? BETA_CREATORS
  const demoGenerations = health?.demo_generations_grant ?? 3

  return (
    <section className="mm-section mm-section--border">
      <MmContainer>
        <div className="mm-trial-band">
          <div>
            <MmEyebrow>{t('trial.eyebrow')}</MmEyebrow>
            <h2 className="mm-trial-band__title">{t('trial.title', { betaCount })}</h2>
            <p className="mm-trial-band__dek">{t('trial.dek', { demoGenerations })}</p>
          </div>
          <MmButton to="/login">{t('trial.cta')}</MmButton>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmCtaBanner() {
  const { t } = useTranslation('marketing')
  const health = usePublicHealth()
  const demoGenerations = health?.demo_generations_grant ?? 3

  return (
    <section className="mm-section mm-cta-banner-wrap">
      <MmContainer>
        <div className="mm-cta-banner">
          <MmEyebrow>{t('cta.eyebrow')}</MmEyebrow>
          <h2 className="mm-cta-banner__title">
            {t('cta.titleLine1')}
            <br />
            {t('cta.titleLine2')}
          </h2>
          <p className="mm-cta-banner__dek">{t('cta.dek', { demoGenerations })}</p>
          <div className="mm-cta-banner__actions">
            <MmButton to="/login" size="lg">
              {t('cta.ctaPrimary')}
            </MmButton>
            <MmButton to="/faq" variant="secondary" size="lg">
              {t('cta.ctaSecondary')}
            </MmButton>
          </div>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmCompareTeaser() {
  const { t } = useTranslation('marketing')
  const { path } = useMarketingPath()

  return (
    <section className="mm-section mm-section--compact">
      <MmContainer>
        <MmEyebrow>{t('compare.eyebrow')}</MmEyebrow>
        <MmDisplayLg as="h2" className="mm-section__title--sm">
          {t('compare.title')}
        </MmDisplayLg>
        <p className="mm-muted mm-compare-teaser__dek">{t('compare.dek')}</p>
        <Link to={path('/pricing')} className="mm-link-arrow">
          {t('compare.link')}
        </Link>
      </MmContainer>
    </section>
  )
}
