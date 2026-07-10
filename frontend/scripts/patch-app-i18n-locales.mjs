import fs from 'fs'
import path from 'path'

const root = path.resolve('src/i18n/locales')
const ruChat = JSON.parse(fs.readFileSync(path.join(root, 'ru/chat.json'), 'utf8'))
const enChat = JSON.parse(fs.readFileSync(path.join(root, 'en/chat.json'), 'utf8'))
const ruStudio = JSON.parse(fs.readFileSync(path.join(root, 'ru/studio.json'), 'utf8'))
const enStudio = JSON.parse(fs.readFileSync(path.join(root, 'en/studio.json'), 'utf8'))
const ruWs = JSON.parse(fs.readFileSync(path.join(root, 'ru/workspace.json'), 'utf8'))
const enWs = JSON.parse(fs.readFileSync(path.join(root, 'en/workspace.json'), 'utf8'))
const ruCommon = JSON.parse(fs.readFileSync(path.join(root, 'ru/common.json'), 'utf8'))
const enCommon = JSON.parse(fs.readFileSync(path.join(root, 'en/common.json'), 'utf8'))

Object.assign(ruCommon, {
  duration: { seconds: '{{n}}с', minutes: '{{n}}м', hours: '{{n}}ч' },
  close: 'Закрыть',
  loading: 'Загрузка…',
  copy: 'Копировать',
  delete: 'Удалить',
  cancel: 'Отменить',
  save: 'Сохранить',
  add: 'Добавить',
  remove: 'Удалить',
  on: 'Вкл.',
  off: 'Выкл.',
  checking: 'проверка…',
  reading: 'Чтение…',
  replace: 'Заменить',
  upload: 'Загрузить',
  reset: 'Сбросить',
  notUploaded: 'Не загружен',
  saving: 'Сохранение…',
  saved: '✓ Сохранено',
})
Object.assign(enCommon, {
  duration: { seconds: '{{n}}s', minutes: '{{n}}m', hours: '{{n}}h' },
  close: 'Close',
  loading: 'Loading…',
  copy: 'Copy',
  delete: 'Delete',
  cancel: 'Cancel',
  save: 'Save',
  add: 'Add',
  remove: 'Remove',
  on: 'On',
  off: 'Off',
  checking: 'checking…',
  reading: 'Reading…',
  replace: 'Replace',
  upload: 'Upload',
  reset: 'Reset',
  notUploaded: 'Not uploaded',
  saving: 'Saving…',
  saved: '✓ Saved',
})

Object.assign(ruChat, {
  outboundLang: { auto: 'Авто (по переписке)', ru: 'Русский' },
  strip: { dialogFallback: 'Диалог', unreadAria: 'Непрочитанные' },
  dock: { backAria: 'Назад к списку диалогов', otherDialogsAria: 'Другие диалоги' },
  notes: {
    kinds: { profile: 'Профиль', context: 'Контекст', manual: 'Заметка' },
    title: 'Заметки',
    userFallback: 'Пользователь',
    closeAria: 'Закрыть заметки',
    panelAria: 'Заметки о пользователе',
    toggleTitle: 'Заметки о пользователе',
    toggleHide: 'Скрыть заметки',
    emptyProfile:
      'Профиль пока пуст — нажмите «AI-анализ» или добавьте заметку вручную.',
    placeholder: 'Ваша заметка о пользователе…',
    analyze: 'AI-анализ',
    analyzing: 'Анализ…',
    add: 'Добавить',
    pin: 'Закрепить',
    unpin: 'Открепить',
    delete: 'Удалить',
  },
  composer: {
    replyTo: 'Ответ на',
    messageFallback: 'Сообщение',
    cancelReplyTitle: 'Отменить ответ',
    removeAttachmentTitle: 'Убрать вложение',
    archiveLabel: 'Из архива студии',
    archiveHint: 'Готовое изображение уйдёт в чат',
    archiveBadge: 'Архив #{{id}}',
    photoDeviceTitle: 'Фото с устройства',
    archiveTitle: 'Из архива студии',
    emojiTitle: 'Эмодзи',
    hintFanvueBlocked: 'Пользователь недоступен на Fanvue — отправка невозможна',
    hintTranslate: 'Сообщение на русском — уйдёт перевод на язык из «Язык ответа»',
    titleFanvueBlocked: 'Пользователь Fanvue недоступен',
    titleTranslate:
      'Пишите на русском; в Telegram/Fanvue уйдёт перевод по выбранному языку',
    shortcut: 'Ctrl+Enter — отправить',
    scrollToLatest: 'К последним ↓',
  },
  messages: {
    loadingHistory: 'Загрузка истории…',
    gotoTitle: 'Перейти к сообщению',
    originalTitle: 'Оригинал',
    sentTitle: 'Ушло пользователю',
    translating: 'перевод и отправка…',
  },
  reactions: {
    aria: 'Реакции',
    removeTitle: 'Убрать реакцию',
    addTitle: 'Поставить реакцию',
    replyTitle: 'Ответить',
    emojiTitle: 'Реакция',
  },
  companion: {
    rateAria: 'Оценка ответа AI',
    rateLabel: 'Оценка AI',
    goodTitle: 'Хороший ответ AI',
    badTitle: 'Плохой ответ AI',
    unrateGood: 'Снять оценку «хорошо»',
    unrateBad: 'Снять оценку «плохо»',
    ratedGood: 'Оценено: хорошо',
    ratedBad: 'Оценено: плохо',
    helpLearn: 'Помогите боту учиться',
    draftLabel: 'Черновик AI',
    failedLabel: 'AI не отправил — проверьте',
    send: 'Отправить',
    reject: 'Отклонить',
    queue: ' · очередь {{count}}',
  },
  threadExtra: {
    hideFromList: 'Убрать из списка',
    fanvueUnavailableBanner:
      'Пользователь Fanvue недоступен — аккаунт удалён или заблокирован на платформе. Отправка сообщений невозможна.',
    unblock: 'Разблокировать',
  },
  templates: {
    title: 'Шаблоны ответов',
    lead: 'Кнопки появляются над полем ввода в чате — быстрая вставка текста.',
    namePlaceholder: 'Название кнопки',
    bodyPlaceholder: 'Текст шаблона',
    add: 'Добавить',
    delete: 'Удалить',
    empty: 'Пока нет шаблонов.',
  },
  errors: {
    loadConversations: 'Не удалось загрузить диалоги',
    loadMessages: 'Не удалось загрузить сообщения',
    saveReplyLang: 'Не удалось сохранить язык ответа',
    saveTranslate: 'Не удалось сохранить настройку перевода',
    saveCompanion: 'Не удалось сохранить режим AI-компаньона',
    assignChatter: 'Не удалось назначить чатера',
    createTemplate: 'Не удалось создать шаблон',
    saveCategory: 'Не удалось сохранить категорию',
    saveBlock: 'Не удалось изменить блокировку',
    hideConfirm:
      'Убрать диалог из списка? История сохранится, но чат исчезнет из списка.',
    hideFailed: 'Не удалось убрать диалог из списка',
    reactionTelegram:
      'Реакция сохранена в чате, но Telegram не принял её — проверьте логи API.',
    reactionFailed: 'Не удалось поставить реакцию',
    sendFailed: 'Не удалось отправить сообщение',
    imageLoadFailed: 'Не удалось загрузить изображение.',
    imageDownloadFailed:
      'Не удалось скачать. На iPhone откройте меню «Поделиться» или удерживайте превью выше → «Сохранить в Фото».',
    shareImageTitle: 'Изображение',
    fanvueConnect:
      'Не удалось подключить Fanvue. Проверьте scopes в Fanvue Developer Area и попробуйте снова.',
    instagramConnect:
      'Не удалось подключить Instagram. Проверьте Business/Creator аккаунт, scopes и настройки Meta App.',
  },
  import: {
    historyLoaded:
      'История загружена: {{imported}} сообщений в {{chats}} диалогах{{skipped}}{{warnings}}',
    skipped: ' ({{count}} уже были в базе)',
    warnings: '. Предупреждений: {{count}}',
  },
})

Object.assign(enChat, {
  outboundLang: { auto: 'Auto (from chat)', ru: 'Russian' },
  strip: { dialogFallback: 'Chat', unreadAria: 'Unread' },
  dock: { backAria: 'Back to chat list', otherDialogsAria: 'Other chats' },
  notes: {
    kinds: { profile: 'Profile', context: 'Context', manual: 'Note' },
    title: 'Notes',
    userFallback: 'User',
    closeAria: 'Close notes',
    panelAria: 'User notes',
    toggleTitle: 'User notes',
    toggleHide: 'Hide notes',
    emptyProfile: 'Profile is empty — run AI analysis or add a note manually.',
    placeholder: 'Your note about this user…',
    analyze: 'AI analysis',
    analyzing: 'Analyzing…',
    add: 'Add',
    pin: 'Pin',
    unpin: 'Unpin',
    delete: 'Delete',
  },
  composer: {
    replyTo: 'Reply to',
    messageFallback: 'Message',
    cancelReplyTitle: 'Cancel reply',
    removeAttachmentTitle: 'Remove attachment',
    archiveLabel: 'From studio archive',
    archiveHint: 'Ready image will be sent to chat',
    archiveBadge: 'Archive #{{id}}',
    photoDeviceTitle: 'Photo from device',
    archiveTitle: 'From studio archive',
    emojiTitle: 'Emoji',
    hintFanvueBlocked: 'Fanvue user unavailable — cannot send',
    hintTranslate: 'Message in Russian — will be translated per Reply language',
    titleFanvueBlocked: 'Fanvue user unavailable',
    titleTranslate:
      'Write in Russian; Telegram/Fanvue will get translation per selected language',
    shortcut: 'Ctrl+Enter — send',
    scrollToLatest: 'Jump to latest ↓',
  },
  messages: {
    loadingHistory: 'Loading history…',
    gotoTitle: 'Go to message',
    originalTitle: 'Original',
    sentTitle: 'Sent to user',
    translating: 'translating and sending…',
  },
  reactions: {
    aria: 'Reactions',
    removeTitle: 'Remove reaction',
    addTitle: 'Add reaction',
    replyTitle: 'Reply',
    emojiTitle: 'Reaction',
  },
  companion: {
    rateAria: 'Rate AI reply',
    rateLabel: 'AI rating',
    goodTitle: 'Good AI reply',
    badTitle: 'Bad AI reply',
    unrateGood: 'Remove good rating',
    unrateBad: 'Remove bad rating',
    ratedGood: 'Rated: good',
    ratedBad: 'Rated: bad',
    helpLearn: 'Help the bot learn',
    draftLabel: 'AI draft',
    failedLabel: 'AI did not send — check',
    send: 'Send',
    reject: 'Reject',
    queue: ' · queue {{count}}',
  },
  threadExtra: {
    hideFromList: 'Remove from list',
    fanvueUnavailableBanner:
      'Fanvue user unavailable — account deleted or blocked on the platform. Cannot send messages.',
    unblock: 'Unblock',
  },
  templates: {
    title: 'Reply templates',
    lead: 'Buttons appear above the composer for quick text insertion.',
    namePlaceholder: 'Button label',
    bodyPlaceholder: 'Template text',
    add: 'Add',
    delete: 'Delete',
    empty: 'No templates yet.',
  },
  errors: {
    loadConversations: 'Could not load chats',
    loadMessages: 'Could not load messages',
    saveReplyLang: 'Could not save reply language',
    saveTranslate: 'Could not save translation setting',
    saveCompanion: 'Could not save AI companion mode',
    assignChatter: 'Could not assign chatter',
    createTemplate: 'Could not create template',
    saveCategory: 'Could not save category',
    saveBlock: 'Could not change block status',
    hideConfirm:
      'Remove chat from list? History is kept but the chat disappears from the list.',
    hideFailed: 'Could not remove chat from list',
    reactionTelegram:
      'Reaction saved in chat but Telegram rejected it — check API logs.',
    reactionFailed: 'Could not add reaction',
    sendFailed: 'Could not send message',
    imageLoadFailed: 'Could not load image.',
    imageDownloadFailed:
      'Download failed. On iPhone use Share menu or long-press preview above → Save to Photos.',
    shareImageTitle: 'Image',
    fanvueConnect:
      'Could not connect Fanvue. Check scopes in Fanvue Developer Area and try again.',
    instagramConnect:
      'Could not connect Instagram. Check Business/Creator account, scopes and Meta App settings.',
  },
  import: {
    historyLoaded:
      'History imported: {{imported}} messages in {{chats}} chats{{skipped}}{{warnings}}',
    skipped: ' ({{count}} already in database)',
    warnings: '. Warnings: {{count}}',
  },
})

// studio + workspace extensions written in separate files for maintainability - import from generated JSON
const extDir = path.join(root, '_app_ext')
for (const loc of ['ru', 'en']) {
  const studioExt = JSON.parse(fs.readFileSync(path.join(extDir, `${loc}-studio-ext.json`), 'utf8'))
  const wsExt = JSON.parse(fs.readFileSync(path.join(extDir, `${loc}-workspace-ext.json`), 'utf8'))
  const wsFlat = JSON.parse(fs.readFileSync(path.join(extDir, `${loc}-workspace-flat.json`), 'utf8'))
  const studioAliases = JSON.parse(fs.readFileSync(path.join(extDir, `${loc}-studio-aliases.json`), 'utf8'))
  Object.assign(loc === 'ru' ? ruStudio : enStudio, studioExt)
  Object.assign(loc === 'ru' ? ruWs : enWs, wsExt)
  deepAssign(loc === 'ru' ? ruWs : enWs, wsFlat)
  deepAssign(loc === 'ru' ? ruStudio : enStudio, studioAliases)
}

function deepAssign(target, patch) {
  for (const [k, v] of Object.entries(patch)) {
    if (v && typeof v === 'object' && !Array.isArray(v) && typeof target[k] === 'object' && target[k]) {
      deepAssign(target[k], v)
    } else {
      target[k] = v
    }
  }
}

enWs.cabinet.team.noMembers = 'No members yet.'

for (const [loc, chat, studio, ws, common] of [
  ['ru', ruChat, ruStudio, ruWs, ruCommon],
  ['en', enChat, enStudio, enWs, enCommon],
]) {
  fs.writeFileSync(path.join(root, loc, 'chat.json'), `${JSON.stringify(chat, null, 2)}\n`)
  fs.writeFileSync(path.join(root, loc, 'studio.json'), `${JSON.stringify(studio, null, 2)}\n`)
  fs.writeFileSync(path.join(root, loc, 'workspace.json'), `${JSON.stringify(ws, null, 2)}\n`)
  fs.writeFileSync(path.join(root, loc, 'common.json'), `${JSON.stringify(common, null, 2)}\n`)
}

console.log('locale files updated')
