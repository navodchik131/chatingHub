import { useCallback, useEffect, useRef, useState } from 'react'
import { WavespeedSetupBanner } from '../WavespeedSetupBanner'
import { StudioArchiveThumbPicker } from './StudioArchiveThumbPicker'
import { StudioMediaSlot } from './StudioMediaSlot'
import { StudioPillField } from './StudioPillField'
import { postStudioJobAndWait } from '../../studioJobs'
import type { StudioArchiveItem } from '../../studioArchive'

const DEFAULT_FACE_MERGE_HINT =
  'Integrate a face into an existing scene. Substitute the face in the reference image with the face from the donor image…'

const DEFAULT_MODEL_SHEET_PROMPT =
  'Сделай на нейтральном сером фоне раскладку персонажа с картинки, треть раскладки слева — ' +
  'крупный план лица, остальное — крупные планы вид справа, вид слева, вид сзади. ' +
  'В полный рост спереди и в полный рост сзади. ' +
  'Одежда - черный топ с глубоким декольте черные спортивные шорты из облегающего материала'

export type BootstrapAspectOption = { value: string; label: string; title?: string }

type BootstrapResult = {
  refined_prompt: string
  generated_image_url?: string | null
  generation_id?: number | null
  wavespeed_message?: string | null
}

type SheetSource = 'upload' | 'archive' | 'step1'

type Props = {
  canGenerate: boolean
  studioPaywalled: boolean
  studioNeedsUserWsKey: boolean
  isTrialing: boolean
  canConnectIntegrations: boolean
  onOpenIntegrations: () => void
  aspectOptions: BootstrapAspectOption[]
  defaultAspect: string
  archiveItems: StudioArchiveItem[]
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
  archiveItems,
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
  const [sheetSource, setSheetSource] = useState<SheetSource | null>(null)
  const [sheetArchiveId, setSheetArchiveId] = useState<number | null>(null)
  const [sheetPrompt, setSheetPrompt] = useState(DEFAULT_MODEL_SHEET_PROMPT)
  const sheetInFlightRef = useRef(false)

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

  const canRunSheet =
    canGenerate &&
    !studioPaywalled &&
    sheetSource != null &&
    !sheetBusy &&
    (sheetSource !== 'upload' || Boolean(sheetFile)) &&
    (sheetSource !== 'archive' || sheetArchiveId != null) &&
    (sheetSource !== 'step1' || Boolean(mergeResult?.generation_id))

  const selectSheetUpload = (f: File | null) => {
    setSheetFile(f)
    if (f) {
      setSheetSource('upload')
      setSheetArchiveId(null)
    } else if (sheetSource === 'upload') {
      setSheetSource(null)
    }
  }

  const runFaceMerge = useCallback(async () => {
    if (!refFormFile || !refFaceFile) return
    setMergeBusy(true)
    onError(null)
    try {
      const fd = new FormData()
      fd.append('ref_form', refFormFile)
      fd.append('ref_face', refFaceFile)
      if (prompt.trim()) fd.append('prompt', prompt.trim())
      fd.append('output_aspect', aspect)
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
    onError,
    onArchiveRefresh,
  ])

  const runSheet = useCallback(async () => {
    if (sheetInFlightRef.current) return
    sheetInFlightRef.current = true
    setSheetBusy(true)
    onError(null)
    try {
      const fd = new FormData()

      if (sheetSource === 'upload' && sheetFile) {
        fd.append('image', sheetFile)
      } else if (sheetSource === 'archive' && sheetArchiveId != null) {
        fd.append('source_generation_id', String(sheetArchiveId))
      } else if (sheetSource === 'step1' && mergeResult?.generation_id) {
        fd.append('source_generation_id', String(mergeResult.generation_id))
      } else {
        onError('Выберите источник: своё фото, кадр из архива или результат шага 1.')
        return
      }

      fd.append('prompt', sheetPrompt.trim())

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
      sheetInFlightRef.current = false
      setSheetBusy(false)
    }
  }, [
    sheetSource,
    sheetFile,
    sheetArchiveId,
    mergeResult?.generation_id,
    sheetPrompt,
    onError,
    onArchiveRefresh,
  ])

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
        <h3 id="bootstrap-step1-title">Шаг 1 — базовый кадр (опционально)</h3>
        <p className="studio-bootstrap__lead muted">
          Два референса: первый — волосы и форма лица, второй — лицо для наложения. Результат можно
          использовать для развёртки ниже.
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
        </div>

        <label className="studio-label studio-bootstrap__prompt">
          <span>Промпт (необязательно)</span>
          <span className="muted small studio-bootstrap__prompt-hint">
            Можно оставить поле пустым — подставится стандартный промпт слияния лиц. Если нужен свой
            сценарий, опишите его здесь.
          </span>
          <textarea
            className="studio-textarea studio-bootstrap__textarea"
            rows={4}
            value={prompt}
            placeholder={DEFAULT_FACE_MERGE_HINT}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </label>

        <div className="studio-bootstrap__actions">
          <button
            type="button"
            className="send-btn"
            disabled={!canRunMerge}
            onClick={() => void runFaceMerge()}
          >
            {mergeBusy ? 'Генерация…' : 'Создать базовый кадр'}
          </button>
        </div>

        {mergePreviewUrl ? (
          <div className="studio-bootstrap__result">
            <p className="studio-bootstrap__result-label">Результат шага 1</p>
            <img src={mergePreviewUrl} alt="Базовый кадр модели" className="studio-bootstrap__result-img" />
          </div>
        ) : null}
      </section>

      <section className="studio-bootstrap__step" aria-labelledby="bootstrap-step2-title">
        <h3 id="bootstrap-step2-title">Развёртка модели</h3>
        <p className="studio-bootstrap__lead muted">
          Кадр 16:9 с раскладкой (лицо, профили, рост) через GPT Image 2 Edit. Шаг 1 не обязателен —
          загрузите своё фото или выберите готовый кадр из архива.
        </p>

        <div className="studio-slot-grid studio-slot-grid--composer">
          <StudioMediaSlot
            label="Своё фото"
            hint="JPG, PNG, WebP"
            previewUrl={sheetSource === 'upload' ? sheetPreview : null}
            accept="image/jpeg,image/png,image/webp"
            onFile={selectSheetUpload}
            onClear={() => selectSheetUpload(null)}
            emptyLabel="Загрузить"
            className={sheetSource === 'upload' ? 'studio-bootstrap__source--active' : ''}
          />
          <div
            className={
              'studio-bootstrap__archive-picker' +
              (sheetSource === 'archive' ? ' studio-bootstrap__source--active' : '')
            }
            style={{ gridColumn: '1 / -1' }}
          >
            <StudioArchiveThumbPicker
              label="Или из архива"
              hint="Готовые кадры из истории"
              items={archiveItems}
              value={sheetSource === 'archive' ? sheetArchiveId : null}
              onChange={(id) => {
                if (id == null) {
                  if (sheetSource === 'archive') setSheetSource(null)
                  setSheetArchiveId(null)
                  return
                }
                setSheetSource('archive')
                setSheetArchiveId(id)
                setSheetFile(null)
              }}
            />
          </div>
          {mergePreviewUrl ? (
            <button
              type="button"
              className={
                'studio-bootstrap__source-thumb studio-bootstrap__source-pick' +
                (sheetSource === 'step1' ? ' is-selected' : '')
              }
              onClick={() => {
                setSheetSource('step1')
                setSheetArchiveId(null)
                setSheetFile(null)
              }}
            >
              <span className="muted small">Кадр из шага 1 (выше)</span>
              <img src={mergePreviewUrl} alt="" />
            </button>
          ) : null}
        </div>

        <label className="studio-label studio-bootstrap__prompt">
          <span>Промпт развёртки</span>
          <span className="muted small studio-bootstrap__prompt-hint">
            Стандартный промпт для GPT Image 2 Edit — можно отредактировать перед генерацией.
            Если очистить поле, снова подставится значение по умолчанию.
          </span>
          <textarea
            className="studio-textarea studio-bootstrap__textarea"
            rows={5}
            value={sheetPrompt}
            onChange={(e) => setSheetPrompt(e.target.value)}
          />
        </label>

        <div className="studio-bootstrap__actions">
          <button
            type="button"
            className="send-btn"
            disabled={!canRunSheet}
            onClick={() => void runSheet()}
          >
            {sheetBusy ? 'Генерация…' : 'Сделать развёртку модели'}
          </button>
        </div>

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
    </div>
  )
}
