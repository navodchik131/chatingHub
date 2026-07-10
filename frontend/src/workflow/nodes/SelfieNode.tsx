import { memo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import { HandleIds, type SelfieNodeData } from '../types'

function SelfieNodeComponent({ id, data }: NodeProps) {
  const { t } = useTranslation('workflow')
  const { setNodes } = useReactFlow()
  const nodeData = data as SelfieNodeData
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
    <BaseNode nodeId={id} type="selfie" error={nodeData.error}>
      <p className="workflow-node__hint">{t('nodeUi.selfie.hint')}</p>
      <label className="workflow-node__toggle nodrag">
        <input type="checkbox" checked={enabled} onChange={onToggle} />
        <span>{enabled ? t('nodeUi.common.toggleOn') : t('nodeUi.common.toggleOff')}</span>
      </label>
      <Handle
        id={HandleIds.selfieOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--selfie"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">selfie</span>
    </BaseNode>
  )
}

export const SelfieNode = memo(SelfieNodeComponent)
