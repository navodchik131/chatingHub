import { apiFetch } from '../../api'
import { formatApiErrorDetail, formatHttpApiError } from '../../apiErrors'

export async function apiJson(path, init) {
  const res = await apiFetch(path, init)
  let data = {}
  try {
    data = await res.json()
  } catch {
    /* ignore */
  }
  if (!res.ok) {
    throw new Error(formatHttpApiError(res, data) || `${res.status} ${path}`)
  }
  return data
}

export async function apiJsonOptional(path, init, fallback) {
  try {
    return await apiJson(path, init)
  } catch {
    return fallback
  }
}

export function fmtCredits(n) {
  return String(Math.max(0, Math.round(Number(n) || 0)))
}

export function fmtMoney(minor, currency = 'RUB') {
  const c = String(currency || 'RUB').toUpperCase()
  const rub = (Number(minor) || 0) / 100
  if (c === 'RUB') {
    return `${rub.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`
  }
  return `${rub.toFixed(2)} ${c}`
}

export function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function fmtDateShort(iso, lang = 'ru') {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const dd = String(d.getDate()).padStart(2, '0')
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const yy = String(d.getFullYear()).slice(-2)
  return lang === 'ru' ? `${dd}.${mo}.${yy}` : `${mo}/${dd}/${yy}`
}

export function fmtToday(lang) {
  const d = new Date()
  const days =
    lang === 'ru'
      ? ['ВС', 'ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ']
      : ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
  const months =
    lang === 'ru'
      ? ['ЯНВАРЯ', 'ФЕВРАЛЯ', 'МАРТА', 'АПРЕЛЯ', 'МАЯ', 'ИЮНЯ', 'ИЮЛЯ', 'АВГУСТА', 'СЕНТЯБРЯ', 'ОКТЯБРЯ', 'НОЯБРЯ', 'ДЕКАБРЯ']
      : ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER']
  return `${days[d.getDay()]} · ${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`
}

export function platformLabel(p) {
  const x = String(p || '').toLowerCase()
  if (x === 'fanvue') return 'FANVUE'
  if (x === 'instagram') return 'INSTAGRAM'
  return 'TELEGRAM'
}

export const AV_GRADIENTS = [
  'linear-gradient(135deg,#38BDF8,#818CF8)',
  'linear-gradient(135deg,#FB923C,#F87171)',
  'linear-gradient(135deg,#4ADE80,#38BDF8)',
  'linear-gradient(135deg,#F472B6,#C084FC)',
  'linear-gradient(135deg,#FACC15,#FB923C)',
]

export const LANG_MAP = {
  'es*': 'Español',
  'en*': 'English',
  'de*': 'Deutsch',
  'ru*': 'Русский',
  nl: 'Nederlands',
}

/** Backend: studio_model_images.STUDIO_MODEL_IMAGE_KINDS */
export const STUDIO_MODEL_IMAGE_KINDS = ['face', 'turnaround', 'body', 'genitals', 'other']

export const PHOTO_TAG_DEFS = [
  { kind: 'face', ru: 'Лицо / идентичность', en: 'Face / identity', shortRu: 'Лицо', shortEn: 'Face' },
  { kind: 'turnaround', ru: 'Развёртка', en: 'Turnaround / character sheet', shortRu: 'Развёртка', shortEn: 'Turnaround' },
  { kind: 'body', ru: 'Тело целиком', en: 'Full body', shortRu: 'Тело', shortEn: 'Body' },
  { kind: 'genitals', ru: 'Интимная зона (реф.)', en: 'Intimate reference', shortRu: 'Интим', shortEn: 'Intimate' },
  { kind: 'other', ru: 'Общий референс', en: 'General reference', shortRu: 'Общий', shortEn: 'Other' },
]

export function normalizePhotoKind(kind) {
  const k = String(kind || 'other').toLowerCase()
  return STUDIO_MODEL_IMAGE_KINDS.includes(k) ? k : 'other'
}

export function photoTagDefs(lang) {
  return PHOTO_TAG_DEFS.map((d) => ({
    kind: d.kind,
    label: lang === 'ru' ? d.ru : d.en,
  }))
}

export function photoKindLabel(lang, kind) {
  const k = normalizePhotoKind(kind)
  const hit = PHOTO_TAG_DEFS.find((d) => d.kind === k)
  if (!hit) return k
  return lang === 'ru' ? hit.ru : hit.en
}

/** Короткая подпись на превью фото. */
export function photoKindShortLabel(lang, kind) {
  const k = normalizePhotoKind(kind)
  const hit = PHOTO_TAG_DEFS.find((d) => d.kind === k)
  if (!hit) return k
  return lang === 'ru' ? hit.shortRu : hit.shortEn
}

export function isPlausibleTelegramBotToken(token) {
  const t = String(token || '').trim()
  return /^\d+:[A-Za-z0-9_-]{20,}$/.test(t)
}

export function ownerReactionEmoji(reactions) {
  if (!Array.isArray(reactions)) return null
  const hit = reactions.find((r) => r && r.actor === 'owner')
  return hit?.emoji || null
}

export function firstAttachmentUrl(attachments) {
  if (!Array.isArray(attachments)) return null
  const hit = attachments.find((a) => a && a.url)
  return hit?.url || null
}
export const REACT_CHOICES = ['👍', '❤️', '😂', '😮', '😢', '🔥']
export const EMOJI_CHOICES = ['😊', '😍', '🥰', '😘', '💕', '🔥', '😂', '😅', '🙈', '😉', '💋', '🌹', '✨', '👀', '🥂', '💫']
