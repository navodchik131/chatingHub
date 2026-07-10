import i18n, { WORKFLOW_NS } from '../i18n'
import type { NodeType } from './types'

export function workflowNodeLabel(type: NodeType): string {
  return i18n.t(`nodes.${type}.label`, { ns: WORKFLOW_NS, defaultValue: type })
}

export function workflowNodeDescription(type: NodeType): string {
  return i18n.t(`nodes.${type}.description`, { ns: WORKFLOW_NS, defaultValue: '' })
}

export function workflowPaletteSectionTitle(sectionId: string): string {
  return i18n.t(`palette.${sectionId}`, { ns: WORKFLOW_NS, defaultValue: sectionId })
}

export function workflowPageText(key: string, options?: Record<string, string>): string {
  return i18n.t(`page.${key}`, { ns: WORKFLOW_NS, ...options })
}
