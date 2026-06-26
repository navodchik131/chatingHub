import { memo, useCallback, useEffect, useRef } from 'react'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { executeWorkflowGeneration } from '../api'
import { serializeGraph } from '../graphResolver'
import { useWorkflowBilling } from '../WorkflowBillingContext'
import { useWorkflowRun } from '../WorkflowRunContext'
import { BaseNode } from './BaseNode'
import { HandleIds, type VideoPromptComposeNodeData } from '../types'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function VideoPromptComposeNodeComponent({ id, data }: NodeProps) {
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const { workspaceId } = useWorkflowRun()
  const { me } = useWorkflowBilling()
  const nodeData = data as VideoPromptComposeNodeData
  const runAbortRef = useRef<AbortController | null>(null)

  const updateNodeData = useCallback(
    (patch: Partial<VideoPromptComposeNodeData>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      )
    },
    [id, setNodes],
  )

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

    updateNodeData({ isRunning: true, error: undefined })

    try {
      const result = await executeWorkflowGeneration(
        serializeGraph(getNodes(), getEdges()),
        id,
        {
          signal: abortController.signal,
          workspaceId,
          maxWaitMs: 15 * 60 * 1000,
        },
      )
      if (abortController.signal.aborted) return

      const prompt =
        (result.refined_prompt ?? '').trim() ||
        (result.motion_video_prompt_auto ?? '').trim() ||
        ''
      if (!prompt) {
        throw new Error('Генерация завершилась без текста промпта')
      }

      updateNodeData({
        prompt,
        isRunning: false,
        error: undefined,
        composedAt: new Date().toISOString(),
      })
    } catch (error) {
      if (isAbortError(error) || abortController.signal.aborted) {
        updateNodeData({ isRunning: false, error: undefined })
        return
      }
      updateNodeData({
        isRunning: false,
        error: error instanceof Error ? error.message : 'Ошибка генерации промпта',
      })
    } finally {
      if (runAbortRef.current === abortController) {
        runAbortRef.current = null
      }
    }
  }, [getEdges, getNodes, id, nodeData.disabled, updateNodeData, workspaceId])

  const onPromptChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      updateNodeData({ prompt: event.target.value })
    },
    [updateNodeData],
  )

  const isPro = (me?.billing_plan ?? '').toLowerCase() === 'pro'
  const promptCost = 2

  return (
    <BaseNode
      nodeId={id}
      type="videoPromptCompose"
      isRunning={nodeData.isRunning}
      error={nodeData.error}
      headerExtra={
        nodeData.prompt?.trim() ? <span className="workflow-node__badge">готово</span> : null
      }
    >
      <Handle
        id={HandleIds.imageGenModelIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--model"
        style={{ top: '10%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '10%' }}
      >
        model
      </span>

      <Handle
        id={HandleIds.motionVideoIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '22%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '22%' }}
      >
        motion
      </span>

      <Handle
        id={HandleIds.clothingIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '34%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '34%' }}
      >
        clothing
      </span>

      <Handle
        id={HandleIds.environmentIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '46%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '46%' }}
      >
        environment
      </span>

      <Handle
        id={HandleIds.imageGenReferenceIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '58%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '58%' }}
      >
        refs
      </span>

      <Handle
        id={HandleIds.imageGenPromptIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--prompt"
        style={{ top: '70%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '70%' }}
      >
        notes
      </span>

      <Handle
        id={HandleIds.firstFrameIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--generation workflow-handle--optional"
        style={{ top: '82%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left workflow-node__handle-label--muted"
        style={{ top: '82%' }}
      >
        1st frame opt
      </span>

      <p className="workflow-node__hint">
        Grok разбирает motion-видео детально → промпт с @Image/@Video для BoardStory Seedance
      </p>

      <textarea
        className="workflow-node__textarea nodrag nowheel"
        placeholder="Промпт появится после генерации — можно отредактировать вручную"
        value={nodeData.prompt ?? ''}
        onChange={onPromptChange}
        rows={8}
        readOnly={nodeData.isRunning}
      />

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
        {nodeData.isRunning ? 'Отменить' : 'Сгенерировать промпт'}
        {!nodeData.isRunning ? (
          <span className="workflow-node__btn-cost">
            {isPro ? 'Pro' : `${promptCost} кр.`}
          </span>
        ) : null}
      </button>

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

export const VideoPromptComposeNode = memo(VideoPromptComposeNodeComponent)
