/** Типы API чата (совместимы с backend/schemas.py). */

export type PlatformId =
  | 'telegram'
  | 'telegram_user'
  | 'fanvue'
  | 'instagram'
  | string

export interface MessageAttachment {
  id: number
  kind: string
  url: string
  mime_type: string
}

export interface ApiMessage {
  id: number
  direction: 'inbound' | 'outbound'
  text_original: string
  text_translated: string | null
  created_at: string
  attachments?: MessageAttachment[]
  reply_to_message_id?: number | null
  reply_preview?: string | null
  reactions?: Array<{ emoji: string; actor?: string }>
  pending?: boolean
  companion_bot?: boolean
}

export interface ApiConversation {
  id: number
  platform: PlatformId
  external_chat_id: string
  user_display_name: string | null
  user_lang: string | null
  outbound_lang: string | null
  auto_translate_disabled: boolean
  companion_mode_override: string | null
  effective_companion_mode: string | null
  manual_category: 'vip' | 'bomzh' | null
  is_blocked: boolean
  peer_unavailable: boolean
  updated_at: string
  has_avatar: boolean
  avatar_url: string | null
  last_message_preview: string | null
  unread_count: number
  is_no_response?: boolean
  is_new?: boolean
}

export interface ConversationFolder {
  id: number
  name: string
  sort_order: number
  conversation_ids: number[]
}

export interface UserMe {
  id: number
  login?: string
  email?: string
  display_name?: string | null
}

export type RealtimeEvent = {
  type: string
  conversation_id?: number
  message?: ApiMessage
}

/** UI-модель сообщения (формат Unibox). */
export interface UiMessage {
  id: number
  kind: 'text' | 'photo' | 'voice' | 'file' | 'video_note' | 'service'
  out: boolean
  text: string
  ru?: string
  lang?: string
  time: string
  day: string
  read: boolean
  pending?: boolean
  replyTo?: number
  attachmentUrl?: string
  attachmentMime?: string
  mediaKey?: string
  fname?: string
  fext?: string
  reactions: Record<string, number>
  mine: string[]
}

/** UI-модель диалога. */
export interface UiChat {
  id: number
  src: string
  type: 'user'
  name: string
  g: number
  unread: number
  lang: string
  handle: string
  tr: { in: boolean; out: boolean; lang: string }
  draft: string
  msgs: UiMessage[]
  notes: { p: Record<string, string>; e: Array<{ d: string; t: string; ai?: boolean }> }
  raw: ApiConversation
  avatarUrl?: string | null
  pinned?: boolean
  muted?: boolean
  biz?: boolean
}

export interface ThreadCacheEntry {
  convId: number
  messages: ApiMessage[]
  savedAt: number
  lastMessageId: number | null
}

export interface ConversationsCacheEntry {
  items: ApiConversation[]
  savedAt: number
}
