import { describe, expect, it } from 'vitest'
import {
  matchesConversationCategory,
  sortConversationsForInbox,
} from './conversationCategories'

describe('conversationCategories', () => {
  it('matches unread category by unread_count', () => {
    expect(matchesConversationCategory({ unread_count: 2, updated_at: '' }, 'unread')).toBe(true)
    expect(matchesConversationCategory({ unread_count: 0, updated_at: '' }, 'unread')).toBe(false)
  })

  it('sorts unread conversations first then by updated_at', () => {
    const sorted = sortConversationsForInbox([
      { id: 1, unread_count: 0, updated_at: '2026-07-17T12:00:00Z' },
      { id: 2, unread_count: 1, updated_at: '2026-07-16T12:00:00Z' },
      { id: 3, unread_count: 2, updated_at: '2026-07-15T12:00:00Z' },
      { id: 4, unread_count: 0, updated_at: '2026-07-18T12:00:00Z' },
    ] as Array<{ id: number; unread_count: number; updated_at: string }>)

    expect(sorted.map((c) => c.id)).toEqual([3, 2, 4, 1])
  })
})
