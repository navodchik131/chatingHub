import type { ReactNode } from 'react'
import type { NodeType } from '../types'
import { NODE_ICONS, NODE_LABELS } from '../constants'

interface BaseNodeProps {
  type: NodeType
  children: ReactNode
  headerExtra?: ReactNode
  isRunning?: boolean
  error?: string
}

export function BaseNode({ type, children, headerExtra, isRunning, error }: BaseNodeProps) {
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
        {headerExtra}
      </div>
      <div className="workflow-node__body">{children}</div>
      {error ? <div className="workflow-node__error">{error}</div> : null}
    </div>
  )
}
