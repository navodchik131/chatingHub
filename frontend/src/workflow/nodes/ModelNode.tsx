import { memo, useCallback } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { useWorkflowModels } from '../WorkflowModelsContext'
import { BaseNode } from './BaseNode'
import { HandleIds, type ModelNodeData } from '../types'

function ModelNodeComponent({ id, data }: NodeProps) {
  const { setNodes } = useReactFlow()
  const models = useWorkflowModels()
  const nodeData = data as ModelNodeData

  const onChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      const raw = event.target.value
      const modelId = raw ? Number(raw) : null
      const model = models.find((m) => m.id === modelId)
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id
            ? {
                ...node,
                data: {
                  ...node.data,
                  modelId,
                  modelName: model?.name ?? '',
                  error: undefined,
                },
              }
            : node,
        ),
      )
    },
    [id, models, setNodes],
  )

  return (
    <BaseNode type="model" error={nodeData.error}>
      <p className="workflow-node__hint">Модель из кабинета — фото уйдут в Grok и WaveSpeed</p>
      <select
        className="workflow-node__field nodrag nowheel"
        value={nodeData.modelId ?? ''}
        onChange={onChange}
      >
        <option value="">Выберите модель…</option>
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name}
          </option>
        ))}
      </select>
      <Handle
        id={HandleIds.modelOut}
        type="source"
        position={Position.Right}
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">model</span>
    </BaseNode>
  )
}

export const ModelNode = memo(ModelNodeComponent)
