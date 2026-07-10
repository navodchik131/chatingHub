import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { createPortal } from 'react-dom'
import {
  NODE_PALETTE_SECTIONS,
  WORKFLOW_PALETTE_COLLAPSED_KEY,
} from './constants'
import { workflowNodeDescription, workflowNodeLabel } from './workflowI18n'
import { NODE_ICON_COLORS, NodeIcon } from './NodeIcons'
import { REACT_FLOW_DRAG_TYPE } from './nodeFactory'
import { isCoarsePointer, useWorkflowMobile } from './useWorkflowMobile'
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

function readPaletteCollapsedPreference(isMobile: boolean): boolean {
  try {
    const raw = localStorage.getItem(WORKFLOW_PALETTE_COLLAPSED_KEY)
    if (raw === '1') return true
    if (raw === '0') return false
  } catch {
    /* ignore */
  }
  return isMobile
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
  const label = workflowNodeLabel(type)
  const description = workflowNodeDescription(type)

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
  const { t, i18n } = useTranslation('workflow')
  const isMobile = useWorkflowMobile()
  const dockRef = useRef<HTMLDivElement>(null)
  const [collapsed, setCollapsed] = useState(() => readPaletteCollapsedPreference(isMobile))
  const [tooltip, setTooltip] = useState<PaletteTooltip | null>(null)

  const hideTooltip = useCallback(() => setTooltip(null), [])

  const showTooltip = useCallback((el: HTMLElement, type: NodeType) => {
    if (isCoarsePointer() || collapsed) return
    const rect = el.getBoundingClientRect()
    setTooltip({
      title: workflowNodeLabel(type),
      description: workflowNodeDescription(type),
      ...paletteTooltipPlacement(rect),
    })
  }, [collapsed, i18n.language])

  useEffect(() => {
    if (!tooltip) return
    const onViewportChange = () => hideTooltip()
    window.addEventListener('resize', onViewportChange)
    return () => window.removeEventListener('resize', onViewportChange)
  }, [tooltip, hideTooltip])

  useEffect(() => {
    const layout = dockRef.current?.closest('.workflow-layout')
    if (!layout) return
    layout.classList.toggle('workflow-layout--palette-collapsed', collapsed)
    return () => layout.classList.remove('workflow-layout--palette-collapsed')
  }, [collapsed])

  const toggleCollapsed = useCallback(() => {
    hideTooltip()
    setCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem(WORKFLOW_PALETTE_COLLAPSED_KEY, next ? '1' : '0')
      } catch {
        /* ignore */
      }
      return next
    })
  }, [hideTooltip])

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
      <div
        ref={dockRef}
        className={`workflow-palette-dock${collapsed ? ' is-collapsed' : ''}`}
        aria-label={t('paletteDock.aria')}
      >
        <div className="workflow-palette-dock__toolbar">
          <span className="workflow-palette-dock__toolbar-title">{t('paletteDock.title')}</span>
          <button
            type="button"
            className="workflow-palette-dock__toggle"
            onClick={toggleCollapsed}
            aria-expanded={!collapsed}
            aria-controls="workflow-palette-dock-body"
            title={collapsed ? t('page.paletteExpand') : t('page.paletteCollapse')}
          >
            <span className="workflow-palette-dock__toggle-icon" aria-hidden>
              {collapsed ? '▲' : '▼'}
            </span>
            <span className="workflow-palette-dock__toggle-label">
              {collapsed ? t('paletteDock.expand') : t('paletteDock.collapse')}
            </span>
          </button>
        </div>
        {!collapsed ? (
          <div id="workflow-palette-dock-body" className="workflow-palette-dock__body">
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
        ) : null}
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
