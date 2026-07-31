export type AboutServiceDeckLabels = {
  motionOn: string
  motionOff: string
  motionTitleOn: string
  motionTitleOff: string
}

declare global {
  interface Window {
    __cycleSync?: () => void
  }
}

/** Init scroll-snap deck behaviour after body HTML is mounted (no iframe). */
export function initAboutServiceDeck(
  deck: HTMLElement,
  labels: AboutServiceDeckLabels,
): () => void {
  const root = document.documentElement
  const btn = deck.querySelector<HTMLButtonElement>('#mtoggle')
  const pbar = deck.querySelector<HTMLElement>('#pbar')
  if (!btn || !pbar) return () => {}

  const setMotion = (mode: 'full' | 'soft') => {
    root.setAttribute('data-motion', mode)
    btn.textContent = mode === 'full' ? labels.motionOn : labels.motionOff
    btn.setAttribute('aria-pressed', String(mode === 'full'))
    btn.title = mode === 'full' ? labels.motionTitleOn : labels.motionTitleOff
    window.__cycleSync?.()
  }

  setMotion('full')
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce) {
    btn.classList.add('hint')
    window.setTimeout(() => btn.classList.remove('hint'), 9000)
  }

  const onToggle = () => {
    setMotion(btn.getAttribute('aria-pressed') === 'true' ? 'soft' : 'full')
  }
  btn.addEventListener('click', onToggle)

  const progress = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight
    pbar.style.width = `${max > 0 ? (window.scrollY / max) * 100 : 0}%`
  }
  window.addEventListener('scroll', progress, { passive: true })
  window.addEventListener('resize', progress)
  progress()

  const slides = Array.from(deck.querySelectorAll<HTMLElement>('.slide'))
  const links = Array.from(deck.querySelectorAll<HTMLAnchorElement>('.rail a'))
  const cnum = deck.querySelector<HTMLElement>('#cnum')

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) e.target.classList.add('in')
      })
    },
    { threshold: 0.16 },
  )

  const raf1 = requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      slides.forEach((s) => io.observe(s))
    })
  })

  const io2 = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting || !cnum) return
        const i = slides.indexOf(e.target as HTMLElement)
        cnum.textContent = String(i + 1).padStart(2, '0')
        let best: HTMLAnchorElement | null = null
        links.forEach((a) => {
          const t = a.getAttribute('href')?.slice(1) ?? ''
          if (slides.findIndex((s) => s.id === t) <= i) best = a
        })
        links.forEach((a) => a.classList.toggle('on', a === best))
      })
    },
    { threshold: 0.5 },
  )
  slides.forEach((s) => io2.observe(s))

  const cyc = deck.querySelector<SVGElement>('svg.cyc')
  let raf: number | null = null
  let heroObserver: IntersectionObserver | null = null

  if (cyc) {
    const comet = cyc.querySelector<SVGGeometryElement>('.comet')
    const head = cyc.querySelector<SVGCircleElement>('.head')
    const nodes = Array.from(cyc.querySelectorAll<SVGGElement>('.node'))
    const R = 150
    const CX = 200
    const CY = 200
    const C = 2 * Math.PI * R
    const DASH = 150
    const PERIOD = 9000
    if (comet) comet.style.animation = 'none'

    let phase = 0
    let last = 0
    let heroVisible = true

    const render = (k: number) => {
      if (comet) comet.style.strokeDashoffset = `${-C * k}px`
      const kh = (k + DASH / C) % 1
      const a = -Math.PI / 2 + kh * 2 * Math.PI
      if (head) {
        head.setAttribute('cx', String(CX + R * Math.cos(a)))
        head.setAttribute('cy', String(CY + R * Math.sin(a)))
      }
      const idx = Math.floor(kh * nodes.length) % nodes.length
      nodes.forEach((n, j) => n.classList.toggle('lit', j === idx))
    }

    const frame = (now: number) => {
      if (!last) last = now
      phase = (phase + (now - last)) % PERIOD
      last = now
      render(phase / PERIOD)
      raf = requestAnimationFrame(frame)
    }

    const spin = (on: boolean) => {
      if (on) {
        if (!raf) {
          last = 0
          raf = requestAnimationFrame(frame)
        }
      } else if (raf) {
        cancelAnimationFrame(raf)
        raf = null
        render(0.3)
      }
    }

    const sync = () => {
      spin(heroVisible && root.getAttribute('data-motion') === 'full')
    }

    window.__cycleSync = sync
    heroObserver = new IntersectionObserver(
      (entries) => {
        heroVisible = entries[0]?.isIntersecting ?? true
        sync()
      },
      { threshold: 0.05 },
    )
    heroObserver.observe(cyc)
    sync()
  }

  const go = (dir: number) => {
    const y = window.scrollY + window.innerHeight * 0.5
    let cur = 0
    slides.forEach((s, i) => {
      if (s.offsetTop <= y) cur = i
    })
    const n = Math.max(0, Math.min(slides.length - 1, cur + dir))
    slides[n]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowRight' || e.key === 'PageDown') {
      e.preventDefault()
      go(1)
    }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
      e.preventDefault()
      go(-1)
    }
    if (e.key === 'Home') {
      e.preventDefault()
      slides[0]?.scrollIntoView({ behavior: 'smooth' })
    }
    if (e.key === 'End') {
      e.preventDefault()
      slides[slides.length - 1]?.scrollIntoView({ behavior: 'smooth' })
    }
  }
  document.addEventListener('keydown', onKeyDown)

  return () => {
    btn.removeEventListener('click', onToggle)
    window.removeEventListener('scroll', progress)
    window.removeEventListener('resize', progress)
    document.removeEventListener('keydown', onKeyDown)
    cancelAnimationFrame(raf1)
    io.disconnect()
    io2.disconnect()
    heroObserver?.disconnect()
    if (raf) cancelAnimationFrame(raf)
    if (window.__cycleSync) delete window.__cycleSync
    root.removeAttribute('data-motion')
  }
}
