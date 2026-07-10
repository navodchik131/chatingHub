import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Handle, Position, useEdges, useNodes, useReactFlow, type NodeProps } from '@xyflow/react'
import { fetchWorkflowReferencePreviewUrl, uploadWorkflowReference } from '../api'
import { BaseNode } from './BaseNode'
import { HandleIds, type RefDescriptionNodeData, type ReferenceNodeData } from '../types'

function ReferenceNodeComponent({ id, data }: NodeProps) {
  const { t } = useTranslation('workflow')
  const { setNodes } = useReactFlow()
  const edges = useEdges()
  const nodes = useNodes()
  const nodeData = data as ReferenceNodeData
  const fileInputRef = useRef<HTMLInputElement>(null)
  const previewUrlRef = useRef<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)

  const hasMedia = Boolean(nodeData.refId)

  const revokePreviewUrl = useCallback((url: string | null | undefined) => {
    if (url?.startsWith('blob:')) {
      URL.revokeObjectURL(url)
    }
  }, [])

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

  const clearMedia = useCallback(() => {
    revokePreviewUrl(previewUrlRef.current)
    previewUrlRef.current = null
    updateNodeData({
      refId: undefined,
      fileName: undefined,
      previewUrl: undefined,
      error: undefined,
    })
  }, [revokePreviewUrl, updateNodeData])

  useEffect(() => {
    const refId = nodeData.refId?.trim()
    if (!refId) {
      revokePreviewUrl(previewUrlRef.current)
      previewUrlRef.current = null
      return
    }

    if (nodeData.previewUrl) {
      previewUrlRef.current = nodeData.previewUrl
      return
    }

    let cancelled = false
    setIsPreviewLoading(true)

    void (async () => {
      try {
        const url = await fetchWorkflowReferencePreviewUrl(refId)
        if (cancelled) {
          revokePreviewUrl(url)
          return
        }
        revokePreviewUrl(previewUrlRef.current)
        previewUrlRef.current = url
        updateNodeData({ previewUrl: url, error: undefined })
      } catch {
        if (!cancelled) {
          clearMedia()
          updateNodeData({
            error: t('nodeUi.reference.refNotFound'),
          })
        }
      } finally {
        if (!cancelled) setIsPreviewLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [nodeData.refId, nodeData.previewUrl, clearMedia, revokePreviewUrl, t, updateNodeData])

  useEffect(
    () => () => {
      revokePreviewUrl(previewUrlRef.current)
    },
    [revokePreviewUrl],
  )

  const handleUpload = useCallback(
    async (file: File) => {
      setIsUploading(true)
      updateNodeData({ error: undefined })
      const localPreview = URL.createObjectURL(file)
      revokePreviewUrl(previewUrlRef.current)
      previewUrlRef.current = localPreview
      updateNodeData({ previewUrl: localPreview })
      try {
        const result = await uploadWorkflowReference(file)
        updateNodeData({
          refId: result.ref_id,
          fileName: result.file_name,
          previewUrl: localPreview,
          error: undefined,
        })
      } catch (error) {
        revokePreviewUrl(localPreview)
        previewUrlRef.current = null
        updateNodeData({
          previewUrl: undefined,
          error: error instanceof Error ? error.message : t('nodeUi.reference.uploadError'),
        })
      } finally {
        setIsUploading(false)
        setIsDragging(false)
      }
    },
    [revokePreviewUrl, t, updateNodeData],
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
    if (!isUploading && !isPreviewLoading) fileInputRef.current?.click()
  }, [isUploading, isPreviewLoading])

  const onClearMedia = useCallback(
    (event: React.MouseEvent) => {
      event.stopPropagation()
      clearMedia()
    },
    [clearMedia],
  )

  const dropzoneClass = [
    'workflow-node__dropzone',
    isDragging ? 'workflow-node__dropzone--active' : '',
    hasMedia ? 'workflow-node__dropzone--filled' : '',
  ]
    .filter(Boolean)
    .join(' ')

  const showPreview = hasMedia && Boolean(nodeData.previewUrl)
  const showLoading = isUploading || (hasMedia && isPreviewLoading && !nodeData.previewUrl)

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

  return (
    <BaseNode
      nodeId={id}
      type="reference"
      isRunning={nodeData.isRunning || isUploading || isPreviewLoading}
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

      <p className="workflow-node__hint">
        {assignedRole ? (
          <>
            {t('nodeUi.refDescription.roleLabel')}: <strong>{assignedRole}</strong>{' '}
            {t('nodeUi.reference.roleConnectGen')}
          </>
        ) : (
          <>{t('nodeUi.reference.uploadHint')}</>
        )}
      </p>
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
        {showLoading ? (
          <>
            <span className="workflow-spinner" />
            <p className="workflow-node__hint">
              {isUploading ? t('nodeUi.common.uploading') : t('nodeUi.common.previewLoading')}
            </p>
          </>
        ) : showPreview ? (
          <>
            <img
              src={nodeData.previewUrl}
              alt={nodeData.fileName ?? t('nodeUi.reference.refAlt')}
              className="workflow-node__preview-img"
            />
            <p className="workflow-node__hint">{nodeData.fileName}</p>
            <button type="button" className="workflow-node__btn workflow-node__btn--ghost" onClick={onClearMedia}>
              {t('nodeUi.common.remove')}
            </button>
          </>
        ) : (
          <>
            <span style={{ fontSize: '1.5rem', opacity: 0.4 }}>↑</span>
            <p className="workflow-node__hint">{t('nodeUi.reference.fileFormats')}</p>
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
