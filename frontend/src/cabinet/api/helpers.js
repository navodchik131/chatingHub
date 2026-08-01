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

export function pickCurrencyAmount(map, preferred = 'RUB') {
  if (!map) return undefined
  const pref = String(preferred || 'RUB').toUpperCase()
  if (map[pref] != null) return map[pref]
  if (map[pref.toLowerCase()] != null) return map[pref.toLowerCase()]
  const keys = Object.keys(map)
  return keys.length ? map[keys[0]] : undefined
}

function donationAvailableAtUtc(occurredAt) {
  const y = occurredAt.getUTCFullYear()
  const m = occurredAt.getUTCMonth()
  const d = occurredAt.getUTCDate()
  if (d <= 15) return new Date(Date.UTC(y, m, 16))
  return new Date(Date.UTC(y, m + 1, 1))
}

export function isDonationAvailableForPayout(occurredAt, now = new Date()) {
  const at = occurredAt instanceof Date ? occurredAt : new Date(occurredAt)
  if (Number.isNaN(at.getTime())) return false
  return now.getTime() >= donationAvailableAtUtc(at).getTime()
}

/** Разбивка сумм по статусу выплаты — как в mm-os-bridge. */
export function summarizeDonationPayouts(events, now = new Date()) {
  const totalByCurrency = {}
  const availableByCurrency = {}
  const heldByCurrency = {}
  const paidByCurrency = {}
  for (const ev of events || []) {
    if (!ev || ev.amount_minor <= 0) continue
    const cur = String(ev.currency || 'RUB').toUpperCase()
    totalByCurrency[cur] = (totalByCurrency[cur] ?? 0) + ev.amount_minor
    if (ev.payout_status === 'paid') {
      paidByCurrency[cur] = (paidByCurrency[cur] ?? 0) + ev.amount_minor
      continue
    }
    if (ev.payout_status === 'in_request') continue
    const at = new Date(ev.occurred_at)
    if (isDonationAvailableForPayout(at, now)) {
      availableByCurrency[cur] = (availableByCurrency[cur] ?? 0) + ev.amount_minor
    } else {
      heldByCurrency[cur] = (heldByCurrency[cur] ?? 0) + ev.amount_minor
    }
  }
  return { totalByCurrency, availableByCurrency, heldByCurrency, paidByCurrency }
}

export function resolveDonationBalances(overview, events, preferredCurrency = 'RUB') {
  const payoutSummary = summarizeDonationPayouts(events)
  const currency = (
    pickCurrencyAmount(overview?.totals_by_currency, preferredCurrency) != null
      ? preferredCurrency
      : Object.keys(overview?.totals_by_currency || {})[0]
        || Object.keys(payoutSummary.totalByCurrency)[0]
        || preferredCurrency
  ).toUpperCase()
  const total =
    pickCurrencyAmount(payoutSummary.totalByCurrency, currency)
    ?? pickCurrencyAmount(overview?.totals_by_currency, currency)
    ?? 0
  const available = pickCurrencyAmount(payoutSummary.availableByCurrency, currency) ?? 0
  const held = pickCurrencyAmount(payoutSummary.heldByCurrency, currency) ?? 0
  const paid = pickCurrencyAmount(payoutSummary.paidByCurrency, currency) ?? 0
  return { currency, total, available, held, paid }
}

export function fmtMoney(minor, currency = 'RUB') {
  const c = String(currency || 'RUB').toUpperCase()
  const rub = (Number(minor) || 0) / 100
  if (c === 'RUB') {
    return `${rub.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`
  }
  if (c === 'USD') {
    return `$${rub.toFixed(2)}`
  }
  if (c === 'EUR') {
    return `€${rub.toFixed(2)}`
  }
  return `${rub.toFixed(2)} ${c}`
}

export const DONATION_CURRENCIES = ['RUB', 'USD', 'EUR']

export const DONATION_MIN_MAJOR = {
  RUB: 100,
  USD: 5,
  EUR: 1,
}

export function donationCurrencySymbol(currency) {
  const c = String(currency || 'RUB').toUpperCase()
  if (c === 'RUB') return '₽'
  if (c === 'USD') return '$'
  if (c === 'EUR') return '€'
  return c
}

export function donationMinHint(currency, lang = 'ru') {
  const c = String(currency || 'RUB').toUpperCase()
  const min = DONATION_MIN_MAJOR[c] ?? 0
  const sym = donationCurrencySymbol(c)
  if (lang === 'ru') {
    return `Минимум ${min} ${sym}`
  }
  return `Minimum ${sym}${min}`
}

/** Человекочитаемый текст ошибки из архива студии (в т.ч. Python-dict строки). */
export function formatArchiveErrorMessage(raw, lang = 'ru') {
  const text = (raw || '').trim()
  if (!text) return lang === 'ru' ? 'Ошибка генерации' : 'Generation failed'
  let parsed = null
  if (text.startsWith('{')) {
    try {
      parsed = JSON.parse(text)
    } catch {
      try {
        parsed = JSON.parse(text.replace(/'/g, '"'))
      } catch {
        parsed = null
      }
    }
  }
  if (parsed && typeof parsed === 'object') {
    const fromDetail = formatApiErrorDetail({ detail: parsed })
    if (fromDetail) return fromDetail
    if (typeof parsed.message === 'string' && parsed.message.trim()) return parsed.message.trim()
  }
  if (/minor_content_prohibited/i.test(text)) {
    const fromCode = formatApiErrorDetail({ detail: { code: 'minor_content_prohibited' } })
    if (fromCode) return fromCode
  }
  return text.slice(0, 140)
}
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
  if (x === 'telegram_user' || x === 'telegram') return 'TELEGRAM'
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
  es: 'Español',
  'es*': 'Español',
  en: 'English',
  'en*': 'English',
  de: 'Deutsch',
  'de*': 'Deutsch',
  ru: 'Русский',
  'ru*': 'Русский',
  fr: 'Français',
  it: 'Italiano',
  pt: 'Português',
  nl: 'Nederlands',
}

export const OUTBOUND_LANG_CODES = ['ru', 'en', 'es', 'de', 'fr', 'it', 'pt', 'nl']

export function normalizeLangCode(raw) {
  return String(raw || '').trim().toLowerCase().replace('*', '')
}

export function replyLangDisplay(conv, lang = 'ru') {
  const forced = normalizeLangCode(conv?.outbound_lang)
  if (forced) return LANG_MAP[forced] || LANG_MAP[`${forced}*`] || forced.toUpperCase()
  const detected = normalizeLangCode(conv?.user_lang)
  if (detected) return LANG_MAP[detected] || LANG_MAP[`${detected}*`] || detected.toUpperCase()
  return lang === 'ru' ? 'Авто' : 'Auto'
}

export function outboundLangOptions(lang, detectedCode) {
  const autoLabel = `${lang === 'ru' ? 'Авто' : 'Auto'} · ${replyLangDisplay({ user_lang: detectedCode }, lang)}`
  return [
    { value: 'auto', label: autoLabel },
    ...OUTBOUND_LANG_CODES.map((code) => ({
      value: code,
      label: LANG_MAP[code] || code.toUpperCase(),
    })),
  ]
}

export function companionModeShort(mode, lang = 'ru') {
  const m = String(mode || 'off').toLowerCase()
  if (m === 'off') return lang === 'ru' ? 'Откл' : 'Off'
  if (m === 'semi_auto') return lang === 'ru' ? 'Полуавто' : 'Semi-auto'
  if (m === 'auto') return lang === 'ru' ? 'Авто' : 'Auto'
  if (m === 'draft') return lang === 'ru' ? 'Черновик' : 'Draft'
  return m.toUpperCase()
}

export function dialogSettingsSummary(conv, lang = 'ru') {
  const mode = conv?.companion_mode_override ?? conv?.effective_companion_mode ?? 'off'
  const translateOn = !conv?.auto_translate_disabled
  return companionModeShort(mode, lang) + (translateOn ? '' : (lang === 'ru' ? ' · без перевода' : ' · no translate'))
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
