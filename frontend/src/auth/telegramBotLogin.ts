/** Telegram login через бота (/start mm_…) — тот же flow, что в mobile. */

import { apiFetch } from '../api'
import { formatHttpApiError } from '../apiErrors'

const POLL_INTERVAL_MS = 1500
const POLL_TIMEOUT_MS = 3 * 60 * 1000

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
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

export async function signInWithTelegramBot(referralCode?: string | null): Promise<string> {
  const started = await startTelegramMobileAuth(referralCode)
  const url = (started.telegram_url || '').trim()
  if (!url) throw new Error('Telegram bot URL missing')

  window.open(url, '_blank', 'noopener,noreferrer')

  const deadline = Date.now() + POLL_TIMEOUT_MS
  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS)
    const poll = await pollTelegramMobileAuth(started.session_id)
    if (poll.status === 'done' && poll.access_token) return poll.access_token
    if (poll.status === 'expired') {
      throw new Error('Session expired — try again')
    }
  }
  throw new Error('Open Telegram, tap Start, then return to this page')
}
