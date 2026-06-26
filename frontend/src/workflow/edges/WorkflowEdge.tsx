import { useState } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  useReactFlow,
  type EdgeProps,
} from '@xyflow/react'

export function WorkflowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
  markerEnd,
  style,
}: EdgeProps) {
  const { setEdges } = useReactFlow()
  const [hovered, setHovered] = useState(false)
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const showTools = selected || hovered

  const onDisconnect = (event: React.MouseEvent) => {
    event.stopPropagation()
    setEdges((edges) => edges.filter((edge) => edge.id !== id))
  }

  return (
    <>
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={24}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      />
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} interactionWidth={20} />
      <EdgeLabelRenderer>
        <div
          className={`workflow-edge-tools nodrag nopan${showTools ? ' is-visible' : ''}`}
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: 'all',
          }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          <button
            type="button"
            className="workflow-edge-tools__btn"
            aria-label="Отсоединить"
            title="Отсоединить"
            onClick={onDisconnect}
          >
            ×
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
