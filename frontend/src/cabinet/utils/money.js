/** Курс USD и форматирование цен для кабинета. */

const FALLBACK_RUB_PER_USD = 90

let cached = {
  rubPerUsd: FALLBACK_RUB_PER_USD,
  fetchedAt: 0,
}

export async function fetchUsdRate() {
  try {
    const r = await fetch('/api/billing/fx/usd', { credentials: 'include' })
    if (!r.ok) throw new Error(`fx ${r.status}`)
    const data = await r.json()
    const rate = Number(data?.rub_per_usd)
    if (Number.isFinite(rate) && rate > 0) {
      cached = { rubPerUsd: rate, fetchedAt: Date.now() }
      return rate
    }
  } catch {
    /* keep cache / fallback */
  }
  return cached.rubPerUsd
}

export function getCachedRubPerUsd() {
  return cached.rubPerUsd > 0 ? cached.rubPerUsd : FALLBACK_RUB_PER_USD
}

/** RU → ₽, EN → $ по курсу (округление до целых долларов для тарифов). */
export function formatPlanPrice(rub, lang, rubPerUsd = getCachedRubPerUsd()) {
  const amount = Number(rub) || 0
  if (lang === 'ru') {
    return `${amount.toLocaleString('ru-RU')} ₽`
  }
  const usd = amount / (rubPerUsd || FALLBACK_RUB_PER_USD)
  const rounded = usd >= 100 ? Math.round(usd) : Math.round(usd * 10) / 10
  return `$${rounded.toLocaleString('en-US', { maximumFractionDigits: rounded % 1 ? 1 : 0 })}`
}

export function formatCreditsPackPrice(rub, lang, rubPerUsd = getCachedRubPerUsd()) {
  return formatPlanPrice(rub, lang, rubPerUsd)
}
