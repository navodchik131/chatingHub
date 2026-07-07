import { NODE_DESCRIPTIONS, NODE_LABELS, NODE_PALETTE_SECTIONS } from './constants'
import { NODE_ICON_COLORS, NodeIcon } from './NodeIcons'
import { REACT_FLOW_DRAG_TYPE } from './nodeFactory'
import { isCoarsePointer } from './useWorkflowMobile'
import type { NodeType } from './types'

type Props = {
  onTapAdd?: (type: NodeType) => void
}

function PaletteItem({
  type,
  onDragStart,
  onItemClick,
}: {
  type: NodeType
  onDragStart: (event: React.DragEvent<HTMLButtonElement>, nodeType: NodeType) => void
  onItemClick: (type: NodeType) => void
}) {
  const color = NODE_ICON_COLORS[type]
  const tooltip = `${NODE_LABELS[type]} — ${NODE_DESCRIPTIONS[type]}`

  return (
    <button
      type="button"
      draggable
      className="workflow-palette-dock__item"
      data-tooltip={tooltip}
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
      {NODE_PALETTE_SECTIONS.map((section) => (
        <div key={section.id} className="workflow-palette-dock__row">
          <div className="workflow-palette-dock__row-head">
            {section.badge ? (
              <span className="workflow-palette-dock__badge" aria-hidden>
                {section.badge}
              </span>
            ) : null}
            <span className="workflow-palette-dock__row-title">{section.title}</span>
          </div>
          <div className="workflow-palette-dock__items">
            {section.types.map((type) => (
              <PaletteItem
                key={type}
                type={type}
                onDragStart={onDragStart}
                onItemClick={onItemClick}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
