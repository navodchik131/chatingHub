import { memo, useMemo, useState } from 'react'
import { Handle, Position, useEdges, useNodes, type NodeProps } from '@xyflow/react'
import { resolveConnectedPreviewMedia } from '../graphResolver'
import { WorkflowImageLightbox } from '../WorkflowImageLightbox'
import { BaseNode } from './BaseNode'
import { HandleIds, type PreviewNodeData } from '../types'

function PreviewNodeComponent({ id, data }: NodeProps) {
  const nodes = useNodes()
  const edges = useEdges()
  const nodeData = data as PreviewNodeData
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)

  const connected = useMemo(
    () => resolveConnectedPreviewMedia(id, nodes, edges),
    [id, nodes, edges],
  )

  const imageUrl = nodeData.imageUrl ?? connected.imageUrl
  const videoUrl = nodeData.videoUrl ?? connected.videoUrl
  const mediaKind = nodeData.mediaKind ?? connected.mediaKind ?? (videoUrl ? 'video' : 'image')
  const hasMedia = Boolean(imageUrl || videoUrl)

  const handleDownload = () => {
    const url = videoUrl || imageUrl
    if (!url) return
    const link = document.createElement('a')
    link.href = url
    link.download = mediaKind === 'video' ? 'modelmate-workflow.mp4' : 'modelmate-workflow.png'
    link.target = '_blank'
    link.rel = 'noopener noreferrer'
    link.click()
  }

  return (
    <>
      <BaseNode nodeId={id} type="preview" isRunning={nodeData.isRunning} error={nodeData.error}>
        <Handle
          id={HandleIds.previewIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--preview"
          style={{ top: '50%' }}
        />
        <span className="workflow-node__handle-label workflow-node__handle-label--left">
          {mediaKind === 'video' ? 'video' : 'image'}
        </span>

        <p className="workflow-node__hint">
          {mediaKind === 'video' ? 'Итоговое видео' : 'Итоговое изображение'}
        </p>

        {hasMedia ? (
          mediaKind === 'video' && videoUrl ? (
            <div className="workflow-node__preview-box workflow-node__preview-box--filled nodrag">
              <video src={videoUrl} controls playsInline className="workflow-node__preview-video" />
            </div>
          ) : (
            <button
              type="button"
              className="workflow-node__preview-box workflow-node__preview-box--filled workflow-node__preview-click nodrag"
              onClick={() => setLightboxUrl(imageUrl ?? null)}
            >
              <img src={imageUrl!} alt="Результат генерации" />
            </button>
          )
        ) : (
          <div className="workflow-node__preview-box">
            <span className="workflow-node__hint">Подключите выход генерации</span>
          </div>
        )}

        <button
          type="button"
          className="workflow-node__btn workflow-node__btn--ghost nodrag"
          onClick={handleDownload}
          disabled={!hasMedia}
        >
          Скачать
        </button>
      </BaseNode>
      <WorkflowImageLightbox
        imageUrl={lightboxUrl}
        onClose={() => setLightboxUrl(null)}
      />
    </>
  )
}

export const PreviewNode = memo(PreviewNodeComponent)
