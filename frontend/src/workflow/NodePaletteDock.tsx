import { NODE_ICONS, NODE_LABELS, NODE_PALETTE } from './constants'
import { REACT_FLOW_DRAG_TYPE } from './nodeFactory'
import type { NodeType } from './types'

export function NodePaletteDock() {
  const onDragStart = (event: React.DragEvent<HTMLButtonElement>, nodeType: NodeType) => {
    event.dataTransfer.setData(REACT_FLOW_DRAG_TYPE, nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="workflow-palette-dock" aria-label="Палитра нод">
      {NODE_PALETTE.map((type) => (
        <button
          key={type}
          type="button"
          draggable
          className="workflow-palette-dock__item"
          data-tooltip={NODE_LABELS[type]}
          aria-label={NODE_LABELS[type]}
          onDragStart={(event) => onDragStart(event, type)}
        >
          <span className="workflow-palette-dock__icon">{NODE_ICONS[type]}</span>
        </button>
      ))}
    </div>
  )
}
