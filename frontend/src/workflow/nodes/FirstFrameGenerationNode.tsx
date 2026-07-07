import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import {
  DEFAULT_GENERATION_MODEL_ID,
  DEFAULT_OUTPUT_ASPECT,
  aspectsForModel,
  fetchGenerationModelOptions,
  modelsForNsfwMode,
  pickValidAspect,
  pickValidModelId,
  type GenerationModelDefinition,
} from '../wavespeedModels'
import { useWorkflowBilling } from '../WorkflowBillingContext'
import { executeWorkflowGeneration } from '../api'
import { useWorkflowRun } from '../WorkflowRunContext'
import { getDownstreamPreviewNodeIds, hasPipelineInput, serializeGraph } from '../graphResolver'
import { WorkflowImageLightbox } from '../WorkflowImageLightbox'
import { BaseNode } from './BaseNode'
import { HandleIds, type FirstFrameGenerationNodeData } from '../types'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function FirstFrameGenerationNodeComponent({ id, data }: NodeProps) {
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const { workspaceId } = useWorkflowRun()
  const nodeData = data as FirstFrameGenerationNodeData
  const edges = getEdges()
  const scenarioMode = useMemo(() => hasPipelineInput(id, edges), [edges, id])
  const nsfwEnabled = nodeData.nsfwEnabled !== false
  const [models, setModels] = useState<GenerationModelDefinition[]>([])
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)
  const runAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    void fetchGenerationModelOptions().then(setModels)
  }, [])

  const availableModels = useMemo(
    () => modelsForNsfwMode(models, nsfwEnabled).filter((m) => m.id !== 'gpt-image-2'),
    [models, nsfwEnabled],
  )

  const waveModelId = useMemo(() => {
    if (availableModels.some((m) => m.id === nodeData.waveModelId)) {
      return nodeData.waveModelId || availableModels[0]?.id || 'nano-banana-pro'
    }
    return availableModels[0]?.id || 'nano-banana-pro'
  }, [availableModels, nodeData.waveModelId])
  const aspectOptions = useMemo(
    () => aspectsForModel(models, waveModelId),
    [models, waveModelId],
  )
  const { quoteWorkflowImageCredits } = useWorkflowBilling()
  const costQuote = quoteWorkflowImageCredits(waveModelId || DEFAULT_GENERATION_MODEL_ID, nsfwEnabled)
  const outputAspect = pickValidAspect(aspectOptions, nodeData.outputAspect)

  const updateNodeData = useCallback(
    (patch: Partial<FirstFrameGenerationNodeData>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  useEffect(() => {
    const nextModel = pickValidModelId(models, nsfwEnabled, nodeData.waveModelId)
    const nextAspect = pickValidAspect(
      aspectsForModel(models, nextModel),
      nodeData.outputAspect,
    )
    if (
      models.length > 0 &&
      (nodeData.waveModelId !== nextModel || nodeData.outputAspect !== nextAspect)
    ) {
      updateNodeData({ waveModelId: nextModel, outputAspect: nextAspect })
    }
  }, [models, nsfwEnabled, nodeData.waveModelId, nodeData.outputAspect, updateNodeData])

  useEffect(() => {
    if (!nodeData.isRunning || runAbortRef.current) return
    updateNodeData({ isRunning: false })
  }, [nodeData.isRunning, updateNodeData])

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

    const nodes = getNodes()
    const edges = getEdges()
    const graph = serializeGraph(nodes, edges)

    updateNodeData({ isRunning: true, error: undefined })

    try {
      const result = await executeWorkflowGeneration(graph, id, {
        signal: abortController.signal,
        workspaceId,
      })
      if (abortController.signal.aborted) return

      const imageUrl = result.generated_image_url?.trim() || null
      if (!imageUrl) {
        throw new Error('Задача завершилась без URL изображения')
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
                imageUrl,
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
                imageUrl,
                generationId,
                videoUrl: undefined,
                mediaKind: 'image',
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
        error: error instanceof Error ? error.message : 'Ошибка генерации',
      })
    } finally {
      if (runAbortRef.current === abortController) {
        runAbortRef.current = null
      }
    }
  }, [getEdges, getNodes, id, setNodes, updateNodeData])

  const onNsfwToggle = useCallback(
    (checked: boolean) => {
      const nextModel = pickValidModelId(models, checked, nodeData.waveModelId)
      const nextAspect = pickValidAspect(
        aspectsForModel(models, nextModel),
        nodeData.outputAspect,
      )
      updateNodeData({
        nsfwEnabled: checked,
        waveModelId: nextModel,
        outputAspect: nextAspect,
      })
    },
    [models, nodeData.outputAspect, nodeData.waveModelId, updateNodeData],
  )

  const onModelChange = useCallback(
    (modelId: string) => {
      const nextAspect = pickValidAspect(aspectsForModel(models, modelId), nodeData.outputAspect)
      updateNodeData({ waveModelId: modelId, outputAspect: nextAspect })
    },
    [models, nodeData.outputAspect, updateNodeData],
  )

  return (
    <>
      <BaseNode
        nodeId={id}
        type="firstFrameGeneration"
        isRunning={nodeData.isRunning}
        error={nodeData.error}
        headerExtra={
          nodeData.imageUrl ? <span className="workflow-node__badge">готово</span> : null
        }
      >
        <Handle
          id={HandleIds.pipelineIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--generation"
          style={{ top: '6%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '6%' }}
        >
          pipeline
        </span>

        {!scenarioMode ? (
          <>
        <Handle
          id={HandleIds.imageGenModelIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--model"
          style={{ top: '18%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '18%' }}
        >
          model
        </span>

        <Handle
          id={HandleIds.imageGenRealismIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--realism"
          style={{ top: '32%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '32%' }}
        >
          realism
        </span>

        <Handle
          id={HandleIds.imageGenPromptIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--prompt"
          style={{ top: '46%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '46%' }}
        >
          prompt
        </span>

        <Handle
          id={HandleIds.imageGenReferenceIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--reference"
          style={{ top: '60%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '60%' }}
        >
          ref (опц.)
        </span>

        <Handle
          id={HandleIds.motionVideoIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--motion"
          style={{ top: '74%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '74%' }}
        >
          motion
        </span>

        <p className="workflow-node__hint">
          Как в студии motion: видео → Grok → WaveSpeed. Лёгкая плёночная зернистость на кадре
          (без сетки на лице; опц. кадр в «Референс»).
        </p>
          </>
        ) : (
          <p className="workflow-node__hint workflow-node__hint--muted">
            Входы через сценарий «Первый кадр» — подключите model/motion/refs к scenario-ноде.
          </p>
        )}

        <div className="workflow-gen-form">
          <div className="workflow-gen-form__row">
            <label className="workflow-gen-form__label" htmlFor={`${id}-model`}>
              Модель
            </label>
            <select
              id={`${id}-model`}
              className="workflow-gen-form__select nodrag nowheel"
              value={waveModelId || DEFAULT_GENERATION_MODEL_ID}
              onChange={(e) => onModelChange(e.target.value)}
              disabled={nodeData.isRunning || !availableModels.length}
            >
              {availableModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.label}
                </option>
              ))}
            </select>
          </div>

          {aspectOptions.length > 0 ? (
            <div className="workflow-gen-form__row">
              <label className="workflow-gen-form__label" htmlFor={`${id}-aspect`}>
                Формат
              </label>
              <select
                id={`${id}-aspect`}
                className="workflow-gen-form__select nodrag nowheel"
                value={outputAspect || DEFAULT_OUTPUT_ASPECT}
                onChange={(e) => updateNodeData({ outputAspect: e.target.value })}
                disabled={nodeData.isRunning}
              >
                {aspectOptions.map((aspect) => (
                  <option key={aspect.key} value={aspect.key}>
                    {aspect.key} · {aspect.size}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <label className="workflow-gen-form__check nodrag">
            <input
              type="checkbox"
              checked={nsfwEnabled}
              onChange={(e) => onNsfwToggle(e.target.checked)}
              disabled={nodeData.isRunning}
            />
            <span>{nsfwEnabled ? 'NSFW' : 'Обычная генерация'}</span>
          </label>
        </div>

        {nodeData.imageUrl ? (
          <button
            type="button"
            className="workflow-node__preview-box workflow-node__preview-box--filled workflow-node__preview-click nodrag"
            onClick={() => setLightboxUrl(nodeData.imageUrl ?? null)}
          >
            <img src={nodeData.imageUrl} alt="Результат генерации" />
          </button>
        ) : (
          <div className="workflow-node__preview-box workflow-node__preview-box--compact">
            <span className="workflow-node__hint">Результат появится здесь</span>
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
          {nodeData.isRunning ? 'Отменить' : 'Сгенерировать кадр'}
          {!nodeData.isRunning ? (
            <span className="workflow-node__btn-cost">
              {costQuote.label === 'Pro' ? 'Pro' : `${costQuote.label} кр.`}
            </span>
          ) : null}
        </button>

        <Handle
          id={HandleIds.imageGenOut}
          type="source"
          position={Position.Right}
          className="workflow-handle workflow-handle--generation"
          style={{ top: '50%' }}
        />
        <span className="workflow-node__handle-label workflow-node__handle-label--right">image</span>
      </BaseNode>
      <WorkflowImageLightbox
        imageUrl={lightboxUrl}
        onClose={() => setLightboxUrl(null)}
      />
    </>
  )
}

export const FirstFrameGenerationNode = memo(FirstFrameGenerationNodeComponent)
