import { NODE_LABELS, NODE_PALETTE } from './constants'
import { NODE_ICON_COLORS, NodeIcon } from './NodeIcons'
import { REACT_FLOW_DRAG_TYPE } from './nodeFactory'
import { isCoarsePointer } from './useWorkflowMobile'
import type { NodeType } from './types'

type Props = {
  onTapAdd?: (type: NodeType) => void
}

export function NodePaletteDock({ onTapAdd }: Props) {
  const onDragStart = (event: React.DragEvent<HTMLButtonElement>, nodeType: NodeType) => {
    event.dataTransfer.setData(REACT_FLOW_DRAG_TYPE, nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  const onItemClick = (type: NodeType) => {
    if (onTapAdd && isCoarsePointer()) {
      onTapAdd(type)
    }
  }

  return (
    <div className="workflow-palette-dock" aria-label="Палитра нод">
      <div className="workflow-palette-dock__scroll">
        {NODE_PALETTE.map((type) => {
          const color = NODE_ICON_COLORS[type]
          return (
            <button
              key={type}
              type="button"
              draggable
              className="workflow-palette-dock__item"
              data-tooltip={NODE_LABELS[type]}
              aria-label={NODE_LABELS[type]}
              onDragStart={(event) => onDragStart(event, type)}
              onClick={() => onItemClick(type)}
              style={{ ['--node-accent' as string]: color }}
            >
              <span className="workflow-palette-dock__icon">
                <NodeIcon type={type} size={18} />
              </span>
              <span className="workflow-palette-dock__label">{NODE_LABELS[type]}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
