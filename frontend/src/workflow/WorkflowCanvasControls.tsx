import { Panel } from '@xyflow/react'

type Props = {
  locked: boolean
  hasSelectedEdges: boolean
  onDisconnectEdges: () => void
  onZoomIn: () => void
  onZoomOut: () => void
  onFitView: () => void
  onToggleLock: () => void
}

export function WorkflowCanvasControls({
  locked,
  hasSelectedEdges,
  onDisconnectEdges,
  onZoomIn,
  onZoomOut,
  onFitView,
  onToggleLock,
}: Props) {
  return (
    <Panel position="bottom-left" className="workflow-canvas-controls-panel">
      <div className="workflow-canvas-controls" role="toolbar" aria-label="Масштаб холста">
        {hasSelectedEdges && !locked ? (
          <button
            type="button"
            className="workflow-canvas-controls__btn workflow-canvas-controls__btn--disconnect"
            title="Отсоединить выбранные связи"
            aria-label="Отсоединить выбранные связи"
            onClick={onDisconnectEdges}
          >
            Отсоед.
          </button>
        ) : null}
        <span className="workflow-canvas-controls__label">Масштаб</span>
        <button
          type="button"
          className="workflow-canvas-controls__btn"
          title="Увеличить"
          aria-label="Увеличить"
          onClick={onZoomIn}
        >
          +
        </button>
        <button
          type="button"
          className="workflow-canvas-controls__btn"
          title="Уменьшить"
          aria-label="Уменьшить"
          onClick={onZoomOut}
        >
          −
        </button>
        <button
          type="button"
          className="workflow-canvas-controls__btn"
          title="Показать весь граф"
          aria-label="Показать весь граф"
          onClick={onFitView}
        >
          ⊡
        </button>
        <button
          type="button"
          className={`workflow-canvas-controls__btn workflow-canvas-controls__btn--lock${locked ? ' is-active' : ''}`}
          title={locked ? 'Разблокировать перетаскивание нод' : 'Заблокировать перетаскивание нод'}
          aria-label={locked ? 'Разблокировать ноды' : 'Заблокировать ноды'}
          aria-pressed={locked}
          onClick={onToggleLock}
        >
          {locked ? 'Блок' : 'Движ'}
        </button>
      </div>
    </Panel>
  )
}
