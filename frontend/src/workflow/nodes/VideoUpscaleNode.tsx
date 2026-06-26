import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import {
  computeVideoUpscaleCreditCost,
  DEFAULT_VIDEO_UPSCALE_PRICING,
  mergeMotionVideoPricing,
  type StudioMotionVideoPricing,
  type VideoUpscaleResolution,
} from '../../studioMotionPricing'
import { executeWorkflowGeneration, fetchWorkflowModelOptions } from '../api'
import { getDownstreamPreviewNodeIds, serializeGraph } from '../graphResolver'
import { useWorkflowBilling } from '../WorkflowBillingContext'
import { useWorkflowRun } from '../WorkflowRunContext'
import { BaseNode } from './BaseNode'
import { HandleIds, type VideoUpscaleNodeData } from '../types'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

const RESOLUTIONS: VideoUpscaleResolution[] = ['720p', '1080p', '2k', '4k']

function VideoUpscaleNodeComponent({ id, data }: NodeProps) {
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const { workspaceId } = useWorkflowRun()
  const { me } = useWorkflowBilling()
  const nodeData = data as VideoUpscaleNodeData
  const [pricing, setPricing] = useState<StudioMotionVideoPricing>(mergeMotionVideoPricing(null))
  const runAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    void fetchWorkflowModelOptions().then((opts) => {
      if (opts.video) setPricing(mergeMotionVideoPricing(opts.video))
    })
  }, [])

  const targetResolution = (nodeData.targetResolution ??
    pricing.video_upscale?.default_resolution ??
    '1080p') as VideoUpscaleResolution

  const costCredits = useMemo(
    () => computeVideoUpscaleCreditCost(targetResolution, pricing),
    [pricing, targetResolution],
  )

  const updateNodeData = useCallback(
    (patch: Partial<VideoUpscaleNodeData>) => {
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

  const onUpscale = useCallback(async () => {
    if (nodeData.disabled) return
    runAbortRef.current?.abort()
    const abortController = new AbortController()
    runAbortRef.current = abortController

    const nodes = getNodes()
    const edges = getEdges()

    updateNodeData({ isRunning: true, error: undefined })

    try {
      const result = await executeWorkflowGeneration(serializeGraph(nodes, edges), id, {
        signal: abortController.signal,
        workspaceId,
        maxWaitMs: 45 * 60 * 1000,
      })
      if (abortController.signal.aborted) return

      const videoUrl = result.video_url?.trim() || null
      if (!videoUrl) {
        throw new Error('Апскейл завершился без URL видео')
      }

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
              data: { ...node.data, videoUrl, imageUrl: undefined, mediaKind: 'video' },
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
        error: error instanceof Error ? error.message : 'Ошибка апскейла видео',
      })
    } finally {
      if (runAbortRef.current === abortController) {
        runAbortRef.current = null
      }
    }
  }, [getEdges, getNodes, id, nodeData.disabled, setNodes, updateNodeData, workspaceId])

  const isPro = (me?.billing_plan ?? '').toLowerCase() === 'pro'
  const upscalePricing = pricing.video_upscale ?? DEFAULT_VIDEO_UPSCALE_PRICING

  return (
    <BaseNode
      nodeId={id}
      type="videoUpscale"
      isRunning={nodeData.isRunning}
      error={nodeData.error}
      headerExtra={
        nodeData.videoUrl ? <span className="workflow-node__badge">готово</span> : null
      }
    >
      <Handle
        id={HandleIds.videoIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--generation"
        style={{ top: '40%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '40%' }}
      >
        video
      </span>

      <p className="workflow-node__hint">
        WaveSpeed Video Upscaler Pro — upscale готового ролика до 720p–4K
      </p>

      <div className="workflow-gen-form nodrag">
        <div className="workflow-gen-form__row">
          <label className="workflow-gen-form__label">Разрешение</label>
          <select
            className="workflow-gen-form__select nodrag"
            value={targetResolution}
            onChange={(e) =>
              updateNodeData({ targetResolution: e.target.value as VideoUpscaleResolution })
            }
            disabled={nodeData.isRunning}
          >
            {(upscalePricing.resolutions ?? RESOLUTIONS).map((r) => (
              <option key={r} value={r}>
                {r.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {nodeData.videoUrl ? (
        <div className="workflow-node__preview-box workflow-node__preview-box--filled nodrag">
          <video
            key={nodeData.videoUrl}
            src={nodeData.videoUrl}
            controls
            playsInline
            className="workflow-node__preview-video"
          />
        </div>
      ) : (
        <div className="workflow-node__preview-box workflow-node__preview-box--compact">
          <span className="workflow-node__hint">Подключите «Видео» и запустите апскейл</span>
        </div>
      )}

      <button
        type="button"
        className={
          nodeData.isRunning
            ? 'workflow-node__btn workflow-node__btn--ghost nodrag'
            : 'workflow-node__btn workflow-node__btn--primary nodrag'
        }
        onClick={() => (nodeData.isRunning ? onCancelRun() : void onUpscale())}
        disabled={nodeData.disabled === true && !nodeData.isRunning}
      >
        {nodeData.isRunning ? 'Отменить' : 'Апскейл видео'}
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

export const VideoUpscaleNode = memo(VideoUpscaleNodeComponent)
