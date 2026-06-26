export const SUBSCRIPTION_STATUS_OPTIONS = [
  'none',
  'incomplete',
  'trialing',
  'active',
  'past_due',
  'canceled',
  'unpaid',
] as const

export const SUBSCRIPTION_STATUS_LABELS: Record<string, string> = {
  none: 'Нет подписки',
  incomplete: 'Оформление',
  trialing: 'Пробный период',
  active: 'Активна',
  past_due: 'Просрочен платёж',
  canceled: 'Отменена',
  unpaid: 'Не оплачена',
}

export const PLAN_TIER_OPTIONS = ['solo', 'pro', 'studio'] as const

export const BILLING_PLAN_OPTIONS = ['credits', 'standard', 'pro'] as const

export function billingPlanLabel(plan: string): string {
  const p = (plan || 'standard').trim().toLowerCase()
  if (p === 'credits') return 'Credits'
  if (p === 'pro' || p === 'byok') return 'Pro'
  if (p === 'standard' || p === 'managed') return 'Standard'
  return p.charAt(0).toUpperCase() + p.slice(1)
}

export function planTierLabel(tier: string | null | undefined): string {
  const t = (tier || 'solo').toLowerCase()
  return t.charAt(0).toUpperCase() + t.slice(1)
}

export const USAGE_KIND_LABELS: Record<string, string> = {
  studio_prompt_refine: 'Студия: генерация',
  studio_image_upscale: 'Студия: апскейл',
  studio_video_upscale: 'Студия: апскейл видео',
  studio_carousel_shot: 'Студия: карусель',
  studio_model_profile_generate: 'Студия: профиль модели',
  yookassa_credits_pack: 'Пополнение баланса',
  yookassa_managed_subscription_bonus: 'Подписка Standard: бонус',
  standard_subscription_bonus: 'Подписка Standard: бонус',
  demo_studio_image: 'Бесплатная генерация',
  referral_signup_bonus: 'Реферал: регистрация',
  referral_referrer_reward: 'Реферал: реферер',
  admin_credit_adjustment: 'Админ: баланс',
}
