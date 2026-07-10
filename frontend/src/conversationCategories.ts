export type ConversationCategory =
  | 'all'
  | 'vip'
  | 'bomzh'
  | 'no_response'
  | 'new'
  | 'blocked'

export interface ConversationCategoryLike {
  manual_category?: 'vip' | 'bomzh' | null
  is_blocked?: boolean
  peer_unavailable?: boolean
  is_no_response?: boolean
  is_new?: boolean
}

export const CONVERSATION_CATEGORY_ORDER: ConversationCategory[] = [
  'all',
  'vip',
  'bomzh',
  'no_response',
  'new',
  'blocked',
]

/** @deprecated use conversationCategoryLabel() from i18n/chatLabels */
export const CONVERSATION_CATEGORY_META: Record<
  ConversationCategory,
  { label: string; short?: string }
> = {
  all: { label: 'all' },
  vip: { label: 'vip' },
  bomzh: { label: 'bomzh' },
  no_response: { label: 'no_response' },
  new: { label: 'new' },
  blocked: { label: 'blocked' },
}

export const MANUAL_CATEGORY_VALUES = ['', 'vip', 'bomzh'] as const

export function matchesConversationCategory(
  conv: ConversationCategoryLike,
  category: ConversationCategory,
): boolean {
  switch (category) {
    case 'all':
      return true
    case 'vip':
      return conv.manual_category === 'vip'
    case 'bomzh':
      return conv.manual_category === 'bomzh'
    case 'no_response':
      return Boolean(conv.is_no_response)
    case 'new':
      return Boolean(conv.is_new)
    case 'blocked':
      return Boolean(conv.is_blocked)
    default:
      return true
  }
}

export function countForConversationCategory(
  conversations: ConversationCategoryLike[],
  category: ConversationCategory,
): number {
  return conversations.filter((c) => matchesConversationCategory(c, category)).length
}

/** @deprecated use conversationCategoryBadgeLabel() from i18n/chatLabels */
export function conversationCategoryBadge(
  conv: ConversationCategoryLike,
): { key: string; label: string } | null {
  if (conv.peer_unavailable) return { key: 'unavailable', label: 'unavailable' }
  if (conv.is_blocked) return { key: 'blocked', label: 'blocked' }
  if (conv.manual_category === 'vip') return { key: 'vip', label: 'VIP' }
  if (conv.manual_category === 'bomzh') return { key: 'bomzh', label: 'bomzh' }
  if (conv.is_no_response) return { key: 'no_response', label: 'no_response' }
  if (conv.is_new) return { key: 'new', label: 'new' }
  return null
}
