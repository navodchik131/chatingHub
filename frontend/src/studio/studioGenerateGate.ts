import i18n, { STUDIO_NS } from '../i18n'
import { studioGenerationUsesDemo } from '../studioImagePricing'

export type StudioImageMode =
  | 'model_scene'
  | 'model'
  | 'photo_edit'
  | 'no_face'
  | 'face_swap'
  | 'grok_compose'

export function studioIntegrationsHint(): string {
  return i18n.t('integrationsHint', { ns: STUDIO_NS })
}

export function studioDemoModelHint(): string {
  return i18n.t('demoModelHint', { ns: STUDIO_NS })
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

function gate(key: string): string {
  return i18n.t(`gate.${key}`, { ns: STUDIO_NS })
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
  if (!canStudioGenerate) return gate('noPermission')

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
    return gate('grokMainUnavailable')
  }

  if (studioMode === 'grok_compose' && !grokSceneConfigured) {
    return gate('grokFaceSwapUnavailable')
  }

  if (studioMode === 'face_swap') {
    if (studioSelectedModelId == null) return gate('faceSwapNoModel')
    if (!studioFile) return gate('faceSwapNoRef')
    return null
  }

  if (studioMode === 'model_scene') {
    if (studioSelectedModelId == null) return gate('mainNoModel')
    if (!studioFile) return gate('mainNoRef')
    return null
  }

  if (studioMode === 'model') {
    if (!grokSceneConfigured) return gate('promptNoGrok')
    if (studioSelectedModelId == null) return gate('promptNoModel')
    if (!studioDesc.trim()) return gate('promptNoText')
    return null
  }

  if (studioMode === 'grok_compose') {
    if (!studioFile) return gate('grokComposeNoScene')
    if (studioSelectedModelId == null && !studioIdentityFile) return gate('grokComposeNoIdentity')
    return null
  }

  if (studioMode === 'photo_edit') {
    if (!studioFile && studioPhotoEditArchiveId == null) return gate('photoEditNoImage')
    if (!studioDesc.trim()) return gate('photoEditNoPrompt')
    const wantsInpaint = studioPaintInpaintMask || studioInpaintMaskFile != null
    if (wantsInpaint && !studioFile && studioPhotoEditArchiveId == null) {
      return gate('photoEditMaskNeedsImage')
    }
    return null
  }

  if (studioMode === 'no_face') {
    if (studioSelectedModelId == null && !studioFile) return gate('noFaceNoInput')
  } else if (!studioDesc.trim() && !studioFile && studioSelectedModelId == null) {
    return gate('needInput')
  }

  if (
    studioFile != null &&
    !studioSendPoseRefToWavespeed &&
    studioSelectedModelId == null &&
    studioMode === 'no_face'
  ) {
    return gate('poseRefOrModel')
  }

  if (!openaiStudioConfigured) return gate('openaiUnavailable')

  if (!studioPromptOnlyDev && !wavespeedConfigured) return studioIntegrationsHint()

  return null
}
