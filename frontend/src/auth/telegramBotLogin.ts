/** Telegram login через бота (/start mm_…) — тот же flow, что в mobile. */

import { apiFetch } from '../api'
import { formatHttpApiError } from '../apiErrors'
import {
  navigatePopupToTelegram,
  openTelegramBotUrl,
} from '../utils/openExternalUrl'

const POLL_INTERVAL_MS = 1500
const POLL_TIMEOUT_MS = 3 * 60 * 1000
const PENDING_KEY = 'mm_pending_tg_auth'

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

type PendingAuth = { sessionId: string; at: number }

function savePending(sessionId: string) {
  const payload: PendingAuth = { sessionId, at: Date.now() }
  const raw = JSON.stringify(payload)
  sessionStorage.setItem(PENDING_KEY, raw)
  try {
    localStorage.setItem(PENDING_KEY, raw)
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearPendingTelegramAuth() {
  sessionStorage.removeItem(PENDING_KEY)
  try {
    localStorage.removeItem(PENDING_KEY)
  } catch {
    /* ignore */
  }
}

function loadPending(): string | null {
  let raw = sessionStorage.getItem(PENDING_KEY)
  if (!raw) {
    try {
      raw = localStorage.getItem(PENDING_KEY)
    } catch {
      raw = null
    }
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as PendingAuth
    if (!parsed.sessionId || Date.now() - parsed.at > POLL_TIMEOUT_MS) {
      clearPendingTelegramAuth()
      return null
    }
    return parsed.sessionId
  } catch {
    clearPendingTelegramAuth()
    return null
  }
}

export async function startTelegramMobileAuth(referralCode?: string | null) {
  const body: { referral_code?: string } = {}
  const ref = (referralCode || '').trim().toUpperCase()
  if (ref) body.referral_code = ref
  const r = await apiFetch('/api/auth/telegram/mobile/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) {
    const j = await r.json().catch(() => ({}))
    throw new Error(formatHttpApiError(r, j))
  }
  return (await r.json()) as {
    session_id: string
    bot_username: string
    telegram_url: string
  }
}

export async function pollTelegramMobileAuth(sessionId: string) {
  const q = encodeURIComponent(sessionId.trim())
  const r = await apiFetch(`/api/auth/telegram/mobile/poll?session_id=${q}`)
  if (!r.ok) {
    const j = await r.json().catch(() => ({}))
    throw new Error(formatHttpApiError(r, j))
  }
  return (await r.json()) as {
    status: 'pending' | 'done' | 'expired'
    access_token?: string | null
  }
}

export async function pollUntilTelegramAuthDone(sessionId: string): Promise<string> {
  const deadline = Date.now() + POLL_TIMEOUT_MS
  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS)
    const poll = await pollTelegramMobileAuth(sessionId)
    if (poll.status === 'done' && poll.access_token) {
      clearPendingTelegramAuth()
      return poll.access_token
    }
    if (poll.status === 'expired') {
      clearPendingTelegramAuth()
      throw new Error('Session expired — try again')
    }
  }
  clearPendingTelegramAuth()
  throw new Error('Open Telegram, tap Start, then return to this page')
}

/** Продолжить вход после возврата из Telegram (PWA / reload / bfcache). */
export async function resumePendingTelegramBotAuth(): Promise<string | null> {
  const sessionId = loadPending()
  if (!sessionId) return null
  try {
    return await pollUntilTelegramAuthDone(sessionId)
  } catch {
    return null
  }
}

export function hasPendingTelegramAuth(): boolean {
  return loadPending() != null
}

export async function signInWithTelegramBot(
  referralCode?: string | null,
  options?: { preopenedPopup?: Window | null },
): Promise<string> {
  const started = await startTelegramMobileAuth(referralCode)
  const url = (started.telegram_url || '').trim()
  if (!url) throw new Error('Telegram bot URL missing')

  savePending(started.session_id)

  const popup = options?.preopenedPopup ?? null
  if (!navigatePopupToTelegram(popup, url)) {
    openTelegramBotUrl(url)
  }

  return pollUntilTelegramAuthDone(started.session_id)
}
