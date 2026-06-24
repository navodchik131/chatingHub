import { memo, useMemo } from 'react'
import { Handle, Position, useEdges, useNodes, type NodeProps } from '@xyflow/react'
import { resolveConnectedImageUrl } from '../graphResolver'
import { BaseNode } from './BaseNode'
import { HandleIds, type PreviewNodeData } from '../types'

function PreviewNodeComponent({ id, data }: NodeProps) {
  const nodes = useNodes()
  const edges = useEdges()
  const nodeData = data as PreviewNodeData

  const imageUrl = useMemo(() => {
    if (nodeData.imageUrl) return nodeData.imageUrl
    return resolveConnectedImageUrl(id, nodes, edges)
  }, [id, nodes, edges, nodeData.imageUrl])

  const hasImage = Boolean(imageUrl)

  const handleDownload = () => {
    if (!imageUrl) return
    const link = document.createElement('a')
    link.href = imageUrl
    link.download = 'modelmate-workflow.png'
    link.target = '_blank'
    link.rel = 'noopener noreferrer'
    link.click()
  }

  return (
    <BaseNode nodeId={id} type="preview" isRunning={nodeData.isRunning} error={nodeData.error}>
      <Handle
        id={HandleIds.previewIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--preview"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--left">image</span>

      <p className="workflow-node__hint">Итоговое изображение</p>

      <div
        className={`workflow-node__preview-box ${hasImage ? 'workflow-node__preview-box--filled' : ''}`}
      >
        {hasImage ? (
          <img src={imageUrl} alt="Результат генерации" />
        ) : (
          <span className="workflow-node__hint">Подключите выход генерации</span>
        )}
      </div>

      <button
        type="button"
        className="workflow-node__btn workflow-node__btn--ghost nodrag"
        onClick={handleDownload}
        disabled={!hasImage}
      >
        Скачать
      </button>
    </BaseNode>
  )
}

export const PreviewNode = memo(PreviewNodeComponent)
