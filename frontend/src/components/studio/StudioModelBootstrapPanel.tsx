import { useCallback, useEffect, useMemo, useState } from 'react'
import { WavespeedSetupBanner } from '../WavespeedSetupBanner'
import { StudioMediaSlot } from './StudioMediaSlot'
import { StudioPillField } from './StudioPillField'
import { IconModel } from './studioIcons'
import { postStudioJobAndWait } from '../../studioJobs'

const DEFAULT_FACE_MERGE_HINT =
  'Integrate a face into an existing scene. Substitute the face in the reference image with the face from the donor image…'

export type BootstrapAspectOption = { value: string; label: string; title?: string }

export type BootstrapModelOption = { value: number; label: string }

type BootstrapResult = {
  refined_prompt: string
  generated_image_url?: string | null
  generation_id?: number | null
  wavespeed_message?: string | null
}

type Props = {
  canGenerate: boolean
  studioPaywalled: boolean
  studioNeedsUserWsKey: boolean
  isTrialing: boolean
  canConnectIntegrations: boolean
  onOpenIntegrations: () => void
  aspectOptions: BootstrapAspectOption[]
  defaultAspect: string
  models: BootstrapModelOption[]
  selectedModelId: number | null
  onModelChange: (id: number | null) => void
  onArchiveRefresh: () => void
  onError: (msg: string | null) => void
}

export function StudioModelBootstrapPanel({
  canGenerate,
  studioPaywalled,
  studioNeedsUserWsKey,
  isTrialing,
  canConnectIntegrations,
  onOpenIntegrations,
  aspectOptions,
  defaultAspect,
  models,
  selectedModelId,
  onModelChange,
  onArchiveRefresh,
  onError,
}: Props) {
  const [refFormFile, setRefFormFile] = useState<File | null>(null)
  const [refFaceFile, setRefFaceFile] = useState<File | null>(null)
  const [refFormPreview, setRefFormPreview] = useState<string | null>(null)
  const [refFacePreview, setRefFacePreview] = useState<string | null>(null)
  const [prompt, setPrompt] = useState('')
  const [aspect, setAspect] = useState(defaultAspect)
  const [mergeBusy, setMergeBusy] = useState(false)
  const [sheetBusy, setSheetBusy] = useState(false)
  const [mergeResult, setMergeResult] = useState<BootstrapResult | null>(null)
  const [sheetResult, setSheetResult] = useState<BootstrapResult | null>(null)
  const [sheetFile, setSheetFile] = useState<File | null>(null)
  const [sheetPreview, setSheetPreview] = useState<string | null>(null)

  useEffect(() => {
    if (!refFormFile) {
      setRefFormPreview(null)
      return
    }
    const url = URL.createObjectURL(refFormFile)
    setRefFormPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [refFormFile])

  useEffect(() => {
    if (!refFaceFile) {
      setRefFacePreview(null)
      return
    }
    const url = URL.createObjectURL(refFaceFile)
    setRefFacePreview(url)
    return () => URL.revokeObjectURL(url)
  }, [refFaceFile])

  useEffect(() => {
    if (!sheetFile) {
      setSheetPreview(null)
      return
    }
    const url = URL.createObjectURL(sheetFile)
    setSheetPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [sheetFile])

  const mergePreviewUrl = mergeResult?.generated_image_url ?? null
  const canRunMerge = canGenerate && !studioPaywalled && refFormFile && refFaceFile && !mergeBusy

  const sheetSourceMode = useMemo(() => {
    if (sheetFile) return 'upload' as const
    if (mergeResult?.generation_id) return 'step1' as const
    return null
  }, [sheetFile, mergeResult?.generation_id])

  const canRunSheet =
    canGenerate &&
    !studioPaywalled &&
    sheetSourceMode != null &&
    !sheetBusy &&
    (sheetSourceMode !== 'step1' || Boolean(mergeResult?.generation_id))

  const runFaceMerge = useCallback(async () => {
    if (!refFormFile || !refFaceFile) return
    setMergeBusy(true)
    onError(null)
    setSheetResult(null)
    try {
      const fd = new FormData()
      fd.append('ref_form', refFormFile)
      fd.append('ref_face', refFaceFile)
      if (prompt.trim()) fd.append('prompt', prompt.trim())
      fd.append('output_aspect', aspect)
      if (selectedModelId != null) fd.append('model_id', String(selectedModelId))
      const res = await postStudioJobAndWait<BootstrapResult>(
        '/api/studio/model-bootstrap/face-merge',
        { method: 'POST', body: fd, timeoutMs: 600_000 },
        { pollMs: 2500, maxWaitMs: 20 * 60 * 1000 },
      )
      setMergeResult(res)
      if (res.wavespeed_message?.trim()) {
        onError(res.wavespeed_message.trim())
      }
      onArchiveRefresh()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Не удалось создать кадр'
      onError(msg)
    } finally {
      setMergeBusy(false)
    }
  }, [
    refFormFile,
    refFaceFile,
    prompt,
    aspect,
    selectedModelId,
    onError,
    onArchiveRefresh,
  ])

  const runSheet = useCallback(async () => {
    setSheetBusy(true)
    onError(null)
    try {
      const fd = new FormData()
      if (selectedModelId != null) fd.append('model_id', String(selectedModelId))
      if (sheetFile) {
        fd.append('image', sheetFile)
      } else if (mergeResult?.generation_id) {
        fd.append('source_generation_id', String(mergeResult.generation_id))
      } else {
        onError('Загрузите кадр или сначала выполните шаг 1.')
        return
      }
      const res = await postStudioJobAndWait<BootstrapResult>(
        '/api/studio/model-bootstrap/sheet',
        { method: 'POST', body: fd, timeoutMs: 600_000 },
        { pollMs: 2500, maxWaitMs: 20 * 60 * 1000 },
      )
      setSheetResult(res)
      if (res.wavespeed_message?.trim()) {
        onError(res.wavespeed_message.trim())
      }
      onArchiveRefresh()
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Не удалось сделать развёртку'
      onError(msg)
    } finally {
      setSheetBusy(false)
    }
  }, [sheetFile, mergeResult?.generation_id, selectedModelId, onError, onArchiveRefresh])

  return (
    <div className="studio-bootstrap">
      {!studioPaywalled && studioNeedsUserWsKey ? (
        <WavespeedSetupBanner
          variant="studio"
          isTrialing={isTrialing}
          canConnect={canConnectIntegrations}
          onOpenIntegrations={onOpenIntegrations}
        />
      ) : null}

      <section className="studio-bootstrap__step" aria-labelledby="bootstrap-step1-title">
        <h3 id="bootstrap-step1-title">Шаг 1 — базовый кадр</h3>
        <p className="studio-bootstrap__lead muted">
          Два референса: первый — волосы и форма лица, второй — лицо для наложения. Результат уйдёт в
          Seedream v4.5 Edit на WaveSpeed и сохранится в архив картинок.
        </p>

        <div className="studio-slot-grid studio-slot-grid--composer">
          <StudioMediaSlot
            label="Референс 1"
            hint="Волосы и форма лица"
            previewUrl={refFormPreview}
            accept="image/jpeg,image/png,image/webp"
            onFile={setRefFormFile}
            onClear={() => setRefFormFile(null)}
            emptyLabel="Загрузить"
          />
          <StudioMediaSlot
            label="Референс 2"
            hint="Лицо для наложения"
            previewUrl={refFacePreview}
            accept="image/jpeg,image/png,image/webp"
            onFile={setRefFaceFile}
            onClear={() => setRefFaceFile(null)}
            emptyLabel="Загрузить"
          />
          <StudioPillField
            label="Формат"
            hint="Разрешение кадра"
            scrollRow
            options={aspectOptions}
            value={aspect}
            onChange={(v) => v != null && setAspect(String(v))}
          />
          {models.length > 0 ? (
            <StudioPillField
              label="Модель"
              hint="Опционально — привязка к архиву"
              icon={<IconModel className="studio-slot__icon-svg" />}
              options={models}
              value={selectedModelId}
              onChange={(v) => onModelChange(v == null ? null : Number(v))}
              allowEmpty
              emptyLabel="Без модели"
            />
          ) : null}
          <label className="studio-label studio-bootstrap__prompt" style={{ gridColumn: '1 / -1' }}>
            <span>Промпт (необязательно)</span>
            <span className="muted small studio-bootstrap__prompt-hint">
              Можно оставить поле пустым — подставится стандартный промпт слияния лиц. Если нужен свой
              сценарий, опишите его здесь.
            </span>
            <textarea
              className="studio-textarea"
              rows={4}
              value={prompt}
              placeholder={DEFAULT_FACE_MERGE_HINT}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </label>
        </div>

        <button
          type="button"
          className="send-btn"
          disabled={!canRunMerge}
          onClick={() => void runFaceMerge()}
        >
          {mergeBusy ? 'Генерация…' : 'Создать базовый кадр'}
        </button>

        {mergePreviewUrl ? (
          <div className="studio-bootstrap__result">
            <p className="studio-bootstrap__result-label">Результат шага 1</p>
            <img src={mergePreviewUrl} alt="Базовый кадр модели" className="studio-bootstrap__result-img" />
          </div>
        ) : null}
      </section>

      {mergeResult?.generated_image_url || mergeResult?.generation_id ? (
        <section className="studio-bootstrap__step" aria-labelledby="bootstrap-step2-title">
          <h3 id="bootstrap-step2-title">Шаг 2 — развёртка модели</h3>
          <p className="studio-bootstrap__lead muted">
            Кадр 16:9 с раскладкой (лицо, профили, рост) через GPT Image 2 Edit. Источник — результат
            шага 1 или своё фото.
          </p>

          <div className="studio-slot-grid studio-slot-grid--composer">
            {mergePreviewUrl ? (
              <div className="studio-bootstrap__source-thumb">
                <span className="muted small">Из шага 1</span>
                <img src={mergePreviewUrl} alt="" />
              </div>
            ) : null}
            <StudioMediaSlot
              label="Своё фото"
              hint="Вместо кадра из шага 1"
              previewUrl={sheetPreview}
              accept="image/jpeg,image/png,image/webp"
              onFile={(f) => {
                setSheetFile(f)
              }}
              onClear={() => setSheetFile(null)}
              emptyLabel="Загрузить"
              fullWidth
            />
          </div>

          <button
            type="button"
            className="send-btn"
            disabled={!canRunSheet}
            onClick={() => void runSheet()}
          >
            {sheetBusy ? 'Генерация…' : 'Сделать развёртку модели'}
          </button>

          {sheetResult?.generated_image_url ? (
            <div className="studio-bootstrap__result">
              <p className="studio-bootstrap__result-label">Развёртка 16:9</p>
              <img
                src={sheetResult.generated_image_url}
                alt="Развёртка модели"
                className="studio-bootstrap__result-img studio-bootstrap__result-img--wide"
              />
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}
