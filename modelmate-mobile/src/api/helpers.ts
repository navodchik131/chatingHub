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

function sameLocalDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear()
    && a.getMonth() === b.getMonth()
    && a.getDate() === b.getDate();
}

export function fmtThreadDayKey(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

export function fmtThreadDayLabel(iso?: string, lang: 'ru' | 'en' = 'ru'): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (sameLocalDay(d, today)) return lang === 'ru' ? 'Сегодня' : 'Today';
  if (sameLocalDay(d, yesterday)) return lang === 'ru' ? 'Вчера' : 'Yesterday';
  return fmtDateShort(iso);
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

const OP_BITS = { chat: 1, studio: 2, models: 4, keys: 8, billing: 16 } as const;

export function maskFromOpRights(opRights: Record<string, boolean>): number {
  let mask = 0;
  for (const [k, bit] of Object.entries(OP_BITS)) {
    if (opRights[k]) mask |= bit;
  }
  return mask;
}

export function rightsFromMask(mask: number): Record<string, boolean> {
  const m = Number(mask) || 0;
  return {
    chat: (m & OP_BITS.chat) === OP_BITS.chat,
    studio: (m & OP_BITS.studio) === OP_BITS.studio,
    models: (m & OP_BITS.models) === OP_BITS.models,
    keys: (m & OP_BITS.keys) === OP_BITS.keys,
    billing: (m & OP_BITS.billing) === OP_BITS.billing,
  };
}

export type CompanionPersonaFields = {
  age?: string | null;
  city?: string | null;
  personality?: string | null;
  speaking_style?: string | null;
};

export function parseCompanionPersona(raw: unknown): CompanionPersonaFields {
  if (!raw) return {};
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as CompanionPersonaFields;
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
    }
  }
  if (typeof raw === 'object') return raw as CompanionPersonaFields;
  return {};
}

export function charFieldsFromModel(model: {
  profile_text?: string;
  companion_persona?: unknown;
  camera_preset_id?: string | number | null;
  export_lat?: number | null;
  export_lon?: number | null;
}): Record<string, string> {
  const p = parseCompanionPersona(model.companion_persona);
  const ageCity = [p.age, p.city].filter(Boolean).join(', ');
  const geo =
    model.export_lat != null && model.export_lon != null
      ? `${model.export_lat}, ${model.export_lon}`
      : '';
  return {
    appearance: model.profile_text || '',
    ageCity,
    character: p.personality || '',
    chatStyle: p.speaking_style || '',
    camera: model.camera_preset_id != null ? String(model.camera_preset_id) : '',
    geo,
  };
}

function pickCurrencyAmount(map: Record<string, number> | undefined, preferred = 'RUB'): number | undefined {
  if (!map) return undefined;
  const pref = preferred.toUpperCase();
  if (map[pref] != null) return map[pref];
  if (map[pref.toLowerCase()] != null) return map[pref.toLowerCase()];
  const keys = Object.keys(map);
  return keys.length ? map[keys[0]] : undefined;
}

function donationAvailableAtUtc(occurredAt: Date): Date {
  const y = occurredAt.getUTCFullYear();
  const m = occurredAt.getUTCMonth();
  const d = occurredAt.getUTCDate();
  if (d <= 15) return new Date(Date.UTC(y, m, 16));
  return new Date(Date.UTC(y, m + 1, 1));
}

function isDonationAvailableForPayout(occurredAt: Date, now = new Date()): boolean {
  if (Number.isNaN(occurredAt.getTime())) return false;
  return now.getTime() >= donationAvailableAtUtc(occurredAt).getTime();
}

export function summarizeDonationPayouts(
  events: { amount_minor?: number; currency?: string; payout_status?: string; occurred_at?: string }[],
  now = new Date(),
) {
  const totalByCurrency: Record<string, number> = {};
  const availableByCurrency: Record<string, number> = {};
  const heldByCurrency: Record<string, number> = {};
  const paidByCurrency: Record<string, number> = {};
  for (const ev of events || []) {
    if (!ev || Number(ev.amount_minor) <= 0) continue;
    const cur = String(ev.currency || 'RUB').toUpperCase();
    totalByCurrency[cur] = (totalByCurrency[cur] ?? 0) + Number(ev.amount_minor);
    if (ev.payout_status === 'paid') {
      paidByCurrency[cur] = (paidByCurrency[cur] ?? 0) + Number(ev.amount_minor);
      continue;
    }
    if (ev.payout_status === 'in_request') continue;
    const at = new Date(ev.occurred_at || '');
    if (isDonationAvailableForPayout(at, now)) {
      availableByCurrency[cur] = (availableByCurrency[cur] ?? 0) + Number(ev.amount_minor);
    } else {
      heldByCurrency[cur] = (heldByCurrency[cur] ?? 0) + Number(ev.amount_minor);
    }
  }
  return { totalByCurrency, availableByCurrency, heldByCurrency, paidByCurrency };
}

export function resolveDonationBalances(
  overview: { totals_by_currency?: Record<string, number> } | null | undefined,
  events: { amount_minor?: number; currency?: string; payout_status?: string; occurred_at?: string }[],
  preferredCurrency = 'RUB',
) {
  const payoutSummary = summarizeDonationPayouts(events);
  const currency = (
    pickCurrencyAmount(overview?.totals_by_currency, preferredCurrency) != null
      ? preferredCurrency
      : Object.keys(overview?.totals_by_currency || {})[0]
        || Object.keys(payoutSummary.totalByCurrency)[0]
        || preferredCurrency
  ).toUpperCase();
  const total =
    pickCurrencyAmount(payoutSummary.totalByCurrency, currency)
    ?? pickCurrencyAmount(overview?.totals_by_currency, currency)
    ?? 0;
  const available = pickCurrencyAmount(payoutSummary.availableByCurrency, currency) ?? 0;
  const held = pickCurrencyAmount(payoutSummary.heldByCurrency, currency) ?? 0;
  const paid = pickCurrencyAmount(payoutSummary.paidByCurrency, currency) ?? 0;
  return { currency, total, available, held, paid };
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
