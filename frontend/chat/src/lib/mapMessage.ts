import type { ApiConversation, ApiMessage, UiChat, UiMessage } from '../types'
import { fmtDay, fmtTime, initials } from './format'
import { platformSrcId } from './platforms'

function firstAttachment(m: ApiMessage) {
  const hit = (m.attachments || []).find((a) => a?.url)
  return hit || null
}

function messageKind(m: ApiMessage): UiMessage['kind'] {
  const att = firstAttachment(m)
  if (!att) return 'text'
  if (att.kind === 'video_note') return 'video_note'
  if (att.kind === 'voice' || att.mime_type?.startsWith('audio/')) return 'voice'
  if (att.mime_type?.startsWith('video/')) return 'photo'
  if (att.mime_type?.startsWith('image/')) return 'photo'
  return 'file'
}

/** API → UI сообщение (формат Unibox). */
export function mapApiMessage(m: ApiMessage, conv: Pick<UiChat, 'tr' | 'lang'>): UiMessage {
  const out = m.direction === 'outbound'
  const original = (m.text_original || '').trim()
  const translated = (m.text_translated || '').trim()
  const att = firstAttachment(m)
  const kind = messageKind(m)

  let text = original
  let ru: string | undefined
  if (out) {
    if (original && translated && original !== translated) {
      text = original
      ru = translated
    } else {
      text = original || translated
    }
  } else {
    text = original
    if (translated && translated !== original) ru = translated
  }

  const reactions: Record<string, number> = {}
  const mine: string[] = []
  for (const r of m.reactions || []) {
    if (!r?.emoji) continue
    reactions[r.emoji] = (reactions[r.emoji] || 0) + 1
    if (r.actor === 'owner') mine.push(r.emoji)
  }

  return {
    id: m.id,
    kind,
    out,
    text,
    ru,
    lang: conv.lang,
    time: fmtTime(m.created_at),
    day: fmtDay(m.created_at),
    read: out,
    pending: Boolean(m.pending),
    replyTo: m.reply_to_message_id || undefined,
    attachmentUrl: att?.url || undefined,
    attachmentMime: att?.mime_type || undefined,
    mediaKey: att?.url ? att.url : undefined,
    fname: kind === 'file' ? (att?.url?.split('/').pop() || 'file') : undefined,
    fext: kind === 'file' ? 'FILE' : undefined,
    reactions,
    mine,
  }
}

export function mapApiMessages(rows: ApiMessage[], conv: Pick<UiChat, 'tr' | 'lang'>): UiMessage[] {
  return rows.map((m) => mapApiMessage(m, conv))
}

export function mapApiConversation(c: ApiConversation, index: number): UiChat {
  const name = (c.user_display_name || c.external_chat_id || `#${c.id}`).trim()
  const lang = (c.user_lang || 'ru').toLowerCase()
  const outbound = (c.outbound_lang || '').trim().toLowerCase()
  const translateOn = !c.auto_translate_disabled
  return {
    id: c.id,
    src: platformSrcId(c.platform),
    type: 'user',
    name,
    g: index % 7,
    unread: c.unread_count || 0,
    lang,
    handle: c.external_chat_id || '',
    tr: {
      in: translateOn,
      out: translateOn,
      lang: outbound || lang || 'en',
    },
    draft: '',
    msgs: [],
    notes: { p: {}, e: [] },
    raw: c,
    avatarUrl: c.avatar_url,
    biz: c.manual_category === 'bomzh',
    pinned: c.manual_category === 'vip',
  }
}

export function mergeApiMessages(existing: ApiMessage[], incoming: ApiMessage[]): ApiMessage[] {
  const byId = new Map<number, ApiMessage>()
  for (const m of existing) byId.set(m.id, m)
  for (const m of incoming) {
    const prev = byId.get(m.id)
    byId.set(m.id, prev ? { ...prev, ...m, pending: false } : m)
  }
  return [...byId.values()].sort((a, b) => a.id - b.id)
}

export function previewText(m: UiMessage | null): string {
  if (!m) return '—'
  if (m.kind === 'photo' || m.kind === 'video_note') {
    const tail = m.text ? `, ${m.text}` : ''
    return m.kind === 'video_note' ? `🎬 Кружок${tail}` : `🖼 Фото${tail}`
  }
  if (m.kind === 'voice') return '🎤 Голосовое'
  if (m.kind === 'file') return `📎 ${m.fname || 'Файл'}`
  return m.ru || m.text || '—'
}

/** Превью в списке диалогов: локальные msgs или last_message_preview с API. */
export function chatListPreview(c: UiChat): string {
  const loaded = c.msgs[c.msgs.length - 1]
  if (loaded) return previewText(loaded)
  const api = (c.raw.last_message_preview || '').trim()
  return api || '—'
}

/** Время последнего сообщения в списке. */
export function chatListTime(c: UiChat): string {
  const loaded = c.msgs[c.msgs.length - 1]
  if (loaded) return loaded.time
  if (c.raw.updated_at) return fmtTime(c.raw.updated_at)
  return ''
}

export function chatSubTitle(c: UiChat): { t: string; on: boolean } {
  return { t: c.raw.platform.replace('_', ' '), on: false }
}

export { initials }
