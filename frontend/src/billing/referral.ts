/** Публичные параметры рефералки (billing_catalog.referral). */

export interface ReferralPublic {
  friend_referral_credits: number
  signup_base_credits: number
  referrer_payment_percent: number
  credit_unit_price_rub: number
  referrer_reward_example_rub: number
  referrer_reward_example_credits: number
}

const FALLBACK: ReferralPublic = {
  friend_referral_credits: 25,
  signup_base_credits: 0,
  referrer_payment_percent: 10,
  credit_unit_price_rub: 3.7,
  referrer_reward_example_rub: 990,
  referrer_reward_example_credits: 26,
}

export function parseReferralFromHealth(
  health: { billing_catalog?: { referral?: unknown } } | null | undefined,
): ReferralPublic {
  const r = health?.billing_catalog?.referral
  if (!r || typeof r !== 'object') return FALLBACK
  const o = r as Record<string, unknown>
  const num = (k: string, fb: number) => {
    const v = Number(o[k])
    return Number.isFinite(v) ? v : fb
  }
  return {
    friend_referral_credits: num('friend_referral_credits', FALLBACK.friend_referral_credits),
    signup_base_credits: num('signup_base_credits', FALLBACK.signup_base_credits),
    referrer_payment_percent: num('referrer_payment_percent', FALLBACK.referrer_payment_percent),
    credit_unit_price_rub: num('credit_unit_price_rub', FALLBACK.credit_unit_price_rub),
    referrer_reward_example_rub: num('referrer_reward_example_rub', FALLBACK.referrer_reward_example_rub),
    referrer_reward_example_credits: num(
      'referrer_reward_example_credits',
      FALLBACK.referrer_reward_example_credits,
    ),
  }
}

/** Кредиты для оплаты подписки по фиксированному курсу (ceil). */
export function subscriptionCostCredits(priceRub: number, unitRub: number): number {
  if (unitRub <= 0) return 0
  return Math.ceil(priceRub / unitRub)
}
