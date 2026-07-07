import { memo, useCallback, useEffect, useRef, useState } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { executeWorkflowGeneration } from '../api'
import { getDownstreamPreviewNodeIds, serializeGraph } from '../graphResolver'
import { useWorkflowRun } from '../WorkflowRunContext'
import { WorkflowImageLightbox } from '../WorkflowImageLightbox'
import { BaseNode } from './BaseNode'
import { HandleIds, type TurnaroundSheetNodeData } from '../types'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function TurnaroundSheetNodeComponent({ id, data }: NodeProps) {
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const { workspaceId } = useWorkflowRun()
  const nodeData = data as TurnaroundSheetNodeData
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)
  const runAbortRef = useRef<AbortController | null>(null)

  const updateNodeData = useCallback(
    (patch: Partial<TurnaroundSheetNodeData>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  useEffect(() => {
    if (!nodeData.isRunning || runAbortRef.current) return
    updateNodeData({ isRunning: false })
  }, [nodeData.isRunning, updateNodeData])

  useEffect(() => {
    return () => {
      runAbortRef.current?.abort()
      runAbortRef.current = null
    }
  }, [])

  const onCancelRun = useCallback(() => {
    runAbortRef.current?.abort()
    runAbortRef.current = null
    updateNodeData({ isRunning: false, error: undefined })
  }, [updateNodeData])

  const onGenerate = useCallback(async () => {
    if (nodeData.disabled) return
    runAbortRef.current?.abort()
    const abortController = new AbortController()
    runAbortRef.current = abortController

    const nodes = getNodes()
    const edges = getEdges()
    const graph = serializeGraph(nodes, edges)

    updateNodeData({ isRunning: true, error: undefined })

    try {
      const result = await executeWorkflowGeneration(graph, id, {
        signal: abortController.signal,
        workspaceId,
        maxWaitMs: 25 * 60 * 1000,
      })
      if (abortController.signal.aborted) return

      const imageUrl = result.generated_image_url?.trim() || null
      if (!imageUrl) {
        throw new Error('Развёртка завершилась без URL изображения')
      }

      const previewTargets = new Set(getDownstreamPreviewNodeIds(id, edges))
      const generationId =
        typeof result.generation_id === 'number' ? result.generation_id : null

      setNodes((current) =>
        current.map((node) => {
          if (node.id === id) {
            return {
              ...node,
              data: {
                ...node.data,
                imageUrl,
                generationId,
                isRunning: false,
                error: undefined,
              },
            }
          }
          if (previewTargets.has(node.id) && node.type === 'preview') {
            return {
              ...node,
              data: {
                ...node.data,
                imageUrl,
                generationId,
                videoUrl: undefined,
                mediaKind: 'image',
              },
            }
          }
          return node
        }),
      )
    } catch (error) {
      if (isAbortError(error) || abortController.signal.aborted) {
        updateNodeData({ isRunning: false, error: undefined })
        return
      }
      updateNodeData({
        isRunning: false,
        error: error instanceof Error ? error.message : 'Ошибка развёртки',
      })
    } finally {
      if (runAbortRef.current === abortController) {
        runAbortRef.current = null
      }
    }
  }, [getEdges, getNodes, id, setNodes, updateNodeData, workspaceId])

  return (
    <>
      <BaseNode
        nodeId={id}
        type="turnaroundSheet"
        isRunning={nodeData.isRunning}
        error={nodeData.error}
        headerExtra={
          nodeData.imageUrl ? <span className="workflow-node__badge">готово</span> : null
        }
      >
        <Handle
          id={HandleIds.imageGenModelIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--model"
          style={{ top: '22%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '22%' }}
        >
          model
        </span>

        <Handle
          id={HandleIds.firstFrameIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--generation"
          style={{ top: '42%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '42%' }}
        >
          first frame
        </span>

        <Handle
          id={HandleIds.imageGenPromptIn}
          type="target"
          position={Position.Left}
          className="workflow-handle workflow-handle--prompt"
          style={{ top: '62%' }}
        />
        <span
          className="workflow-node__handle-label workflow-node__handle-label--left"
          style={{ top: '62%' }}
        >
          prompt
        </span>

        <p className="workflow-node__hint">
          GPT Image 2.0 · character sheet 16:9 · белая сетка на всех ракурсах с лицом (не сзади) ·
          одежда с первого кадра
        </p>

        {nodeData.imageUrl ? (
          <button
            type="button"
            className="workflow-node__preview-box workflow-node__preview-box--filled workflow-node__preview-click nodrag"
            onClick={() => setLightboxUrl(nodeData.imageUrl ?? null)}
          >
            <img src={nodeData.imageUrl} alt="Развёртка" />
          </button>
        ) : (
          <div className="workflow-node__preview-box workflow-node__preview-box--compact">
            <span className="workflow-node__hint">Подключите первый кадр и запустите</span>
          </div>
        )}

        <button
          type="button"
          className={
            nodeData.isRunning
              ? 'workflow-node__btn workflow-node__btn--ghost nodrag'
              : 'workflow-node__btn workflow-node__btn--primary nodrag'
          }
          onClick={() => (nodeData.isRunning ? onCancelRun() : void onGenerate())}
          disabled={nodeData.disabled === true && !nodeData.isRunning}
        >
          {nodeData.isRunning ? 'Отменить' : 'Сгенерировать развёртку'}
        </button>

        <Handle
          id={HandleIds.imageGenOut}
          type="source"
          position={Position.Right}
          className="workflow-handle workflow-handle--generation"
          style={{ top: '50%' }}
        />
        <span className="workflow-node__handle-label workflow-node__handle-label--right">sheet</span>
      </BaseNode>
      <WorkflowImageLightbox imageUrl={lightboxUrl} onClose={() => setLightboxUrl(null)} />
    </>
  )
}

export const TurnaroundSheetNode = memo(TurnaroundSheetNodeComponent)
