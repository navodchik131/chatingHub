import { memo, useCallback } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { executeWorkflowGeneration } from '../api'
import { getDownstreamPreviewNodeIds, serializeGraph } from '../graphResolver'
import { BaseNode } from './BaseNode'
import { HandleIds, type ImageGenerationNodeData } from '../types'

function ImageGenerationNodeComponent({ id, data }: NodeProps) {
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const nodeData = data as ImageGenerationNodeData

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
        style={{ top: '22%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '22%' }}
      >
        model
      </span>

      <Handle
        id={HandleIds.imageGenRealismIn}
        type="target"
        position={Position.Left}
        style={{ top: '38%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '38%' }}
      >
        realism
      </span>

      <Handle
        id={HandleIds.imageGenPromptIn}
        type="target"
        position={Position.Left}
        style={{ top: '54%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '54%' }}
      >
        prompt
      </span>

      <Handle
        id={HandleIds.imageGenReferenceIn}
        type="target"
        position={Position.Left}
        style={{ top: '70%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '70%' }}
      >
        reference
      </span>

      <p className="workflow-node__hint">
        Режим «Основная»: Grok prose → WaveSpeed без рефа в API
      </p>

      {nodeData.imageUrl ? (
        <div className="workflow-node__preview-box workflow-node__preview-box--filled">
          <img src={nodeData.imageUrl} alt="Результат генерации" />
        </div>
      ) : (
        <div className="workflow-node__preview-box">
          <span className="workflow-node__hint">Результат появится после генерации</span>
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
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">image</span>
    </BaseNode>
  )
}

export const ImageGenerationNode = memo(ImageGenerationNodeComponent)
