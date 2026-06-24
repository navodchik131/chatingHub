import { memo, useCallback } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import { HandleIds, type RefDescriptionNodeData } from '../types'

function RefDescriptionNodeComponent({ id, data }: NodeProps) {
  const { setNodes } = useReactFlow()
  const nodeData = data as RefDescriptionNodeData

  const update = useCallback(
    (patch: Partial<RefDescriptionNodeData>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  return (
    <BaseNode nodeId={id} type="refDescription" error={nodeData.error}>
      <p className="workflow-node__hint">
        Опишите, зачем этот референс: поза, outfit, локация…
      </p>
      <label className="workflow-node__label">Роль</label>
      <input
        className="workflow-node__field nodrag nowheel"
        placeholder="Например: pose donor, outfit ref"
        value={nodeData.role ?? ''}
        onChange={(e) => update({ role: e.target.value })}
      />
      <label className="workflow-node__label">Описание</label>
      <textarea
        className="workflow-node__textarea nodrag nowheel"
        placeholder="Сидит на диване, вечерний свет, casual hoodie…"
        value={nodeData.description ?? ''}
        onChange={(e) => update({ description: e.target.value })}
      />
      <Handle
        id={HandleIds.descriptionOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--description"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">desc</span>
    </BaseNode>
  )
}

export const RefDescriptionNode = memo(RefDescriptionNodeComponent)
