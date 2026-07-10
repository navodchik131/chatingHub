import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Handle, Position, useReactFlow, type NodeProps } from '@xyflow/react'
import { executeWorkflowGeneration } from '../api'
import { serializeGraph, upstreamBoardstoryRefHasContent } from '../graphResolver'
import { useWorkflowBilling } from '../WorkflowBillingContext'
import { useWorkflowRun } from '../WorkflowRunContext'
import { WorkflowImageLightbox } from '../WorkflowImageLightbox'
import { SeedanceReferenceGuide } from '../SeedanceReferenceGuide'
import { BaseNode } from './BaseNode'
import { HandleIds, type ScenarioMotionVideoNodeData } from '../types'

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function ScenarioMotionVideoNodeComponent({ id, data }: NodeProps) {
  const { t } = useTranslation('workflow')
  const { setNodes, getNodes, getEdges } = useReactFlow()
  const { workspaceId } = useWorkflowRun()
  const { me } = useWorkflowBilling()
  const nodeData = data as ScenarioMotionVideoNodeData
  const runAbortRef = useRef<AbortController | null>(null)
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)

  const nodes = getNodes()
  const edges = getEdges()
  const clothingRefLoaded = useMemo(
    () => upstreamBoardstoryRefHasContent(id, HandleIds.clothingIn, nodes, edges),
    [edges, id, nodes],
  )
  const environmentRefLoaded = useMemo(
    () => upstreamBoardstoryRefHasContent(id, HandleIds.environmentIn, nodes, edges),
    [edges, id, nodes],
  )

  const generateClothing = nodeData.generateClothingFromVideo === true
  const generateEnvironment = nodeData.generateEnvironmentFromVideo === true
  const sendVideoReference = nodeData.sendVideoReference !== false
    && nodeData.sendReferenceImages !== false
  const generateAudio = nodeData.generateAudio !== false
  const autoMotionPrompt = nodeData.autoMotionPrompt !== false
  const showExtractPreviews =
    generateClothing ||
    generateEnvironment ||
    Boolean(nodeData.clothingImageUrl) ||
    Boolean(nodeData.environmentImageUrl)

  const updateNodeData = useCallback(
    (patch: Partial<ScenarioMotionVideoNodeData>) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      )
    },
    [id, setNodes],
  )

  useEffect(() => {
    return () => {
      runAbortRef.current?.abort()
      runAbortRef.current = null
    }
  }, [])

  const onCancelRun = useCallback(() => {
    runAbortRef.current?.abort()
    runAbortRef.current = null
    updateNodeData({ isRunning: false, error: undefined })
  }, [updateNodeData])

  const onGenerate = useCallback(async () => {
    if (nodeData.disabled) return
    runAbortRef.current?.abort()
    const abortController = new AbortController()
    runAbortRef.current = abortController

    updateNodeData({ isRunning: true, error: undefined })

    try {
      const result = await executeWorkflowGeneration(
        serializeGraph(getNodes(), getEdges()),
        id,
        {
          signal: abortController.signal,
          workspaceId,
          maxWaitMs: 15 * 60 * 1000,
        },
      )
      if (abortController.signal.aborted) return

      const prompt =
        (result.refined_prompt ?? '').trim() ||
        (result.motion_video_prompt_auto ?? '').trim() ||
        ''
      if (!prompt) {
        throw new Error(t('nodeUi.videoPromptCompose.noPromptText'))
      }

      updateNodeData({
        prompt,
        isRunning: false,
        error: undefined,
        composedAt: new Date().toISOString(),
        clothingGenerationId: result.clothing_generation_id ?? null,
        environmentGenerationId: result.environment_generation_id ?? null,
        clothingImageUrl: result.clothing_image_url?.trim() || undefined,
        environmentImageUrl: result.environment_image_url?.trim() || undefined,
      })
    } catch (error) {
      if (isAbortError(error) || abortController.signal.aborted) {
        updateNodeData({ isRunning: false, error: undefined })
        return
      }
      updateNodeData({
        isRunning: false,
        error: error instanceof Error ? error.message : t('nodeUi.videoPromptCompose.promptError'),
      })
    } finally {
      if (runAbortRef.current === abortController) {
        runAbortRef.current = null
      }
    }
  }, [getEdges, getNodes, id, nodeData.disabled, t, updateNodeData, workspaceId])

  const onPromptChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      updateNodeData({ prompt: event.target.value })
    },
    [updateNodeData],
  )

  const isPro = (me?.billing_plan ?? '').toLowerCase() === 'pro'
  const promptCost = 2

  return (
    <BaseNode
      nodeId={id}
      type="scenarioMotionVideo"
      isRunning={nodeData.isRunning}
      error={nodeData.error}
      headerExtra={
        nodeData.prompt?.trim() ? <span className="workflow-node__badge">{t('gen.done')}</span> : null
      }
    >
      <Handle
        id={HandleIds.imageGenModelIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--model"
        style={{ top: '8%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '8%' }}
      >
        model
      </span>

      <Handle
        id={HandleIds.motionVideoIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '18%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '18%' }}
      >
        motion
      </span>

      <Handle
        id={HandleIds.clothingIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '28%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '28%' }}
      >
        clothing
      </span>

      <Handle
        id={HandleIds.environmentIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '38%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '38%' }}
      >
        environment
      </span>

      <Handle
        id={HandleIds.imageGenReferenceIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--reference"
        style={{ top: '48%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '48%' }}
      >
        refs
      </span>

      <Handle
        id={HandleIds.imageGenPromptIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--prompt"
        style={{ top: '58%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left"
        style={{ top: '58%' }}
      >
        notes
      </span>

      <Handle
        id={HandleIds.firstFrameIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--generation workflow-handle--optional"
        style={{ top: '68%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left workflow-node__handle-label--muted"
        style={{ top: '68%' }}
      >
        1st frame opt
      </span>

      <Handle
        id={HandleIds.sheetIn}
        type="target"
        position={Position.Left}
        className="workflow-handle workflow-handle--generation workflow-handle--optional"
        style={{ top: '78%' }}
      />
      <span
        className="workflow-node__handle-label workflow-node__handle-label--left workflow-node__handle-label--muted"
        style={{ top: '78%' }}
      >
        sheet opt
      </span>

      <SeedanceReferenceGuide variant="compose" />

      <p className="workflow-node__hint">{t('nodeUi.scenarioMotionVideo.hint')}</p>

      <div className="workflow-gen-form nodrag">
        <label className="workflow-gen-form__check">
          <input
            type="checkbox"
            checked={sendVideoReference}
            onChange={(e) =>
              updateNodeData({
                sendVideoReference: e.target.checked,
                sendReferenceImages: undefined,
              })
            }
            disabled={nodeData.isRunning}
          />
          <span>{t('nodeUi.videoPromptCompose.sendMotionVideo')}</span>
        </label>
        <label className="workflow-gen-form__check">
          <input
            type="checkbox"
            checked={generateAudio}
            onChange={(e) => updateNodeData({ generateAudio: e.target.checked })}
            disabled={nodeData.isRunning}
          />
          <span>{t('nodeUi.videoGen.audio')}</span>
        </label>
        <label className="workflow-gen-form__check">
          <input
            type="checkbox"
            checked={autoMotionPrompt}
            onChange={(e) => updateNodeData({ autoMotionPrompt: e.target.checked })}
            disabled={nodeData.isRunning}
          />
          <span>{t('nodeUi.videoGen.grokMotionTimeline')}</span>
        </label>
        <label className="workflow-gen-form__check">
          <input
            type="checkbox"
            checked={generateClothing}
            onChange={(e) =>
              updateNodeData({
                generateClothingFromVideo: e.target.checked,
                ...(e.target.checked ? {} : { clothingGenerationId: null, clothingImageUrl: undefined }),
              })
            }
            disabled={nodeData.isRunning || clothingRefLoaded}
          />
          <span>{t('nodeUi.videoPromptCompose.generateClothing')}</span>
        </label>
        <label className="workflow-gen-form__check">
          <input
            type="checkbox"
            checked={generateEnvironment}
            onChange={(e) =>
              updateNodeData({
                generateEnvironmentFromVideo: e.target.checked,
                ...(e.target.checked
                  ? {}
                  : { environmentGenerationId: null, environmentImageUrl: undefined }),
              })
            }
            disabled={nodeData.isRunning || environmentRefLoaded}
          />
          <span>{t('nodeUi.videoPromptCompose.generateEnvironment')}</span>
        </label>
      </div>

      {showExtractPreviews ? (
        <div className="workflow-node__preview-row nodrag">
          {generateClothing || nodeData.clothingImageUrl ? (
            nodeData.clothingImageUrl ? (
              <button
                type="button"
                className="workflow-node__preview-box workflow-node__preview-box--filled workflow-node__preview-click"
                onClick={() => setLightboxUrl(nodeData.clothingImageUrl ?? null)}
              >
                <img src={nodeData.clothingImageUrl} alt={t('nodeUi.videoPromptCompose.clothingAlt')} />
                <span className="workflow-node__preview-caption">{t('nodeUi.videoPromptCompose.clothingCaption')}</span>
              </button>
            ) : (
              <div className="workflow-node__preview-box workflow-node__preview-box--compact">
                <span className="workflow-node__hint">{t('nodeUi.videoPromptCompose.clothingPending')}</span>
              </div>
            )
          ) : null}
          {generateEnvironment || nodeData.environmentImageUrl ? (
            nodeData.environmentImageUrl ? (
              <button
                type="button"
                className="workflow-node__preview-box workflow-node__preview-box--filled workflow-node__preview-click"
                onClick={() => setLightboxUrl(nodeData.environmentImageUrl ?? null)}
              >
                <img src={nodeData.environmentImageUrl} alt={t('nodeUi.videoPromptCompose.environmentAlt')} />
                <span className="workflow-node__preview-caption">{t('nodeUi.videoPromptCompose.environmentCaption')}</span>
              </button>
            ) : (
              <div className="workflow-node__preview-box workflow-node__preview-box--compact">
                <span className="workflow-node__hint">{t('nodeUi.videoPromptCompose.environmentPending')}</span>
              </div>
            )
          ) : null}
        </div>
      ) : null}

      <textarea
        className="workflow-node__textarea nodrag nowheel"
        placeholder={t('nodeUi.videoPromptCompose.promptPlaceholderShort')}
        value={nodeData.prompt ?? ''}
        onChange={onPromptChange}
        rows={6}
        readOnly={nodeData.isRunning}
      />

      <div className="workflow-gen-form__row nodrag">
        <label className="workflow-gen-form__label" htmlFor={`${id}-neg`}>
          Negative
        </label>
        <input
          id={`${id}-neg`}
          className="workflow-gen-form__input nodrag nowheel"
          type="text"
          placeholder={t('nodeUi.common.optional')}
          value={nodeData.negativePrompt ?? ''}
          onChange={(e) => updateNodeData({ negativePrompt: e.target.value })}
          disabled={nodeData.isRunning}
        />
      </div>

      <button
        type="button"
        className={
          nodeData.isRunning
            ? 'workflow-node__btn workflow-node__btn--ghost nodrag'
            : 'workflow-node__btn workflow-node__btn--primary nodrag'
        }
        onClick={() => (nodeData.isRunning ? onCancelRun() : void onGenerate())}
        disabled={nodeData.disabled === true && !nodeData.isRunning}
      >
        {nodeData.isRunning ? t('gen.cancel') : t('nodeUi.videoPromptCompose.generatePrompt')}
        {!nodeData.isRunning ? (
          <span className="workflow-node__btn-cost">
            {isPro ? 'Pro' : `${promptCost} ${t('gen.creditsUnit')}`}
          </span>
        ) : null}
      </button>

      <Handle
        id={HandleIds.pipelineOut}
        type="source"
        position={Position.Right}
        className="workflow-handle workflow-handle--generation"
        style={{ top: '50%' }}
      />
      <span className="workflow-node__handle-label workflow-node__handle-label--right">pipeline</span>

      <WorkflowImageLightbox imageUrl={lightboxUrl} onClose={() => setLightboxUrl(null)} />
    </BaseNode>
  )
}

export const ScenarioMotionVideoNode = memo(ScenarioMotionVideoNodeComponent)
