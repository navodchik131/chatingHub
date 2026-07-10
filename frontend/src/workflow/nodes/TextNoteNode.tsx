import { memo, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useReactFlow, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import type { TextNoteNodeData } from '../types'

function TextNoteNodeComponent({ id, data }: NodeProps) {
  const { t } = useTranslation('workflow')
  const { setNodes } = useReactFlow()
  const nodeData = data as TextNoteNodeData

  const onTextChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = event.target.value
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, text: value } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  return (
    <BaseNode nodeId={id} type="textNote">
      <p className="workflow-node__hint">{t('nodeUi.textNote.hint')}</p>
      <textarea
        className="workflow-node__textarea workflow-node__textarea--note nodrag nowheel"
        placeholder={t('nodeUi.textNote.placeholder')}
        value={nodeData.text ?? ''}
        onChange={onTextChange}
        rows={6}
      />
    </BaseNode>
  )
}

export const TextNoteNode = memo(TextNoteNodeComponent)
