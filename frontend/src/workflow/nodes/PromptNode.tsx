import { memo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import { HandleIds, type PromptNodeData } from '../types'

function PromptNodeComponent({ id, data }: NodeProps) {
  const { t } = useTranslation('workflow')
  const { setNodes } = useReactFlow()
  const nodeData = data as PromptNodeData

  const onPromptChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = event.target.value
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, prompt: value } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  return (
    <BaseNode
      nodeId={id}
      type="prompt"
      isRunning={nodeData.isRunning}
      error={nodeData.error}
    >
      <p className="workflow-node__hint">{t('nodeUi.prompt.hint')}</p>
      <textarea
        className="workflow-node__textarea nodrag nowheel"
        placeholder={t('nodeUi.prompt.placeholder')}
        value={nodeData.prompt ?? ''}
        onChange={onPromptChange}
      />
      <Handle
        id={HandleIds.promptOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--prompt"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">prompt</span>
    </BaseNode>
  )
}

export const PromptNode = memo(PromptNodeComponent)
