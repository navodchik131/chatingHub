import { useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { MmButton } from './components/MmUi'
import { formatRub } from './usePublicHealth'

const PLAN_DEFS = [
  { id: 'solo', label: 'Solo', price: 590 },
  { id: 'studio', label: 'Studio', price: 1490 },
  { id: 'agency', label: 'Agency', price: 3990 },
  { id: 'prosolo', label: 'Pro Solo', price: 990 },
  { id: 'propro', label: 'Pro Studio', price: 2490 },
] as const

const CHAN_COLORS = ['#F0A8C8', '#38BDF8', '#C8F53E', '#C084FC', '#FB923C']

const MOCK_CHANNELS = [
  { tag: 'instagram', earned: 71400, clicks: 1140, regs: 92, paid: 21 },
  { tag: 'telegram', earned: 43850, clicks: 612, regs: 54, paid: 12 },
  { tag: 'youtube', earned: 18420, clicks: 428, regs: 24, paid: 4 },
  { tag: 'facebook', earned: 9350, clicks: 218, regs: 11, paid: 2 },
  { tag: 'tiktok', earned: 5300, clicks: 82, regs: 5, paid: 0 },
]

function Ico({ children }: { children: ReactNode }) {
  return (
    <svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {children}
    </svg>
  )
}

function fmtNum(n: number, locale: string) {
  return n.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU')
}

export function PartnersPage() {
  const { t, i18n } = useTranslation('marketing')
  const registerPath = '/partners/register'
  const [refs, setRefs] = useState(12)
  const [planId, setPlanId] = useState<(typeof PLAN_DEFS)[number]['id']>('studio')
  const [faqOpen, setFaqOpen] = useState(-1)

  const heroStats = t('partnersPage.heroStats', { returnObjects: true }) as Array<{ val: string; label: string }>
  const whyCards = t('partnersPage.whyCards', { returnObjects: true }) as Array<{ title: string; desc: string }>
  const steps = t('partnersPage.steps', { returnObjects: true }) as Array<{ n: string; title: string; desc: string }>
  const trackPoints = t('partnersPage.trackPoints', { returnObjects: true }) as string[]
  const audiences = t('partnersPage.audiences', { returnObjects: true }) as Array<{ title: string; desc: string; stat: string }>
  const terms = t('partnersPage.terms', { returnObjects: true }) as Array<{ n: string; title: string; desc: string }>
  const faqs = t('partnersPage.faqs', { returnObjects: true }) as Array<{ q: string; a: string }>
  const ticker = t('partnersPage.ticker', { returnObjects: true }) as string[]
  const mockMetrics = t('partnersPage.mockMetrics', { returnObjects: true }) as Record<string, string>

  const curPlan = PLAN_DEFS.find((p) => p.id === planId) ?? PLAN_DEFS[1]
  const monthly = Math.round(refs * curPlan.price * 0.3)
  const totalClicks = MOCK_CHANNELS.reduce((n, c) => n + c.clicks, 0)
  const maxEarn = MOCK_CHANNELS[0].earned

  const stepIcons = useMemo(
    () => [
      <Ico key="u"><circle cx="12" cy="8.5" r="3.6" /><path d="M5 20c.8-3.4 3.6-5.4 7-5.4s6.2 2 7 5.4" /></Ico>,
      <Ico key="l"><path d="M10 13.5a3.5 3.5 0 0 0 5 0l3-3a3.5 3.5 0 0 0-5-5l-1.5 1.5" /><path d="M14 10.5a3.5 3.5 0 0 0-5 0l-3 3a3.5 3.5 0 0 0 5 5L12.5 17" /></Ico>,
      <Ico key="c"><path d="M4 20V10M10 20V5M16 20v-8" /><path d="M3 20h18" /></Ico>,
      <Ico key="w"><rect x="3" y="6" width="18" height="13" rx="3" /><path d="M3 10.5h18" /><circle cx="16.5" cy="14.5" r="1.2" /></Ico>,
    ],
    [],
  )

  const whyIcons = useMemo(
    () => [
      <Ico key="i"><path d="M8.5 9.5c1.9 0 2.6 1.4 3.5 2.5s1.6 2.5 3.5 2.5a2.5 2.5 0 0 0 0-5c-1.9 0-2.6 1.4-3.5 2.5s-1.6 2.5-3.5 2.5a2.5 2.5 0 0 1 0-5z" /></Ico>,
      <Ico key="c"><circle cx="12" cy="12" r="8.5" /><path d="M12 7v10" /><path d="M9 9.6c0-1.4 1.3-2.2 3-2.2s3 .9 3 2.1c0 3-6 1.7-6 4.7 0 1.3 1.3 2.2 3 2.2s3-.9 3-2.2" /></Ico>,
      <Ico key="t"><path d="M4 11.5V5.5A1.5 1.5 0 0 1 5.5 4h6l8 8-7.5 7.5z" /><circle cx="8.5" cy="8.5" r="1.4" /></Ico>,
      <Ico key="w"><rect x="3" y="6" width="18" height="13" rx="3" /><path d="M3 10.5h18" /><circle cx="16.5" cy="14.5" r="1.2" /></Ico>,
    ],
    [],
  )

  return (
    <div className="mm-partners">
      <section className="mm-partners-hero">
        <div className="mm-container mm-partners-hero__grid">
          <div>
            <p className="mm-partners-kicker">{t('partnersPage.kicker')}</p>
            <h1 className="mm-partners-display">
              {t('partnersPage.h1a')}
              <br />
              <span className="mm-partners-it">{t('partnersPage.h1it')}</span> {t('partnersPage.h1b')}
            </h1>
            <p className="mm-partners-lead">{t('partnersPage.heroSub')}</p>
            <div className="mm-partners-hero__actions">
              <MmButton to={registerPath} size="lg">
                {t('partnersPage.becomeCta')} →
              </MmButton>
              <MmButton href="#calc" variant="secondary" size="lg">
                {t('partnersPage.calcCta')}
              </MmButton>
            </div>
            <div className="mm-partners-stats">
              {Array.isArray(heroStats)
                ? heroStats.map((hs, i) => (
                    <div key={hs.label}>
                      <div className={`mm-partners-stats__val${i === 0 ? ' mm-partners-stats__val--accent' : i === 1 ? ' mm-partners-stats__val--sky' : ''}`}>
                        {hs.val}
                      </div>
                      <div className="mm-partners-stats__label">{hs.label}</div>
                    </div>
                  ))
                : null}
            </div>
          </div>

          <aside className="mm-partners-card">
            <div className="mm-partners-card__head">
              <span className="mm-partners-kicker">{t('partnersPage.cardKicker')}</span>
              <span className="mm-partners-badge">30% LIFETIME</span>
            </div>
            <div className="mm-partners-card__amount">{t('partnersPage.cardAmount')}</div>
            <p className="mm-partners-card__sub">{t('partnersPage.cardSub')}</p>
            <div className="mm-partners-card__bars">
              {MOCK_CHANNELS.slice(0, 4).map((c, i) => (
                <div key={c.tag}>
                  <div className="mm-partners-bar-row">
                    <span className="mm-partners-bar-dot" style={{ background: CHAN_COLORS[i] }} />
                    <span className="mm-partners-bar-tag">{c.tag}</span>
                    <span className="mm-partners-bar-amt" style={{ color: CHAN_COLORS[i] }}>
                      {formatRub(c.earned)}
                    </span>
                  </div>
                  <div className="mm-partners-bar-track">
                    <div className="mm-partners-bar-fill" style={{ width: `${Math.round((c.earned / maxEarn) * 100)}%`, background: CHAN_COLORS[i] }} />
                  </div>
                </div>
              ))}
            </div>
            <p className="mm-partners-card__note">{t('partnersPage.cardNote')}</p>
          </aside>
        </div>
      </section>

      <div className="mm-partners-ticker" aria-hidden>
        <div className="mm-partners-ticker__track">
          {[...(Array.isArray(ticker) ? ticker : []), ...(Array.isArray(ticker) ? ticker : [])].map((ti, i) => (
            <span key={`${ti}-${i}`} className="mm-partners-ticker__item">
              {ti}
              <span className="mm-partners-ticker__sep">◆</span>
            </span>
          ))}
        </div>
      </div>

      <section className="mm-partners-section">
        <div className="mm-container">
          <p className="mm-partners-kicker">{t('partnersPage.whyKicker')}</p>
          <h2 className="mm-partners-display mm-partners-display--md">{t('partnersPage.whyTitle')}</h2>
          <div className="mm-partners-grid mm-partners-grid--4">
            {Array.isArray(whyCards)
              ? whyCards.map((w, i) => (
                  <article key={w.title} className="mm-partners-tile">
                    <div className="mm-partners-tile__icon">{whyIcons[i]}</div>
                    <h3>{w.title}</h3>
                    <p>{w.desc}</p>
                  </article>
                ))
              : null}
          </div>
        </div>
      </section>

      <section className="mm-partners-section">
        <div className="mm-container">
          <p className="mm-partners-kicker">{t('partnersPage.stepsKicker')}</p>
          <h2 className="mm-partners-display mm-partners-display--md">{t('partnersPage.stepsTitle')}</h2>
          <div className="mm-partners-grid mm-partners-grid--4">
            {Array.isArray(steps)
              ? steps.map((st, i) => (
                  <article key={st.n} className="mm-partners-step">
                    <div className="mm-partners-step__head">
                      <div className="mm-partners-step__icon">{stepIcons[i]}</div>
                      <span className="mm-partners-step__n">{st.n}</span>
                    </div>
                    <h3>{st.title}</h3>
                    <p>{st.desc}</p>
                  </article>
                ))
              : null}
          </div>
        </div>
      </section>

      <section id="calc" className="mm-partners-section">
        <div className="mm-container">
          <div className="mm-partners-calc">
            <div>
              <p className="mm-partners-kicker">{t('partnersPage.calcKicker')}</p>
              <h2 className="mm-partners-display mm-partners-display--sm">{t('partnersPage.calcTitle')}</h2>
              <p className="mm-partners-lead">{t('partnersPage.calcHint')}</p>
              <label className="mm-partners-range">
                <div className="mm-partners-range__head">
                  <span className="mm-partners-kicker">{t('partnersPage.calcRefs')}</span>
                  <span className="mm-partners-range__val">{refs}</span>
                </div>
                <input type="range" min={1} max={120} value={refs} onChange={(e) => setRefs(Number(e.target.value))} />
              </label>
              <div className="mm-partners-plans">
                <span className="mm-partners-kicker">{t('partnersPage.calcPlan')}</span>
                <div className="mm-partners-plans__row">
                  {PLAN_DEFS.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={`mm-partners-plan${planId === p.id ? ' is-active' : ''}`}
                      onClick={() => setPlanId(p.id)}
                    >
                      {p.label} · {fmtNum(p.price, i18n.language)} ₽
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <aside className="mm-partners-calc-result">
              <p className="mm-partners-kicker">{t('partnersPage.calcMonthly')}</p>
              <div className="mm-partners-calc-result__amount">{formatRub(monthly)}</div>
              <p className="mm-partners-calc-result__sub">
                {refs}
                {t('partnersPage.calcCreatorsSuffix')}
                {curPlan.label}
              </p>
              <dl className="mm-partners-calc-rows">
                <div>
                  <dt>{t('partnersPage.calcPerCreator')}</dt>
                  <dd>{formatRub(Math.round(curPlan.price * 0.3))}</dd>
                </div>
                <div>
                  <dt>{t('partnersPage.calcPerYear')}</dt>
                  <dd className="is-accent">{formatRub(monthly * 12)}</dd>
                </div>
                <div>
                  <dt>{t('partnersPage.calcRevenue')}</dt>
                  <dd className="is-sky">
                    {formatRub(refs * curPlan.price)}
                    {t('partnersPage.calcPerMonthSuffix')}
                  </dd>
                </div>
              </dl>
              <p className="mm-partners-calc-disclaimer">{t('partnersPage.calcDisclaimer')}</p>
            </aside>
          </div>
        </div>
      </section>

      <section className="mm-partners-section">
        <div className="mm-container mm-partners-split">
          <div>
            <p className="mm-partners-kicker">{t('partnersPage.trackKicker')}</p>
            <h2 className="mm-partners-display mm-partners-display--sm">
              {t('partnersPage.trackTitleA')} <span className="mm-partners-it">{t('partnersPage.trackTitleIt')}</span>
            </h2>
            <p className="mm-partners-lead">{t('partnersPage.trackSub')}</p>
            <ul className="mm-partners-checklist">
              {Array.isArray(trackPoints)
                ? trackPoints.map((tp) => (
                    <li key={tp}>{tp}</li>
                  ))
                : null}
            </ul>
          </div>
          <div className="mm-partners-mock">
            <div className="mm-partners-mock__chrome">
              <span /><span /><span />
              <span className="mm-partners-mock__title">{t('partnersPage.mockTitle')}</span>
            </div>
            <div className="mm-partners-mock__body">
              <div className="mm-partners-mock__share">
                {MOCK_CHANNELS.map((c, i) => (
                  <div key={c.tag} style={{ flex: Math.max(c.clicks, 1), background: CHAN_COLORS[i] }} />
                ))}
              </div>
              {MOCK_CHANNELS.map((c, i) => (
                <div key={c.tag} className="mm-partners-mock__row">
                  <div className="mm-partners-bar-row">
                    <span className="mm-partners-bar-dot" style={{ background: CHAN_COLORS[i] }} />
                    <span className="mm-partners-bar-tag">{c.tag}</span>
                    <span className="mm-partners-bar-amt" style={{ color: CHAN_COLORS[i] }}>
                      {c.earned ? formatRub(c.earned) : '—'}
                    </span>
                  </div>
                  <div className="mm-partners-mock__metrics">
                    <span>
                      {fmtNum(c.clicks, i18n.language)} <small>{mockMetrics.clicks}</small>
                    </span>
                    <span>
                      {c.regs} <small>{mockMetrics.signups}</small>
                    </span>
                    <span>
                      {c.paid} <small>{mockMetrics.paying}</small>
                    </span>
                    <span>
                      {Math.round((c.clicks / totalClicks) * 100)}% <small>{mockMetrics.share}</small>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mm-partners-section">
        <div className="mm-container">
          <p className="mm-partners-kicker">{t('partnersPage.whoKicker')}</p>
          <h2 className="mm-partners-display mm-partners-display--md">{t('partnersPage.whoTitle')}</h2>
          <div className="mm-partners-grid mm-partners-grid--4">
            {Array.isArray(audiences)
              ? audiences.map((au) => (
                  <article key={au.title} className="mm-partners-audience">
                    <h3>{au.title}</h3>
                    <p>{au.desc}</p>
                    <span className="mm-partners-audience__stat">{au.stat}</span>
                  </article>
                ))
              : null}
          </div>
        </div>
      </section>

      <section className="mm-partners-section">
        <div className="mm-container mm-partners-split">
          <div className="mm-partners-terms">
            <h2 className="mm-partners-display mm-partners-display--xs">{t('partnersPage.termsTitle')}</h2>
            <ol className="mm-partners-terms__list">
              {Array.isArray(terms)
                ? terms.map((tm) => (
                    <li key={tm.n}>
                      <span className="mm-partners-terms__n">{tm.n}</span>
                      <div>
                        <strong>{tm.title}</strong>
                        <p>{tm.desc}</p>
                      </div>
                    </li>
                  ))
                : null}
            </ol>
          </div>
          <div className="mm-partners-faq">
            <h2 className="mm-partners-display mm-partners-display--xs">{t('partnersPage.faqTitle')}</h2>
            {Array.isArray(faqs)
              ? faqs.map((fq, i) => (
                  <div key={fq.q} className="mm-partners-faq__item">
                    <button type="button" className="mm-partners-faq__q" onClick={() => setFaqOpen(faqOpen === i ? -1 : i)} aria-expanded={faqOpen === i}>
                      <span>{fq.q}</span>
                      <span aria-hidden>{faqOpen === i ? '−' : '+'}</span>
                    </button>
                    {faqOpen === i ? <p className="mm-partners-faq__a">{fq.a}</p> : null}
                  </div>
                ))
              : null}
          </div>
        </div>
      </section>

      <section className="mm-partners-section mm-partners-section--cta">
        <div className="mm-container">
          <div className="mm-partners-final">
            <p className="mm-partners-kicker">{t('partnersPage.finalKicker')}</p>
            <h2 className="mm-partners-display mm-partners-display--md">
              {t('partnersPage.finalTitleA')} <span className="mm-partners-it">{t('partnersPage.finalTitleIt')}</span>
            </h2>
            <p className="mm-partners-lead mm-partners-lead--center">{t('partnersPage.finalSub')}</p>
            <div className="mm-partners-hero__actions mm-partners-hero__actions--center">
              <MmButton to={registerPath} size="lg">
                {t('partnersPage.becomeCta')} →
              </MmButton>
              <MmButton href={t('partnersPage.supportUrl')} variant="secondary" size="lg">
                {t('partnersPage.askCta')}
              </MmButton>
            </div>
            <p className="mm-partners-final__note">{t('partnersPage.finalNote')}</p>
          </div>
        </div>
      </section>
    </div>
  )
}
