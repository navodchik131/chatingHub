import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation('workflow')

  return (
    <Panel position="bottom-left" className="workflow-canvas-controls-panel">
      <div className="workflow-canvas-controls" role="toolbar" aria-label={t('nodeUi.canvasControls.toolbarAria')}>
        {hasSelectedEdges && !locked ? (
          <button
            type="button"
            className="workflow-canvas-controls__btn workflow-canvas-controls__btn--disconnect"
            title={t('nodeUi.canvasControls.disconnect')}
            aria-label={t('nodeUi.canvasControls.disconnect')}
            onClick={onDisconnectEdges}
          >
            {t('nodeUi.canvasControls.disconnectShort')}
          </button>
        ) : null}
        <span className="workflow-canvas-controls__label">{t('nodeUi.canvasControls.zoomLabel')}</span>
        <button
          type="button"
          className="workflow-canvas-controls__btn"
          title={t('nodeUi.canvasControls.zoomIn')}
          aria-label={t('nodeUi.canvasControls.zoomIn')}
          onClick={onZoomIn}
        >
          +
        </button>
        <button
          type="button"
          className="workflow-canvas-controls__btn"
          title={t('nodeUi.canvasControls.zoomOut')}
          aria-label={t('nodeUi.canvasControls.zoomOut')}
          onClick={onZoomOut}
        >
          −
        </button>
        <button
          type="button"
          className="workflow-canvas-controls__btn"
          title={t('nodeUi.canvasControls.fitView')}
          aria-label={t('nodeUi.canvasControls.fitView')}
          onClick={onFitView}
        >
          ⊡
        </button>
        <button
          type="button"
          className={`workflow-canvas-controls__btn workflow-canvas-controls__btn--lock${locked ? ' is-active' : ''}`}
          title={locked ? t('nodeUi.canvasControls.lockOn') : t('nodeUi.canvasControls.lockOff')}
          aria-label={locked ? t('nodeUi.canvasControls.unlockAria') : t('nodeUi.canvasControls.lockAria')}
          aria-pressed={locked}
          onClick={onToggleLock}
        >
          {locked ? t('nodeUi.canvasControls.locked') : t('nodeUi.canvasControls.unlocked')}
        </button>
      </div>
    </Panel>
  )
}
