import { apiFetch } from '../api'
import { formatHttpApiError } from '../apiErrors'
import { postStudioJobAndWait } from '../studioJobs'
import type { ProjectGraph } from './types'

export interface WorkflowWorkspaceRecord {
  id: number
  name: string
  graph: ProjectGraph
  created_at: string
  updated_at: string
}

export interface WorkflowWorkspaceListItem {
  id: number
  name: string
  updated_at: string
}

export async function listWorkflowWorkspaces(): Promise<WorkflowWorkspaceListItem[]> {
  const r = await apiFetch('/api/studio/workflow/workspaces')
  if (!r.ok) return []
  const data = (await r.json()) as WorkflowWorkspaceListItem[]
  return Array.isArray(data) ? data : []
}

export async function createWorkflowWorkspace(name: string): Promise<WorkflowWorkspaceRecord> {
  const r = await apiFetch('/api/studio/workflow/workspaces', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  const data = (await r.json().catch(() => ({}))) as WorkflowWorkspaceRecord & { detail?: unknown }
  if (!r.ok) throw new Error(formatHttpApiError(r, data))
  return data
}

export async function getWorkflowWorkspace(id: number): Promise<WorkflowWorkspaceRecord> {
  const r = await apiFetch(`/api/studio/workflow/workspaces/${id}`)
  const data = (await r.json().catch(() => ({}))) as WorkflowWorkspaceRecord & { detail?: unknown }
  if (!r.ok) throw new Error(formatHttpApiError(r, data))
  return data
}

export async function saveWorkflowWorkspace(
  id: number,
  patch: { name?: string; graph?: ProjectGraph },
): Promise<WorkflowWorkspaceRecord> {
  const r = await apiFetch(`/api/studio/workflow/workspaces/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  const data = (await r.json().catch(() => ({}))) as WorkflowWorkspaceRecord & { detail?: unknown }
  if (!r.ok) throw new Error(formatHttpApiError(r, data))
  return data
}

export async function deleteWorkflowWorkspace(id: number): Promise<void> {
  const r = await apiFetch(`/api/studio/workflow/workspaces/${id}`, { method: 'DELETE' })
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw new Error(formatHttpApiError(r, data))
  }
}

export async function uploadWorkflowReference(
  file: File,
): Promise<{ ref_id: string; file_name: string }> {
  const fd = new FormData()
  fd.append('file', file)
  const r = await apiFetch('/api/studio/workflow/reference', { method: 'POST', body: fd })
  const data = (await r.json().catch(() => ({}))) as {
    ref_id?: string
    file_name?: string
    detail?: unknown
  }
  if (!r.ok) {
    throw new Error(formatHttpApiError(r, data))
  }
  if (!data.ref_id) {
    throw new Error('Сервер не вернул ref_id')
  }
  return { ref_id: data.ref_id, file_name: data.file_name ?? file.name }
}

export async function fetchWorkflowReferencePreviewUrl(refId: string): Promise<string> {
  const r = await apiFetch(
    `/api/studio/workflow/reference/${encodeURIComponent(refId)}`,
  )
  if (!r.ok) {
    const data = await r.json().catch(() => ({}))
    throw new Error(formatHttpApiError(r, data))
  }
  const blob = await r.blob()
  return URL.createObjectURL(blob)
}

export async function executeWorkflowGeneration(
  graph: ProjectGraph,
  targetNodeId: string,
  opts?: {
    signal?: AbortSignal
    pollMs?: number
    maxWaitMs?: number
  },
): Promise<{ generated_image_url?: string | null; generation_id?: number | null }> {
  const fd = new FormData()
  fd.append('graph', JSON.stringify(graph))
  fd.append('target_node_id', targetNodeId)
  return postStudioJobAndWait(
    '/api/studio/workflow/execute',
    { method: 'POST', body: fd, timeoutMs: 120_000, signal: opts?.signal },
    { pollMs: opts?.pollMs, maxWaitMs: opts?.maxWaitMs, signal: opts?.signal },
  )
}
