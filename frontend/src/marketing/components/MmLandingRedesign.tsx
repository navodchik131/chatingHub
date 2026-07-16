import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { parseReferralFromHealth } from '../../billing/referral'
import { usePublicHealth } from '../usePublicHealth'
import { MmPainSection, TELEGRAM_CHANNEL_URL } from './MmSections'
import { MmButton, MmContainer, MmDisplayLg, MmEyebrow, MmSerifAccent } from './MmUi'

const TICKER_ITEMS = [
  'Telegram',
  'Fanvue',
  'Instagram — soon',
  'Nano Banana Pro',
  'GPT Image',
  'Seedream 5 Pro',
  'Wan 2.7 Pro',
  'Tribute',
  'WaveSpeed',
  'PWA',
  'SFW / NSFW',
  'Auto-translate',
] as const

const MODULE_SHOTS = [
  { id: 'studio', shot: '/marketing/landing-shots/03-shot.png', tagTone: 'lime' as const, reverse: false },
  { id: 'dialogs', shot: '/marketing/landing-shots/02-shot.png', tagTone: 'sky' as const, reverse: true },
  { id: 'video', shot: '/marketing/landing-shots/04-shot.png', tagTone: 'violet' as const, reverse: false },
  { id: 'characters', shot: '/marketing/landing-shots/05-shot.png', tagTone: 'pink' as const, reverse: true },
  { id: 'donations', shot: '/marketing/landing-shots/06-shot.png', tagTone: 'green' as const, reverse: false },
]

const MODE_SHOTS = [
  '/marketing/ba/ba-swap-a.png',
  '/marketing/ba/ba-swap-a.png',
  '/marketing/ba/ba-outfit-a.jpg',
  '/marketing/ba/ba-loc-a.jpg',
  '/marketing/landing-shots/03-shot.png',
  '/marketing/landing-shots/03-shot.png',
]

const BA_PAIRS = [
  { before: '/marketing/ba/ba-swap-b.jpeg', after: '/marketing/ba/ba-swap-a.png' },
  { before: '/marketing/ba/ba-outfit-b.jpg', after: '/marketing/ba/ba-outfit-a.jpg' },
  { before: '/marketing/ba/ba-loc-b.png', after: '/marketing/ba/ba-loc-a.jpg' },
]

const ENGINE_META = [
  { name: 'Nano Banana Pro', tag: 'SFW', tone: 'green' as const },
  { name: 'GPT Image', tag: 'SFW', tone: 'green' as const },
  { name: 'Seedream 5 Pro', tag: 'NSFW', tone: 'pink' as const },
  { name: 'Wan 2.7 Pro', tag: 'NSFW', tone: 'pink' as const },
]

const COUNTERS = [
  { n: 120000, suffix: '+' },
  { n: 8500, suffix: '+' },
  { n: 6, suffix: '' },
  { n: 4, suffix: '' },
] as const

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12.2l2.3 2.3 4.7-4.9" />
    </svg>
  )
}

export function MmPlatformTicker() {
  const items = [...TICKER_ITEMS, ...TICKER_ITEMS]
  return (
    <div className="mm-landing-ticker" aria-hidden>
      <div className="mm-landing-ticker__track">
        {items.map((item, i) => (
          <span key={`${item}-${i}`} className="mm-landing-ticker__item">
            {item}
            <span className="mm-landing-ticker__dot">◆</span>
          </span>
        ))}
      </div>
    </div>
  )
}

export function MmCompareWorkflow() {
  const { t } = useTranslation('marketing')
  const rows = t('landingV2.compare.rows', { returnObjects: true }) as Array<{
    label: string
    before: string
    after: string
  }>

  return (
    <section className="mm-section mm-landing-compare" aria-labelledby="mm-compare-workflow-title">
      <MmContainer>
        <MmEyebrow>{t('landingV2.compare.eyebrow')}</MmEyebrow>
        <MmDisplayLg id="mm-compare-workflow-title" className="mm-section__title--sm">
          {t('landingV2.compare.title')}
        </MmDisplayLg>
        <div className="mm-landing-compare__table-wrap">
          <div className="mm-landing-compare__table" role="table">
            <div className="mm-landing-compare__head" role="row">
              <div role="columnheader" />
              <div role="columnheader" className="mm-landing-compare__col-before">
                ✕ {t('landingV2.compare.before')}
              </div>
              <div role="columnheader" className="mm-landing-compare__col-after">
                ✓ {t('landingV2.compare.after')}
              </div>
            </div>
            {Array.isArray(rows)
              ? rows.map((row) => (
                  <div key={row.label} className="mm-landing-compare__row" role="row">
                    <div role="cell" className="mm-landing-compare__label">
                      {row.label}
                    </div>
                    <div role="cell" className="mm-landing-compare__before">
                      {row.before}
                    </div>
                    <div role="cell" className="mm-landing-compare__after">
                      {row.after}
                    </div>
                  </div>
                ))
              : null}
          </div>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmSolutionBlock() {
  const { t } = useTranslation('marketing')
  const steps = t('landingV2.steps', { returnObjects: true }) as Array<{ title: string; desc: string }>

  return (
    <>
      <section className="mm-section mm-section--compact mm-landing-solution-intro" aria-labelledby="mm-solution-title">
        <MmContainer>
          <p className="mm-landing-center">
            <MmEyebrow>{t('landingV2.solution.eyebrow')}</MmEyebrow>
          </p>
          <MmDisplayLg id="mm-solution-title" className="mm-landing-center mm-landing-solution-intro__title">
            {t('landingV2.solution.titleBefore')}
            <MmSerifAccent>{t('landingV2.solution.titleAccent')}</MmSerifAccent>
            {t('landingV2.solution.titleAfter')}
          </MmDisplayLg>
        </MmContainer>
      </section>
      <section className="mm-section mm-section--compact" aria-label={t('landingV2.stepsAria')}>
        <MmContainer>
          <div className="mm-landing-steps">
            {Array.isArray(steps)
              ? steps.map((step, i) => (
                  <article key={step.title} className="mm-landing-step-card">
                    <div className="mm-landing-step-card__top">
                      <span className="mm-landing-step-card__icon" aria-hidden>
                        {['★', '▣', '◉'][i] ?? '·'}
                      </span>
                      <span className="mm-landing-step-card__num">{String(i + 1).padStart(2, '0')}</span>
                    </div>
                    <h3>{step.title}</h3>
                    <p>{step.desc}</p>
                  </article>
                ))
              : null}
          </div>
        </MmContainer>
      </section>
    </>
  )
}

export function MmModuleShowcase() {
  const { t } = useTranslation('marketing')
  const modules = t('landingV2.modules', { returnObjects: true }) as Array<{
    tag: string
    title: string
    desc: string
    points: string[]
  }>

  return (
    <section id="studio" className="mm-section mm-landing-modules" aria-label={t('landingV2.modulesAria')}>
      <MmContainer>
        {Array.isArray(modules)
          ? modules.map((mod, i) => {
              const meta = MODULE_SHOTS[i]
              if (!meta) return null
              return (
                <div
                  key={mod.title}
                  className={`mm-landing-module${meta.reverse ? ' mm-landing-module--reverse' : ''}`}
                >
                  <div className="mm-landing-module__copy">
                    <span className={`mm-landing-module__tag mm-landing-module__tag--${meta.tagTone}`}>
                      {mod.tag}
                    </span>
                    <h2 className="mm-landing-module__title">{mod.title}</h2>
                    <p className="mm-landing-module__desc">{mod.desc}</p>
                    <ul className="mm-landing-module__points">
                      {mod.points.map((p) => (
                        <li key={p}>
                          <CheckIcon />
                          <span>{p}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div
                    className="mm-landing-module__shot"
                    style={{ backgroundImage: `url(${meta.shot})` }}
                    role="img"
                    aria-label={mod.title}
                  />
                </div>
              )
            })
          : null}
      </MmContainer>
    </section>
  )
}

export function MmModesShowcase() {
  const { t } = useTranslation('marketing')
  const modes = t('landingV2.modes', { returnObjects: true }) as Array<{ title: string; desc: string }>

  return (
    <section className="mm-section mm-landing-modes" aria-labelledby="mm-modes-title">
      <MmContainer>
        <MmEyebrow>{t('landingV2.modesSection.eyebrow')}</MmEyebrow>
        <MmDisplayLg id="mm-modes-title">{t('landingV2.modesSection.title')}</MmDisplayLg>
        <p className="mm-muted mm-landing-modes__sub">{t('landingV2.modesSection.sub')}</p>
        <div className="mm-landing-modes__grid">
          {Array.isArray(modes)
            ? modes.map((mode, i) => (
                <article key={mode.title} className="mm-landing-mode-card">
                  <div
                    className="mm-landing-mode-card__media"
                    style={{ backgroundImage: `url(${MODE_SHOTS[i] ?? MODE_SHOTS[0]})` }}
                  >
                    <span className="mm-landing-mode-card__step">{String(i + 1).padStart(2, '0')}</span>
                  </div>
                  <div className="mm-landing-mode-card__body">
                    <h3>{mode.title}</h3>
                    <p>{mode.desc}</p>
                  </div>
                </article>
              ))
            : null}
        </div>
      </MmContainer>
    </section>
  )
}

export function MmEnginesShowcase() {
  const { t } = useTranslation('marketing')
  const descs = t('landingV2.engines', { returnObjects: true }) as string[]

  return (
    <section className="mm-section mm-landing-engines" aria-labelledby="mm-engines-title">
      <MmContainer>
        <MmEyebrow>{t('landingV2.enginesSection.eyebrow')}</MmEyebrow>
        <MmDisplayLg id="mm-engines-title" className="mm-section__title--sm">
          {t('landingV2.enginesSection.title')}
        </MmDisplayLg>
        <p className="mm-muted mm-landing-engines__sub">{t('landingV2.enginesSection.sub')}</p>
        <div className="mm-landing-engines__grid">
          {ENGINE_META.map((engine, i) => (
            <article key={engine.name} className="mm-landing-engine-card">
              <div className="mm-landing-engine-card__top">
                <span className="mm-landing-engine-card__initial">{engine.name.charAt(0)}</span>
                <span className={`mm-landing-engine-card__tag mm-landing-engine-card__tag--${engine.tone}`}>
                  {engine.tag}
                </span>
              </div>
              <h3>{engine.name}</h3>
              <p>{Array.isArray(descs) ? descs[i] : ''}</p>
            </article>
          ))}
        </div>
      </MmContainer>
    </section>
  )
}

export function MmBeforeAfterSlider() {
  const { t } = useTranslation('marketing')
  const tabs = t('landingV2.ba.tabs', { returnObjects: true }) as string[]
  const [tab, setTab] = useState(0)
  const [pos, setPos] = useState(50)
  const dragging = useRef(false)
  const boxRef = useRef<HTMLDivElement>(null)

  const pair = BA_PAIRS[tab] ?? BA_PAIRS[0]

  const setPosFromClientX = useCallback((clientX: number) => {
    const box = boxRef.current
    if (!box) return
    const rect = box.getBoundingClientRect()
    const pct = ((clientX - rect.left) / rect.width) * 100
    setPos(Math.min(98, Math.max(2, pct)))
  }, [])

  useEffect(() => {
    const onMove = (e: MouseEvent | TouchEvent) => {
      if (!dragging.current) return
      const x = 'touches' in e ? e.touches[0]?.clientX : e.clientX
      if (x != null) setPosFromClientX(x)
    }
    const onUp = () => {
      dragging.current = false
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    window.addEventListener('touchmove', onMove)
    window.addEventListener('touchend', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      window.removeEventListener('touchmove', onMove)
      window.removeEventListener('touchend', onUp)
    }
  }, [setPosFromClientX])

  return (
    <section className="mm-section mm-landing-ba" aria-labelledby="mm-ba-title">
      <MmContainer>
        <MmEyebrow>{t('landingV2.ba.eyebrow')}</MmEyebrow>
        <MmDisplayLg id="mm-ba-title" className="mm-section__title--sm">
          {t('landingV2.ba.title')}
        </MmDisplayLg>
        <p className="mm-muted mm-landing-ba__sub">{t('landingV2.ba.sub')}</p>
        <div className="mm-landing-ba__tabs" role="tablist">
          {Array.isArray(tabs)
            ? tabs.map((label, i) => (
                <button
                  key={label}
                  type="button"
                  role="tab"
                  aria-selected={tab === i}
                  className={tab === i ? 'mm-landing-ba__tab is-active' : 'mm-landing-ba__tab'}
                  onClick={() => {
                    setTab(i)
                    setPos(50)
                  }}
                >
                  {label}
                </button>
              ))
            : null}
        </div>
        <div
          ref={boxRef}
          className="mm-landing-ba__frame"
          onMouseDown={(e) => {
            dragging.current = true
            setPosFromClientX(e.clientX)
          }}
          onTouchStart={(e) => {
            dragging.current = true
            const x = e.touches[0]?.clientX
            if (x != null) setPosFromClientX(x)
          }}
        >
          <img src={pair.after} alt="" className="mm-landing-ba__img mm-landing-ba__img--after" />
          <div className="mm-landing-ba__before-wrap" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
            <img src={pair.before} alt="" className="mm-landing-ba__img" />
          </div>
          <span className="mm-landing-ba__label mm-landing-ba__label--before">{t('landingV2.ba.before')}</span>
          <span className="mm-landing-ba__label mm-landing-ba__label--after">{t('landingV2.ba.after')}</span>
          <div className="mm-landing-ba__handle" style={{ left: `${pos}%` }}>
            <span aria-hidden>⇆</span>
          </div>
        </div>
      </MmContainer>
    </section>
  )
}

export function MmTelegramReferralRow() {
  const { t } = useTranslation('marketing')
  const health = usePublicHealth()
  const ref = parseReferralFromHealth(health)

  return (
    <section className="mm-section mm-landing-duo" aria-label={t('landingV2.duoAria')}>
      <MmContainer>
        <div className="mm-landing-duo__grid">
          <article className="mm-landing-duo__card mm-landing-duo__card--tg">
            <div className="mm-landing-duo__icon mm-landing-duo__icon--tg" aria-hidden>
              ✈
            </div>
            <h2 className="mm-landing-duo__title">{t('landingV2.telegram.title')}</h2>
            <p>{t('landingV2.telegram.desc')}</p>
            <MmButton href={TELEGRAM_CHANNEL_URL} size="lg">
              {t('landingV2.telegram.cta')} →
            </MmButton>
          </article>
          <article className="mm-landing-duo__card mm-landing-duo__card--ref">
            <div className="mm-landing-duo__icon mm-landing-duo__icon--ref" aria-hidden>
              🎁
            </div>
            <h2 className="mm-landing-duo__title">{t('referral.title')}</h2>
            <p>{t('referral.dek', { ref })}</p>
            <div className="mm-landing-duo__stats">
              <div>
                <strong>+{ref.friend_referral_credits}</strong>
                <span>{t('landingV2.referralStatFriend')}</span>
              </div>
              <div>
                <strong>{ref.referrer_payment_percent}%</strong>
                <span>{t('landingV2.referralStatPay')}</span>
              </div>
            </div>
          </article>
        </div>
      </MmContainer>
    </section>
  )
}

function useCountUp(target: number, active: boolean) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (!active) return
    const t0 = performance.now()
    const dur = 1400
    let raf = 0
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / dur)
      const eased = 1 - (1 - k) ** 3
      setValue(Math.round(target * eased))
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, active])
  return value
}

export function MmPlatformCounters() {
  const { t } = useTranslation('marketing')
  const labels = t('landingV2.counters', { returnObjects: true }) as string[]
  const ref = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) setActive(true)
      },
      { threshold: 0.3 },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return (
    <section className="mm-section mm-landing-counters" aria-label={t('landingV2.countersTitle')}>
      <MmContainer>
        <p className="mm-landing-center">
          <MmEyebrow>{t('landingV2.countersTitle')}</MmEyebrow>
        </p>
        <div ref={ref} className="mm-landing-counters__grid">
          {COUNTERS.map((c, i) => (
            <CounterCard
              key={c.n}
              target={c.n}
              suffix={c.suffix}
              label={Array.isArray(labels) ? labels[i] : ''}
              active={active}
            />
          ))}
        </div>
      </MmContainer>
    </section>
  )
}

function CounterCard({
  target,
  suffix,
  label,
  active,
}: {
  target: number
  suffix: string
  label: string
  active: boolean
}) {
  const value = useCountUp(target, active)
  return (
    <article className="mm-landing-counter-card">
      <div className="mm-landing-counter-card__value">
        {value.toLocaleString('ru-RU')}
        {suffix}
      </div>
      <p>{label}</p>
    </article>
  )
}

export function MmReviewsCarousel() {
  const { t } = useTranslation('marketing')
  const reviews = t('landingV2.reviews', { returnObjects: true }) as Array<{
    quote: string
    name: string
    role: string
  }>
  const [idx, setIdx] = useState(0)
  if (!Array.isArray(reviews) || reviews.length === 0) return null
  const review = reviews[idx % reviews.length]

  return (
    <section className="mm-section mm-landing-reviews" aria-labelledby="mm-reviews-title">
      <MmContainer>
        <MmEyebrow>{t('landingV2.reviewsSection.eyebrow')}</MmEyebrow>
        <MmDisplayLg id="mm-reviews-title" className="mm-section__title--sm">
          {t('landingV2.reviewsSection.title')}
        </MmDisplayLg>
        <article className="mm-landing-review-card">
          <blockquote>“{review.quote}”</blockquote>
          <div className="mm-landing-review-card__foot">
            <div className="mm-landing-review-card__who">
              <span className="mm-landing-review-card__avatar">{review.name.charAt(0)}</span>
              <div>
                <strong>{review.name}</strong>
                <span>{review.role}</span>
              </div>
            </div>
            <div className="mm-landing-review-card__nav">
              <button
                type="button"
                aria-label={t('landingV2.reviewsPrev')}
                onClick={() => setIdx((i) => (i - 1 + reviews.length) % reviews.length)}
              >
                ←
              </button>
              <button
                type="button"
                aria-label={t('landingV2.reviewsNext')}
                onClick={() => setIdx((i) => (i + 1) % reviews.length)}
              >
                →
              </button>
            </div>
          </div>
        </article>
      </MmContainer>
    </section>
  )
}

export function MmLandingFaq() {
  const { t } = useTranslation('marketing')
  const items = t('landingV2.faq', { returnObjects: true }) as Array<{ q: string; a: string }>
  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="mm-section mm-landing-faq" aria-labelledby="mm-landing-faq-title">
      <MmContainer>
        <MmEyebrow>{t('landingV2.faqSection.eyebrow')}</MmEyebrow>
        <MmDisplayLg id="mm-landing-faq-title" className="mm-section__title--sm">
          {t('landingV2.faqSection.title')}
        </MmDisplayLg>
        <div className="mm-landing-faq__list">
          {Array.isArray(items)
            ? items.map((item, i) => {
                const isOpen = open === i
                return (
                  <div key={item.q} className={isOpen ? 'mm-landing-faq__item is-open' : 'mm-landing-faq__item'}>
                    <button
                      type="button"
                      className="mm-landing-faq__q"
                      aria-expanded={isOpen}
                      onClick={() => setOpen(isOpen ? null : i)}
                    >
                      <span>{item.q}</span>
                      <span aria-hidden>{isOpen ? '−' : '+'}</span>
                    </button>
                    {isOpen ? <p className="mm-landing-faq__a">{item.a}</p> : null}
                  </div>
                )
              })
            : null}
        </div>
      </MmContainer>
    </section>
  )
}

export function MmSecurityBlock() {
  const { t } = useTranslation('marketing')
  const items = t('landingV2.security.items', { returnObjects: true }) as Array<{ title: string; desc: string }>

  return (
    <section className="mm-section mm-landing-security" aria-labelledby="mm-security-title">
      <MmContainer>
        <MmEyebrow>{t('landingV2.security.eyebrow')}</MmEyebrow>
        <MmDisplayLg id="mm-security-title" className="mm-section__title--sm">
          {t('landingV2.security.title')}
        </MmDisplayLg>
        <div className="mm-landing-security__grid">
          {Array.isArray(items)
            ? items.map((item, i) => (
                <article key={item.title} className="mm-landing-security-card">
                  <span className="mm-landing-security-card__icon" aria-hidden>
                    {['🔒', '⏱', '🛡'][i] ?? '·'}
                  </span>
                  <h3>{item.title}</h3>
                  <p>{item.desc}</p>
                </article>
              ))
            : null}
        </div>
      </MmContainer>
    </section>
  )
}

export { MmPainSection as MmLandingPain }
