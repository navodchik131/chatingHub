export type SeedanceT2vVariant = 'standard' | 'mini'
export type SeedanceT2vResolution = '480p' | '720p' | '1080p'

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
  default_resolution?: SeedanceT2vResolution
  resolutions?: SeedanceT2vResolution[]
  resolution_multipliers_from_720p?: Partial<Record<SeedanceT2vResolution, number>>
  default_variant?: SeedanceT2vVariant
  variants?: Partial<
    Record<
      SeedanceT2vVariant,
      {
        usd_per_sec_720p_with_reference_video?: number
        usd_per_sec_720p_without_reference_video?: number
        credits_per_sec_720p_with_reference_video?: number
        credits_per_sec_720p_without_reference_video?: number
      }
    >
  >
  mini_t2v_path?: string
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
  default_resolution: '720p',
  resolutions: ['480p', '720p', '1080p'],
  resolution_multipliers_from_720p: { '480p': 0.5, '720p': 1, '1080p': 2.5 },
  default_variant: 'standard',
  variants: {
    standard: {
      usd_per_sec_720p_with_reference_video: 0.5,
      usd_per_sec_720p_without_reference_video: 0.25,
    },
    mini: {
      usd_per_sec_720p_with_reference_video: 0.0975,
      usd_per_sec_720p_without_reference_video: 0.15,
    },
  },
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
    variants: {
      ...DEFAULT_MOTION_VIDEO_PRICING.variants,
      ...(fromHealth.variants ?? {}),
    },
    resolution_multipliers_from_720p: {
      ...DEFAULT_MOTION_VIDEO_PRICING.resolution_multipliers_from_720p,
      ...(fromHealth.resolution_multipliers_from_720p ?? {}),
    },
  }
}

function resolutionMultiplier(
  resolution: SeedanceT2vResolution,
  pricing: StudioMotionVideoPricing,
): number {
  const mults = pricing.resolution_multipliers_from_720p ?? DEFAULT_MOTION_VIDEO_PRICING.resolution_multipliers_from_720p
  return mults?.[resolution] ?? 1
}

function usdPerSecAt720p(
  variant: SeedanceT2vVariant,
  hasReferenceVideo: boolean,
  pricing: StudioMotionVideoPricing,
): number {
  const block = pricing.variants?.[variant]
  if (block) {
    const v = hasReferenceVideo
      ? block.usd_per_sec_720p_with_reference_video
      : block.usd_per_sec_720p_without_reference_video
    if (typeof v === 'number' && Number.isFinite(v) && v >= 0) {
      return v
    }
  }
  if (variant === 'mini') {
    return hasReferenceVideo ? 0.0975 : 0.15
  }
  return hasReferenceVideo
    ? pricing.usd_per_sec_with_reference_video
    : pricing.usd_per_sec_without_reference_video
}

export function motionVideoUsdPerSec(
  variant: SeedanceT2vVariant,
  resolution: SeedanceT2vResolution,
  hasReferenceVideo: boolean,
  pricing?: Partial<StudioMotionVideoPricing> | null,
): number {
  const p = mergeMotionVideoPricing(pricing)
  const base = usdPerSecAt720p(variant, hasReferenceVideo, p)
  return Math.max(0, base * resolutionMultiplier(resolution, p))
}

/** Кредиты за ролик (как на бэкенде: ceil(сек × USD/s × курс / 3.6 ₽ за кредит)). */
export function computeMotionVideoCreditCost(
  durationSeconds: number,
  hasReferenceVideo: boolean,
  pricing?: Partial<StudioMotionVideoPricing> | null,
  options?: {
    variant?: SeedanceT2vVariant
    resolution?: SeedanceT2vResolution
  },
): number {
  const p = mergeMotionVideoPricing(pricing)
  const perCredit = p.rub_per_credit
  if (!Number.isFinite(perCredit) || perCredit <= 0) {
    return Math.max(1, Math.round(durationSeconds))
  }
  const sec = Math.max(1, Math.round(durationSeconds))
  const variant = options?.variant ?? p.default_variant ?? 'standard'
  const resolution = options?.resolution ?? p.default_resolution ?? '720p'
  const usd = motionVideoUsdPerSec(variant, resolution, hasReferenceVideo, p)
  if (!Number.isFinite(usd) || usd < 0) {
    return Math.max(1, sec)
  }
  const rub = usd * sec * p.rub_per_usd
  return Math.max(1, Math.ceil(rub / perCredit))
}
