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
    firstFrameUrl: null,
    firstFrameGenId: null,
    opRights: { chat: true, studio: true, models: true, keys: false, billing: false },
    opModelIds: null,
    authTab: 'login',
    telegramBotUsername: null,
    telegramWidgetCleanup: null,
    referralCode: null,
  }

  const AI_MODEL_MAP = {
    nano: 'nano-banana-pro',
    gpt: 'gpt-image-2',
    seedream: 'seedream-v5.0-pro',
    wan: 'wan-2.7-pro',
  }

  const OP_RIGHT_BITS = {
    chat: API.PERM.CHAT,
    studio: API.PERM.STUDIO_GENERATE,
    models: API.PERM.STUDIO_MODELS,
    keys: API.PERM.INTEGRATIONS,
    billing: API.PERM.BILLING,
  }

  const PHOTO_TAG_DEFS = [
    { kind: 'face', ru: 'Лицо', en: 'Face' },
    { kind: 'face', ru: 'Внешность', en: 'Look' },
    { kind: 'turnaround', ru: 'Развёртка', en: 'Turnaround' },
    { kind: 'body', ru: 'Тело целиком', en: 'Full body' },
    { kind: 'other', ru: 'Selfie', en: 'Selfie' },
    { kind: 'other', ru: 'Основная камера', en: 'Main camera' },
  ]

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

  const REPLY_LANG_MAP = {
    ru: 'Русский',
    en: 'English',
    es: 'Español',
    de: 'Deutsch',
    nl: 'Nederlands',
    fr: 'Français',
    it: 'Italiano',
    pt: 'Português',
  }

  function replyLangLabel(code) {
    const raw = (code || '').replace(/\*$/, '').trim().toLowerCase()
    if (!raw) return '—'
    return REPLY_LANG_MAP[raw] || raw
  }

  function slotUploadKey(mode, index) {
    if (mode === 'outfit') return index === 0 ? 'ref' : 'outfit-cloth'
    if (mode === 'location') return index === 0 ? 'ref' : 'location-photo'
    if (mode === 'carousel') return 'carousel'
    return 'ref'
  }

  function slotStateKey(mode, index) {
    return mode + ':' + index
  }

  if (!store.slotArchivePicks) store.slotArchivePicks = {}

  function mkArchiveMiniGrid(logic, slotKeyStr) {
    const pickedId = store.slotArchivePicks[slotKeyStr]
    return store.archiveImages.slice(0, 8).map((item, i) => {
      const url = archiveThumbUrl(item)
      const pending = isArchivePending(item)
      const bgCore = url
        ? 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
        : G[i % 6]
      return {
        style:
          'aspect-ratio:3/4;border-radius:7px;border:2px solid ' +
          (pickedId === item.id ? '#D7F452' : 'transparent') +
          ';cursor:pointer;background:' +
          bgCore +
          (pending ? ';opacity:.55;' : ''),
        pick: pending
          ? () => {}
          : () => {
              store.slotArchivePicks[slotKeyStr] = item.id
              if (slotKeyStr.endsWith(':0') || slotKeyStr.includes('ref')) {
                delete store.uploadFiles.ref
                delete store.uploadFiles.carousel
              }
              if (slotKeyStr.endsWith(':1')) {
                delete store.uploadFiles['outfit-cloth']
                delete store.uploadFiles['location-photo']
              }
              logic.forceUpdate()
            },
      }
    })
  }

  function carouselPerFrameCost() {
    const n = Number(store.health?.studio_carousel_credit_cost)
    return Number.isFinite(n) && n >= 0 ? n : 2
  }

  function fmtCarouselGenerateCost(lang, count) {
    const perFrame = carouselPerFrameCost()
    const frames = Math.max(2, Math.min(8, Number(count) || 4))
    const total = perFrame * frames
    const cr = lang === 'ru' ? 'кр' : 'cr'
    return `−${total} ${cr}`
  }

  function fmtCarouselModeCardCost(lang) {
    const perFrame = carouselPerFrameCost()
    const cr = lang === 'ru' ? 'кр' : 'cr'
    return lang === 'ru' ? `−${perFrame} ${cr}/кадр` : `−${perFrame} ${cr}/frame`
  }

  function mapCurMode(logic, vals) {
    const s = logic.state
    const base = vals.curMode || {}
    const mode = s.imgMode || 'ref'
    const lang = s.lang || 'ru'
    const segSm = (on) =>
      'flex:1;text-align:center;font-family:JetBrains Mono;font-size:9px;letter-spacing:.5px;padding:4px 8px;border-radius:6px;cursor:pointer;' +
      (on ? 'background:#D7F452;color:#171A05;font-weight:800;' : 'color:#9BA0A6;')
    const slots = (base.slots || []).map((sl, i) => {
      const sk = slotStateKey(mode, i)
      const src = (s.slotSource && s.slotSource[sk]) || (sl.archive ? 'upload' : 'upload')
      const uploadKey = slotUploadKey(mode, i)
      return {
        ...sl,
        uploadKey,
        fromArchive: !!sl.archive && src === 'archive',
        uploadMode: !sl.archive || src !== 'archive',
        upStyle: segSm(src === 'upload'),
        arStyle: segSm(src === 'archive'),
        setUpload: () => logic.setState({ slotSource: { ...(s.slotSource || {}), [sk]: 'upload' } }),
        setArchive: () => logic.setState({ slotSource: { ...(s.slotSource || {}), [sk]: 'archive' } }),
        archiveMini: mkArchiveMiniGrid(logic, sk),
      }
    })
    const out = { ...base, slots }
    if (mode === 'carousel') {
      out.cost = fmtCarouselGenerateCost(lang, s.carouselCount)
    }
    return out
  }

  async function copyText(text) {
    const t = (text || '').trim()
    if (!t) return
    try {
      await navigator.clipboard.writeText(t)
      store.error = null
    } catch {
      store.error = 'Не удалось скопировать'
    }
    store.logic?.forceUpdate()
  }

  const ICO_TG = {
    __html:
      '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor"><path d="M21 4.5L3.5 11.2c-.9.35-.85 1.6.1 1.85l4.4 1.2 1.7 5.2c.3.85 1.4 1 1.9.3l2.4-3.1 4.5 3.3c.75.55 1.8.15 2-.75L23 6c.25-1.1-.85-2-1.9-1.5z"/></svg>',
  }
  const ICO_GLOBE = {
    __html:
      '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.3 3.6 5.3 3.6 8.5s-1.2 6.2-3.6 8.5c-2.4-2.3-3.6-5.3-3.6-8.5S9.6 5.8 12 3.5z"/></svg>',
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
        const patch = {
          chatOpen: i,
          page: 'dialogs',
          msgReact: null,
          emojiOpen: false,
        }
        if (logic.state.isMobile) patch.mobileChat = true
        logic.setState(patch)
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

  function chatStatusType(c) {
    if (c.is_blocked) return 'blocked'
    if (c.peer_unavailable) return 'deleted'
    return false
  }

  function archiveThumbUrl(item) {
    if (!item) return ''
    if (item.media_kind === 'video') {
      const poster = (item.image_url || '').trim()
      if (poster) return poster
      return (item.video_url || '').trim()
    }
    return (item.image_url || '').trim()
  }

  function resolveLightboxId(s) {
    const lb = s?.lightbox
    if (typeof lb === 'number' && !Number.isNaN(lb)) return lb
    if (lb && typeof lb === 'object' && lb.id != null) {
      const n = Number(lb.id)
      return Number.isNaN(n) ? null : n
    }
    return null
  }

  function aspectCss(ratio) {
    const r = (ratio || '9:16').trim()
    if (r === '16:9') return '16/9'
    if (r === '1:1') return '1/1'
    if (r === '4:5') return '4/5'
    if (r === '3:4') return '3/4'
    return '9/16'
  }

  const OPTIMISTIC_ARCHIVE_ID_FLOOR = -1_000_000_000
  let optimisticArchiveSeq = 0
  let archivePollTimer = null

  function isOptimisticArchiveId(id) {
    return id <= OPTIMISTIC_ARCHIVE_ID_FLOOR
  }

  function isArchivePending(item) {
    if (!item) return false
    const st = (item.status || '').trim()
    if (st === 'processing' || st === 'archiving') return true
    if (st === 'failed' || st === 'ready') return false
    if (st === 'provider_ready') {
      if (item.media_kind === 'video') return !(item.video_url || '').trim()
      return !(item.image_url || '').trim()
    }
    return isOptimisticArchiveId(item.id)
  }

  function dedupeArchiveById(items) {
    const seen = new Set()
    const out = []
    for (const g of items) {
      if (seen.has(g.id)) continue
      seen.add(g.id)
      out.push(g)
    }
    return out
  }

  function mergeArchiveItems(current, incoming) {
    if (!incoming.length) return dedupeArchiveById(current)
    const byId = new Map(incoming.map((p) => [p.id, p]))
    const merged = current.map((g) => byId.get(g.id) ?? g)
    const seen = new Set(merged.map((g) => g.id))
    for (const p of incoming) {
      if (!seen.has(p.id)) merged.unshift(p)
    }
    return dedupeArchiveById(merged)
  }

  function createOptimisticArchiveItem(opts) {
    optimisticArchiveSeq += 1
    const tempId = OPTIMISTIC_ARCHIVE_ID_FLOOR - optimisticArchiveSeq
    return {
      tempId,
      item: {
        id: tempId,
        created_at: new Date().toISOString(),
        output_aspect: opts.outputAspect || '9:16',
        studio_model_id: opts.studioModelId ?? null,
        model_name: opts.modelName ?? null,
        prompt_excerpt: (opts.promptExcerpt || '').trim().slice(0, 200) || 'Генерация…',
        status: 'processing',
        media_kind: opts.mediaKind || 'image',
        error_message: null,
        job_id: null,
        image_url: '',
        video_url: null,
      },
    }
  }

  function prependOptimisticArchive(current, item) {
    return dedupeArchiveById([item, ...current])
  }

  function replaceOptimisticArchiveId(current, tempId, realId, patch) {
    return dedupeArchiveById(
      current.map((g) => (g.id === tempId ? { ...g, id: realId, ...patch } : g)),
    )
  }

  function removeOptimisticArchive(current, tempId) {
    return current.filter((g) => g.id !== tempId)
  }

  function hasPendingArchive() {
    return (
      store.archiveImages.some(isArchivePending) ||
      store.archiveVideos.some(isArchivePending)
    )
  }

  function archiveItemPollKey(item) {
    if (!item) return ''
    return [
      item.id,
      item.status || '',
      item.image_url || '',
      item.video_url || '',
      item.error_message || '',
      item.job_id || '',
    ].join('|')
  }

  async function refreshArchiveImages() {
    const optimistic = store.archiveImages.filter((g) => isOptimisticArchiveId(g.id))
    const [page, pending] = await Promise.all([
      API.apiJson('/api/studio/generations?limit=40&skip=0&media_kind=image').catch(() => ({ items: [] })),
      API.apiJson('/api/studio/generations/pending?media_kind=image').catch(() => ({ items: [] })),
    ])
    let images = mergeArchiveItems(page.items || [], pending.items || [])
    images = mergeArchiveItems(images, optimistic)
    store.archiveImages = images
  }

  /** Опрос только незавершённых карточек — без полной перезагрузки архива. */
  async function refreshPendingArchiveOnly() {
    const tracked = store.archiveImages.filter(
      (g) => isArchivePending(g) || isOptimisticArchiveId(g.id),
    )
    if (!tracked.length) return false

    const pending = await API.apiJson('/api/studio/generations/pending?media_kind=image').catch(() => ({
      items: [],
    }))
    const pendingItems = pending.items || []
    const pendingById = new Map(pendingItems.map((p) => [p.id, p]))
    let changed = false
    const completedIds = []

    store.archiveImages = store.archiveImages.map((g) => {
      if (isOptimisticArchiveId(g.id)) {
        const byJob =
          g.job_id != null ? pendingItems.find((p) => p.job_id === g.job_id) : null
        if (byJob) {
          const next = { ...g, ...byJob, id: byJob.id }
          if (archiveItemPollKey(g) !== archiveItemPollKey(next)) changed = true
          return next
        }
        return g
      }
      if (!isArchivePending(g)) return g
      const upd = pendingById.get(g.id)
      if (upd) {
        const next = { ...g, ...upd }
        if (archiveItemPollKey(g) !== archiveItemPollKey(next)) changed = true
        return next
      }
      completedIds.push(g.id)
      return g
    })

    if (completedIds.length) {
      const page = await API.apiJson('/api/studio/generations?limit=40&skip=0&media_kind=image').catch(() => ({
        items: [],
      }))
      const freshById = new Map((page.items || []).map((p) => [p.id, p]))
      store.archiveImages = store.archiveImages.map((g) => {
        if (!completedIds.includes(g.id)) return g
        const fresh = freshById.get(g.id)
        if (!fresh) return g
        const next = { ...g, ...fresh }
        if (archiveItemPollKey(g) !== archiveItemPollKey(next)) changed = true
        return next
      })
    }

    return changed
  }

  function scheduleArchivePoll() {
    if (archivePollTimer != null) return
    const tick = async () => {
      archivePollTimer = null
      if (!store.authed || !hasPendingArchive()) return
      try {
        const changed = await refreshPendingArchiveOnly()
        if (changed) store.logic?.forceUpdate()
      } catch (_) {
        /* тихий опрос */
      }
      if (hasPendingArchive()) {
        archivePollTimer = setTimeout(tick, 12000)
      }
    }
    archivePollTimer = setTimeout(tick, 4000)
  }

  function archiveToFrame(item, i, logic, I) {
    const url = archiveThumbUrl(item)
    const pending = isArchivePending(item)
    const who = item.model_name || '—'
    const ratio = item.output_aspect || '9:16'
    const tileBase =
      'aspect-ratio:9/16;border-radius:10px;display:flex;align-items:flex-end;padding:8px;position:relative;overflow:hidden;cursor:pointer;background:'
    const thumbBase =
      'aspect-ratio:9/16;border-radius:8px;cursor:pointer;border:2px solid transparent;background:'
    const bgCore = url
      ? 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
      : G[i % 6]
    const bgStyle = tileBase + bgCore + ';'
    const thumbStyle = (url
      ? thumbBase + 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
      : thumbBase + G[i % 6]) + ';'
    return {
      id: item.id,
      bg: bgStyle,
      tileStyle: bgStyle,
      thumbStyle,
      label: who + ' · ' + ratio,
      who,
      ratio,
      url,
      pending,
      spinnerWrap:
        'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(6,7,9,.55);',
      spinnerStyle:
        'width:22px;height:22px;border-radius:50%;border:2.5px solid rgba(215,244,82,.25);border-top-color:#D7F452;animation:mmSpin .8s linear infinite;',
      showPlaceholder: !url,
      open: pending
        ? () => {}
        : () => {
            logic.setState({ lightbox: item.id })
            if (!url || isArchivePending(item)) {
              void refreshArchiveImages().then(() => logic.forceUpdate())
            }
          },
    }
  }

  function buildFfThumbStyles(url) {
    const thumbBase =
      'width:70px;aspect-ratio:9/16;border-radius:10px;flex:none;overflow:hidden;background:'
    const bgCore = url
      ? 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[3]
      : G[3]
    const bg = thumbBase + bgCore + ';'
    return {
      loading:
        bg +
        'display:flex;align-items:center;justify-content:center;animation:mmPulse 1.2s ease-in-out infinite;',
      done: bg + 'display:flex;align-items:flex-end;padding:6px;',
    }
  }

  function buildLightboxData(s, lang) {
    const id = resolveLightboxId(s)
    if (id == null) return null
    const item =
      store.archiveImages.find((x) => x.id === id) ||
      store.archiveVideos.find((x) => x.id === id)
    if (!item) return null
    const url = archiveThumbUrl(item)
    const ratio = item.output_aspect || '9:16'
    const previewWrap =
      'width:100%;aspect-ratio:' +
      aspectCss(ratio) +
      ';max-height:min(calc(92vh - 200px),640px);flex:none;flex-shrink:0;border-radius:14px;overflow:hidden;position:relative;background:' +
      (url ? '#0A0B0D' : G[id % 6]) +
      ';'
    const actionsStyle =
      'display:flex;gap:10px;width:100%;flex:none;flex-shrink:0;align-self:stretch;'
    const cardStyle =
      'display:flex;flex-direction:column;align-items:stretch;gap:14px;width:min(92vw,720px);max-height:92vh;flex-shrink:0;'
    const mode =
      item.media_kind === 'video'
        ? lang === 'ru'
          ? 'Видео'
          : 'Video'
        : lang === 'ru'
          ? 'Кадр'
          : 'Frame'
    return {
      previewWrap,
      cardStyle,
      actionsStyle,
      big: previewWrap,
      who: item.model_name || '—',
      ratio,
      mode,
      when: fmtDateShort(item.created_at) + ' · ' + fmtTime(item.created_at),
      url: url || '',
      hasImage: !!url,
      id: item.id,
      showPlaceholder: !url,
    }
  }

  function validateImageGen(logic, vals) {
    const s = logic.state
    const t = vals.t
    const errs = []
    const mode = s.imgMode || 'prompt'
    const slotCounts = { ref: 1, swap: 1, outfit: 2, location: 2, prompt: 0, carousel: 1 }
    const slotN = slotCounts[mode] ?? 0
    const hasCarouselSrc =
      !!resolveCarouselUploadFile(s) ||
      !!s.carouselPickId ||
      !!store.slotArchivePicks[slotStateKey('carousel', 0)]
    const hasFrame =
      mode === 'carousel'
        ? hasCarouselSrc
        : !!store.uploadFiles.ref || !!store.slotArchivePicks[slotStateKey(mode, 0)]
    if (slotN > 0 && !hasFrame && !(mode === 'carousel' && hasCarouselSrc)) errs.push(t.errNoRef)
    if (mode === 'outfit') {
      const hasCloth =
        !!store.uploadFiles['outfit-cloth'] || !!store.slotArchivePicks[slotStateKey('outfit', 1)]
      if (!hasCloth) errs.push(t.errNoRef)
    }
    if (mode === 'location') {
      const hasLoc =
        !!store.uploadFiles['location-photo'] || !!store.slotArchivePicks[slotStateKey('location', 1)]
      if (!hasLoc) errs.push(t.errNoRef)
    }
    if (mode === 'prompt' && !resolveStudioPrompt('prompt')) errs.push(t.errNoPrompt)
    if (mode !== 'outfit' && mode !== 'location' && !store.selectedModelId) errs.push(t.errNoChar)
    return errs
  }

  function waveModelFromState(s) {
    const mapped = AI_MODEL_MAP[s.aiModel]
    if (mapped) return mapped
    return store.selectedWaveModelId
  }

  function isNsfwMode(s) {
    return s.contentMode === 'nsfw' || !!s.nsfw
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
    await refreshArchiveImages()
    const vid = await API.apiJson('/api/studio/generations?limit=40&skip=0&media_kind=video').catch(() => ({ items: [] }))
    const vidPending = await API.apiJson('/api/studio/generations/pending?media_kind=video').catch(() => ({ items: [] }))
    store.archiveVideos = mergeArchiveItems(vid.items || [], vidPending.items || [])
    const motion = await API.apiJson('/api/studio/motion/renders?limit=40&skip=0').catch(() => [])
    store.motionRenders = Array.isArray(motion) ? motion : motion.items || []
    if (hasPendingArchive()) scheduleArchivePoll()
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

  function readReferralCodeFromUrl() {
    try {
      const ref = new URLSearchParams(global.location.search).get('ref')
      return ref ? ref.trim().toUpperCase() : null
    } catch {
      return null
    }
  }

  async function afterAuthSuccess() {
    store.me = await API.apiJson('/api/auth/me')
    store.authed = true
    if (store.me?.email_setup_required) {
      showAuth(true)
      updateAuthUi()
      return
    }
    showAuth(false)
    await refreshAll()
    connectWs()
    const first = store.conversations[0]
    if (first) void loadMessages(first.id)
    store.logic?.forceUpdate()
  }

  async function loadAuthConfig() {
    store.referralCode = readReferralCodeFromUrl()
    try {
      const h = await API.apiJson('/api/health')
      store.health = h
      if (h.telegram_login_configured && h.telegram_login_bot_username) {
        store.telegramBotUsername = String(h.telegram_login_bot_username).trim().replace(/^@/, '')
      } else {
        store.telegramBotUsername = null
      }
    } catch {
      store.telegramBotUsername = null
    }
  }

  function mountAuthTelegramWidget() {
    if (typeof store.telegramWidgetCleanup === 'function') {
      store.telegramWidgetCleanup()
      store.telegramWidgetCleanup = null
    }
    const host = document.getElementById('mm-os-auth-telegram-host')
    const wrap = document.getElementById('mm-os-auth-telegram')
    const divider = document.getElementById('mm-os-auth-or-email')
    if (!host || !wrap) return

    const member = (document.getElementById('mm-os-auth-member')?.value || '').trim()
    const showTg =
      !!store.telegramBotUsername &&
      global.MMOS_TELEGRAM_LOGIN &&
      (store.authTab === 'register' || (store.authTab === 'login' && !member))

    wrap.style.display = showTg ? 'flex' : 'none'
    if (divider) divider.style.display = showTg ? 'flex' : 'none'
    host.replaceChildren()
    if (!showTg) return

    store.telegramWidgetCleanup = global.MMOS_TELEGRAM_LOGIN.mountTelegramLoginWidget(
      host,
      store.telegramBotUsername,
      (user) => {
        void telegramAuth(user)
      },
    )
  }

  async function telegramAuth(user) {
    store.busy = true
    store.error = null
    updateAuthUi()
    const busyEl = document.getElementById('mm-os-auth-telegram-busy')
    if (busyEl) busyEl.style.display = 'block'
    try {
      const res = await global.MMOS_TELEGRAM_LOGIN.postTelegramAuth(
        '/api/auth/telegram',
        user,
        store.referralCode,
      )
      const data = await API.readJson(res)
      if (!res.ok) throw new Error(API.formatDetail(data) || 'Telegram login failed')
      API.setToken(data.access_token)
      await afterAuthSuccess()
    } catch (e) {
      store.error = e.message || String(e)
      updateAuthUi()
    } finally {
      store.busy = false
      if (busyEl) busyEl.style.display = 'none'
      updateAuthUi()
    }
  }

  async function completeOwnerEmail() {
    const email = (document.getElementById('mm-os-auth-complete-email')?.value || '').trim()
    const password = document.getElementById('mm-os-auth-complete-pass')?.value || ''
    if (!email || password.length < 8) {
      store.error = 'Укажите email и пароль (мин. 8 символов)'
      updateAuthUi()
      return
    }
    store.busy = true
    store.error = null
    updateAuthUi()
    try {
      const data = await API.apiJson('/api/auth/email/complete', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      API.setToken(data.access_token)
      showAuth(false)
      await refreshAll()
      connectWs()
      store.logic?.forceUpdate()
    } catch (e) {
      store.error = e.message || String(e)
      updateAuthUi()
    } finally {
      store.busy = false
      updateAuthUi()
    }
  }

  function setAuthTab(tab) {
    store.authTab = tab === 'register' ? 'register' : 'login'
    store.error = null
    updateAuthUi()
    mountAuthTelegramWidget()
  }
  function showAuth(show) {
    const el = document.getElementById('mm-os-auth')
    if (el) el.style.display = show ? 'flex' : 'none'
    const root = document.querySelector('[data-screen-label="ModelMate OS"]')?.parentElement
    if (root) root.style.visibility = show ? 'hidden' : 'visible'
    if (show) {
      updateAuthUi()
      mountAuthTelegramWidget()
    }
  }

  async function bootAuth() {
    await loadAuthConfig()
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
      if (store.me?.email_setup_required) {
        showAuth(true)
      } else {
        showAuth(false)
        await refreshAll()
        connectWs()
        const first = store.conversations[0]
        if (first) void loadMessages(first.id)
      }
    } catch {
      API.setToken(null)
      store.authed = false
      showAuth(true)
    } finally {
      store.authReady = true
      store.logic?.forceUpdate()
    }
  }

  async function register(email, password) {
    store.busy = true
    store.error = null
    updateAuthUi()
    try {
      const body = { email, password }
      if (store.referralCode) body.referral_code = store.referralCode
      const data = await API.apiJson('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      API.setToken(data.access_token)
      await afterAuthSuccess()
    } catch (e) {
      store.error = e.message || String(e)
      updateAuthUi()
    } finally {
      store.busy = false
      updateAuthUi()
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
      await afterAuthSuccess()
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
    const pass = document.getElementById('mm-os-auth-pass')
    const memberWrap = document.getElementById('mm-os-auth-member-wrap')
    const tabLogin = document.getElementById('mm-os-auth-tab-login')
    const tabRegister = document.getElementById('mm-os-auth-tab-register')
    const emailComplete = document.getElementById('mm-os-auth-email-complete')
    const referral = document.getElementById('mm-os-auth-referral')
    const isRegister = store.authTab === 'register'
    const needsEmail = !!store.me?.email_setup_required

    if (err) err.textContent = store.error || ''
    if (btn) {
      btn.disabled = store.busy
      btn.textContent = needsEmail
        ? 'Войти'
        : isRegister
          ? 'Зарегистрироваться'
          : 'Войти'
    }
    if (pass) pass.autocomplete = isRegister ? 'new-password' : 'current-password'
    if (memberWrap) memberWrap.style.display = !needsEmail && !isRegister ? 'block' : 'none'
    if (tabLogin) tabLogin.classList.toggle('is-active', store.authTab === 'login' && !needsEmail)
    if (tabRegister) tabRegister.classList.toggle('is-active', store.authTab === 'register' && !needsEmail)
    if (emailComplete) emailComplete.classList.toggle('is-visible', needsEmail)
    if (referral) {
      if (store.referralCode && !needsEmail) {
        referral.style.display = 'block'
        referral.textContent = 'Реферальный код: ' + store.referralCode
      } else {
        referral.style.display = 'none'
        referral.textContent = ''
      }
    }
    const tabs = document.querySelector('.mm-os-auth-tabs')
    if (tabs) tabs.style.display = needsEmail ? 'none' : 'flex'
    const credentials = document.getElementById('mm-os-auth-credentials')
    if (credentials) credentials.style.display = needsEmail ? 'none' : 'block'
    const telegram = document.getElementById('mm-os-auth-telegram')
    const orEmail = document.getElementById('mm-os-auth-or-email')
    if (telegram && needsEmail) telegram.style.display = 'none'
    if (orEmail && needsEmail) orEmail.style.display = 'none'
    const subtitle = document.getElementById('mm-os-auth-subtitle')
    if (subtitle) {
      subtitle.textContent = needsEmail
        ? 'Завершите настройку аккаунта после входа через Telegram.'
        : 'Войдите или зарегистрируйтесь — тем же аккаунтом, что и в основном кабинете.'
    }
  }

  function bindAuthForm() {
    const form = document.getElementById('mm-os-auth-form')
    if (!form || form.dataset.bound) return
    form.dataset.bound = '1'

    document.getElementById('mm-os-auth-tab-login')?.addEventListener('click', () => setAuthTab('login'))
    document.getElementById('mm-os-auth-tab-register')?.addEventListener('click', () => setAuthTab('register'))
    document.getElementById('mm-os-auth-member')?.addEventListener('input', () => mountAuthTelegramWidget())
    document.getElementById('mm-os-auth-complete-submit')?.addEventListener('click', () => {
      void completeOwnerEmail()
    })

    form.addEventListener('submit', (e) => {
      e.preventDefault()
      if (store.me?.email_setup_required) return
      const email = document.getElementById('mm-os-auth-email')?.value || ''
      const password = document.getElementById('mm-os-auth-pass')?.value || ''
      const member = document.getElementById('mm-os-auth-member')?.value || ''
      if (store.authTab === 'register') {
        void register(email, password)
      } else {
        void login(email, password, member.trim() || null)
      }
    })
  }

  function queryPromptTextarea() {
    return document.querySelector('[data-mm-studio-prompt]')
  }

  function getModeDefaultPrompt(mode) {
    const map = window.MMOS_STUDIO_SCENARIOS?.MODE_DEFAULT_PROMPTS
    if (!map) return ''
    return map[mode] || ''
  }

  function resolveStudioPrompt(mode) {
    const fromField = (queryPromptTextarea()?.value || '').trim()
    if (fromField) return fromField
    return getModeDefaultPrompt(mode)
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
        if (key === 'carousel' && store.logic) {
          store.logic.setState({ carSource: 'upload', carouselPickId: null })
          store.logic.forceUpdate()
        }
      })
      zone.appendChild(clear)
    }
    const vid = box.querySelector('video')
    if (vid) vid.currentTime = 0.15
  }

  function uploadZoneKey(zone) {
    return zone.dataset.mmUpload || zone.dataset.mmSlotUpload || ''
  }

  function carouselUploadZoneHasPreview() {
    const root = document.querySelector('[data-screen-label="Студия — Картинки"]')
    if (!root) return false
    const zone = root.querySelector('[data-mm-slot-upload="carousel"], [data-mm-upload="carousel"]')
    return !!(zone && zone.querySelector('.mm-os-upload-preview'))
  }

  function resolveCarouselUploadFile(s) {
    if (store.uploadFiles.carousel) return store.uploadFiles.carousel
    if (
      store.uploadFiles.ref &&
      !resolveCarouselArchiveId(s) &&
      carouselUploadZoneHasPreview()
    ) {
      return store.uploadFiles.ref
    }
    return null
  }

  function resyncUploadZone(zone) {
    const key = uploadZoneKey(zone)
    if (!key) return
    const bound = zone.dataset.mmBound || ''
    if (bound && bound !== key && bound !== '1') {
      clearUploadZone(zone, bound)
      delete zone.dataset.mmBound
    }
    bindUploadZone(zone)
  }

  function resolveCarouselArchiveId(s) {
    return (
      store.slotArchivePicks[slotStateKey('carousel', 0)] ||
      s.carouselPickId ||
      null
    )
  }

  function resolveCarouselMasterSource(s) {
    const archId = resolveCarouselArchiveId(s)
    if (archId) return { srcId: archId, uploadFile: null }
    const uploadFile = resolveCarouselUploadFile(s)
    if (uploadFile) return { srcId: null, uploadFile }
    return { srcId: null, uploadFile: null }
  }

  function clearCarouselUploadDom() {
    document.querySelectorAll('[data-mm-upload="carousel"]').forEach((zone) => {
      clearUploadZone(zone, 'carousel')
    })
    const root = document.querySelector('[data-screen-label="Студия — Картинки"]')
    root?.querySelectorAll('[data-mm-slot-upload="carousel"]').forEach((zone) => {
      clearUploadZone(zone, 'carousel')
    })
  }

  function clearCarouselLocalUploads() {
    delete store.uploadFiles.carousel
    delete store.uploadFiles.ref
    clearCarouselUploadDom()
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
    const key = uploadZoneKey(zone)
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
        const activeKey = uploadZoneKey(zone) || key
        store.uploadFiles[activeKey] = file
        renderUploadPreview(zone, activeKey, file)
        if (activeKey === 'ref' || activeKey === 'carousel') {
          Object.keys(store.slotArchivePicks || {}).forEach((k) => {
            if (k.startsWith((store.logic?.state?.imgMode || 'ref') + ':')) delete store.slotArchivePicks[k]
          })
        }
        if (activeKey === 'carousel') {
          store.logic?.setState({ carSource: 'upload', carouselPickId: null })
          store.logic?.forceUpdate()
        }
        if (activeKey === 'motion-video') {
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

  function buildCharPhotoCardStyle(url, i) {
    const cardBase =
      'aspect-ratio:3/4;border-radius:10px;overflow:hidden;display:flex;flex-direction:column;align-items:stretch;justify-content:space-between;padding:6px;position:relative;background:'
    const bgCore = url
      ? 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
      : G[i % 6]
    return cardBase + bgCore + ';'
  }

  function mapCharPhotos(model, lang, logic) {
    const charId = model?.id
    const imgs = model?.images || []
    const rawMenu = logic.state.photoMenu
    const menuId = rawMenu != null && rawMenu !== '' ? Number(rawMenu) : null
    return imgs.map((im, i) => {
      const url = im.url || ''
      const imageId = Number(im.id)
      const cardStyle = buildCharPhotoCardStyle(url, i)
      return {
        id: imageId,
        bg: cardStyle,
        cardStyle,
        kind: imageKindLabel(im.kind, lang),
        open: (e) => {
          e?.stopPropagation?.()
          logic.setState({ photoMenu: menuId === imageId ? null : imageId })
        },
        menuOpen: menuId === imageId,
        deletePhoto: (e) => {
          e?.stopPropagation?.()
          void deleteCharPhoto(charId, imageId, logic)
        },
      }
    })
  }

  function mapPhotoTagMenu(lang, logic) {
    const charId = getActiveCharId()
    const rawMenu = logic.state.photoMenu
    const imageId = rawMenu != null && rawMenu !== '' ? Number(rawMenu) : null
    const img = getActiveChar()?.images?.find((x) => Number(x.id) === imageId)
    const curKind = (img?.kind || 'other').toLowerCase()
    return PHOTO_TAG_DEFS.map((d) => ({
      label: lang === 'ru' ? d.ru : d.en,
      style:
        'font-size:11px;font-weight:700;padding:5px 10px;border-radius:7px;cursor:pointer;' +
        (d.kind === curKind
          ? 'background:rgba(215,244,82,.15);color:#D7F452;'
          : 'color:#C9CDD1;'),
      pick: (e) => {
        e?.stopPropagation?.()
        if (!charId || imageId == null) return
        void patchCharPhotoKind(charId, imageId, d.kind, logic)
      },
    }))
  }

  async function patchCharPhotoKind(charId, imageId, kind, logic) {
    store.busy = true
    store.error = null
    try {
      await API.apiJson('/api/studio/models/' + charId + '/images/' + imageId, {
        method: 'PATCH',
        body: JSON.stringify({ kind }),
      })
      await loadModels()
      logic.setState({ photoMenu: null })
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      logic.forceUpdate()
    }
  }

  async function deleteCharPhoto(charId, imageId, logic) {
    if (!confirm('Удалить это фото?')) return
    store.busy = true
    store.error = null
    try {
      await API.apiJson('/api/studio/models/' + charId + '/images/' + imageId, { method: 'DELETE' })
      await loadModels()
      logic.setState({ photoMenu: null })
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      logic.forceUpdate()
    }
  }

  async function deleteConversation(id, logic) {
    if (!confirm('Удалить диалог из списка?')) return
    store.busy = true
    store.error = null
    try {
      await API.apiFetch('/api/conversations/' + id, { method: 'DELETE' })
      await loadConversations()
      logic.setState({ chatOpen: 0, mobileChat: false })
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      logic.forceUpdate()
    }
  }

  function maskFromOpRights(orR) {
    let mask = 0
    for (const [key, bit] of Object.entries(OP_RIGHT_BITS)) {
      if (orR[key]) mask |= bit
    }
    return mask
  }

  function mapOperatorForm(logic, lang, vals) {
    const s = logic.state
    const orR = s.opRights || store.opRights
    const cbStyle = (on) =>
      'width:20px;height:20px;flex:none;border-radius:6px;display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:12px;font-weight:900;' +
      (on ? 'background:#D7F452;color:#171A05;' : 'border:1.5px solid rgba(255,255,255,.2);color:transparent;')
    const opRightDefs = [
      { key: 'chat', label: vals.t.rChat },
      { key: 'studio', label: vals.t.rStudio },
      { key: 'models', label: vals.t.rModels },
      { key: 'keys', label: vals.t.rKeys },
      { key: 'billing', label: vals.t.rBilling },
    ]
    const opRightRows = opRightDefs.map((r) => ({
      label: r.label,
      on: !!orR[r.key],
      cb: cbStyle(!!orR[r.key]),
      rowStyle:
        'display:flex;align-items:center;justify-content:space-between;gap:14px;background:#0D0E11;border:1px solid ' +
        (orR[r.key] ? 'rgba(215,244,82,.25)' : 'rgba(255,255,255,.07)') +
        ';border-radius:12px;padding:14px 16px;cursor:pointer;',
      toggle: () => logic.setState({ opRights: { ...orR, [r.key]: !orR[r.key] }, opError: false }),
    }))
    if (store.opModelIds == null) {
      store.opModelIds = new Set((store.models || []).map((m) => m.id))
    }
    const opModelRows = (store.models || []).map((m) => ({
      id: m.id,
      name: m.name,
      on: store.opModelIds.has(m.id),
      cb: cbStyle(store.opModelIds.has(m.id)),
      toggle: () => {
        if (store.opModelIds.has(m.id)) store.opModelIds.delete(m.id)
        else store.opModelIds.add(m.id)
        logic.setState({ opError: false })
        logic.forceUpdate()
      },
    }))
    return {
      opRightRows,
      opModelRows,
      openNewOp: () => {
        store.opModelIds = new Set((store.models || []).map((m) => m.id))
        logic.setState({
          page: 'newOperator',
          opError: false,
          opRights: { chat: true, studio: true, models: true, keys: false, billing: false },
        })
      },
      closeNewOp: () => logic.setState({ page: 'team', opError: false }),
      saveOp: () => void saveOperator(logic, orR),
    }
  }

  async function saveOperator(logic, orR) {
    const root = document.querySelector('[data-screen-label="Новый оператор"]')
    const login = (root?.querySelector('[data-mm-op-login]')?.value || '').trim().toLowerCase()
    const password = root?.querySelector('[data-mm-op-pass]')?.value || ''
    const shareRaw = (root?.querySelector('[data-mm-op-tribute]')?.value || '').trim()
    const mask = maskFromOpRights(orR)
    if (!Object.values(orR).some(Boolean)) {
      logic.setState({ opError: true })
      logic.forceUpdate()
      return
    }
    if (login.length < 3) {
      store.error = 'Логин оператора: минимум 3 символа'
      logic.forceUpdate()
      return
    }
    if (password.length < 8) {
      store.error = 'Пароль: минимум 8 символов'
      logic.forceUpdate()
      return
    }
    let tributeSharePercent
    if (shareRaw !== '') {
      const n = Number(shareRaw)
      if (!Number.isFinite(n) || n < 0 || n > 100) {
        store.error = 'Доля Tribute: число от 0 до 100'
        logic.forceUpdate()
        return
      }
      tributeSharePercent = Math.round(n)
    }
    store.busy = true
    store.error = null
    try {
      await API.apiJson('/api/workspace/members', {
        method: 'POST',
        body: JSON.stringify({
          member_login: login,
          password,
          permissions_mask: mask,
          allowed_studio_model_ids: [...(store.opModelIds || [])],
          ...(tributeSharePercent !== undefined ? { tribute_share_percent: tributeSharePercent } : {}),
        }),
      })
      if (root?.querySelector('[data-mm-op-login]')) root.querySelector('[data-mm-op-login]').value = ''
      if (root?.querySelector('[data-mm-op-pass]')) root.querySelector('[data-mm-op-pass]').value = ''
      await loadOwnerPanels()
      logic.setState({ page: 'team', opError: false })
    } catch (e) {
      store.error = e.message || String(e)
      logic.setState({ opError: true })
    } finally {
      store.busy = false
      logic.forceUpdate()
    }
  }

  async function genFirstFrame(logic) {
    const s = logic.state
    logic.setState({ ffState: 'loading' })
    store.error = null
    try {
      const fd = new FormData()
      const modelId = store.selectedModelId
      if (modelId) fd.append('model_id', String(modelId))
      fd.append('output_aspect', store.selectedAspect || '9:16')
      fd.append('studio_wave_profile', isNsfwMode(s) ? 'nsfw' : 'regular')
      const videoFile = store.uploadFiles['motion-video']
      if (videoFile) fd.append('video', videoFile)
      const frameFile = store.uploadFiles['motion-frame']
      if (frameFile) fd.append('first_frame_image', frameFile)
      const archId = s.carouselPickId || resolveLightboxId(s)
      if (archId && !videoFile && !frameFile) fd.append('existing_generation_id', String(archId))
      const motion = (queryMotionTextarea()?.value || '').trim()
      if (motion) fd.append('description', motion)
      const accepted = await API.postStudioJob('/api/studio/motion/first-frame', fd)
      let genId = accepted.generation_id || null
      let directUrl = ''
      if (accepted.job_id) {
        const job = await API.pollStudioJob(accepted.job_id, { maxWaitMs: 10 * 60 * 1000 })
        const result = job?.result || {}
        if (result.generation_id != null) genId = result.generation_id
        directUrl = (result.generated_image_url || '').trim()
      }
      await loadArchive()
      const gen = genId != null ? store.archiveImages.find((g) => g.id === genId) : null
      store.firstFrameUrl = directUrl || archiveThumbUrl(gen) || ''
      store.firstFrameGenId = genId || null
      logic.setState({ ffState: 'done' })
      await API.apiJson('/api/auth/me').then((m) => { store.me = m })
    } catch (e) {
      store.error = e.message || String(e)
      logic.setState({ ffState: 'idle' })
    }
    logic.forceUpdate()
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

  function preferNativeShareOnMobile() {
    return /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
  }

  async function downloadArchiveUrl(url, id, isVideo) {
    const src = (url || '').trim()
    if (!src) {
      store.error = 'Файл недоступен для скачивания'
      store.logic?.forceUpdate()
      return
    }
    const defaultName = isVideo ? 'modelmate-video-' + id + '.mp4' : 'modelmate-image-' + id + '.png'
    let blob = null
    try {
      const res = await fetch(src, { credentials: 'include' })
      if (res.ok) blob = await res.blob()
    } catch (_) {}
    if (blob) {
      const file = new File([blob], defaultName, {
        type: blob.type || (isVideo ? 'video/mp4' : 'image/png'),
      })
      if (
        preferNativeShareOnMobile() &&
        typeof navigator.share === 'function' &&
        typeof navigator.canShare === 'function' &&
        navigator.canShare({ files: [file] })
      ) {
        try {
          await navigator.share({ files: [file] })
          return
        } catch (err) {
          if (err && err.name === 'AbortError') return
        }
      }
      const objectUrl = URL.createObjectURL(blob)
      try {
        const a = document.createElement('a')
        a.href = objectUrl
        a.download = defaultName
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
      } finally {
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60000)
      }
      return
    }
    window.open(src, '_blank', 'noopener,noreferrer')
  }

  async function downloadLightbox() {
    const s = store.logic?.state || {}
    const lbData = buildLightboxData(s, s.lang || 'ru')
    let url = (lbData?.url || '').trim()
    let id = lbData?.id || 0
    let isVideo = false
    if (!url && id) {
      const item =
        store.archiveImages.find((x) => x.id === id) ||
        store.archiveVideos.find((x) => x.id === id)
      if (item) {
        isVideo = item.media_kind === 'video'
        url = (isVideo ? item.video_url || item.image_url : item.image_url) || ''
      }
    } else if (id) {
      const item = store.archiveVideos.find((x) => x.id === id)
      if (item) isVideo = true
    }
    await downloadArchiveUrl(url, id, isVideo)
  }

  function bindSlotUploadZones() {
    const root = document.querySelector('[data-screen-label="Студия — Картинки"]')
    if (!root) return
    root.querySelectorAll('[data-mm-slot-upload]').forEach(resyncUploadZone)
  }

  function bindChatComposer() {
    const root = document.querySelector('[data-screen-label="Диалоги"]')
    if (!root) return
    const ta = root.querySelector('textarea[placeholder]')
    if (ta && !ta.dataset.mmReply) {
      ta.dataset.mmReply = '1'
      ta.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault()
          void sendReply()
        }
      })
    }
    const sendBtn = root.querySelector('[data-mm-chat-send]')
    if (sendBtn && !sendBtn.dataset.mmBound) {
      sendBtn.dataset.mmBound = '1'
      sendBtn.addEventListener('click', () => void sendReply())
    }
    const attachBtn = root.querySelector('[data-mm-chat-attach]')
    if (attachBtn && !attachBtn.dataset.mmBound) {
      attachBtn.dataset.mmBound = '1'
      attachBtn.addEventListener('click', () => {
        void pickLocalFile('image/*').then((file) => {
          if (file) store.pendingChatImage = file
        })
      })
    }
  }

  function bindDomActions() {
    bindAuthForm()
    document.querySelectorAll('[data-mm-upload]').forEach(resyncUploadZone)
    bindSlotUploadZones()
    bindCharPanel()
    bindChatComposer()
  }

  async function sendReply() {
    const open = store.logic?.state?.chatOpen ?? 0
    const conv = store.conversations[open]
    if (!conv) return
    const input = queryReplyInput()
    const text = (input?.value || '').trim()
    const image = store.pendingChatImage
    if (!text && !image) return
    store.busy = true
    try {
      if (image) {
        const fd = new FormData()
        if (text) fd.append('text', text)
        fd.append('image', image, image.name || 'photo.jpg')
        const res = await API.apiFetch('/api/conversations/' + conv.id + '/reply', {
          method: 'POST',
          body: fd,
        })
        const data = await API.readJson(res)
        if (!res.ok) throw new Error(API.formatDetail(data) || 'Не удалось отправить')
      } else {
        await API.apiJson('/api/conversations/' + conv.id + '/reply', {
          method: 'POST',
          body: JSON.stringify({ text }),
        })
      }
      if (input) input.value = ''
      store.pendingChatImage = null
      logicClearEmoji(store.logic)
      await loadMessages(conv.id)
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      store.logic?.forceUpdate()
    }
  }

  function logicClearEmoji(logic) {
    if (logic?.state?.emojiOpen) logic.setState({ emojiOpen: false })
  }

  async function startWorkflowScenarioJob(built) {
    const fd = new FormData()
    fd.append('graph', JSON.stringify(built.graph))
    fd.append('target_node_id', built.targetNodeId)
    return API.postStudioJob('/api/studio/workflow/execute', fd)
  }

  async function runGenerate() {
    const logic = store.logic
    if (!logic) return
    const s = logic.state || {}
    const mode = s.imgMode || 'prompt'
    const prompt = resolveStudioPrompt(mode)
    const modelId = store.selectedModelId
    const needsModel = mode === 'ref' || mode === 'swap' || mode === 'prompt'
    if (needsModel && !modelId) {
      store.error = 'Выберите персонажа'
      logic.forceUpdate()
      return
    }
    store.error = null

    if (mode === 'carousel') {
      if (!modelId) {
        store.error = 'Выберите персонажа'
        logic.forceUpdate()
        return
      }
      const { srcId, uploadFile } = resolveCarouselMasterSource(s)
      if (!srcId && !uploadFile) {
        store.error = 'Выберите кадр из архива или загрузите фото для карусели'
        logic.forceUpdate()
        return
      }
      const count = Math.max(2, Math.min(8, Number(s.carouselCount) || 4))
      const model = store.models.find((m) => m.id === modelId)
      const tempIds = []
      for (let i = 0; i < count; i++) {
        const { item, tempId } = createOptimisticArchiveItem({
          mediaKind: 'image',
          promptExcerpt: prompt || `Карусель ${i + 1}/${count}…`,
          studioModelId: modelId,
          modelName: model?.name ?? null,
          outputAspect: store.selectedAspect,
        })
        store.archiveImages = prependOptimisticArchive(store.archiveImages, item)
        tempIds.push(tempId)
      }
      logic.forceUpdate()
      scheduleArchivePoll()
      try {
        const fd = new FormData()
        fd.append('model_id', String(modelId))
        fd.append('count', String(count))
        fd.append('description', prompt)
        fd.append('output_aspect', store.selectedAspect)
        fd.append('studio_wave_profile', isNsfwMode(s) ? 'nsfw' : 'regular')
        const wave = normalizeWaveModel(waveModelFromState(s), isNsfwMode(s))
        fd.append('workflow_wave_model', wave.apiId)
        if (wave.apiId === 'wan-2.7') fd.append('wan_edit_tier', wave.tier)
        if (srcId) fd.append('existing_generation_id', String(srcId))
        else if (uploadFile) fd.append('image', uploadFile, uploadFile.name || 'carousel.jpg')
        const accepted = await API.postStudioJob('/api/studio/carousel', fd)
        await API.pollStudioJob(accepted.job_id, {
          maxWaitMs: Math.max(8 * 60 * 1000, count * 4 * 60 * 1000),
        })
        for (const tid of tempIds) {
          store.archiveImages = removeOptimisticArchive(store.archiveImages, tid)
        }
        await refreshArchiveImages()
        scheduleArchivePoll()
        await API.apiJson('/api/auth/me').then((m) => {
          store.me = m
        })
      } catch (e) {
        for (const tid of tempIds) {
          store.archiveImages = removeOptimisticArchive(store.archiveImages, tid)
        }
        store.error = e.message || String(e)
      } finally {
        logic.forceUpdate()
      }
      return
    }

    const model = needsModel ? store.models.find((m) => m.id === modelId) : null
    const { item: optimistic, tempId } = createOptimisticArchiveItem({
      mediaKind: 'image',
      promptExcerpt: prompt || 'Генерация…',
      studioModelId: modelId || null,
      modelName: model?.name ?? null,
      outputAspect: store.selectedAspect,
    })
    store.archiveImages = prependOptimisticArchive(store.archiveImages, optimistic)
    logic.forceUpdate()
    scheduleArchivePoll()

    try {
      const scenarios = window.MMOS_STUDIO_SCENARIOS
      if (!scenarios || typeof scenarios.buildGraphForMode !== 'function') {
        throw new Error('Workflow-сценарии не загружены')
      }
      const built = await scenarios.buildGraphForMode(mode, {
        API,
        store,
        archiveThumbUrl,
        s,
        modelId,
        userPrompt: prompt,
        helpers: {
          normalizeWaveModel,
          waveModelFromState,
          isNsfwMode,
          slotStateKey,
        },
      })
      if (!built) throw new Error('Неизвестный режим генерации')
      const accepted = await startWorkflowScenarioJob(built)
      const realId = typeof accepted.generation_id === 'number' ? accepted.generation_id : null
      if (realId) {
        store.archiveImages = replaceOptimisticArchiveId(store.archiveImages, tempId, realId, {
          status: 'processing',
          job_id: accepted.job_id ?? null,
        })
      } else {
        store.archiveImages = removeOptimisticArchive(store.archiveImages, tempId)
      }
      scheduleArchivePoll()
      void API.apiJson('/api/auth/me').then((m) => {
        store.me = m
        logic.forceUpdate()
      })
    } catch (e) {
      store.archiveImages = removeOptimisticArchive(store.archiveImages, tempId)
      store.error = e.message || String(e)
    } finally {
      logic.forceUpdate()
    }
  }

  async function runGenerateVideo() {
    if (store.busy) return
    const s = store.logic?.state || {}
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
      if (store.videoResolution) {
        const vr = String(store.videoResolution)
        fd.append('video_resolution', vr === '4K' || vr === '4k' ? '1080p' : vr)
      }
      if (store.videoDuration) fd.append('duration_seconds', String(store.videoDuration))
      if (store.motionVideoFileId) fd.append('motion_video_file_id', store.motionVideoFileId)
      const frameFile = store.uploadFiles['motion-frame']
      if (frameFile) fd.append('image', frameFile)
      const archId = s.carouselPickId || resolveLightboxId(s)
      if (archId && !frameFile) fd.append('existing_generation_id', String(archId))
      if (store.firstFrameGenId && !frameFile && !archId) fd.append('existing_generation_id', String(store.firstFrameGenId))
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
    return (store.donations || []).map((d) => {
      const urls = []
      if (d.telegram_link) {
        urls.push({
          kind: 'Telegram',
          icon: ICO_TG,
          col: '#38BDF8',
          url: d.telegram_link,
          copy: (e) => {
            e?.stopPropagation?.()
            void copyText(d.telegram_link)
          },
        })
      }
      if (d.web_link) {
        urls.push({
          kind: 'Web',
          icon: ICO_GLOBE,
          col: '#C084FC',
          url: d.web_link,
          copy: (e) => {
            e?.stopPropagation?.()
            void copyText(d.web_link)
          },
        })
      }
      if (!urls.length && d.public_url) {
        urls.push({
          kind: 'Link',
          icon: ICO_GLOBE,
          col: '#9BA0A6',
          url: d.public_url,
          copy: (e) => {
            e?.stopPropagation?.()
            void copyText(d.public_url)
          },
        })
      }
      return {
        title: d.title || '—',
        st: (d.status || '—').toUpperCase(),
        stStyle: statusStyle(d.status),
        urls,
      }
    })
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
      const st = chatStatusType(c)
      const blockedTag =
        st === 'blocked' ? vals.t.dlgBlocked : st === 'deleted' ? vals.t.dlgDeleted : false
      const blockedTagStyle =
        'font-family:JetBrains Mono;font-size:7.5px;letter-spacing:.4px;padding:1px 6px;border-radius:4px;' +
        (st === 'blocked'
          ? 'background:rgba(248,113,113,.15);color:#F87171;'
          : 'background:rgba(255,255,255,.08);color:#9BA0A6;')
      return {
        ...d,
        avStyle: st ? d.avStyleLg + 'filter:grayscale(1);opacity:.6;' : d.avStyleLg,
        blockedTag,
        blockedTagStyle,
        nameStyle: 'font-weight:700;font-size:12.5px;' + (st ? 'color:#9BA0A6;' : ''),
        canDelete: !!st,
        delDialog: (e) => {
          e?.stopPropagation?.()
          void deleteConversation(c.id, logic)
        },
        rowStyle:
          'display:flex;gap:10px;align-items:center;padding:9px 8px;border-radius:12px;cursor:pointer;position:relative;' +
          (s.chatOpen === i
            ? 'background:rgba(215,244,82,.07);border:1px solid rgba(215,244,82,.2);'
            : 'border:1px solid transparent;'),
      }
    })

    const bubbleIn =
      'max-width:80%;background:#1A1C20;border:1px solid rgba(255,255,255,.07);border-radius:14px 14px 14px 4px;padding:10px 13px;position:relative;'
    const bubbleOut =
      'max-width:80%;background:rgba(215,244,82,.09);border:1px solid rgba(215,244,82,.2);border-radius:14px 14px 4px 14px;padding:10px 13px;position:relative;'
    const reactChoices = ['❤️', '😍', '😂', '🔥', '👍', '😢']
    const reactions = s.reactions || {}
    const messages = store.messages.map((m, i) => {
      const outbound = m.direction === 'outbound'
      const rx = reactions[i]
      return {
        wrap:
          'display:flex;flex-direction:column;gap:3px;' +
          (outbound ? 'align-items:flex-end;' : 'align-items:flex-start;'),
        bubble: outbound ? bubbleOut : bubbleIn,
        text: m.text_original || '',
        tr: m.text_translated && m.text_translated !== m.text_original ? m.text_translated : false,
        time: fmtDateShort(m.created_at) + ' · ' + fmtTime(m.created_at),
        toggleReact: (e) => {
          e?.stopPropagation?.()
          logic.setState({ msgReact: s.msgReact === i ? null : i, emojiOpen: false })
        },
        reactOpen: s.msgReact === i,
        reactRow: reactChoices.map((rc) => ({
          e: rc,
          pick: (ev) => {
            ev?.stopPropagation?.()
            logic.setState({ reactions: { ...reactions, [i]: rc }, msgReact: null })
          },
        })),
        reaction: rx || false,
        reactBadgeStyle:
          'align-self:' +
          (outbound ? 'flex-end' : 'flex-start') +
          ';background:#0D0E11;border:1px solid rgba(255,255,255,.12);border-radius:20px;padding:1px 7px;font-size:12px;margin-top:-8px;',
      }
    })

    const tagBase =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1.2px;padding:2px 7px;border-radius:5px;"
    const notes = store.notes.map((n) => ({
      tag: (n.kind || 'NOTE').toUpperCase(),
      tagStyle: tagBase + 'background:rgba(215,244,82,.15);color:#D7F452;',
      when: fmtDateShort(n.updated_at || n.created_at),
      text: n.content || '',
    }))

    const archiveFrames = store.archiveImages.map((item, i) =>
      archiveToFrame(item, i, logic, vals),
    )
    const thumbPickBase =
      'aspect-ratio:9/16;border-radius:8px;cursor:pointer;border:2px solid transparent;background:'
    const recentFrames = store.archiveImages.slice(0, 4).map((item, i) => {
      const url = archiveThumbUrl(item)
      const picked = s.carouselPickId === item.id
      const bgCore = url
        ? 'center/cover no-repeat url("' + url.replace(/"/g, '') + '"),' + G[i % 6]
        : G[i % 6]
      return {
        id: item.id,
        label: (item.model_name || '—') + ' · ' + (item.output_aspect || '9:16'),
        thumbStyle:
          thumbPickBase +
          bgCore +
          ';' +
          (picked ? 'border-color:#D7F452;' : ''),
        pick: () => {
          if (!item.id || isArchivePending(item)) return
          clearCarouselLocalUploads()
          store.slotArchivePicks[slotStateKey('carousel', 0)] = item.id
          logic.setState({ carouselPickId: item.id, carSource: 'archive' })
        },
      }
    })
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
    const avBase36 =
      'width:36px;height:36px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px;position:relative;background:'
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
    const curSt = activeConv ? chatStatusType(activeConv) : false
    const threadHead = activeConv
      ? {
          name: activeChat.name,
          initial: activeChat.initial,
          avStyle: avBase36 + activeChat.avStyle,
          vip: activeChat.vip,
          platform: activeChat.platform === 'FANVUE' ? 'Fanvue' : 'Telegram',
          persona: activeChat.persona,
          replyLang: replyLangLabel(activeConv.outbound_lang || activeConv.user_lang),
          blocked: curSt === 'blocked',
          deleted: curSt === 'deleted',
          blockedText: curSt === 'blocked' ? vals.t.dlgBlocked : vals.t.dlgDeleted,
        }
      : {
          name: '—',
          initial: '?',
          avStyle: avBase36 + AV_G[0],
          vip: false,
          platform: '—',
          persona: '—',
          replyLang: '—',
          blocked: false,
          deleted: false,
          blockedText: '',
        }

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
    const charPhotos = activeChar ? mapCharPhotos(activeChar, lang, logic) : []
    const photoTagList = mapPhotoTagList(lang, logic)
    const photoTagMenu = mapPhotoTagMenu(lang, logic)
    const charHistory = charId ? mapCharHistory(charId, lang) : vals.charHistory || []
    const operator = mapOperatorForm(logic, lang, vals)
    const lightboxData = buildLightboxData(s, lang)
    const imgErrList = s.showGenError ? validateImageGen(logic, vals) : []
    const ffUrl = store.firstFrameUrl || ''
    const ffThumb = buildFfThumbStyles(ffUrl)
    const ffModel = store.models.find((m) => m.id === store.selectedModelId)
    const ffThumbLabel = (ffModel?.name || '—') + ' · ' + (store.selectedAspect || '9:16')

    const isMobile = !!s.isMobile
    const isNarrow = !isMobile && typeof window !== 'undefined' && window.innerWidth < 1120
    const showThread = !isMobile || !!s.mobileChat
    const showList = !isMobile || !s.mobileChat
    const isMobileChat = isMobile && !!s.mobileChat
    const curMode = mapCurMode(logic, vals)
    const emojiChoices = ['😊', '😍', '🥰', '😘', '💕', '🔥', '😂', '😅', '🙈', '😉', '💋', '🌹', '✨', '👀', '🥂', '💫']
    const emojiPick = emojiChoices.map((em) => ({
      e: em,
      pick: () => {
        const input = queryReplyInput()
        if (input) {
          input.value = (input.value || '') + em
          input.dispatchEvent(new Event('input', { bubbles: true }))
        }
        logic.setState({ emojiOpen: false })
      },
    }))

    logic._lastT = vals.t

    const imgModes = (vals.imgModes || []).map((im) => ({
      ...im,
      ...(im.id === 'carousel' ? { cost: fmtCarouselModeCardCost(lang) } : {}),
      pick: () => {
        logic.setState({ imgMode: im.id, showGenError: false })
        logic.forceUpdate()
        queueMicrotask(() => bindDomActions())
      },
    }))

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
      threadHead,
      notesTitle: vals.t.fanNotes + (activeChat.name !== '—' ? ' · ' + activeChat.name : ''),
      activeCharName,
      activeCharInitial,
      charPhotos,
      photoTagList,
      photoTagOpts: photoTagList,
      photoTagMenu,
      charHistory,
      showGenError: !!s.showGenError,
      imgErrList,
      triggerGen: () => {
        const errs = validateImageGen(logic, vals)
        if (errs.length) {
          logic.setState({ showGenError: true })
        } else {
          logic.setState({ showGenError: false })
          void runGenerate()
        }
        logic.forceUpdate()
      },
      genFieldErr: (need) =>
        s.showGenError && need ? 'border:1px solid #F87171;border-radius:12px;padding:2px;' : '',
      ffState: s.ffState || 'idle',
      ffIdle: (s.ffState || 'idle') === 'idle',
      ffLoading: s.ffState === 'loading',
      ffDone: s.ffState === 'done',
      genFirstFrame: () => void genFirstFrame(logic),
      ffImgStyleLoading: ffThumb.loading,
      ffImgStyleDone: ffThumb.done,
      ffThumbLabel,
      lightboxData,
      curMode,
      imgModes,
      emojiPick,
      emojiOpen: s.emojiOpen,
      toggleEmoji: () => logic.setState({ emojiOpen: !s.emojiOpen, msgReact: null }),
      backToList: () => logic.setState({ mobileChat: false, msgReact: null, emojiOpen: false }),
      closePops: () => {
        if (s.msgReact !== null || s.emojiOpen) logic.setState({ msgReact: null, emojiOpen: false })
      },
      scrollDown: () => {
        const el = document.getElementById('mm-thread-scroll')
        if (el) el.scrollTop = el.scrollHeight
      },
      showThread,
      showList,
      isMobileChat,
      showNotes: !isMobile && !isNarrow,
      dialogsGrid: isMobile
        ? 'display:flex;flex-direction:column;gap:12px;flex:1;min-height:0;'
        : isNarrow
          ? 'display:grid;grid-template-columns:270px 1fr;gap:12px;flex:1;min-height:420px;'
          : 'display:grid;grid-template-columns:290px 1fr 270px;gap:12px;flex:1;min-height:420px;',
      makeCarousel: () => {
        const id = resolveLightboxId(s)
        if (id) {
          store.slotArchivePicks[slotStateKey('carousel', 0)] = id
          clearCarouselLocalUploads()
        }
        logic.setState({
          page: 'images',
          imgMode: 'carousel',
          lightbox: null,
          slotSource: { ...(s.slotSource || {}), 'carousel:0': id ? 'archive' : 'upload' },
        })
      },
      isCarousel: s.imgMode === 'carousel',
      isStdImg: s.imgMode !== 'carousel',
      carCount: s.carouselCount,
      carCountChips: [2, 3, 4, 6, 8].map((n) => ({
        label: String(n),
        pick: () => logic.setState({ carouselCount: n }),
        style:
          (Number(s.carouselCount) === n ? chipOn : chipOff) +
          'min-width:40px;text-align:center;',
      })),
      carSrcArchiveStyle:
        'flex:1;text-align:center;font-size:12px;font-weight:700;border-radius:8px;padding:9px 12px;cursor:pointer;' +
        (s.carSource !== 'upload'
          ? 'background:rgba(215,244,82,.12);color:#D7F452;border:1px solid rgba(215,244,82,.4);'
          : 'color:#9BA0A6;border:1px solid transparent;'),
      carSrcUploadStyle:
        'flex:1;text-align:center;font-size:12px;font-weight:700;border-radius:8px;padding:9px 12px;cursor:pointer;' +
        (s.carSource === 'upload'
          ? 'background:rgba(215,244,82,.12);color:#D7F452;border:1px solid rgba(215,244,82,.4);'
          : 'color:#9BA0A6;border:1px solid transparent;'),
      setCarArchive: () => {
        delete store.uploadFiles.carousel
        delete store.uploadFiles.ref
        clearCarouselUploadDom()
        logic.setState({ carSource: 'archive' })
      },
      setCarUpload: () => logic.setState({ carSource: 'upload', carouselPickId: null }),
      showCarArchive: s.carSource !== 'upload',
      showCarUpload: s.carSource === 'upload',
      opRightRows: operator.opRightRows,
      opModelRows: operator.opModelRows,
      opError: !!s.opError,
      openNewOp: operator.openNewOp,
      saveOp: operator.saveOp,
      closeNewOp: operator.closeNewOp,
      apiError: store.error,
      apiBusy: store.busy,
      runGenerate: () => void runGenerate(),
      runGenerateVideo: () => void runGenerateVideo(),
      sendReply: () => void sendReply(),
      logout: () => {
        API.setToken(null)
        store.authed = false
        store.me = null
        store.error = null
        setAuthTab('login')
        showAuth(true)
        logic.forceUpdate()
      },
      canChat: isOwner || API.hasPerm(mask, API.PERM.CHAT),
      canStudio: isOwner || API.hasPerm(mask, API.PERM.STUDIO_GENERATE),
      canBilling: isOwner || API.hasPerm(mask, API.PERM.BILLING),
      hasLightbox: lightboxData != null,
      closeLightbox: () => logic.setState({ lightbox: null }),
      downloadLightbox: () => void downloadLightbox(),
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
      if (hasPendingArchive()) scheduleArchivePoll()
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
    register,
    logout: () => API.setToken(null),
    runGenerate,
    runGenerateVideo,
    sendReply,
  }
})(window)
