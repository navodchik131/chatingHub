import { listWorkflowWorkspaces, uploadWorkflowReference } from '../workflow/api'
import type { ProjectGraph } from '../workflow/types'
import { postStudioJobAndWait, postStudioJobStart, type StudioJobAccepted } from '../studioJobs'
import {
  buildFaceSwapDualRefGraph,
  buildFaceSwapModelGraph,
  buildPhotoEditGraph,
  buildPoRefuGraph,
  buildPromptOnlyGraph,
  type BuiltStudioScenario,
  type StudioScenarioGenOptions,
} from './studioScenarioPresets'

export const DEMO_WORKFLOW_NAME = 'Смена модели'

export async function resolveWorkflowWorkspaceIdForExecute(
  workflowDemoLimited: boolean,
): Promise<number | null> {
  if (!workflowDemoLimited) return null
  const workspaces = await listWorkflowWorkspaces()
  const demoWs = workspaces.find((w) => w.name === DEMO_WORKFLOW_NAME)
  if (!demoWs) {
    throw new Error(
      `Не найден workflow «${DEMO_WORKFLOW_NAME}». Обновите страницу или откройте вкладку Workflow.`,
    )
  }
  return demoWs.id
}

export async function startStudioScenarioJob(
  built: BuiltStudioScenario,
  opts?: {
    workspaceId?: number | null
    signal?: AbortSignal
  },
): Promise<StudioJobAccepted> {
  const fd = new FormData()
  fd.append('graph', JSON.stringify(built.graph))
  fd.append('target_node_id', built.targetNodeId)
  if (opts?.workspaceId != null) {
    fd.append('workspace_id', String(opts.workspaceId))
  }
  return postStudioJobStart('/api/studio/workflow/execute', {
    method: 'POST',
    body: fd,
    timeoutMs: 120_000,
    signal: opts?.signal,
  })
}

export async function runStudioScenarioAndWait<T extends Record<string, unknown>>(
  built: BuiltStudioScenario,
  opts?: {
    workspaceId?: number | null
    signal?: AbortSignal
    pollMs?: number
    maxWaitMs?: number
  },
): Promise<T> {
  const fd = new FormData()
  fd.append('graph', JSON.stringify(built.graph))
  fd.append('target_node_id', built.targetNodeId)
  if (opts?.workspaceId != null) {
    fd.append('workspace_id', String(opts.workspaceId))
  }
  return postStudioJobAndWait<T>(
    '/api/studio/workflow/execute',
    { method: 'POST', body: fd, timeoutMs: 120_000, signal: opts?.signal },
    { pollMs: opts?.pollMs, maxWaitMs: opts?.maxWaitMs ?? 25 * 60 * 1000, signal: opts?.signal },
  )
}

export type StudioScenarioFaceSwapInput = {
  sceneFile: File
  identityFile?: File | null
  modelId?: number | null
  genOptions: StudioScenarioGenOptions
  workflowDemoLimited: boolean
  signal?: AbortSignal
}

export async function buildAndStartFaceSwapScenario(
  input: StudioScenarioFaceSwapInput,
): Promise<{ built: BuiltStudioScenario; accepted: StudioJobAccepted }> {
  const sceneRef = await uploadWorkflowReference(input.sceneFile)
  let built: BuiltStudioScenario
  if (input.modelId != null) {
    built = buildFaceSwapModelGraph(input.modelId, sceneRef.ref_id, input.genOptions)
  } else {
    if (!input.identityFile) {
      throw new Error('Загрузите фото модели или выберите модель из кабинета.')
    }
    const identityRef = await uploadWorkflowReference(input.identityFile)
    built = buildFaceSwapDualRefGraph(identityRef.ref_id, sceneRef.ref_id, input.genOptions)
  }
  const workspaceId = await resolveWorkflowWorkspaceIdForExecute(input.workflowDemoLimited)
  const accepted = await startStudioScenarioJob(built, {
    workspaceId,
    signal: input.signal,
  })
  return { built, accepted }
}

export async function buildAndStartPoRefuScenario(input: {
  modelId: number
  sceneFile: File
  genOptions: StudioScenarioGenOptions
  workflowDemoLimited: boolean
  signal?: AbortSignal
}): Promise<{ built: BuiltStudioScenario; accepted: StudioJobAccepted }> {
  const sceneRef = await uploadWorkflowReference(input.sceneFile)
  const built = buildPoRefuGraph(input.modelId, sceneRef.ref_id, input.genOptions)
  const workspaceId = await resolveWorkflowWorkspaceIdForExecute(input.workflowDemoLimited)
  const accepted = await startStudioScenarioJob(built, {
    workspaceId,
    signal: input.signal,
  })
  return { built, accepted }
}

export async function buildAndStartPromptOnlyScenario(input: {
  modelId: number
  genOptions: StudioScenarioGenOptions
  workflowDemoLimited: boolean
  signal?: AbortSignal
}): Promise<{ built: BuiltStudioScenario; accepted: StudioJobAccepted }> {
  const built = buildPromptOnlyGraph(input.modelId, input.genOptions)
  const workspaceId = await resolveWorkflowWorkspaceIdForExecute(input.workflowDemoLimited)
  const accepted = await startStudioScenarioJob(built, {
    workspaceId,
    signal: input.signal,
  })
  return { built, accepted }
}

export async function buildAndStartPhotoEditScenario(input: {
  sceneFile: File
  userPrompt: string
  genOptions: StudioScenarioGenOptions
  workflowDemoLimited: boolean
  signal?: AbortSignal
}): Promise<{ built: BuiltStudioScenario; accepted: StudioJobAccepted }> {
  const sceneRef = await uploadWorkflowReference(input.sceneFile)
  const built = buildPhotoEditGraph(sceneRef.ref_id, {
    ...input.genOptions,
    userPrompt: input.userPrompt,
  })
  const workspaceId = await resolveWorkflowWorkspaceIdForExecute(input.workflowDemoLimited)
  const accepted = await startStudioScenarioJob(built, {
    workspaceId,
    signal: input.signal,
  })
  return { built, accepted }
}

/** @deprecated prefer explicit builders — kept for tests */
export function buildScenarioGraph(
  preset: 'face_swap_dual' | 'po_refu',
  refs: { identityRefId?: string; sceneRefId: string; modelId?: number },
  opts: StudioScenarioGenOptions,
): BuiltStudioScenario {
  if (preset === 'face_swap_dual') {
    if (!refs.identityRefId) throw new Error('identityRefId required')
    return buildFaceSwapDualRefGraph(refs.identityRefId, refs.sceneRefId, opts)
  }
  if (refs.modelId == null) throw new Error('modelId required')
  return buildPoRefuGraph(refs.modelId, refs.sceneRefId, opts)
}

export type { ProjectGraph, StudioScenarioGenOptions, BuiltStudioScenario }
