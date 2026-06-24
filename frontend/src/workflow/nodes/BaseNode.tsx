import type { ReactNode } from 'react'
import { useCallback } from 'react'
import { useReactFlow } from '@xyflow/react'
import type { NodeType } from '../types'
import { NODE_ICONS, NODE_LABELS } from '../constants'

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
  const { setNodes, setEdges } = useReactFlow()

  const onDelete = useCallback(() => {
    setNodes((nodes) => nodes.filter((node) => node.id !== nodeId))
    setEdges((edges) =>
      edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
    )
  }, [nodeId, setEdges, setNodes])

  const classes = ['workflow-node', `workflow-node--${type}`]
  if (isRunning) classes.push('workflow-node--running')
  if (error) classes.push('workflow-node--error')

  return (
    <div className={classes.join(' ')}>
      <div className="workflow-node__header">
        <div className="workflow-node__header-left">
          <span aria-hidden>{NODE_ICONS[type]}</span>
          <span>{NODE_LABELS[type]}</span>
          {isRunning ? <span className="workflow-spinner" aria-hidden /> : null}
        </div>
        <div className="workflow-node__header-actions">
          {headerExtra}
          <button
            type="button"
            className="workflow-node__delete nodrag"
            title="Удалить ноду"
            aria-label="Удалить ноду"
            onClick={onDelete}
          >
            ×
          </button>
        </div>
      </div>
      <div className="workflow-node__body">{children}</div>
      {error ? <div className="workflow-node__error">{error}</div> : null}
    </div>
  )
}
