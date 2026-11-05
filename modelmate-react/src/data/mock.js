// Demo data transferred from the prototype. Presentation-free: swap this
// module for real API calls without touching components.

export const dialogsRaw = [
  { name: 'duty', platform: 'TELEGRAM', last: 'по милости', time: '22:48', av: 0, vip: true, hot: false, lang: 'es*' },
  { name: 'Radomir', platform: 'TELEGRAM', last: 'Дорогая, скоро выходные…', time: '19:33', av: 1, vip: false, hot: true, lang: 'en*' },
  { name: 'Pavol', platform: 'TELEGRAM', last: 'я на работе', time: '18:02', av: 2, vip: false, hot: true, lang: 'en*' },
  { name: 'Renat', platform: 'TELEGRAM', last: 'Нормально, чуть устала…', time: '16:40', av: 3, vip: false, hot: false, lang: 'ru*' },
  { name: 'Thomas', platform: 'TELEGRAM', last: 'Если я узнаю вас поближе…', time: '14:12', av: 4, vip: false, hot: true, lang: 'de*' },
  { name: 'Ariana Woo', platform: 'FANVUE', last: '😊 😇', time: '21:10', av: 3, vip: false, hot: false, lang: 'en*' },
  { name: 'Elijah', platform: 'TELEGRAM', last: 'Привет', time: '11:05', av: 1, vip: false, hot: true, lang: 'nl' },
];

// index -> status. Pavol blocked, Thomas deleted the chat.
export const chatStatus = { 2: 'blocked', 4: 'deleted' };
export const chatNew = { 5: true, 6: true };

export const recentDialogs = [
  { name: 'duty', platform: 'TELEGRAM', last: 'по милости', time: '22:48', av: 0 },
  { name: 'Ariana Woo', platform: 'FANVUE', last: '😊 😇', time: '21:10', av: 3 },
  { name: 'Radomir', platform: 'TELEGRAM', last: 'Дорогая, скоро выходные, как ты планируешь…', time: '19:33', av: 1 },
  { name: 'Pavol', platform: 'TELEGRAM', last: 'я на работе', time: '18:02', av: 2 },
];

export const recentFrameLabels = ['MIA · 9:16', 'MIA · 9:16', 'RUBY · 9:16', 'MIA · 16:9'];

export const langMap = {
  'es*': 'Español', 'en*': 'English', 'de*': 'Deutsch', 'ru*': 'Русский', nl: 'Nederlands',
};

export const msgDefs = [
  { side: 'in', text: 'Очень странно что ты посчитал что это ИИ', tr: false, time: '22:45' },
  { side: 'out', text: 'Миа, я тоже пытаюсь быть с тобой честным. Мы игнорируем это, делаем вид и всё', tr: 'Mia, yo también intento ser sincero contigo…', time: '22:47' },
  { side: 'out', text: 'И не обижайся', tr: 'Y no te sientas ofendida', time: '22:48' },
  { side: 'in', text: 'по милости · por favor', tr: false, time: '22:48' },
];

export const reactChoices = ['❤️', '😍', '😂', '🔥', '👍', '😢'];
export const emojiChoices = ['😊', '😍', '🥰', '😘', '💕', '🔥', '😂', '😅', '🙈', '😉', '💋', '🌹', '✨', '👀', '🥂', '💫'];

export const notesData = (lang) => [
  { tag: lang === 'ru' ? 'ПРОФИЛЬ' : 'PROFILE', kind: 'lime', when: '4 дн.', text: 'Тео (Theo) · Мадрид · есть дети. Предпочитает натуральный контент, детест AI. Недавно оплатил 145€.' },
  { tag: lang === 'ru' ? 'КОНТЕКСТ' : 'CONTEXT', kind: 'orange', when: '4 дн.', text: 'Фан хочет реальное видео без единого элемента ИИ в обмен на оплату платья.' },
  { tag: 'AI', kind: 'purple', when: '4 дн.', text: 'Извиниться за недопонимание. Предложить конкретную цену и сроки. Лёгкий флирт, не углубляться в спор об ИИ.' },
];

export const noteTagDefs = (lang) => [
  { label: lang === 'ru' ? 'ПРОФИЛЬ' : 'PROFILE', col: '#D7F452', bg: 'rgba(215,244,82' },
  { label: lang === 'ru' ? 'КОНТЕКСТ' : 'CONTEXT', col: '#FB923C', bg: 'rgba(251,146,60' },
  { label: lang === 'ru' ? 'ВАЖНО' : 'IMPORTANT', col: '#F87171', bg: 'rgba(248,113,113' },
];

export const modelsByMode = (lang) => ({
  sfw: [
    { id: 'nano', name: 'Nano Banana Pro', note: lang === 'ru' ? 'быстрый, отличная кожа' : 'fast, great skin' },
    { id: 'gpt', name: 'GPT Image', note: lang === 'ru' ? 'точный по промпту' : 'prompt-accurate' },
  ],
  nsfw: [
    { id: 'seedream', name: 'Seedream 5 Pro', note: lang === 'ru' ? 'фотореализм 18+' : 'photoreal 18+' },
    { id: 'wan', name: 'Wan 2.7 Pro', note: lang === 'ru' ? 'детализация тела' : 'body detail' },
  ],
});

export const charactersData = (lang) => [
  {
    id: 'mia', name: 'Mia', initial: 'M', grad: 'linear-gradient(135deg,#F472B6,#C084FC)',
    status: lang === 'ru' ? 'АКТИВНА' : 'ACTIVE', tone: 'active',
    blurb: lang === 'ru' ? 'Основной персонаж · Мадрид · Telegram + Fanvue · EXIF настроен' : 'Main character · Madrid · Telegram + Fanvue · EXIF set',
    tags: ['TELEGRAM', 'FANVUE', 'EXIF ✓', 'PERSONA ✓'],
  },
  {
    id: 'ruby', name: 'Ruby', initial: 'R', grad: 'linear-gradient(135deg,#FB923C,#F87171)',
    status: lang === 'ru' ? 'АКТИВНА' : 'ACTIVE', tone: 'active',
    blurb: lang === 'ru' ? 'Рыжая · рабочие кадры в студии · без компаньона' : 'Redhead · studio frames · no companion',
    tags: ['TELEGRAM', 'EXIF ✓'],
  },
  {
    id: 'velvet', name: 'Velvet', initial: 'V', grad: 'linear-gradient(135deg,#38BDF8,#818CF8)',
    status: lang === 'ru' ? 'ЧЕРНОВИК' : 'DRAFT', tone: 'dim',
    blurb: lang === 'ru' ? 'Новый персонаж — заполните внешность и персону' : 'New character — fill appearance and persona',
    tags: ['—'],
  },
];

export const charTabDefs = (lang) => [
  { id: 'photos', label: lang === 'ru' ? 'Фото и внешность' : 'Photos & look' },
  { id: 'persona', label: lang === 'ru' ? 'Персона (AI-компаньон)' : 'Persona (AI companion)' },
  { id: 'exif', label: lang === 'ru' ? 'EXIF «как с телефона»' : 'EXIF "like a phone"' },
  { id: 'history', label: lang === 'ru' ? 'История модели' : 'Model history' },
];

export const photoTagNames = (lang) =>
  lang === 'ru'
    ? ['Лицо', 'Внешность', 'Развёртка', 'Тело целиком', 'Selfie', 'Основная камера']
    : ['Face', 'Look', 'Turnaround', 'Full body', 'Selfie', 'Main camera'];

export const charPhotoKinds = (lang) =>
  lang === 'ru'
    ? ['ЛИЦО', 'ВНЕШНОСТЬ', 'РАЗВЁРТКА', 'ТЕЛО ЦЕЛИКОМ', 'ЛИЦО']
    : ['FACE', 'LOOK', 'TURNAROUND', 'FULL BODY', 'FACE'];

export const personaFieldDefs = (lang) => [
  { lbl: lang === 'ru' ? 'ВОЗРАСТ' : 'AGE', val: '24', ph: '24', area: false, half: true },
  { lbl: lang === 'ru' ? 'ГОРОД' : 'CITY', val: 'Пермь', ph: '', area: false, half: true },
  { lbl: lang === 'ru' ? 'СТРАНА' : 'COUNTRY', val: 'Россия', ph: '', area: false, half: true },
  { lbl: lang === 'ru' ? 'ЧАСОВОЙ ПОЯС' : 'TIMEZONE', val: '', ph: 'Europe/Madrid', area: false, half: true },
  { lbl: lang === 'ru' ? 'ХАРАКТЕР' : 'PERSONALITY', val: '', ph: lang === 'ru' ? 'тёплая, игривая, немного застенчивая…' : 'warm, playful, a bit shy…', area: true, half: false },
  { lbl: lang === 'ru' ? 'ХОББИ И УВЛЕЧЕНИЯ' : 'HOBBIES', val: '', ph: lang === 'ru' ? 'йога, кофе, путешествия…' : 'yoga, coffee, travel…', area: true, half: false },
  { lbl: lang === 'ru' ? 'ИНТЕРЕСЫ / ТЕМЫ ДЛЯ РАЗГОВОРА' : 'INTERESTS', val: '', ph: lang === 'ru' ? 'музыка, мода, спорт…' : 'music, fashion, sport…', area: true, half: false },
  { lbl: lang === 'ru' ? 'ОБРАЗ ЖИЗНИ' : 'LIFESTYLE', val: '', ph: lang === 'ru' ? 'учится, работает фрилансером, любит вечерние прогулки…' : 'studies, freelances, loves evening walks…', area: true, half: false },
  { lbl: lang === 'ru' ? 'СТИЛЬ ПЕРЕПИСКИ' : 'CHAT STYLE', val: '', ph: lang === 'ru' ? 'короткие сообщения, эмодзи, без формальностей…' : 'short messages, emoji, informal…', area: true, half: false },
  { lbl: lang === 'ru' ? 'ПРЕДЫСТОРИЯ' : 'BACKSTORY', val: '', ph: lang === 'ru' ? 'откуда она, чем занимается, что важно в жизни…' : 'where she is from, what matters to her…', area: true, half: false },
];

export const exifPresets = (lang) =>
  lang === 'ru'
    ? ['— не применять —', 'iPhone 15 Pro', 'Samsung S24 Ultra', 'Pixel 8 Pro']
    : ['— none —', 'iPhone 15 Pro', 'Samsung S24 Ultra', 'Pixel 8 Pro'];

export const historyRowsData = (lang) => [
  { icon: 'image', what: lang === 'ru' ? 'Кадр по промпту · Nano Banana Pro' : 'From prompt · Nano Banana Pro', when: '12.07 · 14:20', tag: '−10 кр.' },
  { icon: 'face', what: 'Face Swap · Seedream 5 Pro', when: '11.07 · 19:02', tag: '−8 кр.' },
  { icon: 'film', what: lang === 'ru' ? 'Видео 1080p · 5с' : 'Video 1080p · 5s', when: '10.07 · 22:40', tag: '−40 кр.' },
  { icon: 'star', what: lang === 'ru' ? 'Обновлено описание внешности' : 'Appearance updated', when: '08.07 · 10:11', tag: '' },
];

export const donStatsData = (lang) => [
  { label: lang === 'ru' ? 'ВСЕГО' : 'TOTAL', value: '100,00 ₽', color: '#F2F3F0' },
  { label: lang === 'ru' ? 'ДОСТУПНО' : 'AVAILABLE', value: '100,00 ₽', color: '#4ADE80' },
  { label: lang === 'ru' ? 'НА УДЕРЖАНИИ' : 'ON HOLD', value: '0,00 ₽', color: '#FB923C' },
  { label: lang === 'ru' ? 'ВЫПЛАЧЕНО' : 'PAID OUT', value: '0,00 ₽', color: '#9BA0A6' },
];

export const donLinksData = (lang) => [
  {
    title: lang === 'ru' ? 'Поддержать Mia 💕' : 'Support Mia 💕', st: 'ACTIVE', tone: 'active',
    urls: [
      { kind: 'Telegram', icon: 'tg', col: '#38BDF8', url: 't.me/tribute/app?startapp=N8c' },
      { kind: 'Web', icon: 'globe', col: '#C084FC', url: 'web.tribute.tg/d/N8c' },
    ],
  },
  {
    title: lang === 'ru' ? 'Платье для съёмки' : 'Dress for a shoot', st: lang === 'ru' ? 'МОДЕРАЦИЯ' : 'PENDING', tone: 'warn',
    urls: [
      { kind: 'Telegram', icon: 'tg', col: '#38BDF8', url: 't.me/tribute/app?startapp=Dr5' },
      { kind: 'Web', icon: 'globe', col: '#C084FC', url: 'web.tribute.tg/d/Dr5' },
    ],
  },
];

export const incomingData = (lang) => [
  { sum: '+100,00 ₽', from: lang === 'ru' ? 'Аноним · «Поддержать Mia»' : 'Anonymous · "Support Mia"', when: '12.07 · 14:45' },
];

export const myDonationsData = (lang) => [
  { title: lang === 'ru' ? 'Поддержать Mia 💕' : 'Support Mia 💕', st: 'ACTIVE', tone: 'active' },
  { title: lang === 'ru' ? 'Платье для съёмки' : 'Dress for a shoot', st: 'PENDING', tone: 'warn' },
  { title: lang === 'ru' ? 'Регулярная подписка' : 'Recurring support', st: 'DRAFT', tone: 'dim' },
];

export const usageBarsData = (lang) => [
  { label: lang === 'ru' ? 'Операторы' : 'Operators', val: '3 / 10', pct: 30 },
  { label: lang === 'ru' ? 'Персонажи' : 'Characters', val: '7 / 10', pct: 70 },
  { label: lang === 'ru' ? 'Диалоги в месяце' : 'Dialogs this month', val: '4 · ∞', pct: 8 },
];

export const priceMap = (lang, period) => ({
  standard: [
    { name: 'Solo', price: period === 'month' ? '590' : '5 660', desc: lang === 'ru' ? '1 оператор · 3 персонажа · кредиты на студию включены' : '1 operator · 3 characters · studio credits included' },
    { name: 'Studio', price: period === 'month' ? '1 490' : '14 300', tag: lang === 'ru' ? 'ВАШ' : 'YOURS', desc: lang === 'ru' ? '10 операторов · 10 персонажей · чат и команда · кредиты включены' : '10 operators · 10 characters · chat & team · credits included' },
    { name: 'Agency', price: period === 'month' ? '3 990' : '38 300', desc: lang === 'ru' ? 'Безлимит операторов · 30 персонажей · приоритетная поддержка' : 'Unlimited operators · 30 characters · priority support' },
  ],
  pro: [
    { name: 'Pro Solo', price: period === 'month' ? '990' : '9 500', desc: lang === 'ru' ? 'Свой ключ WaveSpeed — генерации не тратят кредиты платформы' : "Own WaveSpeed key — generations don't spend platform credits" },
    { name: 'Pro Pro', price: period === 'month' ? '2 490' : '23 900', desc: lang === 'ru' ? 'Всё из Pro Solo + команда до 10 операторов' : 'Everything in Pro Solo + team up to 10 operators' },
    { name: 'Pro Studio', price: period === 'month' ? '4 990' : '47 900', desc: lang === 'ru' ? 'Максимум: безлимит, все каналы, персональный онбординг' : 'Maximum: unlimited, all channels, personal onboarding' },
  ],
});

export const packs = [
  { cr: '100', price: '360 ₽', bonus: false },
  { cr: '300', price: '1 020 ₽', bonus: '+5%' },
  { cr: '600', price: '1 940 ₽', bonus: '+10%' },
  { cr: '1500', price: '4 590 ₽', bonus: '+15%' },
];

export const historyData = (lang) => [
  { date: '12.07.26', what: lang === 'ru' ? 'Донат «Поддержать Mia»' : 'Donation "Support Mia"', delta: '+100 ₽', color: '#4ADE80' },
  { date: '10.07.26', what: lang === 'ru' ? 'Генерация видео · Mia' : 'Video generation · Mia', delta: '−40 кр.', color: '#F87171' },
  { date: '08.07.26', what: lang === 'ru' ? 'Пакет кредитов 600' : 'Credit pack 600', delta: '+600 кр.', color: '#4ADE80' },
  { date: '07.07.26', what: lang === 'ru' ? 'Подписка Standard Studio' : 'Standard Studio subscription', delta: '−1 490 ₽', color: '#F87171' },
];

export const teamKpiData = (lang) => [
  { label: lang === 'ru' ? 'ОТВЕТЫ / МЕС' : 'REPLIES / MO', value: '78' },
  { label: lang === 'ru' ? 'ДИАЛОГИ' : 'DIALOGS', value: '2' },
  { label: lang === 'ru' ? 'ПЕРВЫЙ ОТВЕТ' : 'FIRST REPLY', value: '4м 12с' },
  { label: 'AI 👍 / 👎', value: '92%' },
];

export const membersData = (lang) => [
  {
    login: 'anna_op', meta: `${lang === 'ru' ? 'активна · персонажи' : 'active · characters'}: Mia`,
    initial: 'A', grad: { bg: 'linear-gradient(135deg,#4ADE80,#38BDF8)', ink: '#0A2614' },
    sla: '96%', replies: '52', tribute: '15%',
    rights: [
      { label: 'CHAT', on: true }, { label: 'STUDIO GEN', on: true }, { label: 'MODELS', on: false },
      { label: 'INTEGRATIONS', on: false }, { label: 'BILLING', on: false },
    ],
  },
  {
    login: 'mark_night', meta: `${lang === 'ru' ? 'активен · персонажи' : 'active · characters'}: Mia, Ruby`,
    initial: 'M', grad: { bg: 'linear-gradient(135deg,#FACC15,#FB923C)', ink: '#262008' },
    sla: '88%', replies: '26', tribute: '10%',
    rights: [
      { label: 'CHAT', on: true }, { label: 'STUDIO GEN', on: true }, { label: 'MODELS', on: true },
      { label: 'INTEGRATIONS', on: false }, { label: 'BILLING', on: false },
    ],
  },
];

export const templatesData = (lang) => [
  { title: lang === 'ru' ? 'Приветствие VIP' : 'VIP greeting', body: lang === 'ru' ? 'Привет, милый! Так рада тебя видеть 💕 Как прошёл день?' : 'Hi love! So glad to see you 💕 How was your day?' },
  { title: lang === 'ru' ? 'Оффер видео' : 'Video offer', body: lang === 'ru' ? 'Могу записать для тебя особенное видео… обсудим детали?' : 'I can record a special video for you… shall we discuss?' },
];

export const opModelNames = ['Zaranoir', 'Velvet.X', 'Kima', 'Nadia', 'Rich', 'Ruby', 'Mia'];

export const ratios = ['9:16', '16:9', '1:1', '4:3', '3:4'];
export const countOptions = [2, 3, 4, 6, 8];
export const charNames = ['Mia', 'Ruby', 'Velvet'];

export const dateStr = (lang) => (lang === 'ru' ? 'ВТ · 14 ИЮЛЯ 2026' : 'TUE · JULY 14 2026');
