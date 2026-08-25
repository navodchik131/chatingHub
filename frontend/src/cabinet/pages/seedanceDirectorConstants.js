/** Константы Seedance Director — роли, типы съёмки, подсказки брифа. */

export const CAMERA_MODES = [
  {
    id: 'A',
    ru: 'Селфи — телефон в руке',
    en: 'Selfie — phone in hand',
    descRu: 'вытянутая рука, кадр дышит, взгляд в объектив',
    descEn: 'arm\'s length, natural sway, eye contact',
  },
  {
    id: 'B',
    ru: 'Снимает друг сбоку',
    en: 'Friend filming from side',
    descRu: 'лёгкий увод камеры, естественная дистанция',
    descEn: 'handheld beside her, small reframes',
  },
  {
    id: 'C',
    ru: 'Телефон стоит, никто не держит',
    en: 'Phone propped, untouched',
    descRu: 'кадр зафиксирован, модель входит в него сама',
    descEn: 'locked frame, she moves into shot',
  },
  {
    id: 'D',
    ru: 'Оператор идёт рядом',
    en: 'Operator walking alongside',
    descRu: 'ходовая съёмка, шаги слышны в звуке',
    descEn: 'walking take, footsteps in audio',
  },
  {
    id: 'E',
    ru: 'Зеркало — телефон в кадре',
    en: 'Mirror — phone visible',
    descRu: 'отражение, телефон виден в руке',
    descEn: 'reflection, phone visible in frame',
  },
];

export const ROLE_SUGGESTIONS = [
  'first frame',
  'face',
  'body',
  'character',
  'location',
  'wardrobe',
  'pose',
  'outfit',
];

export const PICKER_FILTERS = ['all', 'first frame', 'face', 'body', 'outfit', 'location'];

export const BRIEF_HINTS = [
  { key: 'shot', ru: 'как снято', en: 'how filmed', ruText: ' Снято на телефон, кадр стоит.', enText: ' Shot on phone, static frame.' },
  { key: 'light', ru: 'свет', en: 'light', ruText: ' Вечерний свет из окна, тёплый.', enText: ' Warm evening window light.' },
  { key: 'end', ru: 'финал кадра', en: 'ending', ruText: ' В конце смотрит чуть мимо камеры.', enText: ' At the end she looks slightly off-camera.' },
];

export const GROK_WRITE_STEPS = [
  { ru: 'Читаю бриф и роли фото', en: 'Reading brief and photo roles' },
  { ru: 'Раскладываю сцену на кадры', en: 'Breaking scene into beats' },
  { ru: 'Пишу камеру, движение, звук', en: 'Writing camera, motion, audio' },
  { ru: 'Делю по лимитам 2.0 / 2.5', en: 'Splitting for 2.0 / 2.5 limits' },
];

export function uid() {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function roleFromKind(kind) {
  const k = String(kind || '').toLowerCase();
  if (k === 'face') return 'face';
  if (k === 'body' || k === 'turnaround') return 'body';
  if (k === 'other') return 'character';
  return k || 'character';
}

export function cycleRole(current) {
  const cur = (current || '').trim() || ROLE_SUGGESTIONS[0];
  const idx = ROLE_SUGGESTIONS.indexOf(cur);
  const next = idx < 0 ? 0 : (idx + 1) % ROLE_SUGGESTIONS.length;
  return ROLE_SUGGESTIONS[next];
}

export function parseAssumedTags(raw) {
  const text = String(raw || '').trim();
  if (!text) return [];
  return text.split(/[·•,;]+/).map((s) => s.trim()).filter(Boolean);
}

export function estimateCredits(durationSeconds) {
  const d = Math.max(1, Number(durationSeconds) || 15);
  return Math.round(d * 7 * 2);
}

export function splitNote(durationSeconds, lang) {
  const d = Math.max(1, Number(durationSeconds) || 15);
  const chunks20 = Math.ceil(d / 15);
  const chunks25 = Math.ceil(d / 30);
  if (d > 15) {
    return lang === 'ru'
      ? `${d} c больше лимита 2.0 (15 c) — промпт разобьётся на ${chunks20} куска, 2.5 уложится в ${chunks25}.`
      : `${d}s exceeds 2.0 limit (15s) — split into ${chunks20} piece(s); 2.5 fits in ${chunks25}.`;
  }
  return lang === 'ru'
    ? 'Уложится в один кусок в обеих версиях.'
    : 'Fits in one piece for both versions.';
}
