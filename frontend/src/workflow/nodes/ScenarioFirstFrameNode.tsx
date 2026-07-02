import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import { HandleIds, type ScenarioFirstFrameNodeData } from '../types'

function ScenarioFirstFrameNodeComponent({ id, data }: NodeProps) {
  const nodeData = data as ScenarioFirstFrameNodeData

  return (
    <BaseNode nodeId={id} type="scenarioFirstFrame" error={nodeData.error}>
      <Handle
        id={HandleIds.imageGenModelIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--model"
        style={{ top: '14%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '14%' }}
      >
        model
      </span>

      <Handle
        id={HandleIds.imageGenPromptIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--prompt"
        style={{ top: '30%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '30%' }}
      >
        prompt
      </span>

      <Handle
        id={HandleIds.imageGenReferenceIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '46%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '46%' }}
      >
        refs
      </span>

      <Handle
        id={HandleIds.motionVideoIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference workflow-handle--optional"
        style={{ top: '62%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left workflow-node__handle-label--muted"
        style={{ top: '62%' }}
      >
        motion opt
      </span>

      <p className="workflow-node__hint">
        Сценарий «первый кадр»: модель + motion-видео или рефы → still на t=0 для motion-пайплайна.
        Подключите к «Первый кадр» через pipeline.
      </p>

      <Handle
        id={HandleIds.pipelineOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--generation"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">pipeline</span>
    </BaseNode>
  )
}

export const ScenarioFirstFrameNode = memo(ScenarioFirstFrameNodeComponent)
