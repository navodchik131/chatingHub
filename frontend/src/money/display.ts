/** Display prices in ₽ (RU) or $ (EN) using CBR USD rate. */

export const FALLBACK_RUB_PER_USD = 90

let cachedRubPerUsd = FALLBACK_RUB_PER_USD

export function getCachedRubPerUsd(): number {
  return cachedRubPerUsd > 0 ? cachedRubPerUsd : FALLBACK_RUB_PER_USD
}

export async function fetchUsdRate(): Promise<number> {
  try {
    const r = await fetch('/api/billing/fx/usd', { credentials: 'include' })
    if (!r.ok) throw new Error(`fx ${r.status}`)
    const data = (await r.json()) as { rub_per_usd?: unknown }
    const rate = Number(data?.rub_per_usd)
    if (Number.isFinite(rate) && rate > 0) {
      cachedRubPerUsd = rate
      return rate
    }
  } catch {
    /* keep cache / fallback */
  }
  return getCachedRubPerUsd()
}

export function isEnglishLocale(lang: string | undefined | null): boolean {
  return (lang || '').toLowerCase().startsWith('en')
}

function formatUsdAmount(usd: number): string {
  const abs = Math.abs(usd)
  let decimals = 0
  if (abs < 10) decimals = abs < 1 ? 2 : 1
  const rounded =
    decimals === 0
      ? Math.round(usd)
      : Math.round(usd * 10 ** decimals) / 10 ** decimals
  return `$${rounded.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  })}`
}

/** Subscription / pack prices. */
export function formatPlanPrice(
  rub: number,
  lang: string,
  rubPerUsd = getCachedRubPerUsd(),
): string {
  const amount = Number(rub) || 0
  if (!isEnglishLocale(lang)) {
    return `${amount.toLocaleString('ru-RU')} ₽`
  }
  const usd = amount / (rubPerUsd || FALLBACK_RUB_PER_USD)
  return formatUsdAmount(usd)
}

/** Small unit amounts (per credit). */
export function formatUnitPrice(
  rub: number,
  lang: string,
  rubPerUsd = getCachedRubPerUsd(),
): string {
  const amount = Number(rub) || 0
  if (!isEnglishLocale(lang)) {
    return amount.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
  }
  const usd = amount / (rubPerUsd || FALLBACK_RUB_PER_USD)
  if (usd < 1) {
    return usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return usd.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

export function formatCreditRate(
  rubPerCredit: number,
  lang: string,
  rubPerUsd = getCachedRubPerUsd(),
): string {
  if (!isEnglishLocale(lang)) {
    return `${formatUnitPrice(rubPerCredit, lang, rubPerUsd)} ₽/кр.`
  }
  return `$${formatUnitPrice(rubPerCredit, lang, rubPerUsd)}/cr.`
}

export function formatCreditOneLiner(
  rubPerCredit: number,
  lang: string,
  rubPerUsd = getCachedRubPerUsd(),
): string {
  if (!isEnglishLocale(lang)) {
    return `1 кредит = ${formatUnitPrice(rubPerCredit, lang, rubPerUsd)} ₽`
  }
  return `1 credit = $${formatUnitPrice(rubPerCredit, lang, rubPerUsd)}`
}

export function formatPerCreditLabel(
  rubPerCredit: number,
  lang: string,
  rubPerUsd = getCachedRubPerUsd(),
): string {
  if (!isEnglishLocale(lang)) {
    return `${formatUnitPrice(rubPerCredit, lang, rubPerUsd)} ₽/кредит`
  }
  return `$${formatUnitPrice(rubPerCredit, lang, rubPerUsd)}/credit`
}

export function formatPerCreditShort(
  rubPerCredit: number,
  lang: string,
  rubPerUsd = getCachedRubPerUsd(),
): string {
  if (!isEnglishLocale(lang)) {
    return `${formatUnitPrice(rubPerCredit, lang, rubPerUsd)} ₽`
  }
  return `$${formatUnitPrice(rubPerCredit, lang, rubPerUsd)}`
}

export function formatPlanPeriodSuffix(lang: string): string {
  return isEnglishLocale(lang) ? '/ mo' : '/ мес'
}

/** Replace hardcoded ₽ in EN about-deck HTML fragments. */
export function patchAboutDeckPrices(
  html: string,
  lang: string,
  rubPerUsd = getCachedRubPerUsd(),
  unitRub = 3.6,
): string {
  if (!isEnglishLocale(lang)) return html

  const creditShort = formatPerCreditShort(unitRub, lang, rubPerUsd)
  const creditOneLiner = formatCreditOneLiner(unitRub, lang, rubPerUsd)
  const payoutMin = formatPlanPrice(500, lang, rubPerUsd)

  let out = html
  out = out.replace(/1 cr = ₽[\d,.]+/g, `1 cr = ${creditShort}`)
  out = out.replace(/<b>1 credit = [\d,.]+ ₽<\/b>/g, `<b>${creditOneLiner}</b>`)
  out = out.replace(/from <b>500 ₽<\/b>/g, `from <b>${payoutMin}</b>`)

  const plans: Array<[string, number]> = [
    ['590', 590],
    ['1 490', 1490],
    ['3 990', 3990],
  ]
  for (const [label, rub] of plans) {
    const price = formatPlanPrice(rub, lang, rubPerUsd)
    out = out.replace(
      new RegExp(`${label.replace(' ', '\\s')} <span>₽ / mo</span>`, 'g'),
      `${price} <span>/ mo</span>`,
    )
  }
  return out
}

export function fillPriceTemplate(
  template: string,
  vars: Record<string, string>,
): string {
  return Object.entries(vars).reduce(
    (text, [key, value]) => text.replaceAll(`{{${key}}}`, value),
    template,
  )
}
