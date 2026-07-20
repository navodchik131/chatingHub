export type Dialog = {
  id: string;
  name: string;
  plat: 'TELEGRAM' | 'FANVUE';
  msg: string;
  vip?: boolean;
  unread?: number;
  gradIndex: number;
};

export const kpis = {
  credits: '510',
  creditsSub: '≈51 кадр',
  plan: 'Studio',
  planSub: 'до 07.12',
  donations: '100 ₽',
  donationsSub: 'к выплате',
  dialogs: '14',
  dialogsSub: '78 ответов',
};

export const dialogsSeed: Dialog[] = [
  { id: 'duty', name: 'duty', plat: 'TELEGRAM', msg: 'по милости', vip: true, unread: 2, gradIndex: 0 },
  { id: 'radomir', name: 'Radomir', plat: 'TELEGRAM', msg: 'Дорогая, скоро выходные…', vip: false, unread: 1, gradIndex: 1 },
  { id: 'ariana', name: 'Ariana Woo', plat: 'FANVUE', msg: '😊 😇', vip: false, unread: 0, gradIndex: 2 },
  { id: 'pavol', name: 'Pavol', plat: 'TELEGRAM', msg: 'я на работе', vip: false, unread: 0, gradIndex: 0 },
];

export const threadMessages = [
  { id: '1', text: 'Очень странно что ты посчитал что это ИИ', out: false },
  { id: '2', text: 'Я тоже пытаюсь быть с тобой честным', out: true, translation: 'Yo también intento ser sincero contigo' },
  { id: '3', text: 'И не обижайся', out: true, translation: 'Y no te sientas ofendida' },
];

export const modeDefs = [
  { id: 'ref', color: '215,244,82', title: 'Кадр по референсу', desc: 'Похожий кадр по образцу', icon: 'image' as const },
  { id: 'swap', color: '240,168,200', title: 'Face Swap', desc: 'Лицо персонажа на кадр', icon: 'user' as const },
  { id: 'outfit', color: '192,132,252', title: 'Замена одежды', desc: 'Одежда с фото на модель', icon: 'star' as const },
  { id: 'loc', color: '56,189,248', title: 'Смена локации', desc: 'Новый фон и окружение', icon: 'image' as const },
  { id: 'prompt', color: '250,204,21', title: 'Кадр по промпту', desc: 'Свободная генерация текстом', icon: 'bolt' as const },
  { id: 'carousel', color: '74,222,128', title: 'Карусель', desc: 'Серия связанных кадров', icon: 'bolt' as const },
];

export const slotLabels: Record<string, string[]> = {
  ref: ['Референс-кадр'],
  swap: ['Референс-кадр'],
  outfit: ['Кадр', 'Фото одежды'],
  loc: ['Кадр', 'Фото локации'],
  prompt: [],
  carousel: ['Базовый кадр'],
};

export const archiveTiles = [
  { who: 'Mia', gradIndex: 0 },
  { who: 'Ruby', gradIndex: 1 },
  { who: 'Mia', gradIndex: 2 },
  { who: 'Mia', gradIndex: 0 },
  { who: 'Ruby', gradIndex: 1 },
  { who: 'Mia', gradIndex: 2 },
];

export const charactersList = [
  { id: 'mia', letter: 'M', name: 'Mia', sub: 'Telegram · Fanvue', gradIndex: 0 },
  { id: 'ruby', letter: 'R', name: 'Ruby', sub: 'Telegram', gradIndex: 1, gradColors: ['#FB923C', '#F87171'] as [string, string] },
];

export const photoTags = ['Лицо', 'Внешность', 'Развёртка', 'Тело целиком'];
export const photoTagsExtended = ['Лицо', 'Внешность', 'Развёртка', 'Тело целиком', 'Selfie'];

export const connectionsList = [
  { id: 'tg', name: 'Telegram', status: '2 БОТА', color: '56,189,248', icon: 'chat' as const },
  { id: 'ws', name: 'WaveSpeed', status: 'ПЛАТФОРМА', color: '215,244,82', icon: 'bolt' as const },
  { id: 'fv', name: 'Fanvue', status: 'ПОДКЛЮЧЁН', color: '240,168,200', icon: 'heart' as const },
  { id: 'tr', name: 'Tribute API', status: 'НЕ НАСТРОЕН', color: '192,132,252', icon: 'card' as const },
];

export const billingPlans = {
  standard: [['Solo', '590'], ['Studio', '1 490'], ['Agency', '3 990']],
  pro: [['Pro Solo', '990'], ['Pro Pro', '2 490'], ['Pro Studio', '5 990']],
};

export const creditPacks = [['100', '360 ₽'], ['300', '1 020 ₽'], ['600', '1 940 ₽'], ['1500', '4 590 ₽']];

export const rightsDefs = [
  { k: 'chat', l: 'Диалоги и ответы' },
  { k: 'studio', l: 'Генерация в студии' },
  { k: 'models', l: 'Персонажи' },
  { k: 'keys', l: 'Ключи интеграций' },
  { k: 'billing', l: 'Оплата и биллинг' },
];

export const adminUsers = [
  { email: 'goldmorfin009@gmail.com', role: 'владелец', plan: 'Credits · Solo', credits: 0, sub: 'нет' },
  { email: 'aimodelcore@gmail.com', role: 'владелец', plan: 'Standard · Pro', credits: 300, sub: 'активна' },
  { email: 'rim1702sr@gmail.com', role: 'владелец', plan: 'Credits · Solo', credits: 16, sub: 'нет' },
  { email: 'anna_op@modelmate.local', role: 'оператор', plan: '—', credits: 0, sub: 'нет' },
];

export const adminPlans = [
  { name: 'Studio', pct: 46, color: '#D7F452' },
  { name: 'Solo', pct: 26, color: '#38BDF8' },
  { name: 'Pro Pro', pct: 15, color: '#C084FC' },
];

export const adminPlanChips = ['Solo', 'Studio', 'Agency', 'Pro Solo', 'Pro Pro'];

export const botUsers = {
  exif: [
    { name: 'Renat', u: 'rentauren', m: '5' },
    { name: 'Ruby Praud', u: 'rubypraud', m: '0' },
    { name: 'Евгений', u: 'stalkerlegend', m: '0' },
  ],
  ig: [
    { name: 'Renat', u: 'rentauren', m: '29' },
    { name: 'DWInstaModelMate', u: 'DWInstaModelMate_bot', m: '0' },
    { name: 'Ruby Praud', u: 'rubypraud', m: '1' },
  ],
};

export const charHistory = [
  { label: 'Кадр по промпту', cost: '−10 кр.' },
  { label: 'Face Swap', cost: '−8 кр.' },
  { label: 'Видео 1080p', cost: '−40 кр.' },
];
