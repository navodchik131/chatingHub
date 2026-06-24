import { memo, useCallback } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import { HandleIds, type RealismNodeData } from '../types'

function RealismNodeComponent({ id, data }: NodeProps) {
  const { setNodes } = useReactFlow()
  const nodeData = data as RealismNodeData
  const enabled = nodeData.enabled !== false

  const onToggle = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id
            ? { ...node, data: { ...node.data, enabled: event.target.checked } }
            : node,
        ),
      )
    },
    [id, setNodes],
  )

  return (
    <BaseNode nodeId={id} type="realism" error={nodeData.error}>
      <p className="workflow-node__hint">
        Phone candid realism — EXIF, grain, anti-plastic negative
      </p>
      <label className="workflow-node__toggle nodrag">
        <input type="checkbox" checked={enabled} onChange={onToggle} />
        <span>{enabled ? 'Включён' : 'Выключен'}</span>
      </label>
      <Handle
        id={HandleIds.realismOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--realism"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">realism</span>
    </BaseNode>
  )
}

export const RealismNode = memo(RealismNodeComponent)
