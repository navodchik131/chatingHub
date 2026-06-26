import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import {
  DEFAULT_MOTION_VIDEO_PRICING,
  computeMotionVideoCreditCost,
  mergeMotionVideoPricing,
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
} from '../types'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

const DEFAULT_ASPECT = '9:16'

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

  const durationSeconds = nodeData.durationSeconds ?? pricing.duration_default ?? 5
  const seedanceVariant = (nodeData.seedanceVariant ?? pricing.default_variant ?? 'standard') as SeedanceT2vVariant
  const videoResolution = (nodeData.videoResolution ??
    pricing.default_resolution ??
    '720p') as SeedanceT2vResolution
  const generateAudio = nodeData.generateAudio !== false
  const autoMotionPrompt = nodeData.autoMotionPrompt !== false
  const outputAspect = nodeData.outputAspect || DEFAULT_ASPECT

  const costCredits = useMemo(
    () =>
      computeMotionVideoCreditCost(durationSeconds, true, pricing, {
        variant: seedanceVariant,
        resolution: videoResolution,
      }),
    [pricing, durationSeconds, seedanceVariant, videoResolution],
  )

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
  }, [getEdges, getNodes, id, setNodes, updateNodeData, workspaceId])

  const durationMin = pricing.duration_min ?? 4
  const durationMax = pricing.duration_max ?? 15
  const resolutions = pricing.resolutions ?? ['480p', '720p', '1080p']
  const isPro = (me?.billing_plan ?? '').toLowerCase() === 'pro'

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
        style={{ top: '28%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '28%' }}
      >
        prompt
      </span>

      <Handle
        id={HandleIds.firstFrameIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--generation"
        style={{ top: '42%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '42%' }}
      >
        first frame
      </span>

      <Handle
        id={HandleIds.sheetIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--generation"
        style={{ top: '56%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '56%' }}
      >
        sheet
      </span>

      <Handle
        id={HandleIds.motionVideoIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '70%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '70%' }}
      >
        motion
      </span>

      <p className="workflow-node__hint">
        Seedance · @Image1 = первый кадр, @Image2 = развёртка (если включена), @Video1 = motion
      </p>

      <div className="workflow-gen-form">
        <div className="workflow-gen-form__row">
          <label className="workflow-gen-form__label" htmlFor={`${id}-variant`}>
            Модель
          </label>
          <select
            id={`${id}-variant`}
            className="workflow-gen-form__select nodrag nowheel"
            value={seedanceVariant}
            onChange={(e) =>
              updateNodeData({ seedanceVariant: e.target.value as SeedanceT2vVariant })
            }
            disabled={nodeData.isRunning}
          >
            <option value="standard">Seedance 2.0</option>
            <option value="mini">Seedance 2.0 Mini</option>
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
              updateNodeData({ videoResolution: e.target.value as SeedanceT2vResolution })
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
          <span>Grok motion timeline</span>
        </label>
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
