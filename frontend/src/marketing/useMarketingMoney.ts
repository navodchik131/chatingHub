import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ReferralPublic } from '../billing/referral'
import {
  fetchUsdRate,
  formatCreditOneLiner,
  formatCreditRate,
  formatPerCreditLabel,
  formatPerCreditShort,
  formatPlanPrice,
  getCachedRubPerUsd,
  isEnglishLocale,
} from '../money/display'
import type { PublicHealthPricing } from './usePublicHealth'

const FALLBACK_CREDITS_MIN = 50
const FALLBACK_CREDITS_BULK_FROM = 200
const FALLBACK_UNIT_RUB = 3.6
const FALLBACK_BULK_UNIT_RUB = 3.24

export type MarketingPriceContext = {
  lang: string
  rubPerUsd: number
  creditsMin: number
  creditsBulkFrom: number
  creditUnitPrice: string
  creditOneLiner: string
  creditsUnit: string
  creditsBulkUnit: string
  creditsUnitShort: string
  creditsBulkUnitShort: string
  referrerRewardExample: string
  /** Alias for compare table `{{unit}}`. */
  unit: string
  ref: ReferralPublic & {
    credit_unit_price_display: string
    referrer_reward_example_display: string
  }
  formatPrice: (rub: number) => string
}

export function buildMarketingPriceContext(
  health: PublicHealthPricing | null | undefined,
  ref: ReferralPublic,
  lang: string,
  rubPerUsd: number,
): MarketingPriceContext {
  const creditsMin = health?.billing_credits_min_purchase ?? FALLBACK_CREDITS_MIN
  const creditsBulkFrom = health?.billing_credits_bulk_from ?? FALLBACK_CREDITS_BULK_FROM
  const unitRub = health?.billing_credits_unit_price_rub ?? FALLBACK_UNIT_RUB
  const bulkUnitRub = health?.billing_credits_bulk_unit_price_rub ?? FALLBACK_BULK_UNIT_RUB

  const creditUnitPrice = formatCreditRate(unitRub, lang, rubPerUsd)
  const creditOneLiner = formatCreditOneLiner(unitRub, lang, rubPerUsd)

  return {
    lang,
    rubPerUsd,
    creditsMin,
    creditsBulkFrom,
    creditUnitPrice,
    creditOneLiner,
    creditsUnit: formatPerCreditLabel(unitRub, lang, rubPerUsd),
    creditsBulkUnit: formatPerCreditLabel(bulkUnitRub, lang, rubPerUsd),
    creditsUnitShort: formatPerCreditShort(unitRub, lang, rubPerUsd),
    creditsBulkUnitShort: formatPerCreditShort(bulkUnitRub, lang, rubPerUsd),
    referrerRewardExample: formatPlanPrice(ref.referrer_reward_example_rub, lang, rubPerUsd),
    unit: creditUnitPrice,
    ref: {
      ...ref,
      credit_unit_price_display: creditUnitPrice,
      referrer_reward_example_display: formatPlanPrice(
        ref.referrer_reward_example_rub,
        lang,
        rubPerUsd,
      ),
    },
    formatPrice: (rub: number) => formatPlanPrice(rub, lang, rubPerUsd),
  }
}

export function useMarketingMoney(
  health: PublicHealthPricing | null | undefined,
  ref: ReferralPublic,
): MarketingPriceContext {
  const { i18n } = useTranslation()
  const lang = isEnglishLocale(i18n.language) ? 'en' : 'ru'
  const [rubPerUsd, setRubPerUsd] = useState(getCachedRubPerUsd())

  useEffect(() => {
    if (lang !== 'en') return undefined
    let cancelled = false
    void fetchUsdRate().then((rate) => {
      if (!cancelled) setRubPerUsd(rate)
    })
    return () => {
      cancelled = true
    }
  }, [lang])

  return useMemo(
    () => buildMarketingPriceContext(health, ref, lang, rubPerUsd),
    [health, ref, lang, rubPerUsd],
  )
}

/** i18n interpolation context without the price formatter function. */
export function marketingI18nCtx(money: MarketingPriceContext): Omit<
  MarketingPriceContext,
  'formatPrice'
> {
  const { formatPrice: _formatPrice, ...ctx } = money
  return ctx
}
