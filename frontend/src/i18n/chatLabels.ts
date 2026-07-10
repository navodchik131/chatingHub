import i18n, { CHAT_NS } from './index'
import type { ConversationCategory, ConversationCategoryLike } from '../conversationCategories'

export function conversationCategoryLabel(category: ConversationCategory): string {
  return i18n.t(`categories.${category}.label`, { ns: CHAT_NS, defaultValue: category })
}

export function conversationCategoryShort(category: ConversationCategory): string | undefined {
  const short = i18n.t(`categories.${category}.short`, {
    ns: CHAT_NS,
    defaultValue: '',
  })
  return short || undefined
}

export function manualCategoryLabel(value: '' | 'vip' | 'bomzh'): string {
  const key = value === '' ? 'none' : value
  return i18n.t(`manualCategory.${key}`, { ns: CHAT_NS })
}

export function conversationCategoryBadgeLabel(
  conv: ConversationCategoryLike,
): { key: string; label: string } | null {
  if (conv.peer_unavailable) return { key: 'unavailable', label: i18n.t('badges.unavailable', { ns: CHAT_NS }) }
  if (conv.is_blocked) return { key: 'blocked', label: i18n.t('badges.blocked', { ns: CHAT_NS }) }
  if (conv.manual_category === 'vip') return { key: 'vip', label: 'VIP' }
  if (conv.manual_category === 'bomzh') return { key: 'bomzh', label: i18n.t('badges.bomzh', { ns: CHAT_NS }) }
  if (conv.is_no_response) return { key: 'no_response', label: i18n.t('badges.noResponse', { ns: CHAT_NS }) }
  if (conv.is_new) return { key: 'new', label: i18n.t('badges.new', { ns: CHAT_NS }) }
  return null
}
