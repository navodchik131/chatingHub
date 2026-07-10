import i18n, { WORKSPACE_NS } from './index'

export function subscriptionStatusLabel(status: string | undefined): string {
  if (!status) return '—'
  return i18n.t(`cabinet.subscriptionStatus.${status}`, {
    ns: WORKSPACE_NS,
    defaultValue: status,
  })
}

export function creditKindLabel(kind: string): string {
  return i18n.t(`cabinet.creditKinds.${kind}`, {
    ns: WORKSPACE_NS,
    defaultValue: kind,
  })
}

export function memberPermissionLabel(key: string): string {
  return i18n.t(`cabinet.team.perms.${key}`, { ns: WORKSPACE_NS })
}

export function companionModeLabel(value: string, scope: 'connection' | 'conversation' = 'connection'): string {
  const prefix = scope === 'conversation' ? 'cabinet.integrations.companionConv.' : 'cabinet.integrations.companion.'
  return i18n.t(`${prefix}${value}`, { ns: WORKSPACE_NS, defaultValue: value })
}
