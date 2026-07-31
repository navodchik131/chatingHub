import { useEffect, useRef, useState } from 'react'

import { useTranslation } from 'react-i18next'



import { fetchUsdRate, getCachedRubPerUsd, patchAboutDeckPrices } from '../money/display'

import { useMarketingPath } from './i18n/useMarketingPath'

import { initAboutServiceDeck } from './aboutServiceDeck'

import './about-service-deck.css'

import './about-service.css'



export function AboutServicePage() {

  const { t } = useTranslation('marketing')

  const { locale } = useMarketingPath()

  const deckRef = useRef<HTMLDivElement>(null)

  const [bodyHtml, setBodyHtml] = useState('')

  const [rubPerUsd, setRubPerUsd] = useState(getCachedRubPerUsd())

  const bodySrc =

    locale === 'en' ? '/about-service-deck.en.body.html' : '/about-service-deck.ru.body.html'



  useEffect(() => {

    document.documentElement.classList.add('mm-about-active')

    return () => document.documentElement.classList.remove('mm-about-active')

  }, [])



  useEffect(() => {

    if (locale !== 'en') return undefined

    let cancelled = false

    void fetchUsdRate().then((rate) => {

      if (!cancelled) setRubPerUsd(rate)

    })

    return () => {

      cancelled = true

    }

  }, [locale])



  useEffect(() => {

    let cancelled = false

    void fetch(bodySrc)

      .then((r) => {

        if (!r.ok) throw new Error(String(r.status))

        return r.text()

      })

      .then((html) => {

        if (!cancelled) setBodyHtml(html)

      })

      .catch(() => {

        if (!cancelled) setBodyHtml('')

      })

    return () => {

      cancelled = true

    }

  }, [bodySrc])



  useEffect(() => {

    const deck = deckRef.current

    if (!deck || !bodyHtml) return

    deck.innerHTML = patchAboutDeckPrices(bodyHtml, locale, rubPerUsd)

    return initAboutServiceDeck(deck, {

      motionOn: t('aboutService.motionOn'),

      motionOff: t('aboutService.motionOff'),

      motionTitleOn: t('aboutService.motionTitleOn'),

      motionTitleOff: t('aboutService.motionTitleOff'),

    })

  }, [bodyHtml, locale, rubPerUsd, t])



  return (

    <div

      ref={deckRef}

      className="mm-about-deck"

      aria-label={t('aboutService.pageAria')}

      suppressHydrationWarning

    />

  )

}

