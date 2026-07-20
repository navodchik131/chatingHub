import type { ContentMode } from '@/src/navigation/types';
import type { HealthOut, UserMeOut } from '@/src/api/types';
import { isNsfwMode, normalizeWaveModel, waveModelFromState } from '@/src/studio/studioHelpers';
import { isProPlan } from '@/src/studio/planCatalog';
import {
  formatStudioImageCostLabel,
  quoteStudioImageCredits,
  studioGenerationUsesDemo,
  type GrokPipelineKind,
} from '@/src/studio/studioImagePricing';
import { computeMotionVideoCreditCost } from '@/src/studio/studioMotionPricing';

/** Как на бэкенде: 720/1080/4k → Seedance resolution. */
export function vidQualityToResolution(vidQuality: string): '480p' | '720p' | '1080p' {
  const v = String(vidQuality || '1080').toLowerCase();
  if (v === '1080' || v === '1080p' || v === '4k') return '1080p';
  if (v === '480' || v === '480p') return '480p';
  return '720p';
}

function mobileModeToStudioMode(modeId: string): string {
  if (modeId === 'loc') return 'location';
  if (modeId === 'ref') return 'model_scene';
  if (modeId === 'prompt') return 'model_scene';
  return modeId;
}

function grokPipelineForMobileMode(modeId: string): GrokPipelineKind {
  if (modeId === 'carousel') return 'light';
  return 'workflow';
}

export function formatGenerationCostLabel(
  credits: number | null,
  opts?: { isProPlan?: boolean; useDemo?: boolean; perFrame?: boolean },
): string {
  if (opts?.isProPlan) return 'Pro';
  if (opts?.useDemo) return '−0 кр.';
  if (credits == null) return '—';
  if (opts?.perFrame) return `−${credits} кр/кадр`;
  return `−${credits} кр.`;
}

export function computeImageGenerationCost(params: {
  modeId: string;
  contentMode: ContentMode;
  aiEngine: string;
  carouselCount?: number;
  health?: HealthOut | null;
  me?: UserMeOut | null;
}): string {
  const pro = isProPlan(params.me?.billing_plan);
  if (pro) return 'Pro';

  if (params.modeId === 'carousel') {
    const perFrame = Number(params.health?.studio_carousel_credit_cost);
    const per = Number.isFinite(perFrame) && perFrame >= 0 ? perFrame : 2;
    const frames = Math.max(2, Math.min(8, Number(params.carouselCount) || 3));
    return formatGenerationCostLabel(per * frames);
  }

  const nsfw = isNsfwMode({ contentMode: params.contentMode });
  const wave = normalizeWaveModel(waveModelFromState({ aiEngine: params.aiEngine, contentMode: params.contentMode }), nsfw);
  const waveProfile = params.contentMode === 'sfw' ? 'regular' : 'nsfw';
  const studioMode = mobileModeToStudioMode(params.modeId);

  const credits = quoteStudioImageCredits({
    waveModelId: wave.apiId,
    waveProfile,
    wanEditTier: wave.tier,
    grokPipeline: grokPipelineForMobileMode(params.modeId),
    studioMode,
    workflow: params.modeId !== 'carousel',
  });

  const useDemo = studioGenerationUsesDemo({
    billingPlan: params.me?.billing_plan,
    demoRemaining: params.me?.demo_generations_remaining ?? 0,
    creditsBalance: params.me?.credits_balance ?? 0,
    waveProfile,
    waveModelId: wave.apiId,
    wanEditTier: wave.tier,
    studioMode,
    workflow: params.modeId !== 'carousel',
  });

  const label = formatStudioImageCostLabel(credits, {
    isProPlan: pro,
    demoRemaining: params.me?.demo_generations_remaining,
    useDemo,
  });
  if (label === 'Pro') return 'Pro';
  if (label === '0') return '−0 кр.';
  return formatGenerationCostLabel(Number(label));
}

export function computeCarouselModeCardCost(health?: HealthOut | null, me?: UserMeOut | null): string {
  if (isProPlan(me?.billing_plan)) return 'Pro';
  const perFrame = Number(health?.studio_carousel_credit_cost);
  const per = Number.isFinite(perFrame) && perFrame >= 0 ? perFrame : 2;
  return formatGenerationCostLabel(per, { perFrame: true });
}

export function computeVideoGenerationCost(params: {
  duration: number;
  quality: string;
  hasReferenceVideo: boolean;
  health?: HealthOut | null;
  me?: UserMeOut | null;
}): string {
  if (isProPlan(params.me?.billing_plan)) return 'Pro';
  const credits = computeMotionVideoCreditCost(
    params.duration,
    params.hasReferenceVideo,
    params.health?.studio_motion_video_pricing,
    {
      variant: 'standard',
      resolution: vidQualityToResolution(params.quality),
    },
  );
  return formatGenerationCostLabel(credits);
}
