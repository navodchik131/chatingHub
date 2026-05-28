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

/** Дефолты = .env.example (если /api/health ещё без studio_motion_video_pricing). */
export const DEFAULT_MOTION_VIDEO_PRICING: StudioMotionVideoPricing = {
  usd_per_sec_with_reference_video: 0.5,
  usd_per_sec_without_reference_video: 0.25,
  rub_per_usd: 80,
  rub_per_credit: 3.6,
  duration_min: 4,
  duration_max: 15,
  duration_default: 5,
}

export function mergeMotionVideoPricing(
  fromHealth?: Partial<StudioMotionVideoPricing> | null,
): StudioMotionVideoPricing {
  if (!fromHealth || typeof fromHealth !== 'object') {
    return { ...DEFAULT_MOTION_VIDEO_PRICING }
  }
  return {
    ...DEFAULT_MOTION_VIDEO_PRICING,
    ...fromHealth,
    usd_per_sec_with_reference_video: Number(
      fromHealth.usd_per_sec_with_reference_video ??
        DEFAULT_MOTION_VIDEO_PRICING.usd_per_sec_with_reference_video,
    ),
    usd_per_sec_without_reference_video: Number(
      fromHealth.usd_per_sec_without_reference_video ??
        DEFAULT_MOTION_VIDEO_PRICING.usd_per_sec_without_reference_video,
    ),
    rub_per_usd: Number(fromHealth.rub_per_usd ?? DEFAULT_MOTION_VIDEO_PRICING.rub_per_usd),
    rub_per_credit: Number(
      fromHealth.rub_per_credit ?? DEFAULT_MOTION_VIDEO_PRICING.rub_per_credit,
    ),
  }
}

/** Кредиты за ролик (как на бэкенде: ceil(сек × USD/s × курс / 3.6 ₽ за кредит)). */
export function computeMotionVideoCreditCost(
  durationSeconds: number,
  hasReferenceVideo: boolean,
  pricing?: Partial<StudioMotionVideoPricing> | null,
): number {
  const p = mergeMotionVideoPricing(pricing)
  const perCredit = p.rub_per_credit
  if (!Number.isFinite(perCredit) || perCredit <= 0) {
    return Math.max(1, Math.round(durationSeconds))
  }
  const sec = Math.max(1, Math.round(durationSeconds))
  const usd = hasReferenceVideo
    ? p.usd_per_sec_with_reference_video
    : p.usd_per_sec_without_reference_video
  if (!Number.isFinite(usd) || usd < 0) {
    return Math.max(1, sec)
  }
  const rub = usd * sec * p.rub_per_usd
  return Math.max(1, Math.ceil(rub / perCredit))
}
