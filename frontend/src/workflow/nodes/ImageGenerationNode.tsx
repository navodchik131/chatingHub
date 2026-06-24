import { memo, useCallback, useEffect, useMemo, useState } from 'react'
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
import { executeWorkflowGeneration } from '../api'
import { getDownstreamPreviewNodeIds, serializeGraph } from '../graphResolver'
import { WorkflowImageLightbox } from '../WorkflowImageLightbox'
import { BaseNode } from './BaseNode'
import { HandleIds, type ImageGenerationNodeData } from '../types'

function ImageGenerationNodeComponent({ id, data }: NodeProps) {
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const nodeData = data as ImageGenerationNodeData
  const nsfwEnabled = nodeData.nsfwEnabled !== false
  const [models, setModels] = useState<GenerationModelDefinition[]>([])
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)

  useEffect(() => {
    void fetchGenerationModelOptions().then(setModels)
  }, [])

  const availableModels = useMemo(
    () => modelsForNsfwMode(models, nsfwEnabled),
    [models, nsfwEnabled],
  )

  const waveModelId = pickValidModelId(models, nsfwEnabled, nodeData.waveModelId)
  const aspectOptions = useMemo(
    () => aspectsForModel(models, waveModelId),
    [models, waveModelId],
  )
  const outputAspect = pickValidAspect(aspectOptions, nodeData.outputAspect)

  const updateNodeData = useCallback(
    (patch: Partial<ImageGenerationNodeData>) => {
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

  const onGenerate = useCallback(async () => {
    const nodes = getNodes()
    const edges = getEdges()
    const graph = serializeGraph(nodes, edges)

    updateNodeData({ isRunning: true, error: undefined })

    try {
      const result = await executeWorkflowGeneration(graph, id)
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
              data: { ...node.data, imageUrl },
            }
          }
          return node
        }),
      )
    } catch (error) {
      updateNodeData({
        isRunning: false,
        error: error instanceof Error ? error.message : 'Ошибка генерации',
      })
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
        type="imageGeneration"
        isRunning={nodeData.isRunning}
        error={nodeData.error}
        headerExtra={
          nodeData.imageUrl ? <span className="workflow-node__badge">готово</span> : null
        }
      >
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
          reference
        </span>

        <label className="workflow-node__label">Модель</label>
        <select
          className="workflow-node__field nodrag nowheel"
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

        {aspectOptions.length > 0 ? (
          <>
            <label className="workflow-node__label">Формат</label>
            <select
              className="workflow-node__field nodrag nowheel"
              value={outputAspect || DEFAULT_OUTPUT_ASPECT}
              onChange={(e) => updateNodeData({ outputAspect: e.target.value })}
              disabled={nodeData.isRunning}
            >
              {aspectOptions.map((aspect) => (
                <option key={aspect.key} value={aspect.key}>
                  {aspect.label} · {aspect.size}
                </option>
              ))}
            </select>
          </>
        ) : null}

        <label className="workflow-node__toggle nodrag">
          <input
            type="checkbox"
            checked={nsfwEnabled}
            onChange={(e) => onNsfwToggle(e.target.checked)}
            disabled={nodeData.isRunning}
          />
          <span>{nsfwEnabled ? 'NSFW' : 'Regular'}</span>
        </label>

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
          className="workflow-node__btn workflow-node__btn--primary nodrag"
          onClick={() => void onGenerate()}
          disabled={nodeData.isRunning}
        >
          {nodeData.isRunning ? 'Генерация…' : 'Сгенерировать'}
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

export const ImageGenerationNode = memo(ImageGenerationNodeComponent)
