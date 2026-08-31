/**
 * Стоимость Seedance Director — Grok compose + генерация по провайдеру.
 */

import {
  computeEvolinkVideoCreditCost,
  computeMotionVideoCreditCost,
  mergeEvolinkVideoPricing,
  mergeMotionVideoPricing,
  type SeedanceT2vResolution,
  type SeedanceT2vVariant,
  type StudioEvolinkVideoPricing,
  type StudioMotionVideoPricing,
} from './studioMotionPricing';

export type SeedanceDirectorPricing = {
  compose_usd_base?: number;
  compose_usd_per_extra_image?: number;
  compose_credits_sample_3_images?: number;
  /** WS Fast T2V output-only @720p (prompt + фото, без ref-video). */
  fast_t2v_output_usd_per_sec_720p?: number;
  piece_credits_sample_20_10s_wavespeed?: number;
};

/** Кредиты за сборку промптов Grok (vision + инструкция). */
export function computeDirectorComposeCreditCost(
  imageCount: number,
  pricing?: SeedanceDirectorPricing | null,
): number {
  const n = Math.max(1, Number(imageCount) || 1);
  if (pricing?.compose_credits_sample_3_images && n === 3) {
    return Math.max(1, Math.round(pricing.compose_credits_sample_3_images));
  }
  const base = Number(pricing?.compose_usd_base ?? 0.03);
  const extra = Number(pricing?.compose_usd_per_extra_image ?? 0.01);
  const usd = base + extra * Math.max(0, n - 1);
  const cpt = 100; // 1 credit = $0.01
  return Math.max(1, Math.round(usd * cpt));
}

/** Кредиты за один кусок видео (2.0 или 2.5). */
export function computeDirectorPieceCreditCost(
  durationSeconds: number,
  version: '2.0' | '2.5',
  options: {
    backend: 'wavespeed' | 'evolink';
    resolution?: SeedanceT2vResolution;
    motionPricing?: Partial<StudioMotionVideoPricing> | null;
    evolinkPricing?: Partial<StudioEvolinkVideoPricing> | null;
    directorPricing?: SeedanceDirectorPricing | null;
  },
): number {
  const dur = Math.max(1, Math.round(Number(durationSeconds) || 1));
  const variant: SeedanceT2vVariant = version === '2.5' ? 'seedance_25' : 'standard';
  const resolution = options.resolution ?? '720p';
  const backend = options.backend ?? 'wavespeed';

  if (backend === 'evolink') {
    return computeEvolinkVideoCreditCost(dur, false, mergeEvolinkVideoPricing(options.evolinkPricing), {
      variant,
      resolution,
    });
  }

  // Fast T2V + reference_images (без ref-video): output-only, не motion ref $0.13/с.
  const fast720 = Number(options.directorPricing?.fast_t2v_output_usd_per_sec_720p ?? 0.2);
  const mult =
    resolution === '480p'
      ? 0.5
      : resolution === '1080p'
        ? 2.5
        : 1;
  const usdPerSec = fast720 * mult;
  const cpt = 100;
  return Math.max(1, Math.round(usdPerSec * dur * cpt));
}

/** Оценка «compose + все куски» для шапки. */
export function estimateDirectorTotalCredits(
  durationSeconds: number,
  imageCount: number,
  pieceCount: number,
  options: {
    backend: 'wavespeed' | 'evolink';
    resolution?: SeedanceT2vResolution;
    directorPricing?: SeedanceDirectorPricing | null;
    motionPricing?: Partial<StudioMotionVideoPricing> | null;
    evolinkPricing?: Partial<StudioEvolinkVideoPricing> | null;
  },
): number {
  const compose = computeDirectorComposeCreditCost(imageCount, options.directorPricing);
  const pieces = Math.max(0, Number(pieceCount) || 0);
  if (!pieces) {
    const p20 = computeDirectorPieceCreditCost(durationSeconds, '2.0', options);
    const p25 = computeDirectorPieceCreditCost(Math.min(30, durationSeconds), '2.5', options);
    return compose + p20 + p25;
  }
  const perPiece = computeDirectorPieceCreditCost(durationSeconds, '2.0', options);
  return compose + perPiece * pieces;
}

export function formatDirectorCreditLabel(credits: number, lang: 'ru' | 'en'): string {
  const n = Math.max(0, Math.round(Number(credits) || 0));
  return lang === 'ru' ? `${n} кр.` : `${n} cr.`;
}
