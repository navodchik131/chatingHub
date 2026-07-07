import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { NODE_DESCRIPTIONS, NODE_LABELS, NODE_PALETTE_SECTIONS } from './constants'
import { NODE_ICON_COLORS, NodeIcon } from './NodeIcons'
import { REACT_FLOW_DRAG_TYPE } from './nodeFactory'
import { isCoarsePointer } from './useWorkflowMobile'
import type { NodeType } from './types'

type Props = {
  onTapAdd?: (type: NodeType) => void
}

type PaletteTooltip = {
  title: string
  description: string
  x: number
  y: number
  placement: 'top' | 'bottom'
}

function PaletteItem({
  type,
  onDragStart,
  onItemClick,
  onShowTooltip,
  onHideTooltip,
}: {
  type: NodeType
  onDragStart: (event: React.DragEvent<HTMLButtonElement>, nodeType: NodeType) => void
  onItemClick: (type: NodeType) => void
  onShowTooltip: (el: HTMLElement, type: NodeType) => void
  onHideTooltip: () => void
}) {
  const color = NODE_ICON_COLORS[type]
  const label = NODE_LABELS[type]
  const description = NODE_DESCRIPTIONS[type]

  return (
    <button
      type="button"
      draggable
      className="workflow-palette-dock__item"
      aria-label={`${label} — ${description}`}
      title={isCoarsePointer() ? `${label} — ${description}` : undefined}
      onDragStart={(event) => onDragStart(event, type)}
      onClick={() => onItemClick(type)}
      onMouseEnter={(event) => onShowTooltip(event.currentTarget, type)}
      onMouseLeave={onHideTooltip}
      onFocus={(event) => onShowTooltip(event.currentTarget, type)}
      onBlur={onHideTooltip}
      style={{ ['--node-accent' as string]: color }}
    >
      <span className="workflow-palette-dock__icon">
        <NodeIcon type={type} size={18} />
      </span>
      <span className="workflow-palette-dock__label">{label}</span>
    </button>
  )
}

function paletteTooltipPlacement(rect: DOMRect): Pick<PaletteTooltip, 'x' | 'y' | 'placement'> {
  const x = rect.left + rect.width / 2
  const spaceAbove = rect.top
  const placement = spaceAbove >= 88 ? 'top' : 'bottom'
  return {
    x,
    y: placement === 'top' ? rect.top - 8 : rect.bottom + 8,
    placement,
  }
}

export function NodePaletteDock({ onTapAdd }: Props) {
  const [tooltip, setTooltip] = useState<PaletteTooltip | null>(null)

  const hideTooltip = useCallback(() => setTooltip(null), [])

  const showTooltip = useCallback((el: HTMLElement, type: NodeType) => {
    if (isCoarsePointer()) return
    const rect = el.getBoundingClientRect()
    setTooltip({
      title: NODE_LABELS[type],
      description: NODE_DESCRIPTIONS[type],
      ...paletteTooltipPlacement(rect),
    })
  }, [])

  useEffect(() => {
    if (!tooltip) return
    const onViewportChange = () => hideTooltip()
    window.addEventListener('resize', onViewportChange)
    return () => window.removeEventListener('resize', onViewportChange)
  }, [tooltip, hideTooltip])

  const onDragStart = (event: React.DragEvent<HTMLButtonElement>, nodeType: NodeType) => {
    hideTooltip()
    event.dataTransfer.setData(REACT_FLOW_DRAG_TYPE, nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  const onItemClick = (type: NodeType) => {
    if (onTapAdd && isCoarsePointer()) {
      onTapAdd(type)
    }
  }

  return (
    <>
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
                  onShowTooltip={showTooltip}
                  onHideTooltip={hideTooltip}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      {tooltip && typeof document !== 'undefined'
        ? createPortal(
            <div
              className={`workflow-palette-dock__tooltip workflow-palette-dock__tooltip--${tooltip.placement}`}
              role="tooltip"
              style={{ left: tooltip.x, top: tooltip.y }}
            >
              <strong>{tooltip.title}</strong>
              <span>{tooltip.description}</span>
            </div>,
            document.body,
          )
        : null}
    </>
  )
}
