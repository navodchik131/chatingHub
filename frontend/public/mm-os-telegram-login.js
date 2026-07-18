/** Telegram Login Widget для frontend (без React). */
;(function (global) {
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

  global.MMOS_TELEGRAM_LOGIN = {
    mountTelegramLoginWidget,
    postTelegramAuth,
  }
})(window)
