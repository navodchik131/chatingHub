export type SeedanceT2vVariant = 'standard' | 'mini'
export type SeedanceT2vResolution = '480p' | '720p' | '1080p'
export type GrokImagineI2vResolution = '480p' | '720p'

export type GrokImagineI2vPricing = {
  usd_per_sec_480p: number
  usd_per_sec_720p: number
  usd_per_image: number
  duration_min: number
  duration_max: number
  duration_default: number
  resolutions: GrokImagineI2vResolution[]
  default_resolution?: GrokImagineI2vResolution
  credits_example_6s_720p?: number
}

export const DEFAULT_GROK_IMAGINE_I2V_PRICING: GrokImagineI2vPricing = {
  usd_per_sec_480p: 0.08,
  usd_per_sec_720p: 0.14,
  usd_per_image: 0.01,
  duration_min: 1,
  duration_max: 15,
  duration_default: 6,
  resolutions: ['480p', '720p'],
  default_resolution: '720p',
}

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
  grok_imagine_i2v?: Partial<GrokImagineI2vPricing>
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
  grok_imagine_i2v: DEFAULT_GROK_IMAGINE_I2V_PRICING,
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
    grok_imagine_i2v: {
      ...DEFAULT_MOTION_VIDEO_PRICING.grok_imagine_i2v,
      ...(fromHealth.grok_imagine_i2v ?? {}),
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

function mergeGrokImagineI2vPricing(
  pricing?: Partial<StudioMotionVideoPricing> | null,
): GrokImagineI2vPricing {
  const p = mergeMotionVideoPricing(pricing)
  const from = p.grok_imagine_i2v ?? {}
  const base = DEFAULT_GROK_IMAGINE_I2V_PRICING
  return {
    usd_per_sec_480p: Number(from.usd_per_sec_480p ?? base.usd_per_sec_480p),
    usd_per_sec_720p: Number(from.usd_per_sec_720p ?? base.usd_per_sec_720p),
    usd_per_image: Number(from.usd_per_image ?? base.usd_per_image),
    duration_min: Number(from.duration_min ?? base.duration_min),
    duration_max: Number(from.duration_max ?? base.duration_max),
    duration_default: Number(from.duration_default ?? base.duration_default),
    resolutions: from.resolutions ?? base.resolutions,
    default_resolution: from.default_resolution ?? base.default_resolution,
    credits_example_6s_720p: from.credits_example_6s_720p ?? base.credits_example_6s_720p,
  }
}

/** Кредиты за Grok Imagine Video v1.5 I2V (USD/с × длительность + фикс. за кадр). */
export function computeGrokImagineI2vCreditCost(
  durationSeconds: number,
  pricing?: Partial<StudioMotionVideoPricing> | null,
  options?: { resolution?: GrokImagineI2vResolution },
): number {
  const p = mergeMotionVideoPricing(pricing)
  const grok = mergeGrokImagineI2vPricing(p)
  const perCredit = p.rub_per_credit
  const sec = Math.max(
    grok.duration_min,
    Math.min(grok.duration_max, Math.round(durationSeconds)),
  )
  const resolution = options?.resolution ?? grok.default_resolution ?? '720p'
  const rate =
    resolution === '480p' ? grok.usd_per_sec_480p : grok.usd_per_sec_720p
  const usd = Math.max(0, rate * sec + grok.usd_per_image)
  if (!Number.isFinite(perCredit) || perCredit <= 0) {
    return Math.max(1, sec)
  }
  const rub = usd * p.rub_per_usd
  return Math.max(1, Math.ceil(rub / perCredit))
}
