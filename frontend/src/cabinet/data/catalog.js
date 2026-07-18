// Studio modes, guide steps and connection definitions — from the prototype.

export const modeDefs = (lang, cr) => [
  {
    id: 'ref', icon: 'layers', cost: `−10 ${cr}`,
    title: lang === 'ru' ? 'Кадр по референсу' : 'From reference',
    desc: lang === 'ru' ? 'Похожий кадр по образцу: поза, свет, стиль' : 'Similar frame from a sample: pose, light, style',
    longDesc: lang === 'ru' ? 'Загрузите один референс — получите близкий кадр с вашим персонажем. Хорош для повторения удачных поз.' : 'Upload one reference — get a close frame with your character.',
    slots: [{ label: lang === 'ru' ? 'Референс-кадр' : 'Reference frame', archive: true }],
    promptHint: lang === 'ru' ? 'Что изменить относительно референса…' : 'What to change vs the reference…',
    showChar: true, showRatio: true,
  },
  {
    id: 'swap', icon: 'face', cost: `−8 ${cr}`, title: 'Face Swap',
    desc: lang === 'ru' ? 'Лицо персонажа на готовый кадр' : "Character's face onto a frame",
    longDesc: lang === 'ru' ? 'Загрузите один референс-кадр. Лицо выбранного персонажа аккуратно заменит лицо на этом кадре — поза, свет и одежда сохранятся.' : "Upload one reference frame. The chosen character's face replaces the face in it.",
    slots: [{ label: lang === 'ru' ? 'Референс-кадр' : 'Reference frame', archive: true }],
    promptHint: lang === 'ru' ? 'Необязательно — уточнения по выражению лица…' : 'Optional — face expression tweaks…',
    showChar: true, showRatio: true,
  },
  {
    id: 'outfit', icon: 'shirt', cost: `−8 ${cr}`,
    title: lang === 'ru' ? 'Замена одежды' : 'Outfit swap',
    desc: lang === 'ru' ? 'Одежда с фото → на персонажа' : 'Clothing from a photo → onto character',
    longDesc: lang === 'ru' ? 'Загрузите один референс с человеком или вещью. Мы выделим одежду и сгенерируем её на выбранном персонаже на однородном фоне.' : 'Upload one reference with a person or item. We extract the clothing and put it on your character on a clean background.',
    slots: [
      { label: lang === 'ru' ? 'Кадр — где заменить одежду' : 'Frame — outfit to replace', archive: true },
      { label: lang === 'ru' ? 'Фото одежды' : 'Clothing photo', archive: false },
    ],
    promptHint: lang === 'ru' ? 'Необязательно — цвет, длина, детали…' : 'Optional — colour, length, details…',
    showChar: true, showRatio: true,
  },
  {
    id: 'location', icon: 'pin', cost: `−8 ${cr}`,
    title: lang === 'ru' ? 'Смена локации' : 'Location swap',
    desc: lang === 'ru' ? 'Перенести персонажа в новое место' : 'Move the character to a new place',
    longDesc: lang === 'ru' ? 'Загрузите один исходный кадр. Кадр остаётся, фон и окружение меняются: пляж, аэропорт, кафе — что угодно.' : 'Upload one source frame. Frame stays, background changes.',
    slots: [
      { label: lang === 'ru' ? 'Кадр — где сменить локацию' : 'Frame — location to replace', archive: true },
      { label: lang === 'ru' ? 'Фото локации' : 'Location photo', archive: false },
    ],
    promptHint: lang === 'ru' ? 'Терраса кафе в Мадриде, вечерний свет…' : 'Café terrace in Madrid, evening light…',
    showChar: true, showRatio: true,
  },
  {
    id: 'prompt', icon: 'text', cost: `−10 ${cr}`,
    title: lang === 'ru' ? 'Кадр по промпту' : 'From prompt',
    desc: lang === 'ru' ? 'Свободная генерация с нуля текстом' : 'Free-form generation from text',
    longDesc: lang === 'ru' ? 'Опишите сцену словами — персонаж подставится из карточки (внешность, EXIF).' : 'Describe the scene — the character comes from its card.',
    slots: [],
    promptHint: lang === 'ru' ? 'Photorealistic 8K still: девушка у окна с кофе, утренний свет…' : 'Photorealistic 8K still: girl by the window with coffee…',
    showChar: true, showRatio: true,
  },
  {
    id: 'carousel', icon: 'grid2', cost: lang === 'ru' ? '−8 кр/кадр' : '−8 cr/frame',
    title: lang === 'ru' ? 'Карусель' : 'Carousel',
    desc: lang === 'ru' ? 'Серия кадров из одного фото' : 'A series of frames from one photo',
    longDesc: lang === 'ru' ? 'Выберите кадр из архива или загрузите готовый, задайте количество кадров — сгенерируем связанную серию (для постов и историй).' : 'Pick a frame from the archive or upload one, set frame count — get a coherent series.',
    slots: [{ label: lang === 'ru' ? 'Базовый кадр' : 'Base frame', archive: true }],
    promptHint: lang === 'ru' ? 'Что меняется от кадра к кадру: ракурс, эмоция…' : 'What changes across frames: angle, emotion…',
    showChar: true, showRatio: true, showCount: true,
  },
];

export const guideDefs = (lang) => [
  {
    title: lang === 'ru' ? 'Создать персонажа' : 'Create a character',
    desc: lang === 'ru' ? 'Загрузите фото-референсы, опишите внешность и персону. Это ваша виртуальная модель — на её основе идут генерации и автоответы.' : 'Upload references, describe the look and persona — your virtual model.',
    cta: lang === 'ru' ? 'К персонажам' : 'To characters', page: 'characters',
  },
  {
    title: lang === 'ru' ? 'Выбрать тариф' : 'Choose a plan',
    desc: lang === 'ru' ? 'Подберите подписку и пополните кредиты — они тратятся на генерации картинок и видео.' : 'Pick a subscription and top up credits used for generations.',
    cta: lang === 'ru' ? 'К тарифам' : 'To plans', page: 'billing',
  },
  {
    title: lang === 'ru' ? 'Подключить каналы' : 'Connect channels',
    desc: lang === 'ru' ? 'Привяжите Telegram/Fanvue и AI-движок. Здесь же — AI-компаньон для автоответов от лица персонажа.' : 'Link Telegram/Fanvue and the AI engine; set up the AI companion.',
    cta: lang === 'ru' ? 'К подключениям' : 'To connections', page: 'connections',
  },
  {
    title: lang === 'ru' ? 'Сгенерировать картинку' : 'Generate an image',
    desc: lang === 'ru' ? 'Выберите режим (референс, Face Swap, одежда, локация, промпт, карусель), модель и формат — и создайте кадр.' : 'Pick a mode, model and format — create a frame.',
    cta: lang === 'ru' ? 'В студию' : 'To studio', page: 'images',
  },
  {
    title: lang === 'ru' ? 'Оживить и запустить донаты' : 'Animate & launch donations',
    desc: lang === 'ru' ? 'Сделайте видео из кадра, ведите диалоги с фанами и подключите донаты — деньги выводятся в разделе «Донаты».' : 'Make a video, chat with fans and enable donations.',
    cta: lang === 'ru' ? 'К донатам' : 'To donations', page: 'donations',
  },
];

export const connDefs = (lang) => [
  {
    id: 'tg', name: 'Telegram', icon: 'tg', tone: 'dim',
    iconCol: { background: 'rgba(56,189,248,.12)', color: '#38BDF8' },
    st: '…',
    desc: lang === 'ru' ? 'Боты для диалогов с фанами: вебхук, AI-компаньон, автоответы, задержка' : 'Fan dialog bots: webhook, AI companion, auto-replies, delay',
    help: lang === 'ru' ? 'Создайте бота у @BotFather, вставьте токен — вебхук настроится сам. Затем привяжите персонажа и включите AI-компаньона, если нужны автоответы.' : 'Create a bot via @BotFather, paste the token — the webhook configures itself.',
  },
  {
    id: 'wavespeed', name: 'WaveSpeed', icon: 'wave', tone: 'dim',
    iconCol: { background: 'rgba(215,244,82,.12)', color: '#D7F452' },
    st: '…',
    desc: lang === 'ru' ? 'AI-движок генераций. Свой ключ на Pro — генерации без списания кредитов' : 'Generation AI engine. Own key on Pro — no platform credits spent',
    help: lang === 'ru' ? 'На Standard используется ключ платформы (списываются кредиты). На Pro вставьте свой API-ключ WaveSpeed — генерации пойдут напрямую.' : 'Standard uses the platform key (credits). On Pro paste your own WaveSpeed API key.',
  },
  {
    id: 'fanvue', name: 'Fanvue', icon: 'heart', tone: 'dim',
    iconCol: { background: 'rgba(240,168,200,.12)', color: '#F0A8C8' },
    st: '…',
    desc: lang === 'ru' ? 'OAuth-коннект аккаунта: диалоги, вебхук, companion-настройки' : 'OAuth account connect: dialogs, webhook, companion settings',
    help: lang === 'ru' ? 'Авторизуйтесь через OAuth, выберите персонажа. Reconnect — если слетела сессия.' : 'Authorize via OAuth and pick a character.',
  },
  {
    id: 'tribute', name: 'Tribute API', icon: 'gift', tone: 'dim',
    iconCol: { background: 'rgba(192,132,252,.12)', color: '#C084FC' },
    st: '…',
    desc: lang === 'ru' ? 'Ваш собственный Tribute-аккаунт для донатов и платных чатов (не платформенные донаты)' : 'Your own Tribute account for donations and paid chats',
    help: lang === 'ru' ? 'Это ВАШ Tribute (авторский API) — не путать с разделом «Донаты», где выплаты идут через аккаунт ModelMate. Ключ и вебхук — по инструкции в Wiki.' : 'This is YOUR Tribute (author API) — not the platform "Donations" section.',
  },
  {
    id: 'ig', name: 'Instagram', icon: 'cam', tone: 'dim',
    iconCol: { background: 'rgba(255,255,255,.07)', color: '#9BA0A6' },
    st: lang === 'ru' ? 'В РАЗРАБОТКЕ' : 'COMING SOON',
    desc: lang === 'ru' ? 'Диалоги Instagram — скоро. Существующие коннекты видны в списке' : 'Instagram dialogs — soon. Existing connects remain visible',
    help: lang === 'ru' ? 'Раздел в разработке — интерфейс ограничен.' : 'Under development — limited UI.',
  },
  {
    id: 'push', name: lang === 'ru' ? 'Уведомления' : 'Notifications', icon: 'bell', tone: 'dim',
    iconCol: { background: 'rgba(74,222,128,.12)', color: '#4ADE80' },
    st: '…',
    desc: lang === 'ru' ? 'Browser push о новых сообщениях в чате и донатах ModelMate' : 'Browser push for new chat messages and ModelMate donations',
    help: lang === 'ru' ? 'Разрешите уведомления в браузере. Работает и в установленной PWA.' : 'Allow notifications in the browser. Works in the installed PWA too.',
  },
];

const F = {
  text: (lbl, val, ph, half) => ({ kind: 'text', lbl, val: val || '', ph: ph || '', half: !!half }),
  select: (lbl, val, opts, half) => ({ kind: 'select', lbl, val, opts, half: !!half }),
  toggle: (lbl, sub, on) => ({ kind: 'toggle', lbl, sub, on }),
  note: (text) => ({ kind: 'note', text }),
};

export const connFieldSets = (lang) => {
  const notAssigned = lang === 'ru' ? 'Не назначена' : 'Not assigned';
  const aiCompOpts = [
    lang === 'ru' ? 'Выключен (оператор)' : 'Off (operator)',
    lang === 'ru' ? 'Включён (AI отвечает)' : 'On (AI replies)',
  ];

  return {
    tg: {
      title: lang === 'ru' ? 'Боты Telegram' : 'Telegram bots',
      prim: lang === 'ru' ? 'Добавить бота' : 'Add bot',
      fields: [
        F.text(lang === 'ru' ? 'ТОКЕН БОТА (BotFather)' : 'BOT TOKEN (BotFather)', '', lang === 'ru' ? 'Вставьте токен BotFather' : 'Paste BotFather token'),
        F.select(lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER', notAssigned, [notAssigned], true),
        F.select(`AI-${lang === 'ru' ? 'КОМПАНЬОН' : 'COMPANION'}`, aiCompOpts[0], aiCompOpts, true),
        F.text(lang === 'ru' ? 'ЗАДЕРЖКА МИН (с)' : 'DELAY MIN (s)', '5', '', true),
        F.text(lang === 'ru' ? 'ЗАДЕРЖКА МАКС (с)' : 'DELAY MAX (s)', '45', '', true),
        F.text(lang === 'ru' ? 'АВТО / ЧАС' : 'AUTO / HOUR', '60', '', true),
        F.note(lang === 'ru' ? 'Несколько ботов по тарифу. Персонаж на подключении — все диалоги бота наследуют его. В каждом чате можно переопределить в шапке диалога.' : "Multiple bots per plan. The connection character is inherited by all the bot's dialogs."),
      ],
      list: [],
    },
    wavespeed: {
      title: lang === 'ru' ? 'AI-движок генераций' : 'Generation AI engine',
      prim: lang === 'ru' ? 'Сохранить' : 'Save',
      fields: [
        F.text(`API-${lang === 'ru' ? 'КЛЮЧ' : 'KEY'}`, '', lang === 'ru' ? 'Вставьте ключ из wavespeed.ai' : 'Paste key from wavespeed.ai'),
        F.note(lang === 'ru' ? 'Pro: нужен ваш API-ключ WaveSpeed — без него генерация недоступна. Standard / Credits: платформа может использовать свой ключ; ваш ключ не обязателен. Зарегистрируйтесь на wavespeed.ai (реф-ссылка ModelMate) и скопируйте ключ.' : 'Pro: needs your WaveSpeed API key. Standard/Credits: platform can use its own key.'),
      ],
      list: [],
    },
    fanvue: {
      title: lang === 'ru' ? 'Аккаунты Fanvue' : 'Fanvue accounts',
      prim: lang === 'ru' ? 'Добавить Fanvue (OAuth)' : 'Add Fanvue (OAuth)',
      fields: [
        F.select(lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER', notAssigned, [notAssigned], true),
        F.select(`AI-${lang === 'ru' ? 'КОМПАНЬОН' : 'COMPANION'}`, aiCompOpts[0], aiCompOpts, true),
        F.text(lang === 'ru' ? 'ЗАДЕРЖКА МИН (с)' : 'DELAY MIN (s)', '5', '', true),
        F.text(lang === 'ru' ? 'ЗАДЕРЖКА МАКС (с)' : 'DELAY MAX (s)', '45', '', true),
        F.text(lang === 'ru' ? 'АВТО / ЧАС' : 'AUTO / HOUR', '60', '', true),
        F.text('WEBHOOK URL', 'https://model-mate.online/api/fanvue/…', '', false),
        F.note(lang === 'ru' ? 'Несколько creator-аккаунтов. Персонаж на подключении — диалоги наследуют его автоматически. Reconnect — если слетела сессия.' : 'Multiple creator accounts. Character on the connection is inherited automatically.'),
      ],
      list: [],
    },
    tribute: {
      title: 'Tribute API',
      prim: lang === 'ru' ? 'Добавить Tribute' : 'Add Tribute',
      fields: [
        F.text(lang === 'ru' ? 'МЕТКА (необязательно)' : 'LABEL (optional)', '', lang === 'ru' ? 'Например: основной Tribute' : 'e.g. main Tribute', true),
        F.select(lang === 'ru' ? 'ПЕРСОНАЖ' : 'CHARACTER', notAssigned, [notAssigned], true),
        F.text(`API-${lang === 'ru' ? 'КЛЮЧ TRIBUTE' : 'KEY TRIBUTE'}`, '', lang === 'ru' ? 'Api-Key из Tribute → Настройки → API' : 'Api-Key from Tribute → Settings → API'),
        F.text(`WEBHOOK URL (Tribute → ${lang === 'ru' ? 'НАСТРОЙКИ' : 'SETTINGS'} → WEBHOOKS)`, 'https://model-mate.online/api/tribute/…', '', false),
        F.note(lang === 'ru' ? 'Донаты и подписки через ВАШ Tribute API (не путать с разделом «Донаты»). Доля чатера задаётся в «Команде». Ключ: панель автора Tribute → Настройки → API Keys → Generate.' : 'Donations & subscriptions via YOUR Tribute API. Chatter share is set in "Team".'),
      ],
      list: [],
    },
    ig: {
      title: 'Instagram',
      prim: lang === 'ru' ? 'Добавить Instagram' : 'Add Instagram',
      disabled: true,
      fields: [
        F.note(lang === 'ru' ? 'Интеграция Instagram Direct пока в разработке. Подключение аккаунта временно недоступно — мы сообщим, когда функция будет готова. Окно ответа — 24 часа после последнего сообщения фана.' : "Instagram Direct integration is under development. Reply window is 24h after the fan's last message."),
      ],
      list: [],
    },
    push: {
      title: lang === 'ru' ? 'Уведомления браузера' : 'Browser notifications',
      prim: lang === 'ru' ? 'Сохранить' : 'Save',
      fields: [
        F.toggle(lang === 'ru' ? 'Новые сообщения в чате' : 'New chat messages', lang === 'ru' ? 'push при входящем от фана' : 'push on incoming fan message', true),
        F.toggle(lang === 'ru' ? 'Донаты ModelMate' : 'ModelMate donations', lang === 'ru' ? 'push при новом донате' : 'push on new donation', true),
        F.toggle(lang === 'ru' ? 'Готовые генерации' : 'Finished generations', lang === 'ru' ? 'когда кадр или видео готовы' : 'when a frame or video is ready', false),
        F.note(lang === 'ru' ? 'Разрешите уведомления в браузере. Работает и в установленной PWA.' : 'Allow notifications in the browser. Works in the installed PWA too.'),
      ],
      list: [],
    },
  };
};
