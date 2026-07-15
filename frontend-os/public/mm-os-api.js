/**
 * API-клиент нового кабинета (тот же бэкенд и JWT, что у frontend/).
 * Cookie path=/ — токен общий между :8080 и :5180 на одном хосте.
 */
;(function (global) {
  const TOKEN_KEY = 'chating_token'
  const COOKIE_MAX_AGE = 60 * 60 * 24 * 90

  function readCookieToken() {
    const m = document.cookie.match(/(?:^|;\s*)chating_token=([^;]*)/)
    return m ? decodeURIComponent(m[1]) : null
  }

  function writeCookieToken(token) {
    if (token) {
      document.cookie =
        TOKEN_KEY +
        '=' +
        encodeURIComponent(token) +
        '; path=/; max-age=' +
        COOKIE_MAX_AGE +
        '; SameSite=Lax'
    } else {
      document.cookie = TOKEN_KEY + '=; path=/; max-age=0; SameSite=Lax'
    }
  }

  function getToken() {
    const ls = localStorage.getItem(TOKEN_KEY)
    if (ls) return ls
    const ck = readCookieToken()
    if (ck) {
      localStorage.setItem(TOKEN_KEY, ck)
      return ck
    }
    return null
  }

  function setToken(token) {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
      writeCookieToken(token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
      writeCookieToken(null)
    }
  }

  function formatDetail(data) {
    if (!data) return ''
    const d = data.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d) && d.length) {
      return d.map((x) => (typeof x === 'object' && x?.msg ? x.msg : String(x))).join('; ')
    }
    if (typeof data.message === 'string') return data.message
    return ''
  }

  async function apiFetch(path, init = {}) {
    const headers = new Headers(init.headers || {})
    const token = getToken()
    if (token) headers.set('Authorization', 'Bearer ' + token)
    if (!headers.has('Accept')) headers.set('Accept', 'application/json')
    if (init.body && typeof init.body === 'string' && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    const res = await fetch(path, { ...init, headers, credentials: 'include' })
    return res
  }

  async function readJson(res) {
    try {
      return await res.json()
    } catch {
      return {}
    }
  }

  async function apiJson(path, init) {
    const res = await apiFetch(path, init)
    const data = await readJson(res)
    if (!res.ok) throw new Error(formatDetail(data) || res.status + ' ' + path)
    return data
  }

  async function postStudioJob(path, body) {
    const res = await apiFetch(path, { method: 'POST', body })
    const data = await readJson(res)
    if (res.status === 202) {
      if (!data.job_id) throw new Error(formatDetail(data) || 'Нет job_id')
      return data
    }
    if (!res.ok) throw new Error(formatDetail(data) || res.statusText)
    throw new Error('Ожидался ответ 202')
  }

  async function pollStudioJob(jobId, opts = {}) {
    const max = opts.maxWaitMs || 25 * 60 * 1000
    const started = Date.now()
    while (Date.now() - started < max) {
      const data = await apiJson('/api/studio/jobs/' + jobId)
      if (data.status === 'completed') return data
      if (data.status === 'failed') {
        throw new Error((data.error_message || '').trim() || 'Задача не выполнена')
      }
      await new Promise((r) => setTimeout(r, opts.pollMs || 2500))
    }
    throw new Error('Превышено время ожидания генерации')
  }

  const PERM = {
    CHAT: 1,
    STUDIO_GENERATE: 2,
    STUDIO_MODELS: 4,
    INTEGRATIONS: 8,
    BILLING: 16,
    MANAGE_MEMBERS: 32,
  }

  function hasPerm(mask, bit) {
    return (mask & bit) === bit
  }

  global.MMOS_API = {
    TOKEN_KEY,
    PERM,
    getToken,
    setToken,
    apiFetch,
    apiJson,
    postStudioJob,
    pollStudioJob,
    hasPerm,
    formatDetail,
    readJson,
  }
})(window)
