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

export const CONVERSATION_CATEGORY_META: Record<
  ConversationCategory,
  { label: string; short?: string }
> = {
  all: { label: 'Все' },
  vip: { label: 'VIP' },
  bomzh: { label: 'Бомж' },
  no_response: { label: 'Без ответа', short: '24ч+' },
  new: { label: 'Новые' },
  blocked: { label: 'Заблок.' },
}

export const MANUAL_CATEGORY_OPTIONS: {
  value: '' | 'vip' | 'bomzh'
  label: string
}[] = [
  { value: '', label: 'Без категории' },
  { value: 'vip', label: 'VIP' },
  { value: 'bomzh', label: 'Бомж' },
]

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

export function conversationCategoryBadge(
  conv: ConversationCategoryLike,
): { key: string; label: string } | null {
  if (conv.is_blocked) return { key: 'blocked', label: 'Блок' }
  if (conv.manual_category === 'vip') return { key: 'vip', label: 'VIP' }
  if (conv.manual_category === 'bomzh') return { key: 'bomzh', label: 'Бомж' }
  if (conv.is_no_response) return { key: 'no_response', label: '24ч+' }
  if (conv.is_new) return { key: 'new', label: 'Новый' }
  return null
}
