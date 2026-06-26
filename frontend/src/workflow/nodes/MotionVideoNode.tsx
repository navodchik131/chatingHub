import { memo, useCallback, useRef, useState } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { uploadWorkflowMotionVideo } from '../api'
import { BaseNode } from './BaseNode'
import { HandleIds, type MotionVideoNodeData } from '../types'

function MotionVideoNodeComponent({ id, data }: NodeProps) {
  const { setNodes } = useReactFlow()
  const nodeData = data as MotionVideoNodeData
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  const updateNodeData = useCallback(
    (patch: Partial<MotionVideoNodeData>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  const onPickFile = useCallback(() => {
    inputRef.current?.click()
  }, [])

  const onFileChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      event.target.value = ''
      if (!file) return
      setUploading(true)
      updateNodeData({ error: undefined })
      try {
        const { motion_video_file_id } = await uploadWorkflowMotionVideo(file)
        updateNodeData({
          motionVideoFileId: motion_video_file_id,
          fileName: file.name,
        })
      } catch (error) {
        updateNodeData({
          error: error instanceof Error ? error.message : 'Не удалось загрузить видео',
        })
      } finally {
        setUploading(false)
      }
    },
    [updateNodeData],
  )

  const onClear = useCallback(() => {
    updateNodeData({ motionVideoFileId: undefined, fileName: undefined, error: undefined })
  }, [updateNodeData])

  const hasVideo = Boolean(nodeData.motionVideoFileId)

  return (
    <BaseNode nodeId={id} type="motionVideo" error={nodeData.error}>
      <p className="workflow-node__hint">
        Motion-референс для Seedance (@Video1). Можно отключить ноду — тогда движение из промпта.
      </p>

      <input
        ref={inputRef}
        type="file"
        accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
        className="workflow-node__file-input"
        onChange={(e) => void onFileChange(e)}
      />

      {hasVideo ? (
        <>
          <p className="workflow-node__hint">{nodeData.fileName || 'Видео загружено'}</p>
          <button
            type="button"
            className="workflow-node__btn workflow-node__btn--ghost nodrag"
            onClick={onClear}
            disabled={uploading}
          >
            Удалить
          </button>
        </>
      ) : (
        <button
          type="button"
          className="workflow-node__btn workflow-node__btn--primary nodrag"
          onClick={onPickFile}
          disabled={uploading}
        >
          {uploading ? 'Загрузка…' : 'Загрузить MP4/WebM'}
        </button>
      )}

      <Handle
        id={HandleIds.motionVideoOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">motion</span>
    </BaseNode>
  )
}

export const MotionVideoNode = memo(MotionVideoNodeComponent)
