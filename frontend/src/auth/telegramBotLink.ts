/** Привязка Telegram через бота — можно выбрать другой аккаунт в приложении. */

import { apiFetch } from '../api'
import { formatHttpApiError } from '../apiErrors'
import {
  navigatePopupToTelegram,
  openTelegramBotUrl,
} from '../utils/openExternalUrl'

const POLL_INTERVAL_MS = 1500
const POLL_TIMEOUT_MS = 3 * 60 * 1000
const PENDING_KEY = 'mm_pending_tg_link'

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

type PendingLink = { sessionId: string; at: number }

function savePending(sessionId: string) {
  const payload: PendingLink = { sessionId, at: Date.now() }
  const raw = JSON.stringify(payload)
  sessionStorage.setItem(PENDING_KEY, raw)
  try {
    localStorage.setItem(PENDING_KEY, raw)
  } catch {
    /* ignore */
  }
}

export function clearPendingTelegramLink() {
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
    const parsed = JSON.parse(raw) as PendingLink
    if (!parsed.sessionId || Date.now() - parsed.at > POLL_TIMEOUT_MS) {
      clearPendingTelegramLink()
      return null
    }
    return parsed.sessionId
  } catch {
    clearPendingTelegramLink()
    return null
  }
}

export function hasPendingTelegramLink(): boolean {
  return loadPending() != null
}

async function startTelegramMobileLink() {
  const r = await apiFetch('/api/auth/telegram/link/mobile/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
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

async function pollTelegramMobileLink(sessionId: string) {
  const q = encodeURIComponent(sessionId.trim())
  const r = await apiFetch(`/api/auth/telegram/link/mobile/poll?session_id=${q}`)
  if (!r.ok) {
    const j = await r.json().catch(() => ({}))
    throw new Error(formatHttpApiError(r, j))
  }
  return (await r.json()) as {
    status: 'pending' | 'done' | 'expired'
    telegram_linked?: boolean | null
    telegram_username?: string | null
  }
}

async function pollUntilTelegramLinkDone(sessionId: string): Promise<void> {
  const deadline = Date.now() + POLL_TIMEOUT_MS
  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS)
    const poll = await pollTelegramMobileLink(sessionId)
    if (poll.status === 'done' && poll.telegram_linked) {
      clearPendingTelegramLink()
      return
    }
    if (poll.status === 'expired') {
      clearPendingTelegramLink()
      throw new Error('Session expired — try again')
    }
  }
  clearPendingTelegramLink()
  throw new Error('Open Telegram, tap Start, then return to this page')
}

export async function resumePendingTelegramBotLink(): Promise<boolean> {
  const sessionId = loadPending()
  if (!sessionId) return false
  try {
    await pollUntilTelegramLinkDone(sessionId)
    return true
  } catch {
    return false
  }
}

export async function linkTelegramViaBot(options?: {
  preopenedPopup?: Window | null
}): Promise<void> {
  const started = await startTelegramMobileLink()
  const url = (started.telegram_url || '').trim()
  if (!url) throw new Error('Telegram bot URL missing')

  savePending(started.session_id)

  const popup = options?.preopenedPopup ?? null
  if (!navigatePopupToTelegram(popup, url)) {
    openTelegramBotUrl(url)
  }

  await pollUntilTelegramLinkDone(started.session_id)
}
