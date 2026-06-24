import { memo, useCallback, useRef, useState } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { uploadWorkflowReference } from '../api'
import { BaseNode } from './BaseNode'
import { HandleIds, type ReferenceNodeData } from '../types'

function ReferenceNodeComponent({ id, data }: NodeProps) {
  const { setNodes } = useReactFlow()
  const nodeData = data as ReferenceNodeData
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  const hasMedia = Boolean(nodeData.refId)

  const updateNodeData = useCallback(
    (patch: Partial<ReferenceNodeData>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  const handleUpload = useCallback(
    async (file: File) => {
      setIsUploading(true)
      updateNodeData({ error: undefined })
      try {
        const previewUrl = URL.createObjectURL(file)
        const result = await uploadWorkflowReference(file)
        updateNodeData({
          refId: result.ref_id,
          fileName: result.file_name,
          previewUrl,
          error: undefined,
        })
      } catch (error) {
        updateNodeData({
          error: error instanceof Error ? error.message : 'Ошибка загрузки',
        })
      } finally {
        setIsUploading(false)
        setIsDragging(false)
      }
    },
    [updateNodeData],
  )

  const onFileInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (file) void handleUpload(file)
      event.target.value = ''
    },
    [handleUpload],
  )

  const onDropZoneClick = useCallback(() => {
    if (!isUploading) fileInputRef.current?.click()
  }, [isUploading])

  const onClearMedia = useCallback(
    (event: React.MouseEvent) => {
      event.stopPropagation()
      updateNodeData({
        refId: undefined,
        fileName: undefined,
        previewUrl: undefined,
        error: undefined,
      })
    },
    [updateNodeData],
  )

  const dropzoneClass = [
    'workflow-node__dropzone',
    isDragging ? 'workflow-node__dropzone--active' : '',
    hasMedia ? 'workflow-node__dropzone--filled' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <BaseNode
      nodeId={id}
      type="reference"
      isRunning={nodeData.isRunning || isUploading}
      error={nodeData.error}
    >
      <Handle
        id={HandleIds.referenceDescriptionIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--description"
        style={{ top: '28%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '28%' }}
      >
        desc
      </span>

      <p className="workflow-node__hint">Референс сцены — подключите «Описание» слева</p>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        hidden
        onChange={onFileInputChange}
      />
      <div
        role="button"
        tabIndex={0}
        className={`${dropzoneClass} nodrag nowheel`}
        onClick={onDropZoneClick}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onDropZoneClick()
          }
        }}
        onDragOver={(event) => {
          event.preventDefault()
          event.stopPropagation()
          setIsDragging(true)
        }}
        onDragLeave={(event) => {
          event.preventDefault()
          event.stopPropagation()
          setIsDragging(false)
        }}
        onDrop={(event) => {
          event.preventDefault()
          event.stopPropagation()
          setIsDragging(false)
          const file = event.dataTransfer.files?.[0]
          if (file) void handleUpload(file)
        }}
      >
        {isUploading ? (
          <>
            <span className="workflow-spinner" />
            <p className="workflow-node__hint">Загрузка…</p>
          </>
        ) : hasMedia && nodeData.previewUrl ? (
          <>
            <img
              src={nodeData.previewUrl}
              alt={nodeData.fileName ?? 'Референс'}
              className="workflow-node__preview-img"
            />
            <p className="workflow-node__hint">{nodeData.fileName}</p>
            <button type="button" className="workflow-node__btn workflow-node__btn--ghost" onClick={onClearMedia}>
              Удалить
            </button>
          </>
        ) : (
          <>
            <span style={{ fontSize: '1.5rem', opacity: 0.4 }}>↑</span>
            <p className="workflow-node__hint">PNG, JPG, WEBP · до 25 МБ</p>
          </>
        )}
      </div>
      <Handle
        id={HandleIds.referenceOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '72%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--right"
        style={{ top: '72%' }}
      >
        ref
      </span>
    </BaseNode>
  )
}

export const ReferenceNode = memo(ReferenceNodeComponent)
