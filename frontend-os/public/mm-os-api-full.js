/**
 * Полная привязка оставшихся разделов кабинета к API.
 * Расширяет MMOS_BRIDGE без изменения макета.
 */
;(function (global) {
  const API = global.MMOS_API
  const bridge = global.MMOS_BRIDGE
  if (!API || !bridge) return

  const store = bridge.store
  const G = [
    'linear-gradient(160deg,#3B2A4F,#1A1428)',
    'linear-gradient(160deg,#4F2A3E,#241019)',
    'linear-gradient(160deg,#2A3E4F,#101A24)',
    'linear-gradient(160deg,#2A4F3B,#0F241A)',
    'linear-gradient(160deg,#4F3E2A,#241C10)',
    'linear-gradient(160deg,#33265C,#150F28)',
  ]

  if (store.chatFilter == null) store.chatFilter = 'all'
  if (store.videoResolution == null) store.videoResolution = '720p'
  if (store.videoDuration == null) store.videoDuration = 5

  function fmtMoney(minor, currency) {
    const c = (currency || 'RUB').toUpperCase()
    const rub = (Number(minor) || 0) / 100
    if (c === 'RUB') return rub.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' ₽'
    return rub.toFixed(2) + ' ' + c
  }

  function fmtToday(lang) {
    const d = new Date()
    const days = lang === 'ru'
      ? ['ВС', 'ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ']
      : ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
    const months = lang === 'ru'
      ? ['ЯНВАРЯ', 'ФЕВРАЛЯ', 'МАРТА', 'АПРЕЛЯ', 'МАЯ', 'ИЮНЯ', 'ИЮЛЯ', 'АВГУСТА', 'СЕНТЯБРЯ', 'ОКТЯБРЯ', 'НОЯБРЯ', 'ДЕКАБРЯ']
      : ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER']
    return days[d.getDay()] + ' · ' + d.getDate() + ' ' + months[d.getMonth()] + ' ' + d.getFullYear()
  }

  function mapVideoChips(logic) {
    const chipOn =
      "font-family:'JetBrains Mono';font-size:11px;background:rgba(215,244,82,.12);color:#D7F452;border:1px solid rgba(215,244,82,.4);padding:5px 14px;border-radius:8px;cursor:pointer;"
    const chipOff =
      "font-family:'JetBrains Mono';font-size:11px;border:1px solid rgba(255,255,255,.12);color:#9BA0A6;padding:5px 14px;border-radius:8px;cursor:pointer;"
    const mk = (key, storeKey, options) =>
      options.map((o) => ({
        label: o,
        style: store[storeKey] === o ? chipOn : chipOff,
        pick: () => {
          store[storeKey] = o
          logic.forceUpdate()
        },
      }))
    return {
      videoQualityChips: mk('res', 'videoResolution', ['480p', '720p', '1080p']),
      videoDurationChips: mk('dur', 'videoDuration', [5, 10, 15]).map((x) => ({
        ...x,
        label: x.label + 's',
      })),
      videoRatioChips: mk('ratio', 'selectedAspect', ['9:16', '16:9', '1:1']),
    }
  }

  function filterConversationsBySearch(convs) {
    const q = (store.chatSearch || '').trim().toLowerCase()
    if (!q) return convs
    return convs.filter((c) => {
      const name = (c.user_display_name || c.external_chat_id || '').toLowerCase()
      const prev = (c.last_message_preview || '').toLowerCase()
      return name.includes(q) || prev.includes(q)
    })
  }

  function filterConversations(convs) {
    const f = store.chatFilter || 'all'
    let list = convs
    if (f === 'vip') list = list.filter((c) => c.manual_category === 'vip')
    else if (f === 'stale') list = list.filter((c) => c.is_no_response)
    else if (f === 'new') list = list.filter((c) => (c.unread_count || 0) > 0)
    return filterConversationsBySearch(list)
  }

  function mapConnections(vals, logic, lang) {
    const ig = store.integrations
    const base = vals.connections || []
    if (!ig) return base
    const stActive =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;padding:2px 8px;border-radius:20px;background:rgba(74,222,128,.12);color:#4ADE80;border:1px solid rgba(74,222,128,.3);"
    const stWarn =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;padding:2px 8px;border-radius:20px;background:rgba(251,146,60,.12);color:#FB923C;border:1px solid rgba(251,146,60,.3);"
    const stDim =
      "font-family:'JetBrains Mono';font-size:8.5px;letter-spacing:1px;padding:2px 8px;border-radius:20px;background:rgba(255,255,255,.06);color:#9BA0A6;border:1px solid rgba(255,255,255,.1);"
    const tgN = (ig.telegram_connections || []).length
    const fvN = (ig.fanvue_connections || []).length
    const trN = (ig.tribute_connections || []).length
    const status = {
      tg: { st: tgN ? (lang === 'ru' ? tgN + ' БОТА' : tgN + ' BOTS') : lang === 'ru' ? 'НЕ НАСТРОЕН' : 'NOT SET', stStyle: tgN ? stActive : stWarn },
      wavespeed: {
        st: ig.wavespeed_configured
          ? ig.wavespeed_managed_by_platform
            ? lang === 'ru' ? 'КЛЮЧ ПЛАТФОРМЫ' : 'PLATFORM KEY'
            : lang === 'ru' ? 'СВОЙ КЛЮЧ' : 'OWN KEY'
          : lang === 'ru' ? 'НЕ НАСТРОЕН' : 'NOT SET',
        stStyle: ig.wavespeed_configured ? stActive : stWarn,
      },
      fanvue: { st: fvN ? (lang === 'ru' ? 'ПОДКЛЮЧЁН' : 'CONNECTED') : lang === 'ru' ? 'НЕ НАСТРОЕН' : 'NOT SET', stStyle: fvN ? stActive : stWarn },
      tribute: { st: trN || ig.tribute_configured ? (lang === 'ru' ? 'НАСТРОЕН' : 'SET') : lang === 'ru' ? 'НЕ НАСТРОЕН' : 'NOT SET', stStyle: trN || ig.tribute_configured ? stActive : stWarn },
      ig: { st: lang === 'ru' ? 'В РАЗРАБОТКЕ' : 'COMING SOON', stStyle: stDim },
      push: { st: typeof Notification !== 'undefined' && Notification.permission === 'granted' ? (lang === 'ru' ? 'ВКЛЮЧЕНЫ' : 'ON') : (lang === 'ru' ? 'ВЫКЛ' : 'OFF'), stStyle: stDim },
    }
    return base.map((c) => {
      const s = status[c.id] || { st: c.st, stStyle: c.stStyle }
      return {
        ...c,
        st: s.st,
        stStyle: s.stStyle + 'display:inline-block;margin-top:3px;',
        open: () => logic.setState({ connDetail: c.id }),
      }
    })
  }

  function mapBilling(vals, lang, me) {
    const fillBase = 'height:100%;background:#4ADE80;border-radius:3px;'
    const pct = (used, max) => (max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0)
    const ops = store.members?.length || 0
    const maxOps = me?.max_operators || me?.plan_max_operators || 10
    const chars = store.models?.length || 0
    const maxChars = me?.max_studio_models || me?.plan_max_studio_models || 10
    const dialogs = store.conversations?.length || 0
    const usageBars = [
      { label: lang === 'ru' ? 'Операторы' : 'Operators', val: ops + ' / ' + maxOps, fill: fillBase + 'width:' + pct(ops, maxOps) + '%;' },
      { label: lang === 'ru' ? 'Персонажи' : 'Characters', val: chars + ' / ' + maxChars, fill: fillBase + 'width:' + pct(chars, maxChars) + '%;' },
      { label: lang === 'ru' ? 'Диалоги' : 'Dialogs', val: String(dialogs), fill: fillBase + 'width:' + Math.min(100, dialogs * 5) + '%;' },
    ]
    const items = store.billingPlans?.items || []
    const creditItems = items.filter((x) => x.credits_pricing)
    const packs = creditItems.slice(0, 4).map((x) => {
      const cp = x.credits_pricing
      const qty = cp?.bulk_from || 100
      const unit = cp?.unit_price_rub || 0
      const bulk = cp?.bulk_unit_price_rub || unit
      const price = Math.round(qty * bulk)
      return {
        cr: String(qty),
        price: price.toLocaleString('ru-RU') + ' ₽',
        bonus: qty >= 600 ? '+15%' : qty >= 300 ? '+10%' : qty >= 150 ? '+5%' : false,
        product: x.product,
        creditsQty: qty,
        pick: () => { store.selectedCreditPack = x.product; payYookassa('credits_pack', qty) },
      }
    })
    const tier = bridge.store.logic?.state?.tier || 'standard'
    const catalog = store.billingPlans?.catalog || {}
    const subPlans = (catalog.subscription_plans || catalog.plans || items).filter?.((x) => x && (x.product || x.name)) || items
    const plans = (Array.isArray(subPlans) ? subPlans : items)
      .filter((x) => !x.credits_pricing)
      .slice(0, 3)
      .map((p, i) => ({
        name: p.title || p.name || p.product,
        price: String(p.price_rub || p.price || '—'),
        tag: i === 1,
        desc: p.description || p.desc || '',
        product: p.product,
        cardStyle: 'background:#121316;border:1px solid ' + (i === 1 ? 'rgba(215,244,82,.35)' : 'rgba(255,255,255,.07)') + ';border-radius:16px;padding:16px 18px;',
        pick: () => { store.selectedPlanProduct = p.product; bridge.store.logic?.forceUpdate() },
        payCard: () => payYookassa(p.product),
        payCredits: () => subscribeWithCredits(p.product),
        payTribute: () => payTributeCheckout(p.product),
      }))
    const ref = store.referral
    const referralLink = ref?.referral_link || '—'
    const referralStats = ref
      ? (lang === 'ru' ? 'Приглашено: ' : 'Invited: ') + (ref.invited_count || 0) + ' · ' + (ref.credits_earned || 0) + ' кр.'
      : '—'
    return { usageBars, plans: plans.length ? plans : vals.plans, packs: packs.length ? packs : vals.packs, referralLink, referralStats, tier }
  }

  function mapRatioChips(logic) {
    const chipOn =
      "font-family:'JetBrains Mono';font-size:11px;background:rgba(215,244,82,.12);color:#D7F452;border:1px solid rgba(215,244,82,.4);padding:5px 14px;border-radius:8px;cursor:pointer;"
    const chipOff =
      "font-family:'JetBrains Mono';font-size:11px;border:1px solid rgba(255,255,255,.12);color:#9BA0A6;padding:5px 14px;border-radius:8px;cursor:pointer;"
    return ['9:16', '16:9', '1:1', '4:3', '3:4'].map((r) => ({
      label: r,
      style: store.selectedAspect === r ? chipOn : chipOff,
      pick: () => {
        store.selectedAspect = r
        logic.forceUpdate()
      },
    }))
  }

  function mapChatFilters(convs, logic, lang, chipOn, chipOff) {
    const f = store.chatFilter || 'all'
    const mk = (id, label, count) => ({
      id,
      label: label + (count != null ? ' · ' + count : ''),
      style: f === id ? chipOn : chipOff,
      pick: () => {
        store.chatFilter = id
        logic.forceUpdate()
      },
    })
    return [
      mk('all', lang === 'ru' ? 'Все' : 'All', convs.length),
      mk('vip', 'VIP', convs.filter((c) => c.manual_category === 'vip').length),
      mk('stale', '24ч+', convs.filter((c) => c.is_no_response).length),
      mk('new', lang === 'ru' ? 'Новые' : 'New', convs.filter((c) => (c.unread_count || 0) > 0).length),
    ]
  }

  function platformCounts(convs) {
    const counts = {}
    for (const c of convs) {
      const p = (c.platform || 'other').toLowerCase()
      counts[p] = (counts[p] || 0) + 1
    }
    return Object.entries(counts)
      .map(([p, n]) => p.toUpperCase() + ' ' + n)
      .join(' · ')
  }

  function updateApiStatusBar() {
    let el = document.getElementById('mm-os-api-status')
    if (!el) {
      el = document.createElement('div')
      el.id = 'mm-os-api-status'
      el.className = 'mm-os-api-status'
      document.body.appendChild(el)
    }
    if (store.busy) {
      el.textContent = 'Загрузка…'
      el.style.display = 'block'
      el.className = 'mm-os-api-status mm-os-api-status--busy'
    } else if (store.error) {
      el.textContent = store.error
      el.style.display = 'block'
      el.className = 'mm-os-api-status mm-os-api-status--err'
    } else {
      el.style.display = 'none'
    }
  }

  function fillModelSelect(sel) {
    if (!sel || sel.dataset.mmFilled) return
    sel.dataset.mmFilled = '1'
    const cur = sel.value
    sel.innerHTML = ''
    const empty = document.createElement('option')
    empty.value = ''
    empty.textContent = 'Не назначена'
    sel.appendChild(empty)
    for (const m of store.models || []) {
      const o = document.createElement('option')
      o.value = String(m.id)
      o.textContent = m.name
      sel.appendChild(o)
    }
    if (cur) sel.value = cur
  }

  async function saveWavespeedKey() {
    const root = document.querySelector('[data-screen-label="Подключения"]')
    const inp = root?.querySelector('[data-mm-conn-wavespeed-key]')
    const key = (inp?.value || '').trim()
    if (!key) { store.error = 'Введите API-ключ WaveSpeed'; return }
    store.busy = true
    try {
      await API.apiJson('/api/integrations/wavespeed', { method: 'PUT', body: JSON.stringify({ api_key: key }) })
      if (inp) inp.value = ''
      await bridge.refreshAll()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function addTelegramBot() {
    const root = document.querySelector('[data-screen-label="Подключения"]')
    const token = (root?.querySelector('[data-mm-conn-tg-token]')?.value || '').trim()
    const modelId = root?.querySelector('[data-mm-conn-tg-model]')?.value || ''
    if (!token) { store.error = 'Введите токен бота'; return }
    store.busy = true
    try {
      const body = { bot_token: token }
      if (modelId) body.studio_model_id = Number(modelId)
      await API.apiJson('/api/integrations/telegram', { method: 'PUT', body: JSON.stringify(body) })
      const inp = root?.querySelector('[data-mm-conn-tg-token]')
      if (inp) inp.value = ''
      await bridge.refreshAll()
      renderIntegrationPanels()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function startFanvueOAuth() {
    const root = document.querySelector('[data-screen-label="Подключения"]')
    const modelId = root?.querySelector('[data-mm-conn-fv-model]')?.value || ''
    store.busy = true
    try {
      const body = {}
      if (modelId) body.studio_model_id = Number(modelId)
      const data = await API.apiJson('/api/integrations/fanvue/oauth/start', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      const url = data.authorize_url || data.url
      if (url) window.location.href = url
      else store.error = 'OAuth URL не получен'
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function saveTributeKey() {
    const root = document.querySelector('[data-screen-label="Подключения"]')
    const key = (root?.querySelector('[data-mm-conn-tribute-key]')?.value || '').trim()
    const label = (root?.querySelector('[data-mm-conn-tribute-label]')?.value || '').trim()
    const modelId = root?.querySelector('[data-mm-conn-tribute-model]')?.value || ''
    if (!key) { store.error = 'Введите Tribute API ключ'; return }
    store.busy = true
    try {
      const body = { api_key: key }
      if (label) body.label = label
      if (modelId) body.studio_model_id = Number(modelId)
      await API.apiJson('/api/integrations/tribute', { method: 'PUT', body: JSON.stringify(body) })
      const inp = root?.querySelector('[data-mm-conn-tribute-key]')
      if (inp) inp.value = ''
      await bridge.refreshAll()
      renderIntegrationPanels()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function payTributeCheckout(product, creditsQuantity) {
    if (!product) return
    store.busy = true
    try {
      const body =
        product === 'credits_pack'
          ? { product, credits_quantity: creditsQuantity }
          : { product }
      const data = await API.apiJson('/api/billing/tribute/checkout', { method: 'POST', body: JSON.stringify(body) })
      if (data.payment_url) window.location.href = data.payment_url
      else if (data.telegram_deep_link) window.location.href = data.telegram_deep_link
      else store.error = 'Не получена ссылка Tribute'
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function subscribeWithCredits(product) {
    if (!product) return
    store.busy = true
    try {
      await API.apiJson('/api/billing/subscribe-with-credits', { method: 'POST', body: JSON.stringify({ product }) })
      await bridge.refreshAll()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function payYookassa(product, creditsQuantity) {
    if (!product) return
    store.busy = true
    try {
      const body =
        product === 'credits_pack'
          ? { product, credits_quantity: creditsQuantity }
          : { product }
      const data = await API.apiJson('/api/billing/yookassa/payment', { method: 'POST', body: JSON.stringify(body) })
      if (data.confirmation_url) window.location.href = data.confirmation_url
      else store.error = 'Не получена ссылка на оплату'
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function savePayoutSettings() {
    const root = document.querySelector('[data-screen-label="Донаты"]')
    const wallet = (root?.querySelector('[data-mm-don-wallet]')?.value || '').trim()
    const asset = root?.querySelector('[data-mm-don-payout-asset]')?.value || 'USDT_TRC20'
    if (!wallet) { store.error = 'Укажите кошелёк для выплат'; return }
    store.busy = true
    try {
      await API.apiJson('/api/creator-donations/payout-settings', {
        method: 'PUT',
        body: JSON.stringify({ wallet_address: wallet, payout_asset: asset }),
      })
      await bridge.refreshAll()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function requestPayout() {
    const root = document.querySelector('[data-screen-label="Донаты"]')
    const wallet = (root?.querySelector('[data-mm-don-wallet]')?.value || '').trim()
    if (wallet) {
      const asset = root?.querySelector('[data-mm-don-payout-asset]')?.value || 'USDT_TRC20'
      store.busy = true
      try {
        await API.apiJson('/api/creator-donations/payout-settings', {
          method: 'PUT',
          body: JSON.stringify({ wallet_address: wallet, payout_asset: asset }),
        })
        store.payoutSettings = { wallet_address: wallet, payout_asset: asset }
      } catch (e) {
        store.error = e.message || String(e)
        store.busy = false
        bridge.store.logic?.forceUpdate()
        return
      }
      store.busy = false
    }
    const avail = store.donationOverview?.pending_payout_by_currency?.RUB ?? 0
    if (!store.payoutSettings?.wallet_address) {
      store.error = 'Сначала сохраните настройки выплат'
      bridge.store.logic?.forceUpdate()
      return
    }
    if (!window.confirm('Запросить выплату ' + fmtMoney(avail, 'RUB') + '?')) return
    store.busy = true
    try {
      await API.apiJson('/api/creator-donations/payout-requests', {
        method: 'POST',
        body: JSON.stringify({ source_currency: 'RUB' }),
      })
      await bridge.refreshAll()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function copyText(text) {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
    } catch (e) {
      store.error = 'Не удалось скопировать'
    }
  }

  function modelName(id) {
    const m = (store.models || []).find((x) => x.id === id)
    return m?.name || '—'
  }

  function buildCurConfig(connId, ig, lang) {
    if (!ig) return []
    if (connId === 'tg') {
      const bots = ig.telegram_connections || []
      if (!bots.length) return []
      const c = bots[0]
      return [
        [lang === 'ru' ? 'Бот' : 'Bot', c.bot_username ? '@' + c.bot_username : '—'],
        [
          lang === 'ru' ? 'Вебхук' : 'Webhook',
          c.webhook_registered ? (lang === 'ru' ? 'активен' : 'active') : lang === 'ru' ? 'не настроен' : 'not set',
        ],
        [lang === 'ru' ? 'Персонаж' : 'Character', modelName(c.studio_model_id)],
        [
          'AI',
          c.companion_mode && c.companion_mode !== 'off' ? c.companion_mode : lang === 'ru' ? 'выключен' : 'off',
        ],
        [
          lang === 'ru' ? 'Задержка' : 'Delay',
          c.companion_delay_min_sec +
            '–' +
            c.companion_delay_max_sec +
            ' c · ' +
            c.companion_max_replies_per_hour +
            '/' +
            (lang === 'ru' ? 'ч' : 'h'),
        ],
      ]
    }
    if (connId === 'fanvue') {
      const rows = ig.fanvue_connections || []
      if (!rows.length) return []
      const c = rows[0]
      return [
        [lang === 'ru' ? 'Аккаунт' : 'Account', (c.creator_user_id || c.label || '—').toString().slice(0, 20)],
        [lang === 'ru' ? 'Персонаж' : 'Character', modelName(c.studio_model_id)],
        ['OAuth', c.oauth_connected ? (lang === 'ru' ? 'сессия активна' : 'session active') : lang === 'ru' ? 'нет' : 'no'],
        [
          'AI',
          c.companion_mode && c.companion_mode !== 'off' ? c.companion_mode : lang === 'ru' ? 'выключен' : 'off',
        ],
      ]
    }
    if (connId === 'tribute') {
      const rows = ig.tribute_connections || []
      if (!rows.length && !ig.tribute_configured) return []
      const c = rows[0]
      return [
        [lang === 'ru' ? 'Метка' : 'Label', c?.label || 'Tribute'],
        [lang === 'ru' ? 'Персонаж' : 'Character', modelName(c?.studio_model_id)],
        ['API', ig.tribute_configured ? '••••' + (c?.id ? String(c.id).slice(-4) : 'set') : '—'],
        ['Webhook', c?.webhook_url ? c.webhook_url.replace(/^https?:\/\//, '').slice(0, 24) + '…' : '—'],
      ]
    }
    if (connId === 'wavespeed') {
      if (!ig.wavespeed_configured) return []
      return [
        [
          lang === 'ru' ? 'Режим' : 'Mode',
          ig.wavespeed_managed_by_platform
            ? lang === 'ru'
              ? 'ключ платформы'
              : 'platform key'
            : lang === 'ru'
              ? 'свой ключ'
              : 'own key',
        ],
        [lang === 'ru' ? 'Кредиты' : 'Credits', lang === 'ru' ? 'списываются' : 'spent'],
      ]
    }
    if (connId === 'push') {
      const on = typeof Notification !== 'undefined' && Notification.permission === 'granted'
      return [
        [lang === 'ru' ? 'Сообщения' : 'Messages', on ? (lang === 'ru' ? 'вкл' : 'on') : lang === 'ru' ? 'выкл' : 'off'],
        [lang === 'ru' ? 'Донаты' : 'Donations', on ? (lang === 'ru' ? 'вкл' : 'on') : lang === 'ru' ? 'выкл' : 'off'],
        [lang === 'ru' ? 'Генерации' : 'Generations', lang === 'ru' ? 'выкл' : 'off'],
      ]
    }
    return []
  }

  function renderIntegrationPanels() {
    const ig = store.integrations
    if (!ig) return

    const tgList = document.querySelector('[data-mm-tg-list]')
    if (tgList) {
      const rows = ig.telegram_connections || []
      tgList.innerHTML = rows.length
        ? rows
            .map(
              (c) =>
                `<div style="background:#0D0E11;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px;margin-bottom:10px;">
                  <div style="font-family:'JetBrains Mono';font-size:10.5px;color:#C9CDD1;">@${c.bot_username || '—'} · ${c.webhook_registered ? '✓ webhook' : 'webhook?'}</div>
                  <div style="font-size:11px;color:#9BA0A6;margin-top:6px;">Модель: ${modelName(c.studio_model_id)}</div>
                </div>`,
            )
            .join('')
        : '<div style="font-size:12px;color:#6B7076;">Нет подключённых ботов</div>'
    }

    const fvList = document.querySelector('[data-mm-fv-list]')
    if (fvList) {
      const rows = ig.fanvue_connections || []
      fvList.innerHTML = rows.length
        ? rows
            .map(
              (c) =>
                `<div style="background:#0D0E11;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px;margin-bottom:10px;">
                  <div style="font-family:'JetBrains Mono';font-size:10.5px;color:#C9CDD1;">${(c.creator_user_id || c.label || 'Fanvue').toString().slice(0, 24)}</div>
                  <div style="font-size:11px;color:#9BA0A6;margin-top:6px;">Модель: ${modelName(c.studio_model_id)}</div>
                </div>`,
            )
            .join('')
        : '<div style="font-size:12px;color:#6B7076;">Нет подключений Fanvue</div>'
    }

    const trList = document.querySelector('[data-mm-tribute-list]')
    if (trList) {
      const rows = ig.tribute_connections || []
      trList.innerHTML = rows.length
        ? rows
            .map(
              (c) =>
                `<div style="background:#0D0E11;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px;margin-bottom:10px;">
                  <div style="font-family:'JetBrains Mono';font-size:10.5px;color:#C9CDD1;">${c.label || 'Tribute'}</div>
                  <div style="font-size:11px;color:#9BA0A6;margin-top:6px;">Модель: ${modelName(c.studio_model_id)}</div>
                  ${c.webhook_url ? `<div style="margin-top:8px;display:flex;gap:8px;align-items:center;"><input readonly value="${c.webhook_url}" style="flex:1;background:#0A0B0D;border:1px solid rgba(255,255,255,.09);border-radius:9px;padding:8px 10px;color:#9BA0A6;font-family:'JetBrains Mono';font-size:10px;"><button type="button" data-mm-copy="${c.webhook_url}" style="border:1px solid rgba(255,255,255,.12);border-radius:9px;padding:8px 12px;font-size:11px;color:#9BA0A6;cursor:pointer;background:transparent;">Копировать</button></div>` : ''}
                </div>`,
            )
            .join('')
        : '<div style="font-size:12px;color:#6B7076;">Нет подключений Tribute</div>'
      trList.querySelectorAll('[data-mm-copy]').forEach((btn) => {
        if (btn.dataset.mmBoundCopy) return
        btn.dataset.mmBoundCopy = '1'
        btn.addEventListener('click', () => void copyText(btn.dataset.mmCopy))
      })
    }

    const walletInp = document.querySelector('[data-mm-don-wallet]')
    if (walletInp && store.payoutSettings?.wallet_address && !walletInp.value) {
      walletInp.value = store.payoutSettings.wallet_address
    }
  }

  async function createDonationLink() {
    const root = document.querySelector('[data-screen-label="Донаты"]')
    const title = (root?.querySelector('[data-mm-don-title]')?.value || '').trim()
    if (!title) { store.error = 'Укажите название ссылки'; return }
    const desc = (root?.querySelector('[data-mm-don-desc]')?.value || '').trim()
    const min = Number(root?.querySelector('[data-mm-don-min]')?.value || 0)
    const modelId = root?.querySelector('[data-mm-don-model]')?.value
    store.busy = true
    try {
      await API.apiJson('/api/creator-donations', {
        method: 'POST',
        body: JSON.stringify({
          title,
          description: desc || null,
          min_amount_minor: Math.round(min * 100),
          studio_model_id: modelId ? Number(modelId) : null,
        }),
      })
      await bridge.refreshAll()
      bridge.store.logic?.setState({ donTab: 'overview' })
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function addSnippet() {
    const title = prompt('Название шаблона')
    if (!title?.trim()) return
    const body = prompt('Текст шаблона')
    if (!body?.trim()) return
    store.busy = true
    try {
      await API.apiJson('/api/workspace/snippets', {
        method: 'POST',
        body: JSON.stringify({ title: title.trim(), body: body.trim() }),
      })
      await bridge.refreshAll()
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  async function addConversationNote() {
    const open = bridge.store.logic?.state?.chatOpen ?? 0
    const conv = store.conversations[open]
    if (!conv) return
    const text = prompt('Текст заметки')
    if (!text?.trim()) return
    store.busy = true
    try {
      await API.apiJson('/api/conversations/' + conv.id + '/notes', {
        method: 'POST',
        body: JSON.stringify({ content: text.trim(), kind: 'note' }),
      })
      const nr = await API.apiJson('/api/conversations/' + conv.id + '/notes')
      store.notes = Array.isArray(nr) ? nr : []
    } catch (e) {
      store.error = e.message || String(e)
    } finally {
      store.busy = false
      bridge.store.logic?.forceUpdate()
    }
  }

  function outReferralLink() {
    return store.referral?.referral_link || ''
  }

  function bindOnce(el, fn) {
    if (!el || el.dataset.mmBoundFull) return
    el.dataset.mmBoundFull = '1'
    el.addEventListener('click', () => void fn())
  }

  function bindFullPanels() {
    updateApiStatusBar()

    bindOnce(document.querySelector('[data-mm-conn-wavespeed-save]'), saveWavespeedKey)
    bindOnce(document.querySelector('[data-mm-conn-tg-add]'), addTelegramBot)
    bindOnce(document.querySelector('[data-mm-conn-fanvue-oauth]'), startFanvueOAuth)
    bindOnce(document.querySelector('[data-mm-conn-tribute-save]'), saveTributeKey)
    bindOnce(document.querySelector('[data-mm-don-create]'), createDonationLink)
    bindOnce(document.querySelector('[data-mm-snippet-add]'), addSnippet)
    bindOnce(document.querySelector('[data-mm-note-add]'), addConversationNote)
    bindOnce(document.querySelector('[data-mm-logout]'), () => {
      API.setToken(null)
      store.authed = false
      if (store.ws) {
        try { store.ws.close() } catch (_) {}
        store.ws = null
      }
      const auth = document.getElementById('mm-os-auth')
      if (auth) auth.style.display = 'flex'
      bridge.store.logic?.forceUpdate()
    })
    bindOnce(document.querySelector('[data-mm-video-generate]'), () => {
      if (typeof bridge.runGenerateVideo === 'function') void bridge.runGenerateVideo()
    })

    document.querySelectorAll('[data-mm-billing-credits]').forEach((el) => {
      bindOnce(el, () => subscribeWithCredits(el.dataset.mmBillingCredits))
    })
    document.querySelectorAll('[data-mm-billing-card]').forEach((el) => {
      bindOnce(el, () => payYookassa(el.dataset.mmBillingCard))
    })

    bindOnce(document.querySelector('[data-mm-don-payout-save]'), savePayoutSettings)
    bindOnce(document.querySelector('[data-mm-don-payout-request]'), requestPayout)
    bindOnce(document.querySelector('[data-mm-referral-copy]'), () => copyText(outReferralLink()))

    const chatSearch = document.querySelector('[data-mm-chat-search]')
    if (chatSearch && !chatSearch.dataset.mmBoundSearch) {
      chatSearch.dataset.mmBoundSearch = '1'
      chatSearch.addEventListener('input', () => {
        store.chatSearch = chatSearch.value
        bridge.store.logic?.forceUpdate()
      })
    }

    document.querySelectorAll('[data-screen-label="Подключения"] select').forEach(fillModelSelect)
    document.querySelectorAll('[data-screen-label="Донаты"] select[data-mm-don-model]').forEach(fillModelSelect)

    if (store.authed) renderIntegrationPanels()

    const wf = document.querySelector('[data-screen-label="Workflow"]')
    if (wf && !wf.dataset.mmWfLink) {
      wf.dataset.mmWfLink = '1'
      const box = wf.querySelector('div[style*="max-width"]') || wf.firstElementChild
      if (box) {
        const a = document.createElement('a')
        a.href = (global.location?.origin || '') + '/'
        a.textContent = 'Открыть Workflow в полном кабинете →'
        a.style.cssText = 'display:inline-block;margin-top:12px;font-weight:800;color:#D7F452;'
        box.appendChild(a)
      }
    }
  }

  const origEnrich = bridge.enrich
  bridge.enrich = function (logic, vals) {
    const out = origEnrich(logic, vals)
    if (!store.authed) return out
    const lang = logic.state.lang || 'ru'
    const me = store.me
    const allConvs = store.conversations
    const convs = filterConversations(allConvs)
    const chipOn =
      "font-family:'JetBrains Mono';font-size:10px;background:rgba(215,244,82,.12);color:#D7F452;border:1px solid rgba(215,244,82,.4);padding:3px 10px;border-radius:20px;cursor:pointer;"
    const chipOff =
      "font-family:'JetBrains Mono';font-size:10px;border:1px solid rgba(255,255,255,.12);color:#9BA0A6;padding:3px 10px;border-radius:20px;cursor:pointer;"

    const connections = mapConnections(vals, logic, lang)
    const connDetailData = connections.find((c) => c.id === logic.state.connDetail) || connections[0] || vals.connDetailData
    const cfsCurrent = buildCurConfig(connDetailData?.id, store.integrations, lang).map((kv) => ({
      k: kv[0],
      v: kv[1],
    }))
    const billing = mapBilling(vals, lang, me)
    const ratioChips = mapRatioChips(logic)
    const chatFilters = mapChatFilters(allConvs, logic, lang, chipOn, chipOff)

    const video = mapVideoChips(logic)
    const filteredIds = new Set(convs.map((c) => c.id))
    const chats = (out.chats || []).filter((ch) => filteredIds.has(ch.id))

    const paidOut = store.donationOverview?.paid_out_by_currency?.RUB ?? store.donationOverview?.paid_out_minor
    const donStats = out.donStats ? [...out.donStats] : []
    if (donStats[3] && paidOut != null) donStats[3] = { ...donStats[3], value: fmtMoney(paidOut, 'RUB') }

    const videoArchive = (store.archiveVideos || []).slice(0, 8).map((item, i) => ({
      bg:
        'aspect-ratio:9/16;display:flex;align-items:center;justify-content:center;position:relative;background:center/cover no-repeat url("' +
        ((item.image_url || '').replace(/"/g, '')) +
        '"),' +
        G[(i + 2) % 6],
      who: item.model_name || '—',
      dur: item.duration_seconds ? item.duration_seconds + 's' : '5s',
      url: item.video_url || item.image_url || '',
    }))

    const recentFrames = out.recentFrames || []

    const avail = store.donationOverview?.pending_payout_by_currency?.RUB ?? 0
    const payoutHint = fmtMoney(avail, 'RUB') + ' − 2%'

    return {
      ...out,
      todayLabel: fmtToday(lang),
      dialogsPlatformLine: platformCounts(allConvs) || '—',
      connections,
      connDetailData,
      cfsCurrent,
      hasCurConfig: cfsCurrent.length > 0,
      connDetailIconBox: connDetailData?.iconBox ? 'width:48px;height:48px;border-radius:14px;display:flex;align-items:center;justify-content:center;flex:none;' + (connDetailData.iconCol || '') : out.connDetailIconBox,
      usageBars: billing.usageBars,
      plans: billing.plans,
      packs: billing.packs,
      referralLink: billing.referralLink,
      referralStats: billing.referralStats,
      ratioChips,
      chatFilters,
      chats,
      donStats,
      payoutHint,
      videoArchive,
      recentFrames,
      userSidebarInitial: ((me?.email || '?')[0] || '?').toUpperCase(),
      userEmailShort: out.userEmailShort,
      ...video,
    }
  }

  const origOnMount = bridge.onMount
  bridge.onMount = function (logic) {
    origOnMount(logic)
    setInterval(() => {
      if (store.authed) bindFullPanels()
    }, 450)
    bindFullPanels()
  }

  bridge.runGenerateVideo = bridge.runGenerateVideo || function () {}
})(window)
