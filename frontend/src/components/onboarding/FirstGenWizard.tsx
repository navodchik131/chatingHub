import { useCallback, useEffect, useRef, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { apiFetch } from '../../api'
import { formatHttpApiError, formatClientFetchError } from '../../apiErrors'
import { WAVESPEED_REF_URL } from '../../billing/planCatalog'
import {
  buildFaceSwapDualRefGraph,
  pickWaveModelId,
} from '../../studio/studioScenarioPresets'
import {
  resolveWorkflowWorkspaceIdForExecute,
  runStudioScenarioAndWait,
} from '../../studio/runStudioScenario'
import { uploadWorkflowReference } from '../../workflow/api'
import {
  markFirstGenWizardDoneForUser,
  trackFunnelEvent,
} from '../../analytics/funnel'
import './first-gen-wizard.css'

type Phase = 'photos' | 'wavespeed' | 'generating' | 'result'

type Props = {
  open: boolean
  ownerId: number
  studioNeedsUserWsKey: boolean
  workflowDemoLimited?: boolean
  onClose: () => void
  onComplete: (generationId: number | null) => void
  onModelSaved?: () => void
  onOpenIntegrations: () => void
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function FirstGenWizard({
  open,
  ownerId,
  studioNeedsUserWsKey,
  workflowDemoLimited = false,
  onClose,
  onComplete,
  onModelSaved,
  onOpenIntegrations,
}: Props) {
  const { t } = useTranslation('studio')
  const [phase, setPhase] = useState<Phase>('photos')
  const [modelFile, setModelFile] = useState<File | null>(null)
  const [refFile, setRefFile] = useState<File | null>(null)
  const [modelPreview, setModelPreview] = useState<string | null>(null)
  const [refPreview, setRefPreview] = useState<string | null>(null)
  const [nsfwEnabled, setNsfwEnabled] = useState(false)
  const [wsKey, setWsKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [resultUrl, setResultUrl] = useState<string | null>(null)
  const [resultGenId, setResultGenId] = useState<number | null>(null)
  const [modelSaved, setModelSaved] = useState(false)
  const [modelSaveBusy, setModelSaveBusy] = useState(false)
  const runAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!modelFile) {
      setModelPreview(null)
      return
    }
    const url = URL.createObjectURL(modelFile)
    setModelPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [modelFile])

  useEffect(() => {
    if (!refFile) {
      setRefPreview(null)
      return
    }
    const url = URL.createObjectURL(refFile)
    setRefPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [refFile])

  useEffect(() => {
    if (!open) return
    trackFunnelEvent('onboarding_wizard_opened')
    setPhase('photos')
    setNsfwEnabled(false)
    setError(null)
    setStatus(null)
    setResultUrl(null)
    setResultGenId(null)
    setModelSaved(false)
    setModelSaveBusy(false)
  }, [open])

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  useEffect(() => {
    return () => {
      runAbortRef.current?.abort()
      runAbortRef.current = null
    }
  }, [])

  const canProceedPhotos = Boolean(modelFile && refFile)

  const abortRun = useCallback(() => {
    runAbortRef.current?.abort()
    runAbortRef.current = null
  }, [])

  const skip = useCallback(() => {
    abortRun()
    setBusy(false)
    setStatus(null)
    trackFunnelEvent('onboarding_wizard_skipped')
    if (ownerId > 0) markFirstGenWizardDoneForUser(ownerId)
    onClose()
  }, [abortRun, onClose, ownerId])

  const onCancelGeneration = useCallback(() => {
    abortRun()
    setBusy(false)
    setStatus(null)
    setError(null)
    setPhase(studioNeedsUserWsKey ? 'wavespeed' : 'photos')
  }, [abortRun, studioNeedsUserWsKey])

  const saveWsKey = async (): Promise<boolean> => {
    const k = wsKey.trim()
    if (k.length < 8) {
      setError(t('firstGenWizard.errWsKeyMin'))
      return false
    }
    setError(null)
    setBusy(true)
    try {
      const r = await apiFetch('/api/integrations/wavespeed', {
        method: 'PUT',
        body: JSON.stringify({ api_key: k }),
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setError(formatHttpApiError(r, j))
        return false
      }
      trackFunnelEvent('onboarding_ws_key_saved')
      setWsKey('')
      return true
    } catch (e) {
      setError(formatClientFetchError(e, true))
      return false
    } finally {
      setBusy(false)
    }
  }

  const runPipeline = async () => {
    if (!modelFile || !refFile) return
    abortRun()
    const abortController = new AbortController()
    runAbortRef.current = abortController

    setError(null)
    setBusy(true)
    setPhase('generating')
    trackFunnelEvent('onboarding_generate_clicked')
    try {
      setStatus(t('firstGenWizard.statusUploading'))
      const waveProfile = nsfwEnabled ? 'nsfw' : 'regular'
      const [identityRef, sceneRef] = await Promise.all([
        uploadWorkflowReference(modelFile),
        uploadWorkflowReference(refFile),
      ])
      if (abortController.signal.aborted) return

      setStatus(t('firstGenWizard.statusGenerating'))
      const built = buildFaceSwapDualRefGraph(identityRef.ref_id, sceneRef.ref_id, {
        outputAspect: '3:4',
        waveProfile,
        waveModelId: pickWaveModelId({
          outputAspect: '3:4',
          waveProfile,
          waveModelId: nsfwEnabled ? 'wan-2.7' : 'nano-banana-2',
        }),
        exifCamera: 'iphone15',
        realismEnabled: true,
      })
      const workspaceId = await resolveWorkflowWorkspaceIdForExecute(workflowDemoLimited)
      if (abortController.signal.aborted) return

      const result = await runStudioScenarioAndWait<{
        generated_image_url?: string | null
        generation_id?: number | null
      }>(built, {
        workspaceId,
        signal: abortController.signal,
      })

      if (abortController.signal.aborted) return

      const url = result.generated_image_url?.trim() || null
      const gid = typeof result.generation_id === 'number' ? result.generation_id : null
      setResultUrl(url)
      setResultGenId(gid)
      setPhase('result')
      trackFunnelEvent('onboarding_generation_success', { generation_id: gid })
      trackFunnelEvent('onboarding_wizard_completed')
      if (ownerId > 0) markFirstGenWizardDoneForUser(ownerId)
    } catch (e) {
      if (isAbortError(e) || abortController.signal.aborted) {
        setPhase(studioNeedsUserWsKey ? 'wavespeed' : 'photos')
        return
      }
      setError(formatClientFetchError(e, true))
      setPhase(studioNeedsUserWsKey ? 'wavespeed' : 'photos')
    } finally {
      if (runAbortRef.current === abortController) {
        runAbortRef.current = null
      }
      setBusy(false)
      setStatus(null)
    }
  }

  const onPhotosNext = () => {
    if (!canProceedPhotos) {
      setError(t('firstGenWizard.errNeedPhotos'))
      return
    }
    if (modelFile) trackFunnelEvent('onboarding_model_photo_set')
    if (refFile) trackFunnelEvent('onboarding_ref_photo_set')
    setError(null)
    if (studioNeedsUserWsKey) {
      setPhase('wavespeed')
    } else {
      void runPipeline()
    }
  }

  const onWsNext = async () => {
    const ok = await saveWsKey()
    if (ok) void runPipeline()
  }

  const saveModelToCabinet = async () => {
    if (!modelFile || modelSaved || modelSaveBusy) return
    setError(null)
    setModelSaveBusy(true)
    trackFunnelEvent('onboarding_model_save_clicked')
    try {
      setStatus(t('firstGenWizard.statusBuildingProfile'))
      const profileFd = new FormData()
      profileFd.append('images', modelFile)
      profileFd.append('onboarding_wizard', '1')
      const profileR = await apiFetch('/api/studio/models/generate-profile', {
        method: 'POST',
        body: profileFd,
        timeoutMs: 120_000,
      })
      if (!profileR.ok) {
        const j = await profileR.json().catch(() => ({}))
        throw new Error(formatHttpApiError(profileR, j))
      }
      const profileData = (await profileR.json()) as { profile_text: string }
      trackFunnelEvent('onboarding_profile_generated')

      setStatus(t('firstGenWizard.statusSavingModel'))
      const modelFd = new FormData()
      modelFd.append('name', t('firstGenWizard.defaultModelName'))
      modelFd.append('profile_text', profileData.profile_text)
      modelFd.append('images', modelFile)
      modelFd.append('image_kinds', JSON.stringify(['face']))
      const modelR = await apiFetch('/api/studio/models', {
        method: 'POST',
        body: modelFd,
        timeoutMs: 120_000,
      })
      if (!modelR.ok) {
        const j = await modelR.json().catch(() => ({}))
        throw new Error(formatHttpApiError(modelR, j))
      }
      setModelSaved(true)
      trackFunnelEvent('onboarding_model_saved')
      onModelSaved?.()
    } catch (e) {
      setError(formatClientFetchError(e, true))
    } finally {
      setModelSaveBusy(false)
      setStatus(null)
    }
  }

  const finishWizard = () => {
    onComplete(resultGenId)
    onClose()
  }

  if (!open) return null

  return (
    <div className="first-gen-wizard-backdrop" role="dialog" aria-modal="true" aria-labelledby="fgw-title">
      <div className="first-gen-wizard panel-glass">
        <header className="first-gen-wizard__head">
          <div>
            <p className="first-gen-wizard__eyebrow">{t('firstGenWizard.eyebrow')}</p>
            <h2 id="fgw-title">{t('firstGenWizard.title')}</h2>
            <p className="muted first-gen-wizard__lead">{t('firstGenWizard.lead')}</p>
          </div>
          <button type="button" className="ghost-btn first-gen-wizard__skip" onClick={skip}>
            {t('firstGenWizard.dismiss')}
          </button>
        </header>

        {error ? (
          <div className="banner error first-gen-wizard__banner" role="alert">
            {error}
          </div>
        ) : null}

        {phase === 'photos' ? (
          <div className="first-gen-wizard__body">
            <div className="first-gen-wizard__grid">
              <label className="first-gen-wizard__slot">
                <span className="first-gen-wizard__slot-label">{t('firstGenWizard.modelPhotoLabel')}</span>
                <span className="first-gen-wizard__slot-hint muted">{t('firstGenWizard.modelPhotoHint')}</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => setModelFile(e.target.files?.[0] ?? null)}
                />
                {modelPreview ? (
                  <img src={modelPreview} alt="" className="first-gen-wizard__preview" />
                ) : (
                  <span className="first-gen-wizard__placeholder">{t('firstGenWizard.upload')}</span>
                )}
              </label>
              <label className="first-gen-wizard__slot">
                <span className="first-gen-wizard__slot-label">{t('firstGenWizard.sceneRefLabel')}</span>
                <span className="first-gen-wizard__slot-hint muted">{t('firstGenWizard.sceneRefHint')}</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => setRefFile(e.target.files?.[0] ?? null)}
                />
                {refPreview ? (
                  <img src={refPreview} alt="" className="first-gen-wizard__preview" />
                ) : (
                  <span className="first-gen-wizard__placeholder">{t('firstGenWizard.upload')}</span>
                )}
              </label>
            </div>

            <div className="first-gen-wizard__mode">
              <span className="first-gen-wizard__mode-label">{t('firstGenWizard.genTypeLabel')}</span>
              <div className="first-gen-wizard__mode-toggle" role="group" aria-label={t('firstGenWizard.genTypeAria')}>
                <button
                  type="button"
                  className={`first-gen-wizard__mode-btn${!nsfwEnabled ? ' is-active' : ''}`}
                  onClick={() => setNsfwEnabled(false)}
                >
                  {t('firstGenWizard.regularPhoto')}
                </button>
                <button
                  type="button"
                  className={`first-gen-wizard__mode-btn${nsfwEnabled ? ' is-active' : ''}`}
                  onClick={() => setNsfwEnabled(true)}
                >
                  {t('firstGenWizard.nsfw')}
                </button>
              </div>
              <p className="muted small first-gen-wizard__mode-hint">
                {nsfwEnabled ? t('firstGenWizard.nsfwHint') : t('firstGenWizard.regularHint')}
              </p>
            </div>

            <div className="first-gen-wizard__actions">
              <button type="button" className="send-btn" disabled={!canProceedPhotos || busy} onClick={onPhotosNext}>
                {t('firstGenWizard.next')}
              </button>
            </div>
          </div>
        ) : null}

        {phase === 'wavespeed' ? (
          <div className="first-gen-wizard__body">
            <p className="muted">
              <Trans
                i18nKey="firstGenWizard.wsLead"
                ns="studio"
                components={{
                  strong: <strong />,
                  wsLink: (
                    <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer" />
                  ),
                }}
              />
            </p>
            <label className="first-gen-wizard__ws-field">
              {t('firstGenWizard.wsKeyLabel')}
              <input
                type="password"
                value={wsKey}
                onChange={(e) => setWsKey(e.target.value)}
                placeholder="sk-…"
                autoComplete="off"
              />
            </label>
            <div className="first-gen-wizard__actions">
              <button type="button" className="ghost-btn" onClick={() => setPhase('photos')} disabled={busy}>
                {t('firstGenWizard.back')}
              </button>
              <button type="button" className="ghost-btn" onClick={onOpenIntegrations} disabled={busy}>
                {t('firstGenWizard.openIntegrations')}
              </button>
              <button
                type="button"
                className="send-btn"
                disabled={busy || wsKey.trim().length < 8}
                onClick={() => void onWsNext()}
              >
                {t('firstGenWizard.saveKeyAndGenerate')}
              </button>
            </div>
          </div>
        ) : null}

        {phase === 'generating' ? (
          <div className="first-gen-wizard__body first-gen-wizard__body--center">
            <p className="first-gen-wizard__spinner" aria-hidden>
              ◌
            </p>
            <p>{status ?? t('firstGenWizard.generating')}</p>
            <p className="muted small">{t('firstGenWizard.generatingEta')}</p>
            <div className="first-gen-wizard__actions first-gen-wizard__actions--center">
              <button type="button" className="ghost-btn" onClick={onCancelGeneration}>
                {t('firstGenWizard.cancel')}
              </button>
            </div>
          </div>
        ) : null}

        {phase === 'result' ? (
          <div className="first-gen-wizard__body">
            <p className="first-gen-wizard__success">{t('firstGenWizard.success')}</p>
            {resultUrl ? (
              <img src={resultUrl} alt={t('firstGenWizard.resultAlt')} className="first-gen-wizard__result" />
            ) : (
              <p className="muted">{t('firstGenWizard.resultSaved')}</p>
            )}
            {modelFile ? (
              <div className="first-gen-wizard__save-model">
                <div className="first-gen-wizard__save-model-head">
                  {modelPreview ? (
                    <img src={modelPreview} alt="" className="first-gen-wizard__save-model-thumb" />
                  ) : null}
                  <div>
                    <p className="first-gen-wizard__save-model-title">{t('firstGenWizard.saveModelTitle')}</p>
                    <p className="muted small first-gen-wizard__save-model-hint">
                      {modelSaved
                        ? t('firstGenWizard.saveModelSaved', { name: t('firstGenWizard.defaultModelName') })
                        : t('firstGenWizard.saveModelHint')}
                    </p>
                  </div>
                </div>
                {!modelSaved ? (
                  <button
                    type="button"
                    className="ghost-btn first-gen-wizard__save-model-btn"
                    disabled={modelSaveBusy || busy}
                    onClick={() => void saveModelToCabinet()}
                  >
                    {modelSaveBusy ? (status ?? t('firstGenWizard.saving')) : t('firstGenWizard.saveModelBtn')}
                  </button>
                ) : (
                  <p className="first-gen-wizard__save-model-done" role="status">
                    {t('firstGenWizard.savedInCabinet')}
                  </p>
                )}
              </div>
            ) : null}
            <div className="first-gen-wizard__actions">
              <button
                type="button"
                className="send-btn"
                disabled={modelSaveBusy}
                onClick={finishWizard}
              >
                {t('firstGenWizard.goStudio')}
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
