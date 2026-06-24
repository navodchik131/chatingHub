import { apiFetch } from '../api'
import { formatHttpApiError } from '../apiErrors'
import { postStudioJobAndWait } from '../studioJobs'
import type { ProjectGraph } from './types'

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

export async function executeWorkflowGeneration(
  graph: ProjectGraph,
  targetNodeId: string,
): Promise<{ generated_image_url?: string | null; generation_id?: number | null }> {
  const fd = new FormData()
  fd.append('graph', JSON.stringify(graph))
  fd.append('target_node_id', targetNodeId)
  return postStudioJobAndWait('/api/studio/workflow/execute', { method: 'POST', body: fd })
}
