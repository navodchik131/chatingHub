/** Почему кнопка «Сгенерировать» в студии картинок неактивна (для title и подсказки под кнопкой). */

export type StudioImageMode = 'model' | 'photo_edit' | 'no_face' | 'face_swap' | 'grok_compose'

export function studioIntegrationsHint(): string {
  return 'Добавьте API-ключ WaveSpeed: кабинет → Подключения → блок WaveSpeed.'
}

export type StudioGenerateGateInput = {
  studioBusy: boolean
  canStudioGenerate: boolean
  studioMode: StudioImageMode
  studioDesc: string
  studioFile: File | null
  studioPhotoEditArchiveId: number | null
  studioSelectedModelId: number | null
  studioSendPoseRefToWavespeed: boolean
  studioPaintInpaintMask: boolean
  studioInpaintMaskFile: File | null
  grokSceneConfigured: boolean
  openaiStudioConfigured: boolean
  wavespeedConfigured: boolean
  studioPromptOnlyDev: boolean
  studioNeedsUserWsKey: boolean
}

export function studioImageGenerateBlockReason(input: StudioGenerateGateInput): string | null {
  const {
    studioBusy,
    canStudioGenerate,
    studioMode,
    studioDesc,
    studioFile,
    studioPhotoEditArchiveId,
    studioSelectedModelId,
    studioSendPoseRefToWavespeed,
    studioPaintInpaintMask,
    studioInpaintMaskFile,
    grokSceneConfigured,
    openaiStudioConfigured,
    wavespeedConfigured,
    studioPromptOnlyDev,
    studioNeedsUserWsKey,
  } = input

  if (studioBusy) return null
  if (!canStudioGenerate) return 'Нет прав на генерацию в студии — уточните у владельца аккаунта.'

  if (studioNeedsUserWsKey) return studioIntegrationsHint()

  if (studioMode === 'grok_compose' && !grokSceneConfigured) {
    return 'Grok не настроен на сервере — генерация «Основная» временно недоступна.'
  }

  if (studioMode === 'face_swap') {
    if (studioSelectedModelId == null) {
      return 'Подмена лица: выберите модель (эталон внешности) в блоке «Модель».'
    }
    if (!studioFile) {
      return 'Подмена лица: загрузите референс — фото со сценой и человеком, которого заменить на вашу модель.'
    }
    return null
  }

  if (studioMode === 'model') {
    if (!grokSceneConfigured) {
      return 'По промту: нужен Grok на сервере (как в режиме «Основная»).'
    }
    if (studioSelectedModelId == null) {
      return 'По промту: выберите модель с фото «Тело целиком» (и «Интимная анатомия» для NSFW).'
    }
    if (!studioDesc.trim()) {
      return 'По промту: опишите сцену в поле промпта.'
    }
    return null
  }

  if (studioMode === 'grok_compose') {
    if (studioSelectedModelId == null) {
      return 'Режим «Основная»: выберите модель с фото и профилем.'
    }
    if (!studioFile) {
      return 'Режим «Основная»: загрузите референс сцены (поза, свет, кадр).'
    }
    return null
  }

  if (studioMode === 'photo_edit') {
    if (!studioFile && studioPhotoEditArchiveId == null) {
      return 'Доработка фото: загрузите снимок или выберите картинку из архива «История».'
    }
    if (!studioDesc.trim()) {
      return 'Доработка фото: опишите в промпте, что изменить на изображении.'
    }
    const wantsInpaint = studioPaintInpaintMask || studioInpaintMaskFile != null
    if (wantsInpaint && !studioFile && studioPhotoEditArchiveId == null) {
      return 'Для маски нужно изображение — загрузите файл или выберите снимок из архива.'
    }
    return null
  }

  if (studioMode === 'no_face') {
    if (studioSelectedModelId == null && !studioFile) {
      return 'Без лица: выберите модель или загрузите референс сцены.'
    }
  } else if (!studioDesc.trim() && !studioFile && studioSelectedModelId == null) {
    return 'Добавьте промпт, референс-фото и/или выберите сохранённую модель.'
  }

  if (
    studioFile != null &&
    !studioSendPoseRefToWavespeed &&
    studioSelectedModelId == null &&
    studioMode === 'no_face'
  ) {
    return 'Выберите модель или включите «Референс позы в WaveSpeed» для загруженного фото.'
  }

  if (!openaiStudioConfigured) {
    return 'Текстовая модель студии на сервере недоступна — генерация временно отключена.'
  }

  if (!studioPromptOnlyDev && !wavespeedConfigured) {
    return studioIntegrationsHint()
  }

  return null
}
