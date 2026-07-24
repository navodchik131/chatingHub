import type { AppLocale } from '@/src/i18n/prefs';

export type Strings = {
  navOverview: string;
  navDialogs: string;
  navStudio: string;
  navCharacters: string;
  navProfile: string;
  navBilling: string;
  navDonations: string;
  navConnections: string;
  navTeam: string;
  profileTitle: string;
  owner: string;
  member: string;
  sectionWorkspace: string;
  sectionSystem: string;
  settingsTitle: string;
  settingsLanguage: string;
  settingsLanguageRu: string;
  settingsLanguageEn: string;
  settingsLanguageHint: string;
  settingsBiometric: string;
  settingsBiometricHint: string;
  settingsBiometricTest: string;
  settingsBiometricUnavailable: string;
  settingsBiometricLock: string;
  settingsBiometricLockHint: string;
  settingsPush: string;
  settingsPushHint: string;
  settingsPushEnabled: string;
  settingsPushDisabled: string;
  settingsSaved: string;
  adminPanel: string;
  logout: string;
  authLogin: string;
  authRegister: string;
  authEmail: string;
  authPassword: string;
  authPasswordHint: string;
  authEnter: string;
  authRegisterBtn: string;
  authEntering: string;
  authRegistering: string;
  authOrEmail: string;
  authTelegramLogin: string;
  authTelegramRegister: string;
  authBiometric: string;
  authNoAccount: string;
  authHasAccount: string;
  studioTitle: string;
  studioImages: string;
  studioImagesDesc: string;
  studioVideo: string;
  studioVideoDesc: string;
  studioArchive: string;
  studioArchiveDesc: string;
  studioVideoArchive: string;
  studioVideoArchiveDesc: string;
  studioAiEngine: string;
  studioReference: string;
  studioReferences: string;
  studioCharacter: string;
  studioFormat: string;
  studioGenerate: string;
  studioGenerating: string;
  studioGeneratingSub: string;
  studioResult: string;
  studioCarouselCount: string;
  studioEditNeedsRef: string;
  studioYes: string;
  studioNo: string;
  studioUploadImage: string;
  studioUploadVideo: string;
  studioVideoUploaded: string;
  studioFirstFrame: string;
  studioReferenceVideo: string;
  studioContentType: string;
  studioCreateVideo: string;
  studioMotionControl: string;
  studioMotionControlDesc: string;
  studioPromptMode: string;
  studioPromptModeDesc: string;
  studioDownload: string;
  studioDownloadMp4: string;
  studioRegen: string;
  commonSave: string;
  commonDelete: string;
  commonSend: string;
  commonAll: string;
  commonModify: string;
  commonDraft: string;
  commonShowMore: string;
  commonSelectFile: string;
  commonUploaded: string;
  commonSaving: string;
  overviewHello: string;
  kpiCredits: string;
  kpiPlan: string;
  kpiDonations: string;
  kpiDialogs: string;
  sectionStudioWhat: string;
  sectionRecentDialogs: string;
  noDialogs: string;
  folderTitle: string;
  folderNotFound: string;
  folderEditTitle: string;
  folderNewTitle: string;
  folderAddTitle: string;
  folderNameLabel: string;
  folderNamePlaceholder: string;
  folderNameExample: string;
  folderChatsInFolder: string;
  folderAddChats: string;
  dialogTitle: string;
  archiveItemTitle: string;
  archiveRetention: string;
  studioEditPromptPlaceholder: string;
  studioQuality: string;
  studioDuration: string;
  studioSecondsSuffix: string;
  studioHasFirstFrame: string;
  studioYesGenerate: string;
  studioGenerateFirstFrameBtn: string;
  studioGeneratingFirstFrame: string;
  studioFirstFrameReady: string;
  studioRegenerateFirstFrame: string;
  studioReferenceAudio: string;
  studioRenderingVideo: string;
  charNewTitle: string;
  charNameLabel: string;
  charFirstPhoto: string;
  charPhotoTag: string;
  charCreate: string;
  charTabPhotos: string;
  charTabPersona: string;
  charTabExif: string;
  charTabHistory: string;
  charAgeCity: string;
  charCharacter: string;
  charChatStyle: string;
  charExifDesc: string;
  charExifPhoneRefs: string;
  charFrontCamera: string;
  charMainCamera: string;
  charJpegHint: string;
  charMainCameraHint: string;
  charCameraPreset: string;
  charGeo: string;
  charNoGenerations: string;
  charPhotoRefs: string;
  charUploadPickTag: string;
  charAppearance: string;
  charAnalyzing: string;
  charGenFromPhoto: string;
  charDescUpdated: string;
  charUploadPhoto: string;
  sectionAccount: string;
  profileEditTitle: string;
  profileChangePassword: string;
  profileCurrentPassword: string;
  profileNewPassword: string;
  profileConfirmPassword: string;
  profileChangePasswordBtn: string;
  connCurrentSetup: string;
  connActive: string;
  connRemove: string;
  connNoActive: string;
  connAddUpdate: string;
  connApiKey: string;
  connApiKeyWs: string;
  connApiKeyPlaceholder: string;
  connWsHint: string;
  connSaveKey: string;
  connSaveFailed: string;
  connWsSaved: string;
  connTgSaved: string;
  connTrSaved: string;
  connCharacter: string;
  billingCredits: string;
  billingHistory: string;
  billingHistoryEmpty: string;
  donationsTotal: string;
  donationsAvailable: string;
  donationsWithdraw: string;
  donationsUsdt: string;
  donationsPayout: string;
  donationsLinks: string;
  donationsMin: string;
  donationsNone: string;
  donationsRecent: string;
  donationsNoEvents: string;
  donationNew: string;
  donationTitle: string;
  donationDesc: string;
  donationMinAmount: string;
  donationModeration: string;
  teamRepliesMonth: string;
  teamMembers: string;
  teamAddOperator: string;
  teamEditOperator: string;
  teamNewOperator: string;
  teamLogin: string;
  teamPassword: string;
  teamNewPasswordOptional: string;
  teamAccessRights: string;
  teamSaveChanges: string;
  teamCreateMember: string;
  teamDeleteMember: string;
  supportTitle: string;
  supportDesc: string;
  supportNewTicket: string;
  supportTicketType: string;
  supportSubject: string;
  supportMessage: string;
  supportSend: string;
  supportYourTickets: string;
  supportNoTickets: string;
  ticketTitle: string;
  errSelectCharacter: string;
  errUploadFirstFrame: string;
  errUploadRefVideo: string;
  errGenPending: string;
  errGenFailed: string;
  errorTitle: string;
  errorDismiss: string;
  errEnterPrompt: string;
  errUploadReference: string;
  errUploadSceneRef: string;
  errUploadOutfitCloth: string;
  errUploadLocationRef: string;
  errUploadEditFrame: string;
  errUploadEditDetailRef: string;
  errPromptOnlyVideo: string;
  folderCreate: string;
  folderCreateFirst: string;
  dialogNotFound: string;
  archiveToVideo: string;
  billingUntil: string;
  connApiKeyToken: string;
  connFvSaved: string;
  connConnectFanvue: string;
  charDelete: string;
  charDeleteConfirm: string;
  charDeletePhotoConfirm: string;
  charRenameLabel: string;
  charRenameSave: string;
  studioSrcUpload: string;
  studioSrcArchive: string;
  ticketReplyPlaceholder: string;
  commonCancel: string;
  downloadFailed: string;
  charBootstrapTitle: string;
  charBootstrapFaceTitle: string;
  charBootstrapFaceDesc: string;
  charBootstrapFaceWarn: string;
  charBootstrapFace1: string;
  charBootstrapFace2: string;
  charBootstrapGenerate: string;
  charBootstrapFaceLoading: string;
  charBootstrapFaceLoadingSub: string;
  charBootstrapResult: string;
  charBootstrapRegenerate: string;
  charBootstrapUseThis: string;
  charBootstrapFaceSaved: string;
  charBootstrapBodyTitle: string;
  charBootstrapBodyDesc: string;
  charBootstrapBody: string;
  charBootstrapBodyLoading: string;
  charBootstrapBodyLoadingSub: string;
  charBootstrapSave: string;
  charBootstrapDone: string;
  charBootstrapErrTwoFaces: string;
  charBootstrapErrFaceResult: string;
  charBootstrapErrBodyRef: string;
  charBootstrapErrBodyResult: string;
};

const RU: Strings = {
  navOverview: 'Обзор',
  navDialogs: 'Диалоги',
  navStudio: 'Студия',
  navCharacters: 'Персонажи',
  navProfile: 'Профиль',
  navBilling: 'Тариф и баланс',
  navDonations: 'Донаты и выплаты',
  navConnections: 'Подключения',
  navTeam: 'Команда',
  profileTitle: 'Профиль',
  owner: 'Владелец',
  member: 'Участник',
  sectionWorkspace: 'WORKSPACE',
  sectionSystem: 'СИСТЕМА',
  settingsTitle: 'Настройки',
  settingsLanguage: 'Язык',
  settingsLanguageRu: 'Русский',
  settingsLanguageEn: 'English',
  settingsLanguageHint: 'Интерфейс приложения. Диалоги с фанами переводятся отдельно.',
  settingsBiometric: 'Face ID / биометрия',
  settingsBiometricHint: 'Проверка отпечатка или Face ID при входе в приложение.',
  settingsBiometricTest: 'Проверить сейчас',
  settingsBiometricUnavailable: 'Биометрия недоступна на этом устройстве.',
  settingsBiometricLock: 'Запрашивать при открытии',
  settingsBiometricLockHint: 'После фона — экран блокировки с биометрией.',
  settingsPush: 'Push-уведомления',
  settingsPushHint: 'Новые сообщения, донаты и статус генераций.',
  settingsPushEnabled: 'Уведомления включены',
  settingsPushDisabled: 'Уведомления выключены',
  settingsSaved: 'Сохранено',
  adminPanel: 'Admin-панель',
  logout: 'Выйти',
  authLogin: 'Вход',
  authRegister: 'Регистрация',
  authEmail: 'EMAIL',
  authPassword: 'ПАРОЛЬ',
  authPasswordHint: 'Минимум 8 символов',
  authEnter: 'Войти',
  authRegisterBtn: 'Зарегистрироваться',
  authEntering: 'Вход…',
  authRegistering: 'Регистрация…',
  authOrEmail: 'или email',
  authTelegramLogin: 'Войти через Telegram',
  authTelegramRegister: 'Зарегистрироваться через Telegram',
  authBiometric: 'Войти по Face ID / отпечатку',
  authNoAccount: 'Нет аккаунта? ',
  authHasAccount: 'Уже есть аккаунт? ',
  studioTitle: 'Студия',
  studioImages: 'Картинки',
  studioImagesDesc: '6 режимов генерации',
  studioVideo: 'Видео',
  studioVideoDesc: 'Оживить кадр',
  studioArchive: 'Архив',
  studioArchiveDesc: 'Все сгенерированные кадры',
  studioVideoArchive: 'Архив видео',
  studioVideoArchiveDesc: 'Все сгенерированные видео',
  studioAiEngine: 'AI-ДВИЖОК',
  studioReference: 'РЕФЕРЕНС',
  studioReferences: 'РЕФЕРЕНСЫ',
  studioCharacter: 'ПЕРСОНАЖ',
  studioFormat: 'ФОРМАТ',
  studioGenerate: 'Сгенерировать',
  studioGenerating: 'Генерируем…',
  studioGeneratingSub: '~10 c',
  studioResult: 'Результат',
  studioCarouselCount: 'КОЛИЧЕСТВО КАДРОВ',
  studioEditNeedsRef: 'Нужен референс?',
  studioYes: 'Да',
  studioNo: 'Нет',
  studioUploadImage: 'Загрузить изображение',
  studioUploadVideo: 'Загрузить видео',
  studioVideoUploaded: 'Видео загружено',
  studioFirstFrame: 'ПЕРВЫЙ КАДР',
  studioReferenceVideo: 'РЕФЕРЕНСНОЕ ВИДЕО',
  studioContentType: 'ТИП КОНТЕНТА',
  studioCreateVideo: 'Создать видео',
  studioMotionControl: 'Motion control',
  studioMotionControlDesc: 'Повтор движения из референс-ролика',
  studioPromptMode: 'По промпту',
  studioPromptModeDesc: 'Видео из текстового описания',
  studioDownload: 'Скачать',
  studioDownloadMp4: 'Скачать MP4',
  studioRegen: '↻ Ещё раз',
  commonSave: 'Сохранить',
  commonDelete: 'Удалить',
  commonSend: 'Отправить',
  commonAll: 'Все',
  commonModify: 'Изменить',
  commonDraft: 'Черновик',
  commonShowMore: 'Показать ещё',
  commonSelectFile: 'Выберите файл',
  commonUploaded: 'Загружено',
  commonSaving: 'Сохранение…',
  overviewHello: 'Привет,',
  kpiCredits: 'КРЕДИТЫ',
  kpiPlan: 'ПОДПИСКА',
  kpiDonations: 'ДОНАТЫ',
  kpiDialogs: 'ДИАЛОГИ',
  sectionStudioWhat: 'СТУДИЯ — ЧТО СДЕЛАТЬ?',
  sectionRecentDialogs: 'НЕДАВНИЕ ДИАЛОГИ',
  noDialogs: 'Нет диалогов',
  folderTitle: 'Папка',
  folderNotFound: 'Папка не найдена',
  folderEditTitle: 'Редактировать папку',
  folderNewTitle: 'Новая папка',
  folderAddTitle: 'Добавить в папку',
  folderNameLabel: 'НАЗВАНИЕ ПАПКИ',
  folderNamePlaceholder: 'Название',
  folderNameExample: 'Например: Постоянные',
  folderChatsInFolder: 'ЧАТЫ В ПАПКЕ',
  folderAddChats: 'ДОБАВИТЬ ЧАТЫ В ПАПКУ',
  dialogTitle: 'Диалог',
  archiveItemTitle: 'Кадр',
  archiveRetention: '⏳ хранится ~4 дня',
  studioEditPromptPlaceholder: 'Например: добавь солнцезащитные очки, убери фон…',
  studioQuality: 'КАЧЕСТВО',
  studioDuration: 'ДЛИТЕЛЬНОСТЬ',
  studioSecondsSuffix: 'с',
  studioHasFirstFrame: 'ПЕРВЫЙ КАДР ЕСТЬ?',
  studioYesGenerate: 'Нет — сгенерировать',
  studioGenerateFirstFrameBtn: '✦ Сгенерировать первый кадр · −10 кр.',
  studioGeneratingFirstFrame: 'Генерируем первый кадр…',
  studioFirstFrameReady: '✓ Первый кадр готов',
  studioRegenerateFirstFrame: '↻ Перегенерировать',
  studioReferenceAudio: 'ЗВУК С РЕФЕРЕНС-ВИДЕО',
  studioRenderingVideo: 'Рендерим видео…',
  charNewTitle: 'Новый персонаж',
  charNameLabel: 'ИМЯ ПЕРСОНАЖА',
  charFirstPhoto: 'ПЕРВОЕ ФОТО',
  charPhotoTag: 'ТЕГ ФОТО',
  charCreate: 'Создать персонажа',
  charTabPhotos: 'Фото',
  charTabPersona: 'Персона',
  charTabExif: 'EXIF',
  charTabHistory: 'История',
  charAgeCity: 'ВОЗРАСТ / ГОРОД',
  charCharacter: 'ХАРАКТЕР',
  charChatStyle: 'СТИЛЬ ПЕРЕПИСКИ',
  charExifDesc: 'EXIF применяется к сохранённым кадрам студии. Загрузите эталоны с телефона или задайте пресет.',
  charExifPhoneRefs: 'ЭТАЛОНЫ EXIF С ТЕЛЕФОНА',
  charFrontCamera: 'ФРОНТАЛЬНАЯ КАМЕРА',
  charMainCamera: 'ОСНОВНАЯ КАМЕРА',
  charJpegHint: 'JPEG из галереи',
  charMainCameraHint: 'Фото с основной камеры',
  charCameraPreset: 'ПРЕСЕТ КАМЕРЫ',
  charGeo: 'ГЕО (ШИРОТА/ДОЛГОТА)',
  charNoGenerations: 'Пока нет генераций',
  charPhotoRefs: 'ФОТО-РЕФЕРЕНСЫ',
  charUploadPickTag: 'Загрузить фото и выбрать тег',
  charAppearance: 'ОПИСАНИЕ ВНЕШНОСТИ',
  charAnalyzing: 'Анализируем фото…',
  charGenFromPhoto: '✦ Сгенерировать из фото',
  charDescUpdated: '✓ Описание обновлено из фото',
  charUploadPhoto: 'Сохранить фото',
  sectionAccount: 'АККАУНТ',
  profileEditTitle: 'Редактировать профиль',
  profileChangePassword: 'СМЕНА ПАРОЛЯ',
  profileCurrentPassword: 'Текущий пароль',
  profileNewPassword: 'Новый пароль',
  profileConfirmPassword: 'Повторите пароль',
  profileChangePasswordBtn: 'Сменить пароль',
  connCurrentSetup: 'ТЕКУЩАЯ НАСТРОЙКА',
  connActive: 'АКТИВНЫЕ ПОДКЛЮЧЕНИЯ',
  connRemove: 'Удалить',
  connNoActive: 'Нет активных подключений',
  connAddUpdate: 'ДОБАВИТЬ / ОБНОВИТЬ',
  connApiKey: 'API-КЛЮЧ',
  connApiKeyWs: 'API-КЛЮЧ WAVESPEED',
  connApiKeyPlaceholder: 'Вставьте ключ из wavespeed.ai',
  connWsHint: 'На Pro нужен ваш API-ключ WaveSpeed. На Standard платформа может использовать свой ключ.',
  connSaveKey: 'Сохранить ключ',
  connSaveFailed: 'Не удалось сохранить. Проверьте ключ и попробуйте снова.',
  connWsSaved: 'Ключ WaveSpeed сохранён.',
  connTgSaved: 'Telegram-бот подключён.',
  connTrSaved: 'Tribute API настроен.',
  connCharacter: 'ПЕРСОНАЖ',
  billingCredits: 'кредитов',
  billingHistory: 'ИСТОРИЯ ОПЕРАЦИЙ',
  billingHistoryEmpty: 'История пуста',
  donationsTotal: 'ВСЕГО',
  donationsAvailable: 'ДОСТУПНО',
  donationsWithdraw: 'ВЫВОД СРЕДСТВ',
  donationsUsdt: 'АДРЕС USDT (TRC20)',
  donationsPayout: 'Заявка на выплату',
  donationsLinks: 'ССЫЛКИ НА ДОНАТ',
  donationsMin: 'Мин.',
  donationsNone: 'Нет донатов',
  donationsRecent: 'ПОСЛЕДНИЕ ПОСТУПЛЕНИЯ',
  donationsNoEvents: 'Пока нет поступлений',
  donationNew: 'Новый донат',
  donationTitle: 'ЗАГОЛОВОК',
  donationDesc: 'ОПИСАНИЕ',
  donationMinAmount: 'МИН. СУММА',
  donationModeration: 'На модерацию',
  teamRepliesMonth: 'ОТВЕТЫ / МЕС',
  teamMembers: 'УЧАСТНИКИ',
  teamAddOperator: '+ Добавить оператора',
  teamEditOperator: 'Редактировать оператора',
  teamNewOperator: 'Новый оператор',
  teamLogin: 'ЛОГИН',
  teamPassword: 'ПАРОЛЬ',
  teamNewPasswordOptional: 'НОВЫЙ ПАРОЛЬ (необязательно)',
  teamAccessRights: 'ПРАВА ДОСТУПА',
  teamSaveChanges: 'Сохранить изменения',
  teamCreateMember: 'Создать участника',
  teamDeleteMember: 'Удалить участника',
  supportTitle: 'Поддержка',
  supportDesc: 'Создавайте обращения и следите за статусом ответа.',
  supportNewTicket: '+ Новое обращение',
  supportTicketType: 'ТИП ОБРАЩЕНИЯ',
  supportSubject: 'Тема обращения',
  supportMessage: 'Сообщение',
  supportSend: 'Отправить',
  supportYourTickets: 'ВАШИ ОБРАЩЕНИЯ',
  supportNoTickets: 'Пока нет обращений',
  ticketTitle: 'Обращение',
  errSelectCharacter: 'Выберите персонажа',
  errUploadFirstFrame: 'Загрузите первый кадр',
  errUploadRefVideo: 'Загрузите референс-видео',
  errGenPending: 'Генерация создана, но результат ещё не готов. Проверьте архив через минуту.',
  errGenFailed: 'Не удалось получить результат генерации.',
  errorTitle: 'Ошибка',
  errorDismiss: 'Понятно',
  errEnterPrompt: 'Опишите, что нужно сгенерировать',
  errUploadReference: 'Загрузите или выберите референс из архива',
  errUploadSceneRef: 'Загрузите кадр сцены (референс позы и ракурса)',
  errUploadOutfitCloth: 'Загрузите референс одежды',
  errUploadLocationRef: 'Загрузите референс локации',
  errUploadEditFrame: 'Загрузите кадр, который нужно изменить',
  errUploadEditDetailRef: 'Загрузите референс детали',
  errPromptOnlyVideo: 'Опишите движение в текстовом поле',
  folderCreate: 'Создать папку',
  folderCreateFirst: 'Сначала создайте папку',
  dialogNotFound: 'Диалог не найден',
  archiveToVideo: 'В видео',
  billingUntil: 'до',
  connApiKeyToken: 'API-КЛЮЧ / ТОКЕН',
  connFvSaved: 'Fanvue подключён.',
  connConnectFanvue: 'Подключить Fanvue',
  charDelete: 'Удалить персонажа',
  charDeleteConfirm: 'Удалить персонажа и все его данные? Это действие нельзя отменить.',
  charDeletePhotoConfirm: 'Удалить это фото из галереи персонажа?',
  charRenameLabel: 'ИМЯ',
  charRenameSave: 'Сохранить имя',
  studioSrcUpload: 'Загрузить',
  studioSrcArchive: 'Из архива',
  ticketReplyPlaceholder: 'Ваш ответ…',
  commonCancel: 'Отмена',
  downloadFailed: 'Ошибка скачивания',
  charBootstrapTitle: '✦ Сгенерировать изображение?',
  charBootstrapFaceTitle: 'Соберём новое лицо',
  charBootstrapFaceDesc: 'Загрузите 2 фото лиц — мы соберём из них новое уникальное лицо для персонажа.',
  charBootstrapFaceWarn: '⚠ Берите качественные фото в хорошем разрешении — от этого зависит результат.',
  charBootstrapFace1: 'Лицо 1',
  charBootstrapFace2: 'Лицо 2',
  charBootstrapGenerate: 'Сгенерировать',
  charBootstrapFaceLoading: 'Собираем лицо…',
  charBootstrapFaceLoadingSub: 'Nano Banana Pro · ~12 c',
  charBootstrapResult: 'Результат',
  charBootstrapRegenerate: '↻ Перегенерировать',
  charBootstrapUseThis: '✓ Использовать эту',
  charBootstrapFaceSaved: '✓ Лицо сохранено',
  charBootstrapBodyTitle: 'Теперь тело',
  charBootstrapBodyDesc: 'Загрузите референс тела, какое хотите видеть у модели — мы соберём фото с этим лицом и телом.',
  charBootstrapBody: 'Тело',
  charBootstrapBodyLoading: 'Собираем тело…',
  charBootstrapBodyLoadingSub: 'Seedream 5 Pro · ~15 c',
  charBootstrapSave: '💾 Сохранить',
  charBootstrapDone: '✓ Лицо и тело сохранены в галерею персонажа',
  charBootstrapErrTwoFaces: 'Загрузите 2 фото лиц',
  charBootstrapErrFaceResult: 'Не удалось получить изображение лица',
  charBootstrapErrBodyRef: 'Загрузите референс тела',
  charBootstrapErrBodyResult: 'Не удалось получить изображение тела',
};

const EN: Strings = {
  navOverview: 'Overview',
  navDialogs: 'Dialogs',
  navStudio: 'Studio',
  navCharacters: 'Characters',
  navProfile: 'Profile',
  navBilling: 'Plan & balance',
  navDonations: 'Donations & payouts',
  navConnections: 'Connections',
  navTeam: 'Team',
  profileTitle: 'Profile',
  owner: 'Owner',
  member: 'Member',
  sectionWorkspace: 'WORKSPACE',
  sectionSystem: 'SYSTEM',
  settingsTitle: 'Settings',
  settingsLanguage: 'Language',
  settingsLanguageRu: 'Russian',
  settingsLanguageEn: 'English',
  settingsLanguageHint: 'App UI language. Fan chat translation is separate.',
  settingsBiometric: 'Face ID / biometrics',
  settingsBiometricHint: 'Use fingerprint or Face ID when opening the app.',
  settingsBiometricTest: 'Test now',
  settingsBiometricUnavailable: 'Biometrics are not available on this device.',
  settingsBiometricLock: 'Require on app open',
  settingsBiometricLockHint: 'After backgrounding — lock screen with biometrics.',
  settingsPush: 'Push notifications',
  settingsPushHint: 'New messages, donations and generation status.',
  settingsPushEnabled: 'Notifications enabled',
  settingsPushDisabled: 'Notifications disabled',
  settingsSaved: 'Saved',
  adminPanel: 'Admin panel',
  logout: 'Sign out',
  authLogin: 'Sign in',
  authRegister: 'Register',
  authEmail: 'EMAIL',
  authPassword: 'PASSWORD',
  authPasswordHint: 'At least 8 characters',
  authEnter: 'Sign in',
  authRegisterBtn: 'Create account',
  authEntering: 'Signing in…',
  authRegistering: 'Registering…',
  authOrEmail: 'or email',
  authTelegramLogin: 'Sign in with Telegram',
  authTelegramRegister: 'Register with Telegram',
  authBiometric: 'Sign in with Face ID / fingerprint',
  authNoAccount: 'No account? ',
  authHasAccount: 'Already have an account? ',
  studioTitle: 'Studio',
  studioImages: 'Images',
  studioImagesDesc: '6 generation modes',
  studioVideo: 'Video',
  studioVideoDesc: 'Animate a frame',
  studioArchive: 'Archive',
  studioArchiveDesc: 'All generated frames',
  studioVideoArchive: 'Video archive',
  studioVideoArchiveDesc: 'All generated videos',
  studioAiEngine: 'AI ENGINE',
  studioReference: 'REFERENCE',
  studioReferences: 'REFERENCES',
  studioCharacter: 'CHARACTER',
  studioFormat: 'FORMAT',
  studioGenerate: 'Generate',
  studioGenerating: 'Generating…',
  studioGeneratingSub: '~10 s',
  studioResult: 'Result',
  studioCarouselCount: 'FRAME COUNT',
  studioEditNeedsRef: 'Need a reference?',
  studioYes: 'Yes',
  studioNo: 'No',
  studioUploadImage: 'Upload image',
  studioUploadVideo: 'Upload video',
  studioVideoUploaded: 'Video uploaded',
  studioFirstFrame: 'FIRST FRAME',
  studioReferenceVideo: 'REFERENCE VIDEO',
  studioContentType: 'CONTENT TYPE',
  studioCreateVideo: 'Create video',
  studioMotionControl: 'Motion control',
  studioMotionControlDesc: 'Repeat motion from reference clip',
  studioPromptMode: 'From prompt',
  studioPromptModeDesc: 'Video from text description',
  studioDownload: 'Download',
  studioDownloadMp4: 'Download MP4',
  studioRegen: '↻ Again',
  commonSave: 'Save',
  commonDelete: 'Delete',
  commonSend: 'Send',
  commonAll: 'All',
  commonModify: 'Edit',
  commonDraft: 'Draft',
  commonShowMore: 'Show more',
  commonSelectFile: 'Choose file',
  commonUploaded: 'Uploaded',
  commonSaving: 'Saving…',
  overviewHello: 'Hi,',
  kpiCredits: 'CREDITS',
  kpiPlan: 'PLAN',
  kpiDonations: 'DONATIONS',
  kpiDialogs: 'DIALOGS',
  sectionStudioWhat: 'STUDIO — WHAT TO CREATE?',
  sectionRecentDialogs: 'RECENT DIALOGS',
  noDialogs: 'No dialogs yet',
  folderTitle: 'Folder',
  folderNotFound: 'Folder not found',
  folderEditTitle: 'Edit folder',
  folderNewTitle: 'New folder',
  folderAddTitle: 'Add to folder',
  folderNameLabel: 'FOLDER NAME',
  folderNamePlaceholder: 'Name',
  folderNameExample: 'e.g. Regulars',
  folderChatsInFolder: 'CHATS IN FOLDER',
  folderAddChats: 'ADD CHATS TO FOLDER',
  dialogTitle: 'Dialog',
  archiveItemTitle: 'Frame',
  archiveRetention: '⏳ stored ~4 days',
  studioEditPromptPlaceholder: 'e.g. add sunglasses, remove background…',
  studioQuality: 'QUALITY',
  studioDuration: 'DURATION',
  studioSecondsSuffix: 's',
  studioHasFirstFrame: 'HAVE A FIRST FRAME?',
  studioYesGenerate: 'No — generate',
  studioGenerateFirstFrameBtn: '✦ Generate first frame · −10 cr.',
  studioGeneratingFirstFrame: 'Generating first frame…',
  studioFirstFrameReady: '✓ First frame ready',
  studioRegenerateFirstFrame: '↻ Regenerate',
  studioReferenceAudio: 'AUDIO FROM REFERENCE VIDEO',
  studioRenderingVideo: 'Rendering video…',
  charNewTitle: 'New character',
  charNameLabel: 'CHARACTER NAME',
  charFirstPhoto: 'FIRST PHOTO',
  charPhotoTag: 'PHOTO TAG',
  charCreate: 'Create character',
  charTabPhotos: 'Photos',
  charTabPersona: 'Persona',
  charTabExif: 'EXIF',
  charTabHistory: 'History',
  charAgeCity: 'AGE / CITY',
  charCharacter: 'PERSONALITY',
  charChatStyle: 'CHAT STYLE',
  charExifDesc: 'EXIF is applied to saved studio frames. Upload phone references or set a preset.',
  charExifPhoneRefs: 'PHONE EXIF REFERENCES',
  charFrontCamera: 'FRONT CAMERA',
  charMainCamera: 'MAIN CAMERA',
  charJpegHint: 'JPEG from gallery',
  charMainCameraHint: 'Photo from main camera',
  charCameraPreset: 'CAMERA PRESET',
  charGeo: 'GEO (LAT/LON)',
  charNoGenerations: 'No generations yet',
  charPhotoRefs: 'PHOTO REFERENCES',
  charUploadPickTag: 'Upload photo and pick tag',
  charAppearance: 'APPEARANCE DESCRIPTION',
  charAnalyzing: 'Analyzing photos…',
  charGenFromPhoto: '✦ Generate from photos',
  charDescUpdated: '✓ Description updated from photos',
  charUploadPhoto: 'Save photo',
  sectionAccount: 'ACCOUNT',
  profileEditTitle: 'Edit profile',
  profileChangePassword: 'CHANGE PASSWORD',
  profileCurrentPassword: 'Current password',
  profileNewPassword: 'New password',
  profileConfirmPassword: 'Confirm password',
  profileChangePasswordBtn: 'Change password',
  connCurrentSetup: 'CURRENT SETUP',
  connActive: 'ACTIVE CONNECTIONS',
  connRemove: 'Remove',
  connNoActive: 'No active connections',
  connAddUpdate: 'ADD / UPDATE',
  connApiKey: 'API KEY',
  connApiKeyWs: 'WAVESPEED API KEY',
  connApiKeyPlaceholder: 'Paste key from wavespeed.ai',
  connWsHint: 'Pro requires your WaveSpeed API key. Standard may use the platform key.',
  connSaveKey: 'Save key',
  connSaveFailed: 'Could not save. Check the key and try again.',
  connWsSaved: 'WaveSpeed key saved.',
  connTgSaved: 'Telegram bot connected.',
  connTrSaved: 'Tribute API configured.',
  connCharacter: 'CHARACTER',
  billingCredits: 'credits',
  billingHistory: 'TRANSACTION HISTORY',
  billingHistoryEmpty: 'No transactions yet',
  donationsTotal: 'TOTAL',
  donationsAvailable: 'AVAILABLE',
  donationsWithdraw: 'WITHDRAW',
  donationsUsdt: 'USDT ADDRESS (TRC20)',
  donationsPayout: 'Request payout',
  donationsLinks: 'DONATION LINKS',
  donationsMin: 'Min.',
  donationsNone: 'No donations',
  donationsRecent: 'RECENT PAYMENTS',
  donationsNoEvents: 'No payments yet',
  donationNew: 'New donation',
  donationTitle: 'TITLE',
  donationDesc: 'DESCRIPTION',
  donationMinAmount: 'MIN. AMOUNT',
  donationModeration: 'Submit for review',
  teamRepliesMonth: 'REPLIES / MO',
  teamMembers: 'MEMBERS',
  teamAddOperator: '+ Add operator',
  teamEditOperator: 'Edit operator',
  teamNewOperator: 'New operator',
  teamLogin: 'LOGIN',
  teamPassword: 'PASSWORD',
  teamNewPasswordOptional: 'NEW PASSWORD (optional)',
  teamAccessRights: 'ACCESS RIGHTS',
  teamSaveChanges: 'Save changes',
  teamCreateMember: 'Create member',
  teamDeleteMember: 'Remove member',
  supportTitle: 'Support',
  supportDesc: 'Create tickets and track response status.',
  supportNewTicket: '+ New ticket',
  supportTicketType: 'TICKET TYPE',
  supportSubject: 'Subject',
  supportMessage: 'Message',
  supportSend: 'Send',
  supportYourTickets: 'YOUR TICKETS',
  supportNoTickets: 'No tickets yet',
  ticketTitle: 'Ticket',
  errSelectCharacter: 'Select a character',
  errUploadFirstFrame: 'Upload a first frame',
  errUploadRefVideo: 'Upload a reference video',
  errGenPending: 'Generation started but result is not ready yet. Check archive in a minute.',
  errGenFailed: 'Could not get generation result.',
  errorTitle: 'Error',
  errorDismiss: 'Got it',
  errEnterPrompt: 'Describe what you want to generate',
  errUploadReference: 'Upload or pick a reference from archive',
  errUploadSceneRef: 'Upload a scene frame (pose and camera reference)',
  errUploadOutfitCloth: 'Upload a clothing reference',
  errUploadLocationRef: 'Upload a location reference',
  errUploadEditFrame: 'Upload the frame to edit',
  errUploadEditDetailRef: 'Upload a detail reference',
  errPromptOnlyVideo: 'Describe the motion in the text field',
  folderCreate: 'Create folder',
  folderCreateFirst: 'Create a folder first',
  dialogNotFound: 'Dialog not found',
  archiveToVideo: 'To video',
  billingUntil: 'until',
  connApiKeyToken: 'API KEY / TOKEN',
  connFvSaved: 'Fanvue connected.',
  connConnectFanvue: 'Connect Fanvue',
  charDelete: 'Delete character',
  charDeleteConfirm: 'Delete this character and all related data? This cannot be undone.',
  charDeletePhotoConfirm: 'Remove this photo from the character gallery?',
  charRenameLabel: 'NAME',
  charRenameSave: 'Save name',
  studioSrcUpload: 'Upload',
  studioSrcArchive: 'From archive',
  ticketReplyPlaceholder: 'Your reply…',
  commonCancel: 'Cancel',
  downloadFailed: 'Download failed',
  charBootstrapTitle: '✦ Generate image?',
  charBootstrapFaceTitle: 'Build a new face',
  charBootstrapFaceDesc: 'Upload 2 face photos — we will merge them into a unique face for your character.',
  charBootstrapFaceWarn: '⚠ Use high-quality photos — the result depends on input quality.',
  charBootstrapFace1: 'Face 1',
  charBootstrapFace2: 'Face 2',
  charBootstrapGenerate: 'Generate',
  charBootstrapFaceLoading: 'Building face…',
  charBootstrapFaceLoadingSub: 'Nano Banana Pro · ~12 s',
  charBootstrapResult: 'Result',
  charBootstrapRegenerate: '↻ Regenerate',
  charBootstrapUseThis: '✓ Use this one',
  charBootstrapFaceSaved: '✓ Face saved',
  charBootstrapBodyTitle: 'Now the body',
  charBootstrapBodyDesc: 'Upload a body reference — we will compose a photo with the saved face and this body.',
  charBootstrapBody: 'Body',
  charBootstrapBodyLoading: 'Building body…',
  charBootstrapBodyLoadingSub: 'Seedream 5 Pro · ~15 s',
  charBootstrapSave: '💾 Save',
  charBootstrapDone: '✓ Face and body saved to character gallery',
  charBootstrapErrTwoFaces: 'Upload 2 face photos',
  charBootstrapErrFaceResult: 'Could not get face image',
  charBootstrapErrBodyRef: 'Upload a body reference',
  charBootstrapErrBodyResult: 'Could not get body image',
};

export const dict: Record<AppLocale, Strings> = { ru: RU, en: EN };

export function languageLabel(locale: AppLocale, t: Strings): string {
  return locale === 'en' ? t.settingsLanguageEn : t.settingsLanguageRu;
}

export function settingsLanguageRow(locale: AppLocale, t: Strings): string {
  return `${t.settingsLanguage} — ${languageLabel(locale, t)}`;
}
