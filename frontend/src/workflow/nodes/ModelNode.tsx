import { memo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { useWorkflowModels } from '../WorkflowModelsContext'
import { BaseNode } from './BaseNode'
import { HandleIds, type ModelNodeData } from '../types'

function ModelNodeComponent({ id, data }: NodeProps) {
  const { t } = useTranslation('workflow')
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
    <BaseNode nodeId={id} type="model" error={nodeData.error}>
      <p className="workflow-node__hint">{t('nodeUi.model.hint')}</p>
      <select
        className="workflow-node__field nodrag nowheel"
        value={nodeData.modelId ?? ''}
        onChange={onChange}
      >
        <option value="">{t('nodeUi.model.selectPlaceholder')}</option>
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
        className="workflow-handle workflow-handle--model"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">model</span>
    </BaseNode>
  )
}

export const ModelNode = memo(ModelNodeComponent)
