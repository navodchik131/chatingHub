import fs from 'fs'

const file = 'src/App.tsx'
let s = fs.readFileSync(file, 'utf8')

const pairs = [
  ['Авто/час', "{t('integrationsExt.autoPerHour')}"],
  ['История', "{t('integrationsExt.history')}"],
  ['Копировать', "{t('integrationsExt.copy')}"],
  ["{conn.label ? conn.label : `Подключение #${conn.id}`}", "{conn.label ? conn.label : t('integrationsExt.connectionN', { id: conn.id })}"],
  ['Webhook URL (Tribute → Настройки → Webhooks)', "{t('integrationsExt.webhookUrlTribute')}"],
  ['Метка (необязательно)', "{t('integrationsExt.labelOptional')}"],
  ['placeholder="Например: Mia Tribute"', 'placeholder={t(\'integrationsExt.labelPh\')}'],
  ['API-ключ Tribute', "{t('integrationsExt.tributeApiKey')}"],
  ['placeholder="Api-Key из Tribute → Настройки → API Keys"', 'placeholder={t(\'integrationsExt.tributeApiKeyPh\')}'],
  ["{tributeEditConnectionId != null ? 'Сохранить ключ' : 'Добавить Tribute'}", "{tributeEditConnectionId != null ? t('integrationsExt.saveTributeKey') : t('integrationsExt.addTribute')}"],
  ['API-ключ', "{t('integrationsExt.llmApiKey')}"],
  ['Включить уведомления', "{t('integrationsExt.pushEnable')}"],
  ['Отменить', "{tCommon('cancel')}"],
  ['Название', "{t('modelsExt.nameLabel')}"],
  [
    'Личность для чат-бота: где живёт, интересы, стиль общения. Бот использует это вместе с\n                            описанием внешности.',
    "{t('modelsExt.personaLead')}",
  ],
  ['Возраст', "{t('modelsExt.age')}"],
  ['Город', "{t('modelsExt.city')}"],
  ['Страна', "{t('modelsExt.country')}"],
  ['Часовой пояс', "{t('modelsExt.timezone')}"],
  ['Характер', "{t('modelsExt.personality')}"],
  ['Образ жизни', "{t('modelsExt.lifestyle')}"],
  ['Предыстория', "{t('modelsExt.backstory')}"],
  ['Сбросить', "{tCommon('reset')}"],
  ["? 'Чтение…'", "? tCommon('reading')"],
  ["? 'Заменить'", "? tCommon('replace')"],
  [": 'Загрузить'}", ": tCommon('upload')}"],
  ['Широта', "{t('modelsExt.latitude')}"],
  ['Долгота', "{t('modelsExt.longitude')}"],
  ['Добавить', "{tCommon('add')}"],
  ['Удалить', "{tc('templates.delete')}"],
  ['Модели студии', "{t('modelsExt.studioModels')}"],
  ['Доля Tribute в KPI, %', "{t('modelsExt.teamTributeShare')}"],
  ['userMeta={`${me?.credits_balance ?? 0} кр. · ${planDisplayShort(me)}`}', 'userMeta={t(\'shell.creditsMeta\', { credits: me?.credits_balance ?? 0, plan: planDisplayShort(me) })}'],
  [
    'Режим: {health.mode ?? \'—\'} · всего в БД: {health.conversations_count ?? 0} диалогов,{\' \'}\n          {health.messages_count ?? 0} сообщений',
    "{t('health.modeLine', { mode: health.mode ?? '—', conversations: health.conversations_count ?? 0, messages: health.messages_count ?? 0 })}",
  ],
  ['· студия: промпт ({health.studio_prompt_credit_cost ?? \'—\'} кр.)', "{t('health.studioPromptOk', { credits: health.studio_prompt_credit_cost ?? '—' })}"],
  ['Картинка', "{ts('imageUi.outputImage')}"],
  ['Только промпт', "{ts('imageUi.outputPromptOnly')}"],
  [
    '<p className="studio-mode-hint">\n                  Только dev-сборка Vite +{\' \'}\n                  <span className="mono">STUDIO_ALLOW_PROMPT_ONLY=true</span> на сервере: WaveSpeed не\n                  вызывается, внизу показывается итоговый JSON-промпт.\n                </p>',
    '<p className="studio-mode-hint">{ts(\'imageUi.devOutputHintPlain\')}</p>',
  ],
  ['Стандарт', "{ts('imageUi.standard')}"],
  [
    'Анализ референса определяет, какие части тела в кадре — промпт и фото модели\n                  подстроятся автоматически (без лишних инструкций про лицо/волосы).',
    "{ts('imageUi.refAnalysisLead')}",
  ],
  [
    'Пайплайн как workflow «По рефу»: модель из кабинета + референс сцены (Grok описывает\n                кадр, WaveSpeed собирает снимок).',
    "{ts('imageUi.pipelineMain')}",
  ],
  [
    'Пайплайн как workflow «Смена модели»: модель из кабинета или отдельное фото identity\n                + референс сцены с человеком.',
    "{ts('imageUi.pipelineFaceSwap')}",
  ],
  ['Кисть', "{ts('imageUi.brushLabel')}"],
  ['Очистить маску', "{ts('imageUi.clearMask')}"],
  ['Фронталка', "{ts('imageUi.exifSelfie')}"],
  ['Основная', "{ts('imageUi.exifMain')}"],
  [
    'При сохранении кадра в архив подставляются эталоны EXIF модели (фронталка или основная\n                камера) или пресет «как с телефона».',
    "{ts('imageUi.exifHint')}",
  ],
  ['{health.studio_upscale_credit_cost} кр.', "{health.studio_upscale_credit_cost} {ts('imageUi.creditSuffix')}"],
  ['{health.studio_carousel_credit_cost} кр./кадр', "{health.studio_carousel_credit_cost} {ts('imageUi.creditPerFrame')}"],
  [": `${studioImageCreditQuote.label} кр.`}", ": `${studioImageCreditQuote.label} ${ts('imageUi.creditSuffix')}`}"],
  ['title="История"', 'title={ts(\'gallery.title\')}'],
  ['Оформите подписку в кабинете → «Тариф и баланс».', "{ts('videoUi.paywall')}"],
  ['label="Формат"', 'label={ts(\'videoUi.formatLabel\')}'],
  ['label="Модель"', 'label={ts(\'videoUi.modelLabel\')}'],
  ['label="Кадр из архива"', 'label={ts(\'videoUi.archiveFrameLabel\')}'],
  ['<span>Причёска модели</span>', '<span>{ts(\'videoUi.lockHairstyle\')}</span>'],
  ['label="Качество"', 'label={ts(\'videoUi.qualityLabel\')}'],
  ['const costSuffix = ` · ${cost} кр.`', "const costSuffix = ` · ${cost} ${ts('imageUi.creditSuffix')}`"],
  ['return { value: sec, label: `${sec} с${costSuffix}` }', 'return { value: sec, label: ts(\'videoUi.durationSec\', { sec }) + costSuffix }'],
  [
    'Стоимость: ${motionVideoUsdPerSecDisplay.toFixed(3)}/с (≈{\' \'}\n                    {computeMotionVideoCreditCost(motionVideoPricing, motionVideoResolution, motionVideoVariant, {\n                      hasReferenceVideo: motionHasReferenceVideo,\n                    }).creditPerSec}{\' \'}\n                    кр./с, {motionVideoResolution},{\' \'}\n                    {motionVideoVariant === \'mini\' ? \'Mini\' : \'Standard\'}\n                    {motionHasReferenceVideo ? \', с реф-видео\' : \'\'})',
    "{ts('videoUi.costHint', { usdPerSec: motionVideoUsdPerSecDisplay.toFixed(3), creditPerSec: computeMotionVideoCreditCost(motionVideoPricing, motionVideoResolution, motionVideoVariant, { hasReferenceVideo: motionHasReferenceVideo }).creditPerSec, resolution: motionVideoResolution, variant: motionVideoVariant === 'mini' ? ts('videoUi.costVariantMini') : ts('videoUi.costVariantStandard'), refVideoSuffix: motionHasReferenceVideo ? ts('videoUi.costRefVideoSuffix') : '', rubPerUsd: motionVideoPricing.rub_per_usd, rubPerCredit: motionVideoPricing.rub_per_credit })}",
  ],
  ['Негатив (по желанию)', "{ts('videoUi.negativeLabel')}"],
  [
    'Пользователь Fanvue недоступен — аккаунт удалён или заблокирован на\n                        платформе. Отправка сообщений невозможна.',
    "{tc('threadExtra.fanvueUnavailableBanner')}",
  ],
  ['Отправить', "{tc('thread.send')}"],
  ['Отклонить', "{tc('companion.reject')}"],
  ['Заметки', "{tc('notes.title')}"],
  ['aria-label="Закрыть заметки"', 'aria-label={tc(\'notes.closeAria\')}'],
  ['Закрыть', "{tCommon('close')}"],
  [
    "`История загружена: ${imported} сообщений в ${chats} диалогах` +\n          (skipped ? ` (${skipped} уже были в базе)` : '') +\n          (j.errors?.length ? `. Предупреждений: ${j.errors.length}` : '')",
    "tc('import.historyLoaded', { imported, chats, skipped: skipped ? tc('import.skipped', { count: skipped }) : '', warnings: j.errors?.length ? tc('import.warnings', { count: j.errors.length }) : '' })",
  ],
  [
    'Direct-сообщения Instagram Business / Creator. Окно ответа — 24 часа после\n                  последнего сообщения фана.',
    "{t('integrationsExt.instagram.body')}",
  ],
  [
    'Донаты и подписки через{\' \'}\n                  <a href="https://wiki.tribute.tg/ru/api" target="_blank" rel="noreferrer">\n                    Tribute API\n                  </a>\n                  . Ниже — пошаговая настройка. Доля чатера в KPI задаётся в разделе «Команда» для каждого участника.',
    '<Trans i18nKey="integrationsExt.tributeLead" ns="workspace" components={{ link: <a href="https://wiki.tribute.tg/ru/api" target="_blank" rel="noreferrer" /> }} />',
  ],
  [
    '<li>\n                    В панели автора Tribute: <strong>⋯ → Настройки → API Keys → Generate API Key</strong> — скопируйте\n                    ключ.\n                  </li>',
    '<li><Trans i18nKey="integrationsExt.tributeStep1" ns="workspace" components={{ strong: <strong /> }} /></li>',
  ],
  [
    '<li>\n                    Здесь: выберите <strong>модель</strong> (к какому профилю относится доход), вставьте API-ключ и\n                    нажмите «Добавить Tribute».\n                  </li>',
    '<li><Trans i18nKey="integrationsExt.tributeStep2" ns="workspace" components={{ strong: <strong /> }} /></li>',
  ],
  [
    '<li>\n                    После сохранения скопируйте <strong>Webhook URL</strong> из карточки подключения и вставьте в\n                    Tribute: <strong>Настройки → API → Webhooks</strong>.\n                  </li>',
    '<li><Trans i18nKey="integrationsExt.tributeStep3" ns="workspace" components={{ strong: <strong /> }} /></li>',
  ],
  [
    '<p className="muted cabinet-module-body">\n                  Промпты и vision в студии всегда идут через AI-ключ, заданный администратором на сервере (\n                  <code>OPENAI_API_KEY</code> / совместимая база). Поля ниже не используются студией и оставлены на будущее.\n                </p>',
    '<p className="muted cabinet-module-body"><Trans i18nKey="integrationsExt.llmBody" ns="workspace" components={{ code: <code /> }} /></p>',
  ],
]

let count = 0
for (const [from, to] of pairs) {
  if (s.includes(from)) {
    s = s.replace(from, to)
    count++
  }
}
fs.writeFileSync(file, s)
console.log('part3 applied', count, 'replacements')
