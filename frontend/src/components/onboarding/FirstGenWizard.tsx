import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../api'
import { formatHttpApiError, formatClientFetchError } from '../../apiErrors'
import { WAVESPEED_REF_URL } from '../../billing/planCatalog'
import { postStudioJobAndWait } from '../../studioJobs'
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
  onClose: () => void
  onComplete: (generationId: number | null) => void
  onOpenIntegrations: () => void
}

export function FirstGenWizard({
  open,
  ownerId,
  studioNeedsUserWsKey,
  onClose,
  onComplete,
  onOpenIntegrations,
}: Props) {
  const [phase, setPhase] = useState<Phase>('photos')
  const [modelFile, setModelFile] = useState<File | null>(null)
  const [refFile, setRefFile] = useState<File | null>(null)
  const [modelPreview, setModelPreview] = useState<string | null>(null)
  const [refPreview, setRefPreview] = useState<string | null>(null)
  const [wsKey, setWsKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [resultUrl, setResultUrl] = useState<string | null>(null)
  const [resultGenId, setResultGenId] = useState<number | null>(null)

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
    setError(null)
    setStatus(null)
    setResultUrl(null)
    setResultGenId(null)
  }, [open])

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  const canProceedPhotos = Boolean(modelFile && refFile)

  const skip = useCallback(() => {
    trackFunnelEvent('onboarding_wizard_skipped')
    if (ownerId > 0) markFirstGenWizardDoneForUser(ownerId)
    onClose()
  }, [onClose, ownerId])

  const saveWsKey = async (): Promise<boolean> => {
    const k = wsKey.trim()
    if (k.length < 8) {
      setError('Вставьте API-ключ WaveSpeed (минимум 8 символов).')
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
    setError(null)
    setBusy(true)
    setPhase('generating')
    trackFunnelEvent('onboarding_generate_clicked')
    try {
      setStatus('Анализируем фото модели и собираем профиль…')
      const profileFd = new FormData()
      profileFd.append('images', modelFile)
      const profileR = await apiFetch('/api/studio/models/generate-profile', {
        method: 'POST',
        body: profileFd,
      })
      if (!profileR.ok) {
        const j = await profileR.json().catch(() => ({}))
        throw new Error(formatHttpApiError(profileR, j))
      }
      const profileData = (await profileR.json()) as { profile_text: string }
      trackFunnelEvent('onboarding_profile_generated')

      setStatus('Сохраняем модель в кабинете…')
      const modelFd = new FormData()
      modelFd.append('name', 'Моя модель')
      modelFd.append('profile_text', profileData.profile_text)
      modelFd.append('images', modelFile)
      modelFd.append('image_kinds', JSON.stringify(['face']))
      const modelR = await apiFetch('/api/studio/models', { method: 'POST', body: modelFd })
      if (!modelR.ok) {
        const j = await modelR.json().catch(() => ({}))
        throw new Error(formatHttpApiError(modelR, j))
      }
      const model = (await modelR.json()) as { id: number }

      setStatus('Генерируем первую картинку…')
      const genFd = new FormData()
      genFd.append('description', '')
      genFd.append('model_id', String(model.id))
      genFd.append('image', refFile)
      genFd.append('output_aspect', '3:4')
      genFd.append('studio_mode', 'no_face')
      genFd.append('wan_edit_tier', 'standard')
      genFd.append('studio_wave_profile', 'regular')
      genFd.append('generate_wavespeed', '1')
      genFd.append('wavespeed_single_reference', '1')
      genFd.append('send_pose_reference_to_wavespeed', '0')
      genFd.append('lock_model_hairstyle', '0')
      genFd.append('exif_camera', 'iphone15')
      genFd.append('workflow_source', '1')
      genFd.append('workflow_wave_model', 'nano-banana-2')

      const result = await postStudioJobAndWait<{
        generated_image_url?: string | null
        generation_id?: number | null
      }>('/api/studio/refine-prompt', { method: 'POST', body: genFd })

      const url = result.generated_image_url?.trim() || null
      const gid = typeof result.generation_id === 'number' ? result.generation_id : null
      setResultUrl(url)
      setResultGenId(gid)
      setPhase('result')
      trackFunnelEvent('onboarding_generation_success', { generation_id: gid })
      trackFunnelEvent('onboarding_wizard_completed')
      if (ownerId > 0) markFirstGenWizardDoneForUser(ownerId)
    } catch (e) {
      setError(formatClientFetchError(e, true))
      setPhase(studioNeedsUserWsKey ? 'wavespeed' : 'photos')
    } finally {
      setBusy(false)
      setStatus(null)
    }
  }

  const onPhotosNext = () => {
    if (!canProceedPhotos) {
      setError('Загрузите фото модели и референс сцены.')
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

  if (!open) return null

  return (
    <div className="first-gen-wizard-backdrop" role="dialog" aria-modal="true" aria-labelledby="fgw-title">
      <div className="first-gen-wizard panel-glass">
        <header className="first-gen-wizard__head">
          <div>
            <p className="first-gen-wizard__eyebrow">Первая картинка</p>
            <h2 id="fgw-title">Попробуйте студию за 2 минуты</h2>
            <p className="muted first-gen-wizard__lead">
              Два фото — модель и референс сцены. Мы соберём профиль по вашему снимку и сгенерируем кадр.
            </p>
          </div>
          <button type="button" className="ghost-btn first-gen-wizard__skip" onClick={skip} disabled={busy}>
            Позже
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
                <span className="first-gen-wizard__slot-label">1. Фото модели</span>
                <span className="first-gen-wizard__slot-hint muted">Лицо / внешность для профиля</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => setModelFile(e.target.files?.[0] ?? null)}
                />
                {modelPreview ? (
                  <img src={modelPreview} alt="" className="first-gen-wizard__preview" />
                ) : (
                  <span className="first-gen-wizard__placeholder">+ Загрузить</span>
                )}
              </label>
              <label className="first-gen-wizard__slot">
                <span className="first-gen-wizard__slot-label">2. Референс сцены</span>
                <span className="first-gen-wizard__slot-hint muted">Поза, свет, кадр</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => setRefFile(e.target.files?.[0] ?? null)}
                />
                {refPreview ? (
                  <img src={refPreview} alt="" className="first-gen-wizard__preview" />
                ) : (
                  <span className="first-gen-wizard__placeholder">+ Загрузить</span>
                )}
              </label>
            </div>
            <div className="first-gen-wizard__actions">
              <button type="button" className="send-btn" disabled={!canProceedPhotos || busy} onClick={onPhotosNext}>
                Далее
              </button>
            </div>
          </div>
        ) : null}

        {phase === 'wavespeed' ? (
          <div className="first-gen-wizard__body">
            <p className="muted">
              На тарифе <strong>Pro</strong> нужен ваш ключ{' '}
              <a href={WAVESPEED_REF_URL} target="_blank" rel="noopener noreferrer">
                WaveSpeed
              </a>
              . На Standard и Credits платформа может использовать свой ключ.
            </p>
            <label className="first-gen-wizard__ws-field">
              API-ключ WaveSpeed
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
                Назад
              </button>
              <button type="button" className="ghost-btn" onClick={onOpenIntegrations} disabled={busy}>
                Открыть подключения
              </button>
              <button
                type="button"
                className="send-btn"
                disabled={busy || wsKey.trim().length < 8}
                onClick={() => void onWsNext()}
              >
                Сохранить ключ и сгенерировать
              </button>
            </div>
          </div>
        ) : null}

        {phase === 'generating' ? (
          <div className="first-gen-wizard__body first-gen-wizard__body--center">
            <p className="first-gen-wizard__spinner" aria-hidden>
              ◌
            </p>
            <p>{status ?? 'Генерация…'}</p>
            <p className="muted small">Обычно 1–3 минуты. Не закрывайте окно.</p>
          </div>
        ) : null}

        {phase === 'result' ? (
          <div className="first-gen-wizard__body">
            <p className="first-gen-wizard__success">Готово — первая картинка в архиве.</p>
            {resultUrl ? (
              <img src={resultUrl} alt="Результат генерации" className="first-gen-wizard__result" />
            ) : (
              <p className="muted">Результат сохранён в «Сохранённые» — откройте вкладку «Картинки».</p>
            )}
            <div className="first-gen-wizard__actions">
              <button
                type="button"
                className="send-btn"
                onClick={() => {
                  onComplete(resultGenId)
                  onClose()
                }}
              >
                Перейти в студию
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
