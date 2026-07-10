import fs from 'fs'

const file = 'src/App.tsx'
let s = fs.readFileSync(file, 'utf8')

const pairs = [
  // workflow throw errors
  ["throw new Error('Основная: нужны модель и референс сцены.')", "throw new Error(ts('runtime.workflowMainNeedInputs'))"],
  ["throw new Error('Face swap: загрузите референс сцены.')", "throw new Error(ts('runtime.workflowFaceSwapNoScene'))"],
  ["throw new Error('По промту: выберите модель.')", "throw new Error(ts('runtime.workflowPromptNoModel'))"],
  ["throw new Error('Доработка фото: загрузите снимок.')", "throw new Error(ts('runtime.workflowPhotoEditNoImage'))"],
  ["throw new Error('Режим студии не поддерживается через workflow.')", "throw new Error(ts('runtime.workflowModeUnsupported'))"],
  // grok compose strings
  [
    "'Первый кадр (сцена для вашей модели, без внешности из видео):\\n' + scene",
    "ts('videoUi.grokSceneLine', { scene })",
  ],
  [
    "parts.push('Движение по ролику (Grok timeline):\\n' + motion)",
    "parts.push(ts('videoUi.grokMotionLine', { motion }))",
  ],
  [
    "parts.push('Кадр для модели:\\n' + scene)",
    "parts.push(ts('videoUi.grokFrameLine', { scene }))",
  ],
  [
    "parts.push('Движение (Grok timeline):\\n' + timeline)",
    "parts.push(ts('videoUi.grokMotionLine', { motion: timeline }))",
  ],
  ["motionFrameNotes.trim() || 'Первый кадр…'", "motionFrameNotes.trim() || ts('runtime.firstFramePlaceholder')"],
  [
    "setStudioWavespeedMsg(`Сохранено кадров: ${items.length}. ${note}`)",
    "setStudioWavespeedMsg(ts('imageUi.carouselSaved', { count: items.length, note }))",
  ],
  [
    "`Карусель: добавлено ${items.length} кадров — смотрите в «Сохранённые».`",
    "ts('imageUi.carouselAdded', { count: items.length })",
  ],
  ["setError(`Сначала выберите фото модели (до ${STUDIO_MODEL_MAX_IMAGES} файлов).`)", "setError(ts('runtime.modelPhotosRequired', { max: STUDIO_MODEL_MAX_IMAGES }))"],
  ["'Сообщение'", "tc('composer.messageFallback')"],
  // integrations JSX
  ['<h4 className="cabinet-module-title">{t(\'integrationsExt.llm.title\')}</h4>'],
  [
    '<p className="muted cabinet-module-body">\n                  Промпты и vision в студии всегда идут через AI-ключ, заданный администратором на сервере (\n                  <code>OPENAI_API_KEY</code> / совместимая база). Поля ниже не используются студией и оставлены на будущее.\n                </p>',
    '<p className="muted cabinet-module-body">\n                  <Trans i18nKey="integrationsExt.llm.body" ns="workspace" components={{ code: <code /> }} />\n                </p>',
  ],
  ['<h4 className="cabinet-module-title">AI-компаньон · обратная связь</h4>', '<h4 className="cabinet-module-title">{t(\'integrationsExt.companionFeedback.title\')}</h4>'],
  ['<p className="muted">Загрузка…</p>', '<p className="muted">{tCommon(\'loading\')}</p>'],
  ['<p className="muted small">Отчётов пока нет — появятся после первых оценок и ночного прогона.</p>', '<p className="muted small">{t(\'integrationsExt.companionFeedback.empty\')}</p>'],
  ['<h4 className="cabinet-module-title">Уведомления</h4>', '<h4 className="cabinet-module-title">{t(\'notifications.title\')}</h4>'],
  ['<p className="muted cabinet-module-body">Браузерные уведомления о новых сообщениях в чате.</p>', '<p className="muted cabinet-module-body">{t(\'notifications.body\')}</p>'],
  ['<p className="muted small">Разрешите уведомления для сайта в настройках браузера.</p>', '<p className="muted small">{t(\'notifications.denied\')}</p>'],
  ['<p className="muted small">На сервере не включены push-уведомления.</p>', '<p className="muted small">{t(\'notifications.serverDisabled\')}</p>'],
  ['<li>Новые DM появятся в разделе «Диалоги» → Instagram. Отвечайте в течение 24 ч.</li>', '<li>{t(\'integrationsExt.instagram.step2\')}</li>'],
  // models ext
  ['<p className="studio-phone-exif-refs__title">Эталоны EXIF с телефона</p>', '<p className="studio-phone-exif-refs__title">{t(\'modelsExt.exifRefsTitle\')}</p>'],
  ['<span>Фронтальная камера</span>', '<span>{t(\'modelsExt.exifSelfie\')}</span>'],
  ['<p className="muted small">Не загружен</p>', '<p className="muted small">{tCommon(\'notUploaded\')}</p>'],
  ['<span>Основная камера</span>', '<span>{t(\'modelsExt.exifMain\')}</span>'],
  ['<option value="">— не применять —</option>', '<option value="">{t(\'modelsExt.cameraPresetNone\')}</option>'],
  ['<span className="ghost-btn model-card-add-btn">Добавить фото</span>', '<span className="ghost-btn model-card-add-btn">{t(\'modelsExt.addPhoto\')}</span>'],
  ['<h4 className="account-sub">Шаблоны ответов</h4>', '<h4 className="account-sub">{t(\'modelsExt.snippetsTitle\')}</h4>'],
  ['<h4 className="account-sub">Участники</h4>', '<h4 className="account-sub">{t(\'team.membersTitle\')}</h4>'],
  ['<p className="muted">Пока никого нет — добавьте первого выше.</p>', '<p className="muted">{t(\'team.membersEmpty\')}</p>'],
  // health footer
  ['<span className="warn">API недоступен</span>', '<span className="warn">{t(\'health.telegramUnreachable\')}</span>'],
  ['<span className="muted">проверка…</span>', '<span className="muted">{tCommon(\'checking\')}</span>'],
  ['<span className="muted"> · интеграции через личный кабинет (webhook)</span>', '<span className="muted">{t(\'health.webhookIntegrations\')}</span>'],
  ['<span className="ok"> · прокси TG</span>', '<span className="ok">{t(\'health.telegramProxy\')}</span>'],
  ['<span className="warn"> · студия: текстовая модель на сервере недоступна</span>', '<span className="warn">{t(\'health.studioTextUnavailable\')}</span>'],
  // studio image UI
  ['<span className="studio-mode-label">Вывод</span>', '<span className="studio-mode-label">{ts(\'imageUi.outputLabel\')}</span>'],
  ['<span className="studio-mode-label">Качество</span>', '<span className="studio-mode-label">{ts(\'imageUi.qualityLabel\')}</span>'],
  ['<p className="studio-mode-hint">Pro — выше детализация, обычно дороже по кредитам.</p>', '<p className="studio-mode-hint">{ts(\'imageUi.proHint\')}</p>'],
  ['<span>Нарисовать маску кистью — белым отметьте, что нужно изменить на снимке.</span>', '<span>{ts(\'imageUi.paintMaskLabel\')}</span>'],
  ['<option value="s">Тонкая</option>', '<option value="s">{ts(\'imageUi.brushThin\')}</option>'],
  ['<option value="m">Средняя</option>', '<option value="m">{ts(\'imageUi.brushMedium\')}</option>'],
  ['<option value="l">Толщина</option>', '<option value="l">{ts(\'imageUi.brushThick\')}</option>'],
  ['<span className="muted studio-file-name">альтернатива кисти</span>', '<span className="muted studio-file-name">{ts(\'imageUi.maskFileAlt\')}</span>'],
  ['<span>Причёска с модели</span>', '<span>{ts(\'imageUi.lockHairstyle\')}</span>'],
  ['<span>Референс позы в WaveSpeed</span>', '<span>{ts(\'imageUi.poseRefWavespeed\')}</span>'],
  ['<span className="studio-slot__label">Промпт</span>', '<span className="studio-slot__label">{ts(\'imageUi.promptLabel\')}</span>'],
  ['<h3 className="studio-generated-title">Результат</h3>', '<h3 className="studio-generated-title">{ts(\'imageUi.resultTitle\')}</h3>'],
  ['<span className="studio-upscale-control-label">Апскейл</span>', '<span className="studio-upscale-control-label">{ts(\'imageUi.upscaleLabel\')}</span>'],
  ["{studioCarouselBusy ? 'Карусель…' : 'Карусель ×4'}", "{studioCarouselBusy ? ts('imageUi.carouselBusy') : ts('imageUi.carousel4')}"],
  ["{studioDownloadBusy ? 'Сохранение…' : 'Скачать'}", "{studioDownloadBusy ? tCommon('saving') : ts('imageUi.download')}"],
  ["? 'Генерация…'", "? ts('imageUi.generating')"],
  ["? 'Собрать промпт'", "? ts('imageUi.buildPrompt')"],
  [": 'Сгенерировать'}", ": ts('imageUi.generate')}"],
  ['<h2 id="studio-bootstrap-heading">База модели</h2>', '<h2 id="studio-bootstrap-heading">{ts(\'page.bootstrapTitle\')}</h2>'],
  ['<div className="banner info">Генерация недоступна по правам.</div>', '<div className="banner info">{ts(\'page.noGeneratePermission\')}</div>'],
  ['<h2 id="studio-motion-heading">Видео</h2>', '<h2 id="studio-motion-heading">{ts(\'page.videoTitle\')}</h2>'],
  ['<h3>Кадр и движение</h3>', '<h3>{ts(\'videoUi.stepFrameTitle\')}</h3>'],
  ["emptyLabel={motionVideoFile?.name || 'Загрузить'}", "emptyLabel={motionVideoFile?.name || tCommon('upload')}"],
  ["{ value: 'regular', label: 'Обычный' }", "{ value: 'regular', label: ts('videoUi.frameStyleRegular') }"],
  ['<span>Timeline по ролику</span>', '<span>{ts(\'videoUi.timelineToggle\')}</span>'],
  ['<span>Кадр без WaveSpeed</span>', '<span>{ts(\'videoUi.stillWithoutWs\')}</span>'],
  ['<summary>Grok: сцена и движение</summary>', '<summary>{ts(\'videoUi.grokPreviewSummary\')}</summary>'],
  ["{motionBusyCompose ? 'Grok…' : 'Промпт по видео'}", "{motionBusyCompose ? ts('videoUi.composeBusy') : ts('videoUi.composeBtn')}"],
  ["? 'Дождитесь окончания загрузки реф-видео на сервер'", "? ts('videoUi.uploadWaitTitle')"],
  ["? 'Кадр…'", "? ts('videoUi.frameBusy')"],
  ["? 'Загрузка видео…'", "? ts('videoUi.videoUploadBusy')"],
  [": 'Сгенерировать кадр'}", ": ts('videoUi.generateFrame')}"],
  ['<span className="studio-slot__hint">Сцена и движение</span>', '<span className="studio-slot__hint">{ts(\'videoUi.briefHint\')}</span>'],
  ['<span>Звук</span>', '<span>{ts(\'videoUi.soundToggle\')}</span>'],
  ['<summary>Промпт Seedance</summary>', '<summary>{ts(\'videoUi.seedancePromptSummary\')}</summary>'],
  ["{motionVideoDownloadBusy ? 'Сохранение…' : 'Скачать'}", "{motionVideoDownloadBusy ? tCommon('saving') : ts('videoUi.download')}"],
  ["{motionBusyVideo ? 'Видео…' : 'Сгенерировать видео'}", "{motionBusyVideo ? ts('videoUi.generateVideoBusy') : ts('videoUi.generateVideo')}"],
  // chat thread
  ["{convHideBusy ? '…' : 'Убрать из списка'}", "{convHideBusy ? '…' : tc('threadExtra.hideFromList')}"],
  ['<span className="muted">Загрузка истории…</span>', '<span className="muted">{tc(\'messages.loadingHistory\')}</span>'],
  ["? 'перевод и отправка…'", "? tc('messages.translating')"],
  ["title={info.hasOwner ? 'Убрать реакцию' : 'Поставить реакцию'}", "title={info.hasOwner ? tc('reactions.removeTitle') : tc('reactions.addTitle')}"],
  ['<span className="bubble-companion-rate-label">Оценка AI</span>', '<span className="bubble-companion-rate-label">{tc(\'companion.rateLabel\')}</span>'],
  ["? 'Снять оценку «хорошо»'", "? tc('companion.unrateGood')"],
  [": 'Хороший ответ AI'", ": tc('companion.goodTitle')"],
  ["? 'Снять оценку «плохо»'", "? tc('companion.unrateBad')"],
  [": 'Плохой ответ AI'", ": tc('companion.badTitle')"],
  ["? 'Сохранение…'", "? tCommon('saving')"],
  ["? '✓ Сохранено'", "? tCommon('saved')"],
  ["? 'Оценено: хорошо'", "? tc('companion.ratedGood')"],
  ["? 'Оценено: плохо'", "? tc('companion.ratedBad')"],
  [": 'Помогите боту учиться'}", ": tc('companion.helpLearn')}"],
  ["{manualDraft ? 'Черновик AI' : 'AI не отправил — проверьте'}", "{manualDraft ? tc('companion.draftLabel') : tc('companion.failedLabel')}"],
  ['<span className="composer-reply-bar__label">Ответ на</span>', '<span className="composer-reply-bar__label">{tc(\'composer.replyTo\')}</span>'],
  ['<span className="muted">Архив #{chatReplyArchiveId}</span>', '<span className="muted">{tc(\'composer.archiveBadge\', { id: chatReplyArchiveId })}</span>'],
  ["? 'Пользователь недоступен на Fanvue — отправка невозможна'", "? tc('composer.hintFanvueBlocked')"],
  [": 'Сообщение на русском — уйдёт перевод на язык из «Язык ответа»'", ": tc('composer.hintTranslate')"],
  ["? 'Пользователь Fanvue недоступен'", "? tc('composer.titleFanvueBlocked')"],
  [": 'Пишите на русском; в Telegram/Fanvue уйдёт перевод по выбранному языку'", ": tc('composer.titleTranslate')"],
  ['<span className="hint">Ctrl+Enter — отправить</span>', '<span className="hint">{tc(\'composer.shortcut\')}</span>'],
  ["title={convNotesOpen ? 'Скрыть заметки' : 'Заметки о пользователе'}", "title={convNotesOpen ? tc('notes.toggleHide') : tc('notes.toggleTitle')}"],
  ['<h4>Заметки</h4>', '<h4>{tc(\'notes.title\')}</h4>'],
  ["{selected.user_display_name ?? 'Пользователь'}", "{selected.user_display_name ?? tc('notes.userFallback')}"],
  ["title={n.is_pinned ? 'Открепить' : 'Закрепить'}", "title={n.is_pinned ? tc('notes.unpin') : tc('notes.pin')}"],
  ["{n.is_pinned ? 'Открепить' : 'Закрепить'}", "{n.is_pinned ? tc('notes.unpin') : tc('notes.pin')}"],
  ["{convNotesAnalyzeBusy ? 'Анализ…' : 'AI-анализ'}", "{convNotesAnalyzeBusy ? tc('notes.analyzing') : tc('notes.analyze')}"],
]

let count = 0
for (const [from, to] of pairs) {
  if (s.includes(from)) {
    s = s.replace(from, to)
    count++
  }
}
fs.writeFileSync(file, s)
console.log('part2 applied', count, 'replacements')
