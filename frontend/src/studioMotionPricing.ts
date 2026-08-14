/** 1 credit = $0.01 USD (cent-credits). */
export const CREDITS_PER_USD = 100

export function usdToCredits(usd: number, markupUsd = 0.002): number {
  const total = Math.max(0, Number(usd) + Number(markupUsd))
  if (!Number.isFinite(total) || total <= 0) return 1
  return Math.max(1, Math.ceil(total * CREDITS_PER_USD))
}

export function creditsToUsd(credits: number): number {
  return Math.max(0, Math.round(Number(credits) || 0)) / CREDITS_PER_USD
}
export type SeedanceT2vResolution = '480p' | '720p' | '1080p'
export type GrokImagineI2vResolution = '480p' | '720p'

export type VideoUpscaleResolution = '720p' | '1080p' | '2k' | '4k'

export type VideoUpscalePricing = {
  resolutions: VideoUpscaleResolution[]
  default_resolution: VideoUpscaleResolution
  min_billed_seconds?: number
  usd_per_5s_720p?: number
  usd_per_5s_1080p?: number
  usd_per_5s_2k?: number
  usd_per_5s_4k?: number
  credits_by_resolution?: Partial<Record<VideoUpscaleResolution, number>>
  credits_example_1080p?: number
}

export const DEFAULT_VIDEO_UPSCALE_PRICING: VideoUpscalePricing = {
  resolutions: ['720p', '1080p', '2k', '4k'],
  default_resolution: '1080p',
  min_billed_seconds: 5,
  usd_per_5s_720p: 0.1,
  usd_per_5s_1080p: 0.15,
  usd_per_5s_2k: 0.2,
  usd_per_5s_4k: 0.25,
  credits_by_resolution: { '720p': 3, '1080p': 4, '2k': 5, '4k': 6 },
  credits_example_1080p: 4,
}

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
  video_upscale?: Partial<VideoUpscalePricing>
}

/** Дефолты = WaveSpeed 720p + .env (если /api/health ещё без studio_motion_video_pricing). */
export const DEFAULT_MOTION_VIDEO_PRICING: StudioMotionVideoPricing = {
  usd_per_sec_with_reference_video: 0.13,
  usd_per_sec_without_reference_video: 0.24,
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
      usd_per_sec_720p_with_reference_video: 0.13,
      usd_per_sec_720p_without_reference_video: 0.24,
    },
    mini: {
      usd_per_sec_720p_with_reference_video: 0.0975,
      usd_per_sec_720p_without_reference_video: 0.15,
    },
    seedance_25: {
      usd_per_sec_720p_with_reference_video: 0.22,
      usd_per_sec_720p_without_reference_video: 0.36,
    },
  },
  grok_imagine_i2v: DEFAULT_GROK_IMAGINE_I2V_PRICING,
  video_upscale: DEFAULT_VIDEO_UPSCALE_PRICING,
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
    video_upscale: {
      ...DEFAULT_VIDEO_UPSCALE_PRICING,
      ...(fromHealth.video_upscale ?? {}),
      credits_by_resolution: {
        ...DEFAULT_VIDEO_UPSCALE_PRICING.credits_by_resolution,
        ...(fromHealth.video_upscale?.credits_by_resolution ?? {}),
      },
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
  if (variant === 'seedance_25') {
    return hasReferenceVideo ? 0.22 : 0.36
  }
  return hasReferenceVideo
    ? pricing.usd_per_sec_with_reference_video
    : pricing.usd_per_sec_without_reference_video
}

function clampReferenceVideoSeconds(raw: number, outputDuration: number): number {
  const out = Math.max(1, Math.round(outputDuration))
  const ref = Math.ceil(raw)
  return Math.max(2, Math.min(30, Math.min(ref, out)))
}

function motionVideoBilledSeconds(
  outputDuration: number,
  hasReferenceVideo: boolean,
  referenceVideoDuration?: number | null,
): number {
  const out = Math.max(1, Math.round(outputDuration))
  if (!hasReferenceVideo) return out
  if (referenceVideoDuration == null || !Number.isFinite(referenceVideoDuration)) {
    return out
  }
  const ref = clampReferenceVideoSeconds(referenceVideoDuration, out)
  return ref + out
}

/** Полная стоимость ролика в USD (WaveSpeed: с ref — billed ref+output). */
export function computeMotionVideoUsdCost(
  durationSeconds: number,
  hasReferenceVideo: boolean,
  pricing?: Partial<StudioMotionVideoPricing> | null,
  options?: {
    variant?: SeedanceT2vVariant
    resolution?: SeedanceT2vResolution
    referenceVideoDuration?: number | null
  },
): number {
  const p = mergeMotionVideoPricing(pricing)
  const out = Math.max(p.duration_min, Math.min(p.duration_max, Math.round(durationSeconds)))
  const variant = options?.variant ?? p.default_variant ?? 'standard'
  const resolution = options?.resolution ?? p.default_resolution ?? '720p'
  const rate = motionVideoUsdPerSec(variant, resolution, hasReferenceVideo, p)
  if (hasReferenceVideo) {
    const billed = motionVideoBilledSeconds(out, true, options?.referenceVideoDuration)
    return Math.max(0, rate * billed)
  }
  return Math.max(0, rate * out)
}

export function formatMotionUsd(usd: number): string {
  if (!Number.isFinite(usd) || usd <= 0) return '$0.00'
  if (usd < 0.01) return `$${usd.toFixed(3)}`
  return `$${usd.toFixed(2)}`
}

/** USD-эквивалент cent-credits. */
export function computeUsdFromCredits(credits: number): number {
  return creditsToUsd(credits)
}

/** «130 кр. ($1.30)». */
export function formatMotionCreditCost(
  credits: number,
  _pricing?: Partial<StudioMotionVideoPricing> | null,
  creditsSuffix = 'cr.',
): string {
  const usd = creditsToUsd(credits)
  return `${credits} ${creditsSuffix} (${formatMotionUsd(usd)})`
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

/** Кредиты за ролик: ceil(USD × 100). */
export function computeMotionVideoCreditCost(
  durationSeconds: number,
  hasReferenceVideo: boolean,
  pricing?: Partial<StudioMotionVideoPricing> | null,
  options?: {
    variant?: SeedanceT2vVariant
    resolution?: SeedanceT2vResolution
    referenceVideoDuration?: number | null
  },
): number {
  const usd = computeMotionVideoUsdCost(durationSeconds, hasReferenceVideo, pricing, options)
  return usdToCredits(usd, 0)
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

/** USD за Grok Imagine Video v1.5 I2V. */
export function computeGrokImagineI2vUsdCost(
  durationSeconds: number,
  pricing?: Partial<StudioMotionVideoPricing> | null,
  options?: { resolution?: GrokImagineI2vResolution },
): number {
  const p = mergeMotionVideoPricing(pricing)
  const grok = mergeGrokImagineI2vPricing(p)
  const sec = Math.max(
    grok.duration_min,
    Math.min(grok.duration_max, Math.round(durationSeconds)),
  )
  const resolution = options?.resolution ?? grok.default_resolution ?? '720p'
  const rate =
    resolution === '480p' ? grok.usd_per_sec_480p : grok.usd_per_sec_720p
  return Math.max(0, rate * sec + grok.usd_per_image)
}

export function computeGrokImagineI2vCreditCost(
  durationSeconds: number,
  pricing?: Partial<StudioMotionVideoPricing> | null,
  options?: { resolution?: GrokImagineI2vResolution },
): number {
  const usd = computeGrokImagineI2vUsdCost(durationSeconds, pricing, options)
  return usdToCredits(usd, 0)
}

export type StudioEvolinkVideoPricing = StudioMotionVideoPricing & {
  backend?: string
  duration_max_20?: number
  duration_max_25?: number
  always_charges_credits?: boolean
  nsfw_supported?: boolean
  resolutions_by_variant?: Partial<Record<SeedanceT2vVariant, SeedanceT2vResolution[]>>
}

export const DEFAULT_EVOLINK_VIDEO_PRICING: StudioEvolinkVideoPricing = {
  ...DEFAULT_MOTION_VIDEO_PRICING,
  usd_per_sec_with_reference_video: 0.121,
  usd_per_sec_without_reference_video: 0.199,
  duration_max_20: 15,
  duration_max_25: 30,
  always_charges_credits: true,
  nsfw_supported: false,
  variants: {
    standard: {
      usd_per_sec_720p_output: 0.199,
      usd_per_sec_720p_video_reference: 0.121,
      usd_per_sec_480p_output: 0.092,
      usd_per_sec_480p_video_reference: 0.056,
      usd_per_sec_720p_with_reference_video: 0.121,
      usd_per_sec_720p_without_reference_video: 0.199,
    },
    seedance_25: {
      usd_per_sec_720p_output: 0.293,
      usd_per_sec_720p_video_reference: 0.179,
      usd_per_sec_480p_output: 0.136,
      usd_per_sec_480p_video_reference: 0.083,
      usd_per_sec_720p_with_reference_video: 0.179,
      usd_per_sec_720p_without_reference_video: 0.293,
    },
  },
  resolutions_by_variant: {
    standard: ['480p', '720p'],
    seedance_25: ['480p', '720p'],
  },
}

export function mergeEvolinkVideoPricing(
  fromHealth?: Partial<StudioEvolinkVideoPricing> | null,
): StudioEvolinkVideoPricing {
  const base = mergeMotionVideoPricing(fromHealth)
  return {
    ...DEFAULT_EVOLINK_VIDEO_PRICING,
    ...base,
    ...fromHealth,
    duration_max_20: Number(fromHealth?.duration_max_20 ?? DEFAULT_EVOLINK_VIDEO_PRICING.duration_max_20),
    duration_max_25: Number(fromHealth?.duration_max_25 ?? DEFAULT_EVOLINK_VIDEO_PRICING.duration_max_25),
    variants: {
      ...DEFAULT_EVOLINK_VIDEO_PRICING.variants,
      ...(fromHealth?.variants ?? {}),
      ...(base.variants ?? {}),
    },
    resolutions_by_variant: {
      ...DEFAULT_EVOLINK_VIDEO_PRICING.resolutions_by_variant,
      ...(fromHealth?.resolutions_by_variant ?? {}),
    },
  }
}

export function evolinkDurationMax(
  variant: SeedanceT2vVariant,
  pricing?: Partial<StudioEvolinkVideoPricing> | null,
): number {
  const p = mergeEvolinkVideoPricing(pricing)
  return variant === 'seedance_25' ? (p.duration_max_25 ?? 30) : (p.duration_max_20 ?? 15)
}

function evolinkUsdPerSec(
  variant: SeedanceT2vVariant,
  resolution: SeedanceT2vResolution,
  hasReferenceVideo: boolean,
  pricing: StudioEvolinkVideoPricing,
): number {
  const block = pricing.variants?.[variant] as Record<string, number | undefined> | undefined
  const resKey = resolution === '480p' ? '480p' : '720p'
  const kind = hasReferenceVideo ? 'video_reference' : 'output'
  const primary = block?.[`usd_per_sec_${resKey}_${kind}`]
  if (typeof primary === 'number' && Number.isFinite(primary) && primary >= 0) {
    return primary
  }
  const legacy720 = hasReferenceVideo
    ? block?.usd_per_sec_720p_with_reference_video
    : block?.usd_per_sec_720p_without_reference_video
  if (typeof legacy720 === 'number' && Number.isFinite(legacy720) && legacy720 >= 0) {
    return legacy720
  }
  return hasReferenceVideo
    ? (pricing.usd_per_sec_with_reference_video ?? 0.121)
    : (pricing.usd_per_sec_without_reference_video ?? 0.199)
}

export function computeEvolinkVideoUsdCost(
  durationSeconds: number,
  hasReferenceVideo: boolean,
  pricing?: Partial<StudioEvolinkVideoPricing> | null,
  options?: {
    variant?: SeedanceT2vVariant
    resolution?: SeedanceT2vResolution
    referenceVideoDuration?: number | null
  },
): number {
  const p = mergeEvolinkVideoPricing(pricing)
  const variant = options?.variant ?? p.default_variant ?? 'standard'
  const maxDur = evolinkDurationMax(variant, p)
  const out = Math.max(p.duration_min, Math.min(maxDur, Math.round(durationSeconds)))
  const resolution = options?.resolution ?? p.default_resolution ?? '720p'
  const rate = evolinkUsdPerSec(variant, resolution, hasReferenceVideo, p)
  if (hasReferenceVideo) {
    const billed = motionVideoBilledSeconds(out, true, options?.referenceVideoDuration)
    return Math.max(0, rate * billed)
  }
  return Math.max(0, rate * out)
}

export function computeEvolinkVideoCreditCost(
  durationSeconds: number,
  hasReferenceVideo: boolean,
  pricing?: Partial<StudioEvolinkVideoPricing> | null,
  options?: {
    variant?: SeedanceT2vVariant
    resolution?: SeedanceT2vResolution
    referenceVideoDuration?: number | null
  },
): number {
  const usd = computeEvolinkVideoUsdCost(durationSeconds, hasReferenceVideo, pricing, options)
  return usdToCredits(usd, 0)
}

/** Кредиты за Video Upscaler Pro (мин. 5 с биллинга WaveSpeed). */
export function computeVideoUpscaleCreditCost(
  targetResolution: VideoUpscaleResolution | string,
  pricing?: Partial<StudioMotionVideoPricing> | null,
): number {
  const p = mergeMotionVideoPricing(pricing)
  const up = { ...DEFAULT_VIDEO_UPSCALE_PRICING, ...(p.video_upscale ?? {}) }
  const res = (targetResolution || up.default_resolution || '1080p').toLowerCase() as VideoUpscaleResolution
  const fromMap = up.credits_by_resolution?.[res]
  if (typeof fromMap === 'number' && fromMap > 0) {
    return fromMap
  }
  const usdMap: Record<VideoUpscaleResolution, number> = {
    '720p': up.usd_per_5s_720p ?? 0.1,
    '1080p': up.usd_per_5s_1080p ?? 0.15,
    '2k': up.usd_per_5s_2k ?? 0.2,
    '4k': up.usd_per_5s_4k ?? 0.25,
  }
  const usd = usdMap[res in usdMap ? res : '1080p']
  return usdToCredits(usd, 0)
}
