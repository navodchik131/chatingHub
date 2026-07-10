import i18n, { WORKFLOW_NS } from '../i18n'
import { sanitizeGraphForExport } from './graphResolver'
import type { ProjectGraph } from './types'

export const WORKFLOW_EXPORT_FORMAT = 'modelmate-workflow' as const
export const WORKFLOW_EXPORT_VERSION = 1 as const

export interface WorkflowExportFile {
  format: typeof WORKFLOW_EXPORT_FORMAT
  version: typeof WORKFLOW_EXPORT_VERSION
  name: string
  exported_at: string
  graph: ProjectGraph
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidProjectGraph(raw: unknown): raw is ProjectGraph {
  if (!isRecord(raw)) return false
  return Array.isArray(raw.nodes) && Array.isArray(raw.edges)
}

export function parseWorkflowImport(raw: string): WorkflowExportFile {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error(i18n.t('nodeUi.export.invalidJson', { ns: WORKFLOW_NS }))
  }
  if (!isRecord(parsed)) {
    throw new Error(i18n.t('nodeUi.export.invalidFormat', { ns: WORKFLOW_NS }))
  }

  if (parsed.format === WORKFLOW_EXPORT_FORMAT && isValidProjectGraph(parsed.graph)) {
    return {
      format: WORKFLOW_EXPORT_FORMAT,
      version: WORKFLOW_EXPORT_VERSION,
      name: typeof parsed.name === 'string' && parsed.name.trim() ? parsed.name.trim() : i18n.t('nodeUi.export.importDefaultName', { ns: WORKFLOW_NS }),
      exported_at: typeof parsed.exported_at === 'string' ? parsed.exported_at : new Date().toISOString(),
      graph: parsed.graph,
    }
  }

  if (isValidProjectGraph(parsed)) {
    return {
      format: WORKFLOW_EXPORT_FORMAT,
      version: WORKFLOW_EXPORT_VERSION,
      name: i18n.t('nodeUi.export.importDefaultName', { ns: WORKFLOW_NS }),
      exported_at: new Date().toISOString(),
      graph: parsed,
    }
  }

  if (isRecord(parsed.graph) && isValidProjectGraph(parsed.graph)) {
    return {
      format: WORKFLOW_EXPORT_FORMAT,
      version: WORKFLOW_EXPORT_VERSION,
      name: typeof parsed.name === 'string' && parsed.name.trim() ? parsed.name.trim() : i18n.t('nodeUi.export.importDefaultName', { ns: WORKFLOW_NS }),
      exported_at: new Date().toISOString(),
      graph: parsed.graph,
    }
  }

  throw new Error(i18n.t('nodeUi.export.noGraph', { ns: WORKFLOW_NS }))
}

export function buildWorkflowExport(name: string, graph: ProjectGraph): WorkflowExportFile {
  return {
    format: WORKFLOW_EXPORT_FORMAT,
    version: WORKFLOW_EXPORT_VERSION,
    name: name.trim() || i18n.t('nodeUi.export.projectDefaultName', { ns: WORKFLOW_NS }),
    exported_at: new Date().toISOString(),
    graph: sanitizeGraphForExport(graph),
  }
}

export function downloadWorkflowExport(name: string, graph: ProjectGraph): void {
  const payload = buildWorkflowExport(name, graph)
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json;charset=utf-8',
  })
  const safeName = (name.trim() || 'workflow')
    .replace(/[^\w\u0400-\u04FF\-]+/gi, '-')
    .replace(/-+/g, '-')
    .slice(0, 48)
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = `${safeName || 'workflow'}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 500)
  }
}
