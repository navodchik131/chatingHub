import { memo, useCallback } from 'react'
import { useReactFlow, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import type { TextNoteNodeData } from '../types'

function TextNoteNodeComponent({ id, data }: NodeProps) {
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
      <p className="workflow-node__hint">
        Подсказки, чеклист или любой текст — не участвует в генерации
      </p>
      <textarea
        className="workflow-node__textarea workflow-node__textarea--note nodrag nowheel"
        placeholder={'Например: 1) photo base — исходная pose\n2) ref локации — только фон\n3) Seedream для edit…'}
        value={nodeData.text ?? ''}
        onChange={onTextChange}
        rows={6}
      />
    </BaseNode>
  )
}

export const TextNoteNode = memo(TextNoteNodeComponent)
