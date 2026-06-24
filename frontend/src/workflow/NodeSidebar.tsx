import { NODE_DESCRIPTIONS, NODE_ICONS, NODE_LABELS, NODE_PALETTE } from './constants'
import { REACT_FLOW_DRAG_TYPE } from './nodeFactory'
import type { NodeType } from './types'

export function NodeSidebar() {
  const onDragStart = (event: React.DragEvent<HTMLDivElement>, nodeType: NodeType) => {
    event.dataTransfer.setData(REACT_FLOW_DRAG_TYPE, nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <aside className="workflow-sidebar">
      <div className="workflow-sidebar__head">
        <h2>Ноды</h2>
        <p>Перетащите на канвас</p>
      </div>
      <div className="workflow-sidebar__list">
        {NODE_PALETTE.map((type) => (
          <div
            key={type}
            draggable
            className="workflow-palette-item"
            onDragStart={(event) => onDragStart(event, type)}
          >
            <div className="workflow-palette-item__row">
              <div className="workflow-palette-item__icon">{NODE_ICONS[type]}</div>
              <div>
                <p className="workflow-palette-item__label">{NODE_LABELS[type]}</p>
                <p className="workflow-palette-item__desc">{NODE_DESCRIPTIONS[type]}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="workflow-sidebar__hint">
        <p>• Описание → Референс → Генерация</p>
        <p>• × на ноде или Delete — удалить</p>
        <p>• Граф сохраняется локально</p>
      </div>
    </aside>
  )
}
