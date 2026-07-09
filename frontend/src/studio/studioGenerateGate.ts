import { studioGenerationUsesDemo } from '../studioImagePricing'

export type StudioImageMode =
  | 'model_scene'
  | 'model'
  | 'photo_edit'
  | 'no_face'
  | 'face_swap'
  | 'grok_compose'

export function studioIntegrationsHint(): string {
  return 'Добавьте API-ключ WaveSpeed: кабинет → Подключения → блок WaveSpeed.'
}

export function studioDemoModelHint(): string {
  return 'На демо без кредитов: любая модель профиля (Обычные / NSFW), кроме Wan 2.7 Pro. Или пополните кредиты.'
}

export type StudioGenerateGateInput = {
  studioBusy: boolean
  canStudioGenerate: boolean
  studioMode: StudioImageMode
  studioDesc: string
  studioFile: File | null
  studioIdentityFile: File | null
  studioWaveModelId: string
  studioWaveProfile: 'regular' | 'nsfw'
  studioWanEditTier: 'standard' | 'pro'
  creditsBalance: number
  demoRemaining: number
  billingPlan: string | null | undefined
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
    studioIdentityFile,
    studioWaveModelId,
    studioWaveProfile,
    studioWanEditTier,
    creditsBalance,
    demoRemaining,
    billingPlan,
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

  const useDemo = studioGenerationUsesDemo({
    billingPlan,
    demoRemaining,
    creditsBalance,
    waveProfile: studioWaveProfile,
    waveModelId: studioWaveModelId,
    wanEditTier: studioWanEditTier,
    studioMode,
    workflow: true,
  })
  if (!useDemo && creditsBalance <= 0 && (demoRemaining ?? 0) > 0) {
    return studioDemoModelHint()
  }

  if (studioMode === 'model_scene' && !grokSceneConfigured) {
    return 'Grok не настроен на сервере — режим «Основная» временно недоступен.'
  }

  if (studioMode === 'grok_compose' && !grokSceneConfigured) {
    return 'Grok не настроен на сервере — режим «Face swap» временно недоступен.'
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

  if (studioMode === 'model_scene') {
    if (studioSelectedModelId == null) {
      return 'Основная: выберите модель с развёрткой/лицом/телом и JSON-профилем.'
    }
    if (!studioFile) {
      return 'Основная: загрузите референс сцены — Grok и WaveSpeed используют его для точного кадра.'
    }
    return null
  }

  if (studioMode === 'model') {
    if (!grokSceneConfigured) {
      return 'По промту: нужен Grok на сервере.'
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
    if (!studioFile) {
      return 'Face swap: загрузите референс сцены (поза, свет, кадр).'
    }
    if (studioSelectedModelId == null && !studioIdentityFile) {
      return 'Face swap: выберите модель из кабинета или загрузите фото модели (identity).'
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
