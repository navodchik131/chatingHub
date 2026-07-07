import { memo, useMemo, useState } from 'react'
import { Handle, Position, useEdges, useNodes, type NodeProps } from '@xyflow/react'
import { resolveConnectedPreviewMedia, resolvePreviewGenerationId } from '../graphResolver'
import { WorkflowImageLightbox } from '../WorkflowImageLightbox'
import { BaseNode } from './BaseNode'
import { HandleIds, type PreviewNodeData, type RefDescriptionNodeData } from '../types'

function PreviewNodeComponent({ id, data }: NodeProps) {
  const nodes = useNodes()
  const edges = useEdges()
  const nodeData = data as PreviewNodeData
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)

  const connected = useMemo(
    () => resolveConnectedPreviewMedia(id, nodes, edges),
    [id, nodes, edges],
  )

  const imageUrl = connected.imageUrl ?? nodeData.imageUrl
  const videoUrl = connected.videoUrl ?? nodeData.videoUrl
  const mediaKind =
    connected.mediaKind ?? nodeData.mediaKind ?? (videoUrl ? 'video' : 'image')
  const hasMedia = Boolean(imageUrl || videoUrl)
  const hasImageRef = mediaKind === 'image' && Boolean(imageUrl)
  const generationId = useMemo(
    () => resolvePreviewGenerationId(id, nodes, edges) ?? nodeData.generationId ?? null,
    [id, nodes, edges, nodeData.generationId],
  )
  const canUseAsRef = hasImageRef && Boolean(generationId)

  const assignedRole = useMemo(() => {
    for (const edge of edges) {
      if (edge.target !== id || edge.targetHandle !== HandleIds.referenceDescriptionIn) continue
      const source = nodes.find((node) => node.id === edge.source)
      if (source?.type !== 'refDescription') continue
      const role = String((source.data as RefDescriptionNodeData).role ?? '').trim()
      if (role) return role
    }
    return ''
  }, [edges, id, nodes])

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
          id={HandleIds.referenceDescriptionIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--description"
          style={{ top: '22%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '22%' }}
        >
          desc
        </span>

        <Handle
          id={HandleIds.previewIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--preview"
          style={{ top: '58%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '58%' }}
        >
          {mediaKind === 'video' ? 'video' : 'image'}
        </span>

        {canUseAsRef ? (
          <>
            <Handle
              id={HandleIds.referenceOut}
              type="source"
              position={Position.Right}
              className="workflow-handle workflow-handle--reference"
              style={{ top: '58%' }}
            />
            <span
              className="workflow-node__handle-label workflow-node__handle-label--right"
              style={{ top: '58%' }}
            >
              ref
            </span>
          </>
        ) : null}

        <p className="workflow-node__hint">
          {mediaKind === 'video' ? (
            'Итоговое видео'
          ) : assignedRole ? (
            <>
              Роль: <strong>{assignedRole}</strong> — выход ref → references
            </>
          ) : canUseAsRef ? (
            <>Подключите «Описание референса» слева и ref → references</>
          ) : (
            'Подключите выход генерации или дождитесь результата'
          )}
        </p>

        {hasMedia ? (
          mediaKind === 'video' && videoUrl ? (
            <div className="workflow-node__preview-box workflow-node__preview-box--filled nodrag">
              <video
                key={videoUrl}
                src={videoUrl}
                controls
                playsInline
                className="workflow-node__preview-video"
              />
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
