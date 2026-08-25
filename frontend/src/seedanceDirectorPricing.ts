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

  // WaveSpeed T2V с reference_images — тариф with ref.
  return computeMotionVideoCreditCost(dur, true, mergeMotionVideoPricing(options.motionPricing), {
    variant,
    resolution,
  });
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
