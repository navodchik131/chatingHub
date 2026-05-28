export type StudioMotionVideoPricing = {
  usd_per_sec_with_reference_video: number
  usd_per_sec_without_reference_video: number
  rub_per_usd: number
  rub_per_credit: number
  duration_min: number
  duration_max: number
  duration_default: number
  credits_per_sec_with_reference_video?: number
  credits_per_sec_without_reference_video?: number
}

/** Кредиты за ролик (как на бэкенде: ceil(сек × USD/s × курс / 3.6 ₽ за кредит)). */
export function computeMotionVideoCreditCost(
  durationSeconds: number,
  hasReferenceVideo: boolean,
  pricing: StudioMotionVideoPricing | undefined,
): number | null {
  if (!pricing) return null
  const perCredit = pricing.rub_per_credit
  if (!Number.isFinite(perCredit) || perCredit <= 0) return null
  const sec = Math.max(1, Math.round(durationSeconds))
  const usd = hasReferenceVideo
    ? pricing.usd_per_sec_with_reference_video
    : pricing.usd_per_sec_without_reference_video
  if (!Number.isFinite(usd) || usd < 0) return null
  const rub = usd * sec * pricing.rub_per_usd
  return Math.max(1, Math.ceil(rub / perCredit))
}
