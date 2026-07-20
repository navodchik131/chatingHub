export function fmtCredits(n: number | undefined | null): string {
  return String(Math.max(0, Math.round(Number(n) || 0)));
}

export function fmtMoney(minor: number, currency = 'RUB'): string {
  const rub = (Number(minor) || 0) / 100;
  if (currency.toUpperCase() === 'RUB') {
    return `${rub.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} ₽`;
  }
  return `${rub.toFixed(2)} ${currency}`;
}

/** Сумма в рублях (как в admin API), не в копейках. */
export function fmtRub(amount: number): string {
  const n = Math.max(0, Math.round(Number(amount) || 0));
  if (n >= 1_000_000) {
    const m = n / 1_000_000;
    return `${m >= 10 ? Math.round(m) : m.toFixed(2).replace(/\.?0+$/, '')} млн ₽`;
  }
  return `${n.toLocaleString('ru-RU')} ₽`;
}

export function fmtTime(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function fmtDateShort(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getFullYear()).slice(-2)}`;
}

export function platformLabel(p?: string): string {
  const x = String(p || '').toLowerCase();
  if (x === 'fanvue') return 'FANVUE';
  if (x === 'instagram') return 'INSTAGRAM';
  return 'TELEGRAM';
}

export const STUDIO_MODEL_IMAGE_KINDS = ['face', 'turnaround', 'body', 'genitals', 'other'] as const;

export const PHOTO_TAG_DEFS = [
  { kind: 'face', shortRu: 'Лицо' },
  { kind: 'turnaround', shortRu: 'Развёртка' },
  { kind: 'body', shortRu: 'Тело' },
  { kind: 'genitals', shortRu: 'Интим' },
  { kind: 'other', shortRu: 'Общий' },
];

export function normalizePhotoKind(kind: string): string {
  const k = String(kind || 'other').toLowerCase();
  return STUDIO_MODEL_IMAGE_KINDS.includes(k as (typeof STUDIO_MODEL_IMAGE_KINDS)[number]) ? k : 'other';
}

export function photoTagsRu(): string[] {
  return PHOTO_TAG_DEFS.map((d) => d.shortRu);
}

export function photoTagKindByIndex(index: number): string {
  return PHOTO_TAG_DEFS[index]?.kind ?? 'other';
}

export function photoKindShortLabel(kind: string): string {
  const hit = PHOTO_TAG_DEFS.find((d) => d.kind === normalizePhotoKind(kind));
  return hit?.shortRu ?? kind;
}

export function maskFromOpRights(opRights: Record<string, boolean>): number {
  const bits = { chat: 1, studio: 2, models: 4, keys: 8, billing: 16 };
  let mask = 0;
  for (const [k, bit] of Object.entries(bits)) {
    if (opRights[k]) mask |= bit;
  }
  return mask;
}

export const AI_ENGINE_LABELS: Record<string, string> = {
  'nano-banana-pro': 'Nano Banana Pro',
  'gpt-image-2': 'GPT Image',
  'seedream-v5.0-pro': 'Seedream 5 Pro',
  'wan-2.7-pro': 'Wan 2.7 Pro',
  'wan-2.7': 'Wan 2.7',
};

export const AI_ENGINE_IDS: Record<string, string> = {
  'Nano Banana Pro': 'nano-banana-pro',
  'GPT Image': 'gpt-image-2',
  'Seedream 5 Pro': 'seedream-v5.0-pro',
  'Wan 2.7 Pro': 'wan-2.7-pro',
};

export function engineLabelFromId(id: string): string {
  return AI_ENGINE_LABELS[id] ?? id;
}

export function engineIdFromLabel(label: string): string {
  return AI_ENGINE_IDS[label] ?? 'nano-banana-pro';
}
