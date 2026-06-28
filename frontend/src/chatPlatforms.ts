export type ChatPlatform = 'telegram' | 'fanvue' | 'instagram'

export const CHAT_PLATFORM_ORDER: ChatPlatform[] = ['telegram', 'fanvue', 'instagram']

export const CHAT_PLATFORM_META: Record<
  ChatPlatform,
  { label: string; icon: string }
> = {
  telegram: { label: 'Telegram', icon: '/marketing/telegram.svg' },
  fanvue: { label: 'Fanvue', icon: '/marketing/fanvue.svg' },
  instagram: { label: 'Instagram', icon: '/marketing/insta.svg' },
}

export function chatPlatformLabel(platform: ChatPlatform): string {
  return CHAT_PLATFORM_META[platform].label
}

interface ConversationLike {
  platform: string
  unread_count?: number
}

interface IntegrationLike {
  telegram_connections?: unknown[] | null
  fanvue_connections?: unknown[] | null
  instagram_connections?: unknown[] | null
}

export function visibleChatPlatforms(
  conversations: ConversationLike[],
  integ: IntegrationLike | null | undefined,
): ChatPlatform[] {
  const has = (p: ChatPlatform) =>
    conversations.some((c) => c.platform === p) ||
    (p === 'telegram' ? (integ?.telegram_connections?.length ?? 0) > 0 : false) ||
    (p === 'fanvue' ? (integ?.fanvue_connections?.length ?? 0) > 0 : false) ||
    (p === 'instagram' ? (integ?.instagram_connections?.length ?? 0) > 0 : false)

  return CHAT_PLATFORM_ORDER.filter(has)
}

export function unreadCountForPlatform(
  conversations: ConversationLike[],
  platform: ChatPlatform,
): number {
  return conversations.reduce(
    (sum, c) => sum + (c.platform === platform ? (c.unread_count ?? 0) : 0),
    0,
  )
}
