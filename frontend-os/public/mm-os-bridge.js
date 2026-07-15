/**
 * Мост: макет DesignCode ↔ API бэкенда.
 * Не меняет вёрстку — только подменяет данные и вешает обработчики на существующие элементы.
 */
;(function (global) {
  const API = global.MMOS_API
  if (!API) {
    console.error('mm-os-bridge: MMOS_API not loaded')
    return
  }

  const G = [
    'linear-gradient(160deg,#3B2A4F,#1A1428)',
    'linear-gradient(160deg,#4F2A3E,#241019)',
    'linear-gradient(160deg,#2A3E4F,#101A24)',
    'linear-gradient(160deg,#2A4F3B,#0F241A)',
    'linear-gradient(160deg,#4F3E2A,#241C10)',
    'linear-gradient(160deg,#33265C,#150F28)',
  ]
  const AV_G = [
    'linear-gradient(135deg,#38BDF8,#818CF8);color:#0A1526;',
    'linear-gradient(135deg,#FB923C,#F87171);color:#26140A;',
    'linear-gradient(135deg,#4ADE80,#38BDF8);color:#0A2614;',
    'linear-gradient(135deg,#F472B6,#C084FC);color:#260A1C;',
    'linear-gradient(135deg,#FACC15,#FB923C);color:#262008;',
  ]

  const store = {
    logic: null,
    authed: false,
    authReady: false,
    me: null,
    health: null,
    conversations: [],
    messages: [],
    notes: [],
    models: [],
    archiveImages: [],
    archiveVideos: [],
    motionRenders: [],
    integrations: null,
    tributeEarnings: null,
    donationOverview: null,
    donations: [],
    donationEvents: [],
    billingPlans: null,
    creditHistory: [],
    referral: null,
    payoutSettings: null,
    members: [],
    snippets: [],
    chatterStats: null,
    ws: null,
    busy: false,
    error: null,
    selectedModelId: null,
    selectedWaveModelId: null,
    genModels: [],
    selectedAspect: '9:16',
    uploadFiles: {},
    uploadPreviewUrls: {},
    motionVideoFileId: null,
    charProfileDraft: {},
    selectedPhotoKind: 'face',
    avatarCache: {},
  }

  function fmtCredits(n) {
    const v = Math.max(0, Math.round(Number(n) || 0))
    return String(v)
  }

  function shortEmail(email) {
    const e = (email || '').trim()
    if (e.length <= 14) return e
    return e.slice(0, 12) + '…'
  }

  function fmtMoney(minor, currency) {
    const c = (currency || 'RUB').toUpperCase()
    const rub = (Number(minor) || 0) / 100
    if (c === 'RUB') return rub.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₽'
    return rub.toFixed(2) + ' ' + c
  }

  function fmtTime(iso) {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return hh + ':' + mm
  }

  function fmtDateShort(iso) {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    const dd = String(d.getDate()).padStart(2, '0')
    const mo = String(d.getMonth() + 1).padStart(2, '0')
    return dd + '.' + mo
  }

  function platformLabel(p) {
    const x = (p || '').toLowerCase()
    if (x === 'fanvue') return 'FANVUE'
    if (x === 'instagram') return 'INSTAGRAM'
    return 'TELEGRAM'
  }

  function platColor(p) {
    return platformLabel(p) === 'FANVUE' ? '#F0A8C8' : '#38BDF8'
  }

  function displayName(c) {
    return (c.user_display_name || c.external_chat_id || '—').trim()
  }

  function mkDlgFromConv(c, i, logic) {
    const name = displayName(c)
    const initial = (name[0] || '?').toUpperCase()
    const avBase32 = 'width:32px;height:32px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;background:'
    const avBase36 = 'width:36px;height:36px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;position:relative;background:'
    const lang = c.user_lang ? c.user_lang + '*' : ''
    return {
      id: c.id,
      name,
      platform: platformLabel(c.platform),
      last: (c.last_message_preview || '—').slice(0, 80),
      time: fmtTime(c.updated_at),
      initial,
      avStyle: avBase32 + AV_G[i % 5],
      avStyleLg: avBase36 + AV_G[i % 5],
      platColor: platColor(c.platform),
      vip: c.manual_category === 'vip',
      hot: Boolean(c.is_no_response),
      lang,
      unread: c.unread_count || 0,
      open: () => {
        logic.setState({ chatOpen: i, page: 'dialogs' })
        void loadMessages(c.id)
      },
    }
  }

  const REGULAR_ENGINE_IDS = ['nano-banana-2', 'nano-banana-pro', 'gpt-image-2', 'seedream-v5.0-pro']
  const NSFW_ENGINE_IDS = ['wan-2.7', 'wan-2.7-pro', 'seedream-v5.0-pro']
  const FALLBACK_GEN_MODELS = [
    { id: 'nano-banana-2', label: 'Nano Banana', nsfwOnly: false },
    { id: 'nano-banana-pro', label: 'Nano Banana Pro', nsfwOnly: false },
    { id: 'gpt-image-2', label: 'GPT Image 2', nsfwOnly: false },
    { id: 'seedream-v5.0-pro', label: 'Seedream 5 Pro', nsfwOnly: false },
    { id: 'wan-2.7', label: 'Wan 2.7', nsfwOnly: true },
    { id: 'wan-2.7-pro', label: 'Wan 2.7 Pro', nsfwOnly: true },
  ]

  function enginesForNsfw(nsfw) {
    const allowed = nsfw ? NSFW_ENGINE_IDS : REGULAR_ENGINE_IDS
    const byId = new Map((store.genModels.length ? store.genModels : FALLBACK_GEN_MODELS).map((m) => [m.id, m]))
    return allowed.map((id) => byId.get(id)).filter(Boolean)
  }

  function normalizeWaveModel(id, nsfw) {
    const x = (id || '').trim().toLowerCase()
    if (x === 'wan-2.7-pro') return { apiId: 'wan-2.7', tier: 'pro' }
    if (x === 'wan-2.7') return { apiId: 'wan-2.7', tier: 'standard' }
    if (REGULAR_ENGINE_IDS.includes(x) || NSFW_ENGINE_IDS.includes(x)) return { apiId: x, tier: 'standard' }
    return { apiId: nsfw ? 'wan-2.7' : 'nano-banana-pro', tier: 'standard' }
  }

  function mapEngineChips(logic, lang) {
    const nsfw = !!logic.state.nsfw
    const acc = nsfw ? '#F0A8C8' : '#D7F452'
    const models = enginesForNsfw(nsfw)
    let cur = store.selectedWaveModelId
    if (!models.some((m) => m.id === cur)) {
      cur = models[0]?.id || (nsfw ? 'wan-2.7' : 'nano-banana-pro')
      store.selectedWaveModelId = cur
    }
    const modelHint = nsfw
      ? lang === 'ru'
        ? 'NSFW-движки: без цензуры, приватная очередь. Доступно на Pro / Studio.'
        : 'NSFW engines: uncensored, private queue. Pro / Studio only.'
      : lang === 'ru'
        ? 'SFW-движки: быстрые, безопасный контент для всех каналов.'
        : 'SFW engines: fast, safe content for all channels.'
    const modelChips = models.map((m) => ({
      id: m.id,
      label: m.label,
      pick: () => {
        store.selectedWaveModelId = m.id
        logic.forceUpdate()
      },
      style:
        'font-size:12px;padding:7px 14px;border-radius:9px;cursor:pointer;' +
        (m.id === cur
          ? 'font-weight:800;background:' +
            (nsfw ? 'rgba(240,168,200,.14)' : 'rgba(215,244,82,.12)') +
            ';color:' +
            acc +
            ';border:1px solid ' +
            (nsfw ? 'rgba(240,168,200,.5)' : 'rgba(215,244,82,.5)') +
            ';'
          : 'font-weight:700;border:1px solid rgba(255,255,255,.12);color:#9BA0A6;'),
    }))
    return { modelChips, modelHint }
  }

  function archiveThumbUrl(item) {
    return (item.image_url || '').trim()
  }

  function archiveToFrame(item, i, logic, I) {
    const url = archiveThumbUrl(item)
    const who = item.model_name || '—'
    const ratio = item.output_aspect || '9:16'
    const tileBase =
      'aspect-ratio:9/16;border-radius:10px;display:flex;align-items:flex-end;padding:8px;position:relative;overflow:hidden;cursor:pointer;background:'
    const thumbBase =
      'aspect-ratio:9/16;border-radius:8px;cursor:pointer;border:2px solid transparent;background:'
    const bgStyle = url
      ? tileBase + 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
      : tileBase + G[i % 6]
    const thumbStyle = url
      ? thumbBase + 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
      : thumbBase + G[i % 6]
    return {
      id: item.id,
      bg: bgStyle,
      tileStyle: bgStyle,
      thumbStyle,
      label: who + ' · ' + ratio,
      who,
      ratio,
      url,
      open: () => {
        logic.setState({
          lightbox: {
            bgStyle: 'width:100%;aspect-ratio:9/16;border-radius:16px;background:center/cover no-repeat url("' +
              url.replace(/"/g, '') + '"),' + G[i % 6],
            who,
            ratio,
            model: '',
            url,
            id: item.id,
          },
        })
      },
    }
  }

  function modelCoverStyle(m, i, coverBase) {
    const url = (m.images && m.images[0] && m.images[0].url) || ''
    const grad = G[i % 6].replace('160deg', '135deg')
    if (url) {
      return (
        coverBase +
        'center/cover no-repeat url("' +
        url.replace(/"/g, '') +
        '"),' +
        grad
      )
    }
    return coverBase + grad
  }

  function imageKindLabel(kind, lang) {
    const k = (kind || 'other').toLowerCase()
    const ru = {
      face: 'ЛИЦО',
      turnaround: 'РАЗВЁРТКА',
      body: 'ТЕЛО',
      genitals: 'ИНТИМ',
      other: 'ДРУГОЕ',
    }
    const en = {
      face: 'FACE',
      turnaround: 'TURNAROUND',
      body: 'BODY',
      genitals: 'INTIMATE',
      other: 'OTHER',
    }
    const map = lang === 'ru' ? ru : en
    return map[k] || k.toUpperCase()
  }

  function modelToCharacter(m, i, lang, logic, stActive, stDim, coverBase) {
    const name = m.name || 'Model'
    const initial = (name[0] || 'M').toUpperCase()
    const profile = (m.profile_text || '').trim()
    const hasPhotos = (m.images || []).length > 0
    const active = profile.length > 0 || hasPhotos
    const status = active
      ? lang === 'ru' ? 'АКТИВНА' : 'ACTIVE'
      : lang === 'ru' ? 'ЧЕРНОВИК' : 'DRAFT'
    const statusStyle = active ? stActive : stDim
    const tags = []
    if (hasPhotos) tags.push('PHOTOS ✓')
    if (profile) tags.push('PROFILE ✓')
    if (!tags.length) tags.push('ID ' + m.id)
    return {
      id: m.id,
      name,
      initial,
      cover: modelCoverStyle(m, i, coverBase),
      status,
      statusStyle,
      blurb: profile.slice(0, 120) || (lang === 'ru' ? 'Заполните внешность и фото' : 'Fill appearance and photos'),
      tags,
      open: () => logic.setState({ charDetail: String(m.id), charTab: 'photos', page: 'characters' }),
    }
  }

  async function loadMessages(convId) {
    const data = await API.apiJson('/api/conversations/' + convId + '/messages?limit=50')
    store.messages = Array.isArray(data) ? data : []
    await API.apiFetch('/api/conversations/' + convId + '/read', { method: 'POST' })
    const nr = await API.apiJson('/api/conversations/' + convId + '/notes').catch(() => [])
    store.notes = Array.isArray(nr) ? nr : []
    store.logic?.forceUpdate()
    void loadConversations()
  }

  async function loadConversations() {
    const r = await API.apiFetch('/api/conversations')
    if (r.status === 403) {
      store.conversations = []
      return
    }
    if (!r.ok) return
    store.conversations = await API.readJson(r)
  }

  async function loadArchive() {
    const img = await API.apiJson('/api/studio/generations?limit=40&skip=0&media_kind=image').catch(() => ({ items: [] }))
    const vid = await API.apiJson('/api/studio/generations?limit=40&skip=0&media_kind=video').catch(() => ({ items: [] }))
    store.archiveImages = img.items || []
    store.archiveVideos = vid.items || []
    const motion = await API.apiJson('/api/studio/motion/renders?limit=40&skip=0').catch(() => [])
    store.motionRenders = Array.isArray(motion) ? motion : motion.items || []
  }

  async function loadGenModels() {
    const data = await API.apiJson('/api/studio/workflow/model-options').catch(() => null)
    const list = data?.models
    if (Array.isArray(list) && list.length) {
      store.genModels = list.map((m) => ({
        id: m.id,
        label: m.label,
        nsfwOnly: !!m.nsfw_only,
      }))
    } else {
      store.genModels = FALLBACK_GEN_MODELS
    }
  }

  async function loadModels() {
    const data = await API.apiJson('/api/studio/models').catch(() => [])
    store.models = Array.isArray(data) ? data : []
    if (!store.selectedModelId && store.models[0]) {
      store.selectedModelId = store.models[0].id
    }
  }

  async function loadOwnerPanels() {
    if (!store.me?.is_workspace_owner) return
    store.donationOverview = await API.apiJson('/api/creator-donations/overview').catch(() => null)
    store.donations = await API.apiJson('/api/creator-donations').catch(() => [])
    store.donationEvents = await API.apiJson('/api/creator-donations/events?limit=50').catch(() => [])
    store.billingPlans = await API.apiJson('/api/billing/plans').catch(() => null)
    store.creditHistory = await API.apiJson('/api/workspace/credit-history?limit=40&skip=0').catch(() => [])
    store.referral = await API.apiJson('/api/referral/me').catch(() => null)
    store.payoutSettings = await API.apiJson('/api/creator-donations/payout-settings').catch(() => null)
    store.members = await API.apiJson('/api/workspace/members').catch(() => [])
    store.snippets = await API.apiJson('/api/workspace/snippets').catch(() => [])
    store.chatterStats = await API.apiJson('/api/workspace/chatter-stats/summary').catch(() => null)
  }

  async function loadIntegrations() {
    store.integrations = await API.apiJson('/api/integrations').catch(() => null)
  }

  async function loadTribute() {
    store.tributeEarnings = await API.apiJson('/api/tribute/earnings/summary').catch(() => null)
  }

  async function refreshAll() {
    if (!store.authed) return
    await Promise.all([
      API.apiJson('/api/auth/me').then((m) => { store.me = m }),
      API.apiJson('/api/health').then((h) => { store.health = h }),
      loadConversations(),
      loadModels(),
      loadGenModels(),
      loadArchive(),
      loadIntegrations(),
      loadTribute(),
      loadOwnerPanels(),
    ])
    store.logic?.forceUpdate()
  }

  function sumOutboundMessages(cs) {
    if (!cs) return 0
    const self = cs.self || cs.self_row
    let n = self?.outbound_messages || 0
    for (const m of cs.members || []) n += m.outbound_messages || 0
    return n
  }

  let wsBackoffMs = 2000

  function connectWs() {
    if (store.ws) {
      try { store.ws.close() } catch (_) {}
      store.ws = null
    }
    const token = API.getToken()
    if (!token || !store.authed) return
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    let ws
    try {
      ws = new WebSocket(proto + '://' + location.host + '/api/ws?token=' + encodeURIComponent(token))
    } catch (_) {
      return
    }
    store.ws = ws
    ws.onopen = () => {
      wsBackoffMs = 2000
    }
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'studio_generation' || msg.type === 'studio_job') {
          void loadArchive()
          void API.apiJson('/api/auth/me').then((m) => { store.me = m; store.logic?.forceUpdate() })
        }
        if (msg.type === 'new_message' || msg.type === 'message_updated') {
          void loadConversations()
          const open = store.logic?.state?.chatOpen
          const conv = store.conversations[open]
          if (conv) void loadMessages(conv.id)
        }
      } catch (_) {}
    }
    ws.onclose = () => {
      store.ws = null
      if (!store.authed) return
      setTimeout(connectWs, wsBackoffMs)
      wsBackoffMs = Math.min(Math.round(wsBackoffMs * 1.6), 30000)
    }
  }

  function showAuth(show) {
    const el = document.getElementById('mm-os-auth')
    if (el) el.style.display = show ? 'flex' : 'none'
    const root = document.querySelector('[data-screen-label="ModelMate OS"]')?.parentElement
    if (root) root.style.visibility = show ? 'hidden' : 'visible'
  }

  async function bootAuth() {
    const token = API.getToken()
    if (!token) {
      store.authed = false
      store.authReady = true
      showAuth(true)
      return
    }
    try {
      store.me = await API.apiJson('/api/auth/me')
      store.authed = true
      showAuth(false)
      await refreshAll()
      connectWs()
      const first = store.conversations[0]
      if (first) void loadMessages(first.id)
    } catch {
      API.setToken(null)
      store.authed = false
      showAuth(true)
    } finally {
      store.authReady = true
      store.logic?.forceUpdate()
    }
  }

  async function login(email, password, memberLogin) {
    store.busy = true
    store.error = null
    updateAuthUi()
    try {
      const body = memberLogin
        ? { email, password, member_login: memberLogin }
        : { email, password }
      const data = await API.apiJson('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      API.setToken(data.access_token)
      store.authed = true
      showAuth(false)
      await refreshAll()
      connectWs()
      const first = store.conversations[0]
      if (first) void loadMessages(first.id)
      store.logic?.forceUpdate()
    } catch (e) {
      store.error = e.message || String(e)
      updateAuthUi()
    } finally {
      store.busy = false
      updateAuthUi()
    }
  }

  function updateAuthUi() {
    const err = document.getElementById('mm-os-auth-err')
    const btn = document.getElementById('mm-os-auth-submit')
    if (err) err.textContent = store.error || ''
    if (btn) btn.disabled = store.busy
  }

  function bindAuthForm() {
    const form = document.getElementById('mm-os-auth-form')
    if (!form || form.dataset.bound) return
    form.dataset.bound = '1'
    form.addEventListener('submit', (e) => {
      e.preventDefault()
      const email = document.getElementById('mm-os-auth-email')?.value || ''
      const password = document.getElementById('mm-os-auth-pass')?.value || ''
      const member = document.getElementById('mm-os-auth-member')?.value || ''
      void login(email, password, member.trim() || null)
    })
  }

  function queryPromptTextarea() {
    const imgs = document.querySelector('[data-screen-label="Студия — Картинки"]')
    return imgs?.querySelector('textarea') || null
  }

  function queryMotionTextarea() {
    const vid = document.querySelector('[data-screen-label="Студия — Видео"]')
    return vid?.querySelector('textarea') || null
  }

  function queryReplyInput() {
    const dlg = document.querySelector('[data-screen-label="Диалоги"]')
    return dlg?.querySelector('input[type="text"], textarea') || null
  }

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;')
  }

  function revokeUploadPreview(key) {
    const url = store.uploadPreviewUrls[key]
    if (url) {
      URL.revokeObjectURL(url)
      delete store.uploadPreviewUrls[key]
    }
  }

  function renderUploadPreview(zone, key, file) {
    if (!zone || !file) return
    revokeUploadPreview(key)
    const url = URL.createObjectURL(file)
    store.uploadPreviewUrls[key] = url
    zone.classList.add('mm-os-upload--filled')
    zone.querySelectorAll(':scope > span, :scope > div:not(.mm-os-upload-preview)').forEach((el) => {
      el.classList.add('mm-os-upload-ghost')
    })
    let box = zone.querySelector('.mm-os-upload-preview')
    if (!box) {
      box = document.createElement('div')
      box.className = 'mm-os-upload-preview'
      zone.appendChild(box)
    }
    const isVideo = (file.type || '').startsWith('video/')
    const media = isVideo
      ? '<video src="' + url + '" muted playsinline preload="metadata"></video>'
      : '<img src="' + url + '" alt="">'
    box.innerHTML =
      media +
      '<span class="mm-os-upload-name" title="' +
      escHtml(file.name) +
      '">' +
      escHtml(file.name) +
      '</span>'
    let badge = zone.querySelector('.mm-os-upload-badge')
    if (!badge) {
      badge = document.createElement('span')
      badge.className = 'mm-os-upload-badge'
      zone.appendChild(badge)
    }
    badge.textContent = isVideo ? 'VIDEO' : 'PHOTO'
    let clear = zone.querySelector('.mm-os-upload-clear')
    if (!clear) {
      clear = document.createElement('button')
      clear.type = 'button'
      clear.className = 'mm-os-upload-clear'
      clear.setAttribute('aria-label', 'Убрать файл')
      clear.textContent = '×'
      clear.addEventListener('click', (e) => {
        e.stopPropagation()
        clearUploadZone(zone, key)
      })
      zone.appendChild(clear)
    }
    const vid = box.querySelector('video')
    if (vid) vid.currentTime = 0.15
  }

  function clearUploadZone(zone, key) {
    if (!zone) return
    revokeUploadPreview(key)
    delete store.uploadFiles[key]
    if (key === 'motion-video') store.motionVideoFileId = null
    zone.classList.remove('mm-os-upload--filled', 'mm-os-upload--busy')
    zone.querySelector('.mm-os-upload-preview')?.remove()
    zone.querySelector('.mm-os-upload-badge')?.remove()
    zone.querySelector('.mm-os-upload-clear')?.remove()
    zone.querySelectorAll('.mm-os-upload-ghost').forEach((el) => el.classList.remove('mm-os-upload-ghost'))
  }

  function pickLocalFile(accept) {
    return new Promise((resolve) => {
      const inp = document.createElement('input')
      inp.type = 'file'
      inp.accept = accept
      inp.onchange = () => resolve(inp.files?.[0] || null)
      inp.click()
    })
  }

  async function uploadMotionDrivingVideo(file) {
    const fd = new FormData()
    fd.append('video', file)
    const res = await API.apiFetch('/api/studio/motion/upload-driving-video', { method: 'POST', body: fd })
    const data = await API.readJson(res)
    if (!res.ok) throw new Error(API.formatDetail(data) || 'Не удалось загрузить видео')
    const id = String(data.motion_video_file_id || '').trim()
    if (!id) throw new Error('Сервер не вернул id видео')
    store.motionVideoFileId = id
    return id
  }

  function bindUploadZone(zone) {
    const key = zone.dataset.mmUpload
    if (!key) return
    const accept = zone.dataset.mmAccept || (key === 'motion-video' ? 'video/mp4,video/*' : 'image/*')
    if (zone.dataset.mmBound === key) {
      const file = store.uploadFiles[key]
      if (file && !zone.querySelector('.mm-os-upload-preview')) renderUploadPreview(zone, key, file)
      return
    }
    zone.dataset.mmBound = key
    zone.classList.add('mm-os-upload-zone')
    zone.addEventListener('click', (e) => {
      if (e.target.closest('.mm-os-upload-clear')) return
      void (async () => {
        const file = await pickLocalFile(accept)
        if (!file) return
        store.uploadFiles[key] = file
        renderUploadPreview(zone, key, file)
        if (key === 'motion-video') {
          zone.classList.add('mm-os-upload--busy')
          try {
            await uploadMotionDrivingVideo(file)
          } catch (err) {
            store.error = err.message || String(err)
            clearUploadZone(zone, key)
            store.logic?.forceUpdate()
          } finally {
            zone.classList.remove('mm-os-upload--busy')
          }
          return
        }
        if (key === 'char-photo') {
          zone.classList.add('mm-os-upload--busy')
          try {
            await uploadCharPhoto(file)
            clearUploadZone(zone, key)
          } catch (err) {
            store.error = err.message || String(err)
            clearUploadZone(zone, key)
            store.logic?.forceUpdate()
          } finally {
            zone.classList.remove('mm-os-upload--busy')
          }
        }
      })()
    })
    const file = store.uploadFiles[key]
    if (file) renderUploadPreview(zone, key, file)
  }

  function getActiveCharId() {
    const raw = store.logic?.state?.charDetail
    if (!raw) return null
    const id = Number(raw)
    return Number.isFinite(id) ? id : null
  }

  function getActiveChar() {
    const id = getActiveCharId()
    if (!id) return null
    return store.models.find((m) => m.id === id) || null
  }

  function mapCharPhotos(model, lang) {
    const cpBase =
      'aspect-ratio:3/4;border-radius:10px;overflow:hidden;display:flex;align-items:flex-end;padding:6px;background:'
    const imgs = model?.images || []
    return imgs.map((im, i) => {
      const url = im.url || ''
      const bg = url
        ? cpBase + 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
        : cpBase + G[i % 6]
      return {
        id: im.id,
        bg,
        kind: imageKindLabel(im.kind, lang),
      }
    })
  }

  function mapPhotoTagList(lang, logic) {
    const chipOff =
      'font-size:11px;font-weight:700;border:1px solid rgba(255,255,255,.12);color:#9BA0A6;padding:5px 12px;border-radius:8px;cursor:pointer;'
    const chipOn =
      chipOff + 'border-color:rgba(215,244,82,.5);color:#D7F452;background:rgba(215,244,82,.08);'
    const defs = [
      { kind: 'face', label: lang === 'ru' ? 'Лицо / внешность' : 'Face / look' },
      { kind: 'turnaround', label: lang === 'ru' ? 'Развёртка' : 'Turnaround' },
      { kind: 'body', label: lang === 'ru' ? 'Тело целиком' : 'Full body' },
      { kind: 'other', label: 'Selfie' },
      { kind: 'other', label: lang === 'ru' ? 'Локация' : 'Location' },
    ]
    return defs.map((d) => ({
      kind: d.kind,
      label: d.label,
      style: store.selectedPhotoKind === d.kind ? chipOn : chipOff,
      pick: () => {
        store.selectedPhotoKind = d.kind
        logic.forceUpdate()
      },
    }))
  }

  function mapCharHistory(charId, lang) {
    const chHistBase =
      'aspect-ratio:9/16;display:flex;align-items:flex-end;padding:8px;position:relative;overflow:hidden;background:'
    return store.archiveImages
      .filter((item) => item.studio_model_id === charId)
      .slice(0, 12)
      .map((item, i) => {
        const url = item.image_url || ''
        const bg = url
          ? chHistBase + 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
          : chHistBase + G[i % 6]
        return {
          bg,
          title: item.model_name || '—',
          ratio: item.output_aspect || '9:16',
          prompt: (item.prompt || item.description || '—').slice(0, 72),
        }
      })
  }

  async function uploadCharPhoto(file) {
    const charId = getActiveCharId()
    if (!charId) throw new Error('Персонаж не выбран')
    const fd = new FormData()
    fd.append('images', file)
    fd.append('image_kinds', JSON.stringify([store.selectedPhotoKind || 'face']))
    const res = await API.apiFetch('/api/studio/models/' + charId + '/images', { method: 'POST', body: fd })
    const data = await API.readJson(res)
    if (!res.ok) throw new Error(API.formatDetail(data) || 'Не удалось загрузить фото')
    await loadModels()
    store.logic?.forceUpdate()
  }

  async function saveCharProfile() {
    const charId = getActiveCharId()
    if (!charId) return
    const ta = document.querySelector('[data-mm-char-profile]')
    const profileText = (ta?.value || store.charProfileDraft[charId] || '').trim()
    store.busy = true
    store.error = null
    try {
      await API.apiJson('/api/studio/models/' + charId, {
        method: 'PATCH',
        body: JSON.stringify({ profile_text: profileText }),
      })
      delete store.charProfileDraft[charId]
      await loadModels()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  async function deleteChar() {
    const charId = getActiveCharId()
    if (!charId) return
    const m = getActiveChar()
    if (!confirm('Удалить персонажа «' + (m?.name || charId) + '»?')) return
    store.busy = true
    try {
      await API.apiJson('/api/studio/models/' + charId, { method: 'DELETE' })
      store.logic?.setState({ charDetail: null, charTab: 'photos' })
      await loadModels()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  async function generateCharProfile() {
    const m = getActiveChar()
    const imgs = m?.images || []
    if (!imgs.length) {
      store.error = 'Сначала загрузите хотя бы одно фото'
      store.logic?.forceUpdate()
      return
    }
    store.busy = true
    store.error = null
    try {
      const fd = new FormData()
      for (const im of imgs.slice(0, 8)) {
        const res = await API.apiFetch(im.url)
        if (!res.ok) throw new Error('Не удалось прочитать фото модели')
        const blob = await res.blob()
        fd.append('images', blob, 'model-' + im.id + '.jpg')
      }
      const genRes = await API.apiFetch('/api/studio/models/generate-profile', { method: 'POST', body: fd })
      const data = await API.readJson(genRes)
      if (!genRes.ok) throw new Error(API.formatDetail(data) || 'Генерация не удалась')
      const text = String(data.profile_text || '').trim()
      const charId = getActiveCharId()
      if (charId) store.charProfileDraft[charId] = text
      const ta = document.querySelector('[data-mm-char-profile]')
      if (ta) ta.value = text
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  async function createNewCharacter() {
    const lang = store.logic?.state?.lang || 'ru'
    const name = prompt(lang === 'ru' ? 'Имя нового персонажа' : 'New character name')
    if (!name || !name.trim()) return
    store.busy = true
    store.error = null
    try {
      const fd = new FormData()
      fd.append('name', name.trim())
      fd.append('profile_text', '')
      const res = await API.apiFetch('/api/studio/models', { method: 'POST', body: fd })
      const data = await API.readJson(res)
      if (!res.ok) throw new Error(API.formatDetail(data) || 'Не удалось создать персонажа')
      await loadModels()
      store.logic?.setState({ charDetail: String(data.id), charTab: 'photos', page: 'characters' })
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  function companionPersonaToApi(p) {
    const trim = (v) => (v == null ? '' : String(v)).trim()
    const out = {
      age: trim(p.age) || null,
      city: trim(p.city) || null,
      country: trim(p.country) || null,
      timezone: trim(p.timezone) || null,
      personality: trim(p.personality) || null,
      hobbies: trim(p.hobbies) || null,
      interests: trim(p.interests) || null,
      lifestyle: trim(p.lifestyle) || null,
      speaking_style: trim(p.speaking_style) || null,
      backstory: trim(p.backstory) || null,
    }
    const hasAny = Object.values(out).some((v) => v)
    return hasAny ? out : {}
  }

  function readCharPersonaForm() {
    const root = document.querySelector('[data-screen-label="Персонажи"]')
    if (!root) return {}
    const val = (sel) => root.querySelector(sel)?.value ?? ''
    return {
      age: val('[data-mm-persona="age"]'),
      city: val('[data-mm-persona="city"]'),
      country: val('[data-mm-persona="country"]'),
      timezone: val('[data-mm-persona="timezone"]'),
      personality: val('[data-mm-persona="personality"]'),
      hobbies: val('[data-mm-persona="hobbies"]'),
      interests: val('[data-mm-persona="interests"]'),
      speaking_style: val('[data-mm-persona="speaking_style"]'),
      backstory: val('[data-mm-persona="backstory"]'),
    }
  }

  function syncCharPersonaForm(m) {
    const root = document.querySelector('[data-screen-label="Персонажи"]')
    if (!root || !m) return
    const p = m.companion_persona || {}
    const set = (sel, v) => {
      const el = root.querySelector(sel)
      if (el) el.value = v == null ? '' : String(v)
    }
    set('[data-mm-persona="age"]', p.age)
    set('[data-mm-persona="city"]', p.city)
    set('[data-mm-persona="country"]', p.country)
    set('[data-mm-persona="timezone"]', p.timezone)
    set('[data-mm-persona="personality"]', p.personality)
    set('[data-mm-persona="hobbies"]', p.hobbies)
    set('[data-mm-persona="interests"]', p.interests)
    set('[data-mm-persona="speaking_style"]', p.speaking_style)
    set('[data-mm-persona="backstory"]', p.backstory)
  }

  async function saveCharPersona() {
    const charId = getActiveCharId()
    if (!charId) return
    store.busy = true
    store.error = null
    try {
      await API.apiJson('/api/studio/models/' + charId, {
        method: 'PATCH',
        body: JSON.stringify({ companion_persona: companionPersonaToApi(readCharPersonaForm()) }),
      })
      await loadModels()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  let lastSyncedCharId = null

  function syncCharProfileTextarea() {
    const charId = getActiveCharId()
    const ta = document.querySelector('[data-mm-char-profile]')
    if (!ta) return
    if (!charId) {
      ta.value = ''
      lastSyncedCharId = null
      return
    }
    if (lastSyncedCharId === charId && document.activeElement === ta) return
    const m = getActiveChar()
    ta.value = store.charProfileDraft[charId] ?? m?.profile_text ?? ''
    lastSyncedCharId = charId
    syncCharPersonaForm(m)
  }

  function bindCharPanel() {
    const root = document.querySelector('[data-screen-label="Персонажи"]')
    if (!root) return
    syncCharProfileTextarea()

    const ta = root.querySelector('[data-mm-char-profile]')
    if (ta && !ta.dataset.mmBound) {
      ta.dataset.mmBound = '1'
      ta.addEventListener('input', () => {
        const id = getActiveCharId()
        if (id) store.charProfileDraft[id] = ta.value
      })
    }

    const bindBtn = (sel, fn) => {
      const el = root.querySelector(sel)
      if (!el || el.dataset.mmBound) return
      el.dataset.mmBound = '1'
      el.addEventListener('click', () => void fn())
    }

    bindBtn('[data-mm-char-save]', saveCharProfile)
    bindBtn('[data-mm-char-delete]', deleteChar)
    bindBtn('[data-mm-char-gen-profile]', generateCharProfile)
    bindBtn('[data-mm-char-persona-save]', saveCharPersona)

    const newBtn = document.querySelector('[data-mm-char-new]')
    if (newBtn && !newBtn.dataset.mmBound) {
      newBtn.dataset.mmBound = '1'
      newBtn.addEventListener('click', () => void createNewCharacter())
    }
  }

  function bindDomActions() {
    bindAuthForm()
    document.querySelectorAll('[data-mm-upload]').forEach(bindUploadZone)
    bindCharPanel()
  }

  async function sendReply() {
    const open = store.logic?.state?.chatOpen ?? 0
    const conv = store.conversations[open]
    if (!conv) return
    const input = queryReplyInput()
    const text = (input?.value || '').trim()
    if (!text) return
    store.busy = true
    try {
      await API.apiJson('/api/conversations/' + conv.id + '/reply', {
        method: 'POST',
        body: JSON.stringify({ text }),
      })
      if (input) input.value = ''
      await loadMessages(conv.id)
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  function imgModeToStudio(mode) {
    const map = {
      ref: 'model_scene',
      swap: 'face_swap',
      outfit: 'photo_edit',
      location: 'photo_edit',
      prompt: 'model',
      carousel: 'carousel',
    }
    return map[mode] || 'model'
  }

  async function runGenerate() {
    if (store.busy) return
    const s = store.logic?.state || {}
    const mode = s.imgMode || 'prompt'
    const prompt = (queryPromptTextarea()?.value || '').trim()
    const modelId = store.selectedModelId
    if (!modelId) {
      store.error = 'Выберите персонажа'
      store.logic?.forceUpdate()
      return
    }
    store.busy = true
    store.error = null
    try {
      if (mode === 'carousel') {
        const srcId = store.logic?.state?.lightbox?.id
        if (!srcId) throw new Error('Выберите кадр из архива для карусели')
        await API.apiJson('/api/studio/generations/' + srcId + '/carousel', {
          method: 'POST',
          body: JSON.stringify({ count: s.carCount || 6 }),
        })
      } else {
        const fd = new FormData()
        fd.append('description', prompt)
        fd.append('model_id', String(modelId))
        fd.append('output_aspect', store.selectedAspect)
        fd.append('studio_mode', imgModeToStudio(mode))
        fd.append('studio_wave_profile', s.nsfw ? 'nsfw' : 'regular')
        const wave = normalizeWaveModel(store.selectedWaveModelId, !!s.nsfw)
        fd.append('workflow_wave_model', wave.apiId)
        if (wave.apiId === 'wan-2.7') fd.append('wan_edit_tier', wave.tier)
        fd.append('generate_wavespeed', '1')
        fd.append('wavespeed_single_reference', '1')
        const file = store.uploadFiles.ref
        if (file && mode !== 'prompt') fd.append('image', file)
        const accepted = await API.postStudioJob('/api/studio/refine-prompt', fd)
        if (accepted.job_id) {
          await API.pollStudioJob(accepted.job_id, { maxWaitMs: 8 * 60 * 1000 }).catch(() => {})
        }
      }
      await loadArchive()
      await API.apiJson('/api/auth/me').then((m) => { store.me = m })
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  async function runGenerateVideo() {
    if (store.busy) return
    const motion = (queryMotionTextarea()?.value || '').trim()
    if (!motion) {
      store.error = 'Опишите движение'
      store.logic?.forceUpdate()
      return
    }
    const modelId = store.selectedModelId
    if (!modelId) {
      store.error = 'Выберите персонажа'
      store.logic?.forceUpdate()
      return
    }
    store.busy = true
    try {
      const fd = new FormData()
      fd.append('model_id', String(modelId))
      fd.append('prompt', motion)
      fd.append('output_aspect', store.selectedAspect)
      if (store.videoResolution) fd.append('video_resolution', store.videoResolution)
      if (store.videoDuration) fd.append('duration_seconds', String(store.videoDuration))
      if (store.motionVideoFileId) fd.append('motion_video_file_id', store.motionVideoFileId)
      const frameFile = store.uploadFiles['motion-frame']
      if (frameFile) fd.append('image', frameFile)
      const archId = s.lightbox?.id
      if (archId && !frameFile) fd.append('existing_generation_id', String(archId))
      const accepted = await API.postStudioJob('/api/studio/motion/render-video', fd)
      if (accepted.job_id) await API.pollStudioJob(accepted.job_id, { maxWaitMs: 15 * 60 * 1000 }).catch(() => {})
      await loadArchive()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  function modelNameById(id) {
    if (id == null) return '—'
    const m = store.models.find((x) => x.id === id)
    return m?.name || '—'
  }

  function emptyVals(vals) {
    return {
      ...vals,
      creditsBalance: '—',
      userEmailShort: '',
      userRolePlan: '',
      donationsKpiTotal: '—',
      donationsKpiPayout: '—',
      planDisplayName: '—',
      planUntil: '—',
      dialogsTotal: '0',
      dialogsUnreadLabel: vals.t.allRead,
      teamRepliesCount: '0',
      creditsFramesHint: '0 ' + vals.t.framesLeft,
      recentDialogs: [],
      recentFrames: [],
      chats: [],
      messages: [],
      notes: [],
      archiveFrames: [],
      videoArchive: [],
      charChips: [],
      modelChips: vals.modelChips || [],
      modelHint: vals.modelHint || '',
      characters: [],
      donStats: [],
      donLinks: [],
      incoming: [],
      myDonations: [],
      history: [],
      members: [],
      templates: [],
      teamKpi: [],
      activeChat: { name: '—', initial: '?', vip: false, persona: '—', lang: '—', avStyle: AV_G[0] },
      notesTitle: vals.t.fanNotes,
      activeCharName: '—',
      activeCharInitial: '—',
      charPhotos: [],
      photoTagList: [],
      charHistory: [],
      runGenerate: () => {},
      runGenerateVideo: () => {},
      sendReply: () => {},
      logout: () => {},
      apiError: store.error,
      apiBusy: store.busy,
    }
  }

  function mapDonationLinks(lang) {
    const stActive =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;padding:2px 8px;border-radius:20px;background:rgba(74,222,128,.12);color:#4ADE80;border:1px solid rgba(74,222,128,.3);"
    const stWarn =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;padding:2px 8px;border-radius:20px;background:rgba(251,146,60,.12);color:#FB923C;border:1px solid rgba(251,146,60,.3);"
    const stDim =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;padding:2px 8px;border-radius:20px;background:rgba(255,255,255,.06);color:#9BA0A6;border:1px solid rgba(255,255,255,.1);"
    const statusStyle = (st) => {
      const u = (st || '').toUpperCase()
      if (u === 'ACTIVE' || u === 'АКТИВНА') return stActive
      if (u === 'PENDING' || u === 'МОДЕРАЦИЯ') return stWarn
      return stDim
    }
    return (store.donations || []).map((d) => ({
      title: d.title || '—',
      url: d.public_url || d.slug || '—',
      st: (d.status || '—').toUpperCase(),
      stStyle: statusStyle(d.status),
    }))
  }

  function mapIncomingEvents(lang) {
    const linkTitle = (id) => (store.donations || []).find((d) => d.id === id)?.title || ''
    return (store.donationEvents || []).slice(0, 10).map((e) => ({
      sum: '+' + fmtMoney(e.amount_minor, e.currency),
      from:
        (lang === 'ru' ? 'Входящий' : 'Incoming') +
        (linkTitle(e.creator_donation_link_id) ? ' · «' + linkTitle(e.creator_donation_link_id) + '»' : ''),
      when: fmtDateShort(e.occurred_at) + ' · ' + fmtTime(e.occurred_at),
    }))
  }

  function mapTeam(lang, vals) {
    const rOn =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:.5px;background:rgba(215,244,82,.12);color:#D7F452;padding:2px 8px;border-radius:5px;"
    const rOff =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:.5px;background:rgba(255,255,255,.05);color:#5C6066;padding:2px 8px;border-radius:5px;text-decoration:line-through;"
    const mbBase =
      'width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;flex:none;background:'
    const permBits = [
      ['CHAT', API.PERM.CHAT],
      ['STUDIO GEN', API.PERM.STUDIO_GENERATE],
      ['MODELS', API.PERM.STUDIO_MODELS],
      ['INTEGRATIONS', API.PERM.INTEGRATIONS],
      ['BILLING', API.PERM.BILLING],
    ]
    const members = (store.members || []).map((m, i) => {
      const names = (m.allowed_studio_model_ids || [])
        .map((id) => modelNameById(id))
        .filter((n) => n !== '—')
        .join(', ')
      const st = store.chatterStats?.members?.find((s) => s.user_id === m.id) || {}
      return {
        login: m.member_login,
        meta: (m.is_active ? (lang === 'ru' ? 'активен' : 'active') : lang === 'ru' ? 'выкл' : 'off') + (names ? ' · ' + (lang === 'ru' ? 'персонажи' : 'characters') + ': ' + names : ''),
        initial: (m.member_login[0] || '?').toUpperCase(),
        avStyle: mbBase + AV_G[i % 5],
        sla: (() => {
          const sec = st.median_reply_seconds
          return sec != null ? Math.floor(sec / 60) + 'м ' + (sec % 60) + 'с' : '—'
        })(),
        replies: String(st.outbound_messages || 0),
        tribute: (m.tribute_share_percent || 0) + '%',
        rights: permBits.map(([label, bit]) => ({
          label,
          style: API.hasPerm(m.permissions_mask, bit) ? rOn : rOff,
        })),
      }
    })
    const templates = (store.snippets || []).map((s) => ({
      title: s.title || '—',
      body: s.body || '',
    }))
    const cs = store.chatterStats
    const totalReplies = sumOutboundMessages(cs)
    const teamKpi = [
      { label: lang === 'ru' ? 'ОТВЕТЫ / МЕС' : 'REPLIES / MO', value: String(totalReplies) },
      { label: lang === 'ru' ? 'ДИАЛОГИ' : 'DIALOGS', value: String(cs?.self?.conversations_replied ?? cs?.self_row?.conversations_replied ?? 0) },
      {
        label: lang === 'ru' ? 'ПЕРВЫЙ ОТВЕТ' : 'FIRST REPLY',
        value: (() => {
          const sec = cs?.self?.median_reply_seconds ?? cs?.self_row?.median_reply_seconds
          return sec != null ? Math.floor(sec / 60) + 'м ' + (sec % 60) + 'с' : '—'
        })(),
      },
      {
        label: 'AI 👍 / 👎',
        value: (() => {
          const pos = cs?.self?.companion_ratings_positive ?? 0
          const neg = cs?.self?.companion_ratings_negative ?? 0
          const tot = pos + neg
          return tot ? Math.round((pos / tot) * 100) + '%' : '—'
        })(),
      },
    ]
    return { members, templates, teamKpi }
  }

  function enrich(logic, vals) {
    if (!store.authed) return emptyVals(vals)
    const s = logic.state
    const lang = s.lang || 'ru'
    const me = store.me
    const mask = me?.permissions_mask ?? 0
    const isOwner = me?.is_workspace_owner

    const credits = me ? fmtCredits(me.credits_balance) : vals.creditsBalance || '0'
    const email = me ? shortEmail(me.email) : ''
    const planName = me?.plan_display_name || me?.plan_tier || '—'
    const role = isOwner ? vals.t.owner : (me?.member_login || vals.t.owner)
    const helloName = (me?.email || '').split('@')[0] || '—'
    const hello = lang === 'ru' ? 'С возвращением, ' + helloName : 'Welcome back, ' + helloName

    const convs = store.conversations
    const unreadTotal = convs.reduce((a, c) => a + (c.unread_count || 0), 0)
    const recentDialogs = convs.slice(0, 4).map((c, i) => mkDlgFromConv(c, i, logic))
    const chats = convs.map((c, i) => {
      const d = mkDlgFromConv(c, i, logic)
      return {
        ...d,
        avStyle: d.avStyleLg,
        rowStyle:
          'display:flex;gap:10px;align-items:center;padding:9px 8px;border-radius:12px;cursor:pointer;' +
          (s.chatOpen === i
            ? 'background:rgba(215,244,82,.07);border:1px solid rgba(215,244,82,.2);'
            : 'border:1px solid transparent;'),
      }
    })

    const bubbleIn =
      'max-width:78%;background:#1A1C20;border:1px solid rgba(255,255,255,.07);border-radius:14px 14px 14px 4px;padding:10px 13px;'
    const bubbleOut =
      'max-width:78%;background:rgba(215,244,82,.09);border:1px solid rgba(215,244,82,.2);border-radius:14px 14px 4px 14px;padding:10px 13px;'
    const messages = store.messages.map((m) => ({
      wrap: 'display:flex;justify-content:' + (m.direction === 'outbound' ? 'flex-end' : 'flex-start') + ';',
      bubble: m.direction === 'outbound' ? bubbleOut : bubbleIn,
      text: m.text_original || '',
      tr: m.text_translated && m.text_translated !== m.text_original ? m.text_translated : false,
      time: fmtDateShort(m.created_at) + ' · ' + fmtTime(m.created_at),
    }))

    const tagBase =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;padding:2px 7px;border-radius:5px;"
    const notes = store.notes.map((n) => ({
      tag: (n.kind || 'NOTE').toUpperCase(),
      tagStyle: tagBase + 'background:rgba(215,244,82,.15);color:#D7F452;',
      when: fmtDateShort(n.updated_at || n.created_at),
      text: n.content || '',
    }))

    const archiveFrames = store.archiveImages.map((item, i) => archiveToFrame(item, i, logic, vals))
    const recentFrames = archiveFrames.slice(0, 4)
    const videoArchive = store.archiveVideos.slice(0, 4).map((item, i) => ({
      bg: 'aspect-ratio:9/16;display:flex;align-items:center;justify-content:center;position:relative;background:center/cover no-repeat url("' +
        (item.image_url || '').replace(/"/g, '') + '"),' + G[(i + 2) % 6],
      who: item.model_name || '—',
      dur: '5s',
    }))

    const chipOn =
      "font-family:'JetBrains Mono';font-size:10px;background:rgba(215,244,82,.12);color:#D7F452;border:1px solid rgba(215,244,82,.4);padding:3px 10px;border-radius:20px;cursor:pointer;"
    const chipOff =
      "font-family:'JetBrains Mono';font-size:10px;border:1px solid rgba(255,255,255,.12);color:#9BA0A6;padding:3px 10px;border-radius:20px;cursor:pointer;"
    const engine = mapEngineChips(logic, lang)
    const charChips = store.models.map((m) => ({
      id: m.id,
      label: m.name,
      pick: () => {
        store.selectedModelId = m.id
        logic.forceUpdate()
      },
      style:
        'font-size:12px;font-weight:' +
        (store.selectedModelId === m.id ? '800' : '700') +
        ';' +
        (store.selectedModelId === m.id
          ? 'background:rgba(240,168,200,.12);color:#F0A8C8;border:1px solid rgba(240,168,200,.4);'
          : 'border:1px solid rgba(255,255,255,.12);color:#9BA0A6;') +
        'padding:6px 14px;border-radius:9px;cursor:pointer;',
    }))

    const stActive =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;padding:2px 8px;border-radius:20px;background:rgba(74,222,128,.12);color:#4ADE80;border:1px solid rgba(74,222,128,.3);"
    const stDim =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;padding:2px 8px;border-radius:20px;background:rgba(255,255,255,.06);color:#9BA0A6;border:1px solid rgba(255,255,255,.1);"
    const coverBase =
      'height:110px;display:flex;align-items:center;justify-content:center;background:'
    const characters = store.models.map((m, i) =>
      modelToCharacter(m, i, lang, logic, stActive, stDim, coverBase),
    )

    const donTotal = store.donationOverview?.totals_by_currency?.RUB ?? store.donationOverview?.totals_by_currency?.rub
    const donAvail = store.donationOverview?.pending_payout_by_currency?.RUB ?? store.donationOverview?.pending_payout_by_currency?.rub
    const currency = store.donationOverview?.currency || 'RUB'
    const donStats = [
      { label: lang === 'ru' ? 'ВСЕГО' : 'TOTAL', value: fmtMoney(donTotal, currency), color: '#F2F3F0' },
      { label: lang === 'ru' ? 'ДОСТУПНО' : 'AVAILABLE', value: fmtMoney(donAvail, currency), color: '#4ADE80' },
      { label: lang === 'ru' ? 'НА УДЕРЖАНИИ' : 'ON HOLD', value: fmtMoney(store.donationOverview?.pending_payout_by_currency?.RUB, currency), color: '#FB923C' },
      { label: lang === 'ru' ? 'ВЫПЛАЧЕНО' : 'PAID OUT', value: '—', color: '#9BA0A6' },
    ]

    const history = (store.creditHistory?.items || store.creditHistory || [])
      .slice(0, 8)
      .map((row) => ({
        date: fmtDateShort(row.created_at),
        what: row.kind || '—',
        delta: (row.credits_delta > 0 ? '+' : '') + row.credits_delta + ' кр.',
        color: row.credits_delta >= 0 ? '#4ADE80' : '#F87171',
      }))

    const navGroups = (vals.navGroups || []).map((grp) => ({
      ...grp,
      items: grp.items.map((it) => {
        let badge = it.badge
        if (it.label === vals.t.navDialogs || (it.label && it.label.includes('Диалог'))) {
          badge = unreadTotal > 0 ? String(unreadTotal) : false
        }
        if (it.label === vals.t.navDonations && store.donationOverview?.active_links) {
          badge = String(store.donationOverview.active_links)
        }
        return { ...it, badge }
      }),
    }))

    const chatFilters = [
      { label: (lang === 'ru' ? 'Все · ' : 'All · ') + convs.length, style: chipOn },
      { label: 'VIP · ' + convs.filter((c) => c.manual_category === 'vip').length, style: chipOff },
      { label: '24ч+ · ' + convs.filter((c) => c.is_no_response).length, style: chipOff },
      { label: lang === 'ru' ? 'Новые' : 'New', style: chipOff },
    ]

    const openIdx = s.chatOpen ?? 0
    const activeConv = convs[openIdx]
    const activeChat = activeConv
      ? {
          name: displayName(activeConv),
          initial: (displayName(activeConv)[0] || '?').toUpperCase(),
          vip: activeConv.manual_category === 'vip',
          persona: modelNameById(activeConv.studio_model_id),
          lang: activeConv.user_lang || activeConv.outbound_lang || '—',
          platform: platformLabel(activeConv.platform),
          avStyle: AV_G[openIdx % 5],
        }
      : { name: '—', initial: '?', vip: false, persona: '—', lang: '—', avStyle: AV_G[0] }

    const creditsNum = me ? Number(me.credits_balance) || 0 : 0
    const creditsFramesHint = '≈ ' + Math.max(0, Math.floor(creditsNum / 10)) + ' ' + vals.t.framesLeft
    const teamRepliesCount = String(sumOutboundMessages(store.chatterStats))
    const dialogsTotal = String(convs.length)
    const dialogsUnreadLabel =
      unreadTotal > 0
        ? unreadTotal + (lang === 'ru' ? ' новых' : ' new')
        : vals.t.allRead

    const donLinks = mapDonationLinks(lang)
    const incoming = mapIncomingEvents(lang)
    const myDonations = donLinks
    const { members, templates, teamKpi } = mapTeam(lang, vals)

    const charId = s.charDetail ? Number(s.charDetail) || null : null
    const activeChar = charId ? store.models.find((m) => m.id === charId) : null
    const activeCharName = activeChar?.name || '—'
    const activeCharInitial = ((activeChar?.name || '—')[0] || '?').toUpperCase()
    const charPhotos = activeChar ? mapCharPhotos(activeChar, lang) : []
    const photoTagList = mapPhotoTagList(lang, logic)
    const charHistory = charId ? mapCharHistory(charId, lang) : vals.charHistory || []

    return {
      ...vals,
      t: { ...vals.t, hello },
      creditsBalance: credits,
      creditsFramesHint,
      userEmailShort: email,
      userRolePlan: role + ' · ' + planName,
      donationsKpiTotal: fmtMoney(donTotal, currency),
      donationsKpiPayout: fmtMoney(donAvail, currency),
      dialogsTotal,
      dialogsUnreadLabel,
      teamRepliesCount,
      planDisplayName: planName,
      planUntil: me?.subscription_period_end ? fmtDateShort(me.subscription_period_end) : '—',
      navGroups,
      recentDialogs,
      recentFrames,
      chats,
      messages,
      notes,
      chatFilters,
      archiveFrames,
      videoArchive,
      charChips,
      modelChips: engine.modelChips,
      modelHint: engine.modelHint,
      characters,
      donStats,
      donLinks,
      incoming,
      myDonations,
      history,
      members,
      templates,
      teamKpi,
      activeChat,
      notesTitle: vals.t.fanNotes + (activeChat.name !== '—' ? ' · ' + activeChat.name : ''),
      activeCharName,
      activeCharInitial,
      charPhotos,
      photoTagList,
      charHistory,
      apiError: store.error,
      apiBusy: store.busy,
      runGenerate: () => void runGenerate(),
      runGenerateVideo: () => void runGenerateVideo(),
      sendReply: () => void sendReply(),
      logout: () => {
        API.setToken(null)
        store.authed = false
        showAuth(true)
        logic.forceUpdate()
      },
      canChat: isOwner || API.hasPerm(mask, API.PERM.CHAT),
      canStudio: isOwner || API.hasPerm(mask, API.PERM.STUDIO_GENERATE),
      canBilling: isOwner || API.hasPerm(mask, API.PERM.BILLING),
    }
  }

  let lastChatOpen = -1

  function onMount(logic) {
    store.logic = logic
    bindAuthForm()
    showAuth(true)
    void bootAuth()
    const obs = new MutationObserver(() => bindDomActions())
    obs.observe(document.body, { childList: true, subtree: true })
    bindDomActions()
    setInterval(() => {
      if (!store.authed || !store.logic) return
      bindDomActions()
      const co = store.logic.state.chatOpen ?? 0
      if (co !== lastChatOpen) {
        lastChatOpen = co
        const conv = store.conversations[co]
        if (conv) void loadMessages(conv.id)
      }
      const cd = store.logic.state.charDetail ?? null
      const cdNum = cd != null && cd !== '' ? Number(cd) : null
      if (cdNum !== lastSyncedCharId) syncCharProfileTextarea()
    }, 400)
  }

  global.MMOS_BRIDGE = {
    onMount,
    enrich,
    store,
    refreshAll,
    login,
    logout: () => API.setToken(null),
    runGenerate,
    runGenerateVideo,
    sendReply,
  }
})(window)
