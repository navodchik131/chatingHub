import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { BaseNode } from './BaseNode'
import { HandleIds, type ScenarioOutfitChangeNodeData } from '../types'

function ScenarioOutfitChangeNodeComponent({ id, data }: NodeProps) {
  const nodeData = data as ScenarioOutfitChangeNodeData

  return (
    <BaseNode nodeId={id} type="scenarioOutfitChange" error={nodeData.error}>
      <Handle
        id={HandleIds.imageGenModelIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--model"
        style={{ top: '16%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '16%' }}
      >
        model
      </span>

      <Handle
        id={HandleIds.imageGenRealismIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--realism"
        style={{ top: '32%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '32%' }}
      >
        realism
      </span>

      <Handle
        id={HandleIds.imageGenSelfieIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--selfie"
        style={{ top: '40%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '40%' }}
      >
        selfie
      </span>

      <Handle
        id={HandleIds.imageGenPromptIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--prompt"
        style={{ top: '52%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '52%' }}
      >
        prompt
      </span>

      <Handle
        id={HandleIds.imageGenReferenceIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '68%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '68%' }}
      >
        references
      </span>

      <p className="workflow-node__hint">
        Сценарий «смена одежды»: photo base + outfit refs → нода «Генерация» через pipeline.
        Identity и pose сохраняются, меняется только одежда.
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

export const ScenarioOutfitChangeNode = memo(ScenarioOutfitChangeNodeComponent)
