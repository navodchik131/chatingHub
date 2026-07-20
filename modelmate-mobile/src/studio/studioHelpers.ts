const AI_MODEL_MAP: Record<string, string> = {
  nano: 'nano-banana-pro',
  gpt: 'gpt-image-2',
  seedream: 'seedream-v5.0-pro',
  wan: 'wan-2.7-pro',
  'Nano Banana Pro': 'nano-banana-pro',
  'GPT Image': 'gpt-image-2',
  'Seedream 5 Pro': 'seedream-v5.0-pro',
  'Wan 2.7 Pro': 'wan-2.7-pro',
};

export function isNsfwMode(s: { contentMode?: string; nsfw?: boolean }) {
  return s?.contentMode === 'nsfw' || !!s?.nsfw;
}

export function waveModelFromState(s: { aiModel?: string; aiEngine?: string; contentMode?: string }) {
  const key = s?.aiEngine || s?.aiModel;
  const mapped = key ? AI_MODEL_MAP[key] : undefined;
  if (mapped) return mapped;
  return isNsfwMode(s) ? 'wan-2.7-pro' : 'nano-banana-pro';
}

export function normalizeWaveModel(id: string, nsfw: boolean) {
  const x = String(id || '').trim().toLowerCase();
  const mapped = AI_MODEL_MAP[x] || x;
  if (mapped === 'wan-2.7-pro') return { apiId: 'wan-2.7', tier: 'pro' };
  if (mapped === 'wan-2.7') return { apiId: 'wan-2.7', tier: 'standard' };
  if (['nano-banana-pro', 'gpt-image-2', 'seedream-v5.0-pro'].includes(mapped)) {
    return { apiId: mapped, tier: 'standard' };
  }
  return { apiId: nsfw ? 'wan-2.7' : 'nano-banana-pro', tier: 'standard' };
}

export function normalizeStudioModelId(id: unknown): number | null {
  if (id == null || id === '') return null;
  const n = Number(id);
  return Number.isFinite(n) ? n : null;
}

export function modelIdByName(models: { id: number; name: string }[], name: string): number | null {
  const hit = models.find((m) => m.name === name);
  return hit?.id ?? null;
}
