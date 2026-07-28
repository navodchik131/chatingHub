/** Telegram login для PWA (mm-os-bridge): бот + polling. */
;(function (global) {
  const POLL_INTERVAL_MS = 1500
  const POLL_TIMEOUT_MS = 3 * 60 * 1000

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms)
    })
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

  async function signInWithTelegramBot(referralCode) {
    const started = await startTelegramMobileAuth(referralCode)
    const url = String(started.telegram_url || '').trim()
    if (!url) throw new Error('Telegram bot URL missing')
    window.open(url, '_blank', 'noopener,noreferrer')

    const deadline = Date.now() + POLL_TIMEOUT_MS
    while (Date.now() < deadline) {
      await sleep(POLL_INTERVAL_MS)
      const poll = await pollTelegramMobileAuth(started.session_id)
      if (poll.status === 'done' && poll.access_token) return poll.access_token
      if (poll.status === 'expired') throw new Error('Сессия истекла — попробуйте снова')
    }
    throw new Error('Откройте Telegram, нажмите Start и вернитесь на эту страницу')
  }

  global.MMOS_TELEGRAM_LOGIN = {
    mountTelegramLoginWidget,
    postTelegramAuth,
    signInWithTelegramBot,
  }
})(window)
