import { memo, useCallback } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import {
  DEFAULT_WAVESPEED_MODEL_ID,
  WAVESPEED_MODELS,
} from '../wavespeedModels'
import { executeWorkflowGeneration } from '../api'
import { getDownstreamPreviewNodeIds, serializeGraph } from '../graphResolver'
import { BaseNode } from './BaseNode'
import { HandleIds, type ImageGenerationNodeData } from '../types'

function ImageGenerationNodeComponent({ id, data }: NodeProps) {
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const nodeData = data as ImageGenerationNodeData
  const waveModelId = nodeData.waveModelId ?? DEFAULT_WAVESPEED_MODEL_ID
  const nsfwEnabled = nodeData.nsfwEnabled !== false

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

  return (
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

      <label className="workflow-node__label">Модель WaveSpeed</label>
      <select
        className="workflow-node__field nodrag nowheel"
        value={waveModelId}
        onChange={(e) => updateNodeData({ waveModelId: e.target.value })}
        disabled={nodeData.isRunning}
      >
        {WAVESPEED_MODELS.map((model) => (
          <option key={model.id} value={model.id}>
            {model.label} · {model.provider}
          </option>
        ))}
      </select>

      <label className="workflow-node__toggle nodrag">
        <input
          type="checkbox"
          checked={nsfwEnabled}
          onChange={(e) => updateNodeData({ nsfwEnabled: e.target.checked })}
          disabled={nodeData.isRunning}
        />
        <span>{nsfwEnabled ? 'NSFW (без лимитов Google)' : 'Regular (ограничения Google)'}</span>
      </label>

      {nodeData.imageUrl ? (
        <div className="workflow-node__preview-box workflow-node__preview-box--filled">
          <img src={nodeData.imageUrl} alt="Результат генерации" />
        </div>
      ) : (
        <div className="workflow-node__preview-box">
          <span className="workflow-node__hint">Grok соберёт промпт из графа → WaveSpeed</span>
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
  )
}

export const ImageGenerationNode = memo(ImageGenerationNodeComponent)
