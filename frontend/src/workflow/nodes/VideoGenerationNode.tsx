import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import {
  DEFAULT_GROK_IMAGINE_I2V_PRICING,
  DEFAULT_MOTION_VIDEO_PRICING,
  computeGrokImagineI2vCreditCost,
  computeMotionVideoCreditCost,
  mergeMotionVideoPricing,
  type GrokImagineI2vResolution,
  type StudioMotionVideoPricing,
} from '../../studioMotionPricing'
import { executeWorkflowGeneration, fetchWorkflowModelOptions } from '../api'
import { getDownstreamPreviewNodeIds, serializeGraph } from '../graphResolver'
import { useWorkflowBilling } from '../WorkflowBillingContext'
import { useWorkflowRun } from '../WorkflowRunContext'
import { BaseNode } from './BaseNode'
import {
  HandleIds,
  type SeedanceT2vResolution,
  type SeedanceT2vVariant,
  type VideoGenerationNodeData,
  type WorkflowVideoProvider,
} from '../types'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

const DEFAULT_ASPECT = '9:16'

type VideoModelKey = 'seedance-standard' | 'seedance-mini' | 'grok-imagine-i2v'

function modelKeyFromNodeData(data: VideoGenerationNodeData): VideoModelKey {
  if (data.videoProvider === 'grok_imagine_i2v') {
    return 'grok-imagine-i2v'
  }
  return data.seedanceVariant === 'mini' ? 'seedance-mini' : 'seedance-standard'
}

function patchFromModelKey(key: VideoModelKey): Partial<VideoGenerationNodeData> {
  if (key === 'grok-imagine-i2v') {
    return {
      videoProvider: 'grok_imagine_i2v',
      seedanceVariant: 'standard',
      generateAudio: false,
      autoMotionPrompt: false,
    }
  }
  return {
    videoProvider: 'seedance_t2v',
    seedanceVariant: key === 'seedance-mini' ? 'mini' : 'standard',
  }
}

function VideoGenerationNodeComponent({ id, data }: NodeProps) {
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const { workspaceId } = useWorkflowRun()
  const { me } = useWorkflowBilling()
  const nodeData = data as VideoGenerationNodeData
  const [pricing, setPricing] = useState<StudioMotionVideoPricing>(DEFAULT_MOTION_VIDEO_PRICING)
  const runAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    void fetchWorkflowModelOptions().then((opts) => {
      if (opts.video) setPricing(mergeMotionVideoPricing(opts.video))
    })
  }, [])

  const videoProvider = (nodeData.videoProvider ?? 'seedance_t2v') as WorkflowVideoProvider
  const isGrok = videoProvider === 'grok_imagine_i2v'
  const grokPricing = pricing.grok_imagine_i2v ?? DEFAULT_GROK_IMAGINE_I2V_PRICING

  const durationSeconds = nodeData.durationSeconds ?? (isGrok ? grokPricing.duration_default ?? 6 : pricing.duration_default ?? 5)
  const seedanceVariant = (nodeData.seedanceVariant ?? pricing.default_variant ?? 'standard') as SeedanceT2vVariant
  const videoResolution = (nodeData.videoResolution ??
    (isGrok ? grokPricing.default_resolution ?? '720p' : pricing.default_resolution ?? '720p')) as
    | SeedanceT2vResolution
    | GrokImagineI2vResolution
  const generateAudio = !isGrok && nodeData.generateAudio !== false
  const autoMotionPrompt = !isGrok && nodeData.autoMotionPrompt !== false
  const outputAspect = nodeData.outputAspect || DEFAULT_ASPECT
  const modelKey = modelKeyFromNodeData(nodeData)

  const costCredits = useMemo(() => {
    if (isGrok) {
      return computeGrokImagineI2vCreditCost(durationSeconds, pricing, {
        resolution: videoResolution as GrokImagineI2vResolution,
      })
    }
    return computeMotionVideoCreditCost(durationSeconds, true, pricing, {
      variant: seedanceVariant,
      resolution: videoResolution as SeedanceT2vResolution,
    })
  }, [pricing, durationSeconds, seedanceVariant, videoResolution, isGrok])

  const updateNodeData = useCallback(
    (patch: Partial<VideoGenerationNodeData>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  useEffect(() => {
    return () => {
      runAbortRef.current?.abort()
      runAbortRef.current = null
    }
  }, [])

  const onCancelRun = useCallback(() => {
    runAbortRef.current?.abort()
    runAbortRef.current = null
    updateNodeData({ isRunning: false, error: undefined })
  }, [updateNodeData])

  const onGenerate = useCallback(async () => {
    if (nodeData.disabled) return
    runAbortRef.current?.abort()
    const abortController = new AbortController()
    runAbortRef.current = abortController

    updateNodeData({ isRunning: true, error: undefined })

    try {
      const result = await executeWorkflowGeneration(
        serializeGraph(getNodes(), getEdges()),
        id,
        {
          signal: abortController.signal,
          workspaceId,
          maxWaitMs: 30 * 60 * 1000,
        },
      )
      if (abortController.signal.aborted) return

      const videoUrl = result.video_url?.trim() || null
      if (!videoUrl) {
        throw new Error('Видео-генерация завершилась без URL')
      }

      const edges = getEdges()
      const previewTargets = new Set(getDownstreamPreviewNodeIds(id, edges))
      const generationId =
        typeof result.generation_id === 'number' ? result.generation_id : null

      setNodes((current) =>
        current.map((node) => {
          if (node.id === id) {
            return {
              ...node,
              data: {
                ...node.data,
                videoUrl,
                generationId,
                isRunning: false,
                error: undefined,
              },
            }
          }
          if (previewTargets.has(node.id) && node.type === 'preview') {
            return {
              ...node,
              data: {
                ...node.data,
                videoUrl,
                imageUrl: undefined,
                mediaKind: 'video',
              },
            }
          }
          return node
        }),
      )
    } catch (error) {
      if (isAbortError(error) || abortController.signal.aborted) {
        updateNodeData({ isRunning: false, error: undefined })
        return
      }
      updateNodeData({
        isRunning: false,
        error: error instanceof Error ? error.message : 'Ошибка видео',
      })
    } finally {
      if (runAbortRef.current === abortController) {
        runAbortRef.current = null
      }
    }
  }, [getEdges, getNodes, id, nodeData.disabled, setNodes, updateNodeData, workspaceId])

  const durationMin = isGrok ? (grokPricing.duration_min ?? 1) : (pricing.duration_min ?? 4)
  const durationMax = isGrok ? (grokPricing.duration_max ?? 15) : (pricing.duration_max ?? 15)
  const resolutions = isGrok
    ? (grokPricing.resolutions ?? ['480p', '720p'])
    : (pricing.resolutions ?? ['480p', '720p', '1080p'])
  const isPro = (me?.billing_plan ?? '').toLowerCase() === 'pro'

  const onModelChange = useCallback(
    (key: VideoModelKey) => {
      const patch = patchFromModelKey(key)
      if (key === 'grok-imagine-i2v') {
        const grokRes = grokPricing.resolutions ?? ['480p', '720p']
        const nextRes = grokRes.includes(videoResolution as GrokImagineI2vResolution)
          ? videoResolution
          : (grokPricing.default_resolution ?? '720p')
        const nextDur = Math.max(
          grokPricing.duration_min ?? 1,
          Math.min(grokPricing.duration_max ?? 15, durationSeconds),
        )
        updateNodeData({ ...patch, videoResolution: nextRes, durationSeconds: nextDur })
        return
      }
      const seedRes = pricing.resolutions ?? ['480p', '720p', '1080p']
      const nextRes = seedRes.includes(videoResolution as SeedanceT2vResolution)
        ? videoResolution
        : (pricing.default_resolution ?? '720p')
      const nextDur = Math.max(
        pricing.duration_min ?? 4,
        Math.min(pricing.duration_max ?? 15, durationSeconds),
      )
      updateNodeData({ ...patch, videoResolution: nextRes, durationSeconds: nextDur })
    },
    [durationSeconds, grokPricing, pricing, updateNodeData, videoResolution],
  )

  return (
    <BaseNode
      nodeId={id}
      type="videoGeneration"
      isRunning={nodeData.isRunning}
      error={nodeData.error}
      headerExtra={
        nodeData.videoUrl ? <span className="workflow-node__badge">готово</span> : null
      }
    >
      <Handle
        id={HandleIds.imageGenModelIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--model"
        style={{ top: '14%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '14%' }}
      >
        model
      </span>

      <Handle
        id={HandleIds.imageGenPromptIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--prompt"
        style={{ top: '22%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '22%' }}
      >
        prompt
      </span>

      <Handle
        id={HandleIds.clothingIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '34%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '34%' }}
      >
        clothing
      </span>

      <Handle
        id={HandleIds.environmentIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '46%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '46%' }}
      >
        environment
      </span>

      {!isGrok ? (
        <>
          <Handle
            id={HandleIds.motionVideoIn}
            type="target"
            position={Position.Left}
            className="workflow-handle workflow-handle--reference"
            style={{ top: '58%' }}
          />
          <span
            className="workflow-node__handle-label workflow-node__handle-label--left"
            style={{ top: '58%' }}
          >
            motion
          </span>

          <Handle
            id={HandleIds.imageGenReferenceIn}
            type="target"
            position={Position.Left}
            className="workflow-handle workflow-handle--reference"
            style={{ top: '70%' }}
          />
          <span
            className="workflow-node__handle-label workflow-node__handle-label--left"
            style={{ top: '70%' }}
          >
            refs
          </span>

          <Handle
            id={HandleIds.firstFrameIn}
            type="target"
            position={Position.Left}
            className="workflow-handle workflow-handle--generation workflow-handle--optional"
            style={{ top: '82%' }}
          />
          <span
            className="workflow-node__handle-label workflow-node__handle-label--left workflow-node__handle-label--muted"
            style={{ top: '82%' }}
          >
            1st frame opt
          </span>
        </>
      ) : (
        <Handle
          id={HandleIds.firstFrameIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--generation"
          style={{ top: '58%' }}
        />
      )}

      {!isGrok ? null : (
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '58%' }}
        >
          first frame
        </span>
      )}

      <p className="workflow-node__hint">
        {isGrok
          ? 'Grok Imagine Video · первый кадр + промпт с описанием движения'
          : 'BoardStory: @Image1+ = модель из кабинета, clothing/env refs, @Video1 = motion. Без первого кадра.'}
      </p>

      <div className="workflow-gen-form">
        <div className="workflow-gen-form__row">
          <label className="workflow-gen-form__label" htmlFor={`${id}-variant`}>
            Модель
          </label>
          <select
            id={`${id}-variant`}
            className="workflow-gen-form__select nodrag nowheel"
            value={modelKey}
            onChange={(e) => onModelChange(e.target.value as VideoModelKey)}
            disabled={nodeData.isRunning}
          >
            <option value="seedance-standard">Seedance 2.0</option>
            <option value="seedance-mini">Seedance 2.0 Mini</option>
            <option value="grok-imagine-i2v">Grok Imagine Video v1.5</option>
          </select>
        </div>

        <div className="workflow-gen-form__row">
          <label className="workflow-gen-form__label" htmlFor={`${id}-dur`}>
            Длительность
          </label>
          <select
            id={`${id}-dur`}
            className="workflow-gen-form__select nodrag nowheel"
            value={String(durationSeconds)}
            onChange={(e) => updateNodeData({ durationSeconds: Number(e.target.value) })}
            disabled={nodeData.isRunning}
          >
            {Array.from({ length: durationMax - durationMin + 1 }, (_, i) => durationMin + i).map(
              (sec) => (
                <option key={sec} value={sec}>
                  {sec} сек
                </option>
              ),
            )}
          </select>
        </div>

        <div className="workflow-gen-form__row">
          <label className="workflow-gen-form__label" htmlFor={`${id}-res`}>
            Качество
          </label>
          <select
            id={`${id}-res`}
            className="workflow-gen-form__select nodrag nowheel"
            value={videoResolution}
            onChange={(e) =>
              updateNodeData({
                videoResolution: e.target.value as SeedanceT2vResolution | GrokImagineI2vResolution,
              })
            }
            disabled={nodeData.isRunning}
          >
            {resolutions.map((res) => (
              <option key={res} value={res}>
                {res}
              </option>
            ))}
          </select>
        </div>

        {!isGrok ? (
          <>
            <div className="workflow-gen-form__row">
              <label className="workflow-gen-form__label" htmlFor={`${id}-aspect`}>
                Формат
              </label>
              <select
                id={`${id}-aspect`}
                className="workflow-gen-form__select nodrag nowheel"
                value={outputAspect}
                onChange={(e) => updateNodeData({ outputAspect: e.target.value })}
                disabled={nodeData.isRunning}
              >
                <option value="9:16">9:16</option>
                <option value="16:9">16:9</option>
                <option value="1:1">1:1</option>
                <option value="3:4">3:4</option>
                <option value="4:3">4:3</option>
              </select>
            </div>

            <label className="workflow-gen-form__check nodrag">
              <input
                type="checkbox"
                checked={generateAudio}
                onChange={(e) => updateNodeData({ generateAudio: e.target.checked })}
                disabled={nodeData.isRunning}
              />
              <span>Звук</span>
            </label>

            <label className="workflow-gen-form__check nodrag">
              <input
                type="checkbox"
                checked={autoMotionPrompt}
                onChange={(e) => updateNodeData({ autoMotionPrompt: e.target.checked })}
                disabled={nodeData.isRunning}
              />
              <span>Grok motion timeline (авто-описание движения)</span>
            </label>
          </>
        ) : null}
      </div>

      {nodeData.videoUrl ? (
        <div className="workflow-node__preview-box workflow-node__preview-box--filled nodrag">
          <video src={nodeData.videoUrl} controls playsInline className="workflow-node__preview-video" />
        </div>
      ) : (
        <div className="workflow-node__preview-box workflow-node__preview-box--compact">
          <span className="workflow-node__hint">Результат видео появится здесь</span>
        </div>
      )}

      <button
        type="button"
        className={
          nodeData.isRunning
            ? 'workflow-node__btn workflow-node__btn--ghost nodrag'
            : 'workflow-node__btn workflow-node__btn--primary nodrag'
        }
        onClick={() => (nodeData.isRunning ? onCancelRun() : void onGenerate())}
        disabled={nodeData.disabled === true && !nodeData.isRunning}
      >
        {nodeData.isRunning ? 'Отменить' : 'Сгенерировать видео'}
        {!nodeData.isRunning ? (
          <span className="workflow-node__btn-cost">
            {isPro ? 'Pro' : `${costCredits} кр.`}
          </span>
        ) : null}
      </button>

      <Handle
        id={HandleIds.videoOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--generation"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">video</span>
    </BaseNode>
  )
}

export const VideoGenerationNode = memo(VideoGenerationNodeComponent)
