import type { ReactNode } from 'react'
import { useCallback } from 'react'
import { useReactFlow } from '@xyflow/react'
import { NODE_LABELS } from '../constants'
import { NODE_ICON_COLORS, NodeIcon } from '../NodeIcons'
import { WorkflowNodeMenu } from '../WorkflowNodeMenu'
import { isWorkflowNodeDisabled } from '../workflowNodeState'
import type { NodeType } from '../types'

interface BaseNodeProps {
  nodeId: string
  type: NodeType
  children: ReactNode
  headerExtra?: ReactNode
  isRunning?: boolean
  error?: string
}

export function BaseNode({
  nodeId,
  type,
  children,
  headerExtra,
  isRunning,
  error,
}: BaseNodeProps) {
  const { setNodes, setEdges, getNode } = useReactFlow()
  const nodeData = getNode(nodeId)?.data as Record<string, unknown> | undefined
  const disabled = isWorkflowNodeDisabled(nodeData)

  const onDelete = useCallback(() => {
    setNodes((nodes) => nodes.filter((node) => node.id !== nodeId))
    setEdges((edges) =>
      edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
    )
  }, [nodeId, setEdges, setNodes])

  const onToggleDisabled = useCallback(() => {
    setNodes((nodes) =>
      nodes.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, disabled: !disabled } }
          : node,
      ),
    )
  }, [disabled, nodeId, setNodes])

  const classes = ['workflow-node', `workflow-node--${type}`]
  if (isRunning) classes.push('workflow-node--running')
  if (error) classes.push('workflow-node--error')
  if (disabled) classes.push('workflow-node--disabled')

  const iconColor = NODE_ICON_COLORS[type]

  return (
    <div className={classes.join(' ')}>
      <div className="workflow-node__header">
        <div className="workflow-node__header-left">
          <span
            className="workflow-node__type-icon"
            style={{ color: iconColor, background: `${iconColor}18` }}
          >
            <NodeIcon type={type} size={14} />
          </span>
          <span>{NODE_LABELS[type]}</span>
          {disabled ? <span className="workflow-node__badge workflow-node__badge--muted">выкл</span> : null}
          {isRunning ? <span className="workflow-spinner" aria-hidden /> : null}
        </div>
        <div className="workflow-node__header-actions">
          {headerExtra}
          <WorkflowNodeMenu
            disabled={disabled}
            onToggleDisabled={onToggleDisabled}
            onDelete={onDelete}
          />
        </div>
      </div>
      <div className="workflow-node__body">{children}</div>
      {error ? <div className="workflow-node__error">{error}</div> : null}
    </div>
  )
}
