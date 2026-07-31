/** Telegram login для PWA (mm-os-bridge): бот + polling. */
;(function (global) {
  const POLL_INTERVAL_MS = 1500
  const POLL_TIMEOUT_MS = 3 * 60 * 1000
  const PENDING_KEY = 'mm_pending_tg_auth'

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms)
    })
  }

  function isMobileLikeClient() {
    return (
      window.matchMedia('(pointer: coarse)').matches ||
      window.matchMedia('(max-width: 768px)').matches ||
      window.matchMedia('(display-mode: standalone)').matches ||
      (global.navigator && global.navigator.standalone === true)
    )
  }

  function openExternalUrl(url) {
    const href = String(url || '').trim()
    if (!href) return
    if (isMobileLikeClient()) {
      global.location.assign(href)
      return
    }
    const popup = global.open(href, '_blank', 'noopener,noreferrer')
    if (!popup) global.location.assign(href)
  }

  function openExternalUrlDeferred(url, popup) {
    const href = String(url || '').trim()
    if (!href) return
    if (popup && !popup.closed) {
      try {
        popup.location.href = href
        return
      } catch (_) {
        /* fallback */
      }
    }
    openExternalUrl(href)
  }

  function savePending(sessionId) {
    global.sessionStorage.setItem(
      PENDING_KEY,
      JSON.stringify({ sessionId: sessionId, at: Date.now() }),
    )
  }

  function clearPending() {
    global.sessionStorage.removeItem(PENDING_KEY)
  }

  function loadPending() {
    const raw = global.sessionStorage.getItem(PENDING_KEY)
    if (!raw) return null
    try {
      const parsed = JSON.parse(raw)
      if (!parsed.sessionId || Date.now() - parsed.at > POLL_TIMEOUT_MS) {
        clearPending()
        return null
      }
      return parsed.sessionId
    } catch (_) {
      clearPending()
      return null
    }
  }

  function mountTelegramLoginWidget(container, botUsername, onAuth) {
    const username = String(botUsername || '')
      .trim()
      .replace(/^@/, '')
    if (!username || !container) return function () {}

    container.replaceChildren()
    const callbackName = 'onTelegramAuth_' + Math.random().toString(36).slice(2)
    global[callbackName] = onAuth

    const script = document.createElement('script')
    script.async = true
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', username)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-userpic', 'false')
    script.setAttribute('data-request-access', 'write')
    script.setAttribute('data-onauth', callbackName + '(user)')
    container.appendChild(script)

    return function cleanup() {
      container.replaceChildren()
      delete global[callbackName]
    }
  }

  async function postTelegramAuth(path, user, referralCode) {
    const body = Object.assign({}, user)
    const ref = String(referralCode || '')
      .trim()
      .toUpperCase()
    if (ref) body.referral_code = ref
    return global.MMOS_API.apiFetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  }

  async function startTelegramMobileAuth(referralCode) {
    const body = {}
    const ref = String(referralCode || '')
      .trim()
      .toUpperCase()
    if (ref) body.referral_code = ref
    const res = await global.MMOS_API.apiFetch('/api/auth/telegram/mobile/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await global.MMOS_API.readJson(res)
    if (!res.ok) throw new Error(global.MMOS_API.formatDetail(data) || 'Telegram start failed')
    return data
  }

  async function pollTelegramMobileAuth(sessionId) {
    const q = encodeURIComponent(String(sessionId || '').trim())
    const res = await global.MMOS_API.apiFetch('/api/auth/telegram/mobile/poll?session_id=' + q)
    const data = await global.MMOS_API.readJson(res)
    if (!res.ok) throw new Error(global.MMOS_API.formatDetail(data) || 'Telegram poll failed')
    return data
  }

  async function pollUntilDone(sessionId) {
    const deadline = Date.now() + POLL_TIMEOUT_MS
    while (Date.now() < deadline) {
      await sleep(POLL_INTERVAL_MS)
      const poll = await pollTelegramMobileAuth(sessionId)
      if (poll.status === 'done' && poll.access_token) {
        clearPending()
        return poll.access_token
      }
      if (poll.status === 'expired') {
        clearPending()
        throw new Error('Сессия истекла — попробуйте снова')
      }
    }
    throw new Error('Откройте Telegram, нажмите Start и вернитесь на эту страницу')
  }

  async function resumePendingTelegramBotAuth() {
    const sessionId = loadPending()
    if (!sessionId) return null
    try {
      return await pollUntilDone(sessionId)
    } catch (_) {
      return null
    }
  }

  function hasPendingTelegramAuth() {
    return loadPending() != null
  }

  async function signInWithTelegramBot(referralCode, options) {
    const preopenedPopup = options && options.preopenedPopup
    const started = await startTelegramMobileAuth(referralCode)
    const url = String(started.telegram_url || '').trim()
    if (!url) throw new Error('Telegram bot URL missing')

    savePending(started.session_id)

    if (isMobileLikeClient()) {
      openExternalUrl(url)
      return pollUntilDone(started.session_id)
    }

    openExternalUrlDeferred(url, preopenedPopup || null)
    return pollUntilDone(started.session_id)
  }

  global.MMOS_TELEGRAM_LOGIN = {
    mountTelegramLoginWidget,
    postTelegramAuth,
    signInWithTelegramBot,
    resumePendingTelegramBotAuth,
    hasPendingTelegramAuth,
  }
})(window)
