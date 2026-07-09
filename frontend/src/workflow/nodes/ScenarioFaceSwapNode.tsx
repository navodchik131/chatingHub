import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import { HandleIds, type ScenarioFaceSwapNodeData } from '../types'

function ScenarioFaceSwapNodeComponent({ id, data }: NodeProps) {
  const nodeData = data as ScenarioFaceSwapNodeData

  return (
    <BaseNode nodeId={id} type="scenarioFaceSwap" error={nodeData.error}>
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
        model (opt)
      </span>

      <Handle
        id={HandleIds.imageGenRealismIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--realism"
        style={{ top: '28%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '28%' }}
      >
        realism
      </span>

      <Handle
        id={HandleIds.imageGenSelfieIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--selfie"
        style={{ top: '36%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '36%' }}
      >
        selfie
      </span>

      <Handle
        id={HandleIds.imageGenPromptIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--prompt"
        style={{ top: '48%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '48%' }}
      >
        prompt
      </span>

      <Handle
        id={HandleIds.identityRefIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--model"
        style={{ top: '62%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '62%' }}
      >
        identity ref
      </span>

      <Handle
        id={HandleIds.imageGenReferenceIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '76%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '76%' }}
      >
        scene ref
      </span>

      <p className="workflow-node__hint">
        Без ноды «Модель»: identity ref (кто) + scene ref (pose/фон). С моделью из кабинета —
        достаточно scene ref.
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

export const ScenarioFaceSwapNode = memo(ScenarioFaceSwapNodeComponent)
