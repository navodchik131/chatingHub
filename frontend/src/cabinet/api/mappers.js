import {
  AV_GRADIENTS,
  fmtDateShort,
  fmtMoney,
  fmtTime,
  platformLabel,
  ownerReactionEmoji,
  firstAttachmentUrl,
} from './helpers'

export function displayName(c) {
  return (c.user_display_name || c.external_chat_id || '—').trim()
}

export function chatStatusType(c) {
  if (c.is_blocked) return 'blocked'
  if (c.peer_unavailable) return 'deleted'
  return null
}

export function mapDialogRow(c, index) {
  const name = displayName(c)
  const st = chatStatusType(c)
  return {
    id: c.id,
    index,
    name,
    platform: platformLabel(c.platform),
    last: (c.last_message_preview || '—').slice(0, 80),
    time: fmtTime(c.updated_at),
    av: index % AV_GRADIENTS.length,
    vip: c.manual_category === 'vip',
    hot: Boolean(c.is_no_response),
    lang: c.user_lang ? `${c.user_lang}*` : '',
    unread: c.unread_count || 0,
    isNew: (c.unread_count || 0) > 0,
    status: st,
  }
}

export function mapMessage(m) {
  const outbound = m.direction === 'outbound'
  const tr = outbound && m.text_translated && m.text_translated !== m.text_original
  return {
    id: m.id,
    side: outbound ? 'out' : 'in',
    text: m.text_original || '',
    tr: tr ? m.text_translated : false,
    time: fmtTime(m.created_at),
    reactions: m.reactions || [],
    ownerReaction: ownerReactionEmoji(m.reactions),
    attachmentUrl: firstAttachmentUrl(m.attachments),
    attachments: m.attachments || [],
    pending: Boolean(m.pending),
  }
}

export function mapNote(n, lang) {
  const tagBase = lang === 'ru' ? 'ЗАМЕТКА' : 'NOTE'
  const kind = n.kind || 'manual'
  if (kind === 'ai_profile') {
    return { tag: lang === 'ru' ? 'ПРОФИЛЬ' : 'PROFILE', kind: 'lime', when: fmtDateShort(n.created_at, lang), text: n.content || '' }
  }
  if (kind === 'ai_daily') {
    return { tag: lang === 'ru' ? 'КОНТЕКСТ' : 'CONTEXT', kind: 'orange', when: fmtDateShort(n.created_at, lang), text: n.content || '' }
  }
  if (kind === 'ai_insight') {
    return { tag: 'AI', kind: 'purple', when: fmtDateShort(n.created_at, lang), text: n.content || '' }
  }
  return { tag: tagBase, kind: 'lime', when: fmtDateShort(n.created_at, lang), text: n.content || '' }
}

export function mapCharacter(m, lang) {
  const name = m.name || '—'
  const initial = (name[0] || '?').toUpperCase()
  const active = m.status !== 'draft'
  return {
    id: String(m.id),
    name,
    initial,
    grad: AV_GRADIENTS[(m.id || 0) % AV_GRADIENTS.length],
    status: active ? (lang === 'ru' ? 'АКТИВНА' : 'ACTIVE') : lang === 'ru' ? 'ЧЕРНОВИК' : 'DRAFT',
    tone: active ? 'active' : 'dim',
    blurb: m.description || (lang === 'ru' ? 'Персонаж студии' : 'Studio character'),
    tags: [m.platform || 'TELEGRAM'].filter(Boolean),
    raw: m,
  }
}

export function modelNameById(models, id) {
  if (id == null) return '—'
  const m = (models || []).find((x) => Number(x.id) === Number(id))
  return m?.name || '—'
}

export function formatCompanionMode(mode, lang) {
  const m = String(mode || 'off').toLowerCase()
  if (m === 'off') return lang === 'ru' ? 'ВЫКЛ' : 'OFF'
  if (m === 'auto') return 'AUTO'
  if (m === 'semi_auto') return lang === 'ru' ? 'ПОЛУ-AUTO' : 'SEMI'
  if (m === 'draft') return lang === 'ru' ? 'ЧЕРНОВИК' : 'DRAFT'
  return m.toUpperCase()
}

export function computeNavBadges(cabinet, me) {
  const unread = (cabinet.conversations || []).reduce((a, c) => a + (c.unread_count || 0), 0)
  const moderation = (cabinet.donations || []).filter((d) => d.status === 'moderation').length
  const plan = String(me?.billing_plan || '').toLowerCase()
  const isPro = plan === 'pro' || plan === 'byok'
  const badges = {}
  if (unread > 0) badges.dialogs = unread > 99 ? '99+' : String(unread)
  if (moderation > 0) badges.donations = String(moderation)
  if (isPro) badges.workflow = 'PRO'
  return badges
}

export function mapIntegrationConnections(platformId, integrations, models, lang) {
  const ig = integrations
  if (!ig) return []
  const modelLabel = (id) => modelNameById(models, id)
  if (platformId === 'tg') {
    return (ig.telegram_connections || []).map((c) => ({
      id: c.id,
      name: c.bot_username ? `@${c.bot_username}` : (c.label || `#${c.id}`),
      meta: [
        c.webhook_registered ? (lang === 'ru' ? 'webhook активен' : 'webhook active') : (lang === 'ru' ? 'webhook ?' : 'webhook ?'),
        modelLabel(c.studio_model_id),
      ].join(' · '),
    }))
  }
  if (platformId === 'fanvue') {
    return (ig.fanvue_connections || []).map((c) => ({
      id: c.id,
      name: c.creator_uuid ? `${String(c.creator_uuid).slice(0, 8)}…` : (c.label || `#${c.id}`),
      meta: [
        c.oauth_connected ? 'OAuth' : (lang === 'ru' ? 'OAuth ?' : 'OAuth ?'),
        modelLabel(c.studio_model_id),
      ].join(' · '),
    }))
  }
  if (platformId === 'tribute') {
    return (ig.tribute_connections || []).map((c) => ({
      id: c.id,
      name: c.label || (lang === 'ru' ? 'Tribute' : 'Tribute'),
      meta: modelLabel(c.studio_model_id),
    }))
  }
  return []
}

export function mapIntegrationCurrent(platformId, integrations, models, lang) {
  const ig = integrations
  if (!ig) return []
  const modelLabel = (id) => modelNameById(models, id)
  if (platformId === 'wavespeed' && ig.wavespeed_configured) {
    return [
      { k: lang === 'ru' ? 'Режим' : 'Mode', v: ig.wavespeed_managed_by_platform ? (lang === 'ru' ? 'ключ платформы' : 'platform key') : (lang === 'ru' ? 'свой ключ' : 'own key') },
      { k: lang === 'ru' ? 'Статус' : 'Status', v: lang === 'ru' ? 'настроен' : 'configured' },
    ]
  }
  if (platformId === 'tg') {
    const bots = ig.telegram_connections || []
    if (!bots.length) return []
    const c = bots[0]
    return [
      { k: lang === 'ru' ? 'Бот' : 'Bot', v: c.bot_username ? `@${c.bot_username}` : '—' },
      { k: 'Webhook', v: c.webhook_registered ? (lang === 'ru' ? 'активен' : 'active') : '?' },
      { k: lang === 'ru' ? 'Персонаж' : 'Character', v: modelLabel(c.studio_model_id) },
    ]
  }
  if (platformId === 'fanvue') {
    const rows = ig.fanvue_connections || []
    if (!rows.length) return []
    const c = rows[0]
    return [
      { k: lang === 'ru' ? 'Аккаунт' : 'Account', v: c.creator_uuid ? `${String(c.creator_uuid).slice(0, 12)}…` : '—' },
      { k: lang === 'ru' ? 'Персонаж' : 'Character', v: modelLabel(c.studio_model_id) },
      { k: 'OAuth', v: c.oauth_connected ? (lang === 'ru' ? 'активен' : 'active') : '—' },
    ]
  }
  if (platformId === 'tribute') {
    const rows = ig.tribute_connections || []
    if (!rows.length && !ig.tribute_configured) return []
    const c = rows[0]
    return [
      ...(c?.label ? [{ k: lang === 'ru' ? 'Метка' : 'Label', v: c.label }] : []),
      ...(c ? [{ k: lang === 'ru' ? 'Персонаж' : 'Character', v: modelLabel(c.studio_model_id) }] : []),
      { k: lang === 'ru' ? 'Статус' : 'Status', v: ig.tribute_configured ? (lang === 'ru' ? 'настроен' : 'configured') : '—' },
    ]
  }
  if (platformId === 'push') {
    const on = typeof Notification !== 'undefined' && Notification.permission === 'granted'
    return [
      { k: lang === 'ru' ? 'Браузер' : 'Browser', v: on ? (lang === 'ru' ? 'разрешены' : 'granted') : (lang === 'ru' ? 'не разрешены' : 'denied') },
    ]
  }
  return []
}

export function mapUsageBars(me, lang) {
  const lim = me?.limits || {}
  const usedUsers = me?.team_members_count ?? 0
  const maxUsers = lim.max_users ?? 1
  const usedModels = me?.models_count ?? 0
  const maxModels = lim.max_models ?? 1
  const dialogs = me?.dialogs_this_month ?? 0
  const maxDialogs = lim.max_dialogs_per_month
  const pct = (used, max) => (max > 0 ? Math.min(100, Math.round((used / max) * 100)) : 0)
  return [
    {
      label: lang === 'ru' ? 'Операторы' : 'Operators',
      val: `${usedUsers} / ${maxUsers}`,
      pct: pct(usedUsers, maxUsers),
    },
    {
      label: lang === 'ru' ? 'Персонажи' : 'Characters',
      val: `${usedModels} / ${maxModels}`,
      pct: pct(usedModels, maxModels),
    },
    {
      label: lang === 'ru' ? 'Диалоги в месяце' : 'Dialogs this month',
      val: maxDialogs ? `${dialogs} / ${maxDialogs}` : `${dialogs} · ∞`,
      pct: maxDialogs ? pct(dialogs, maxDialogs) : 0,
    },
  ]
}

export function mapCreditHistory(rows, lang) {
  return (rows || []).map((row) => {
    const deltaNum = Number(row.delta || 0)
    const positive = deltaNum >= 0
    const delta = row.delta_display || (positive ? `+${deltaNum}` : String(deltaNum))
    return {
      date: fmtDateShort(row.created_at, lang),
      what: row.description || row.kind || '—',
      delta,
      color: positive ? '#4ADE80' : '#F87171',
    }
  })
}

export function mapConnectionStatus(integrations, connId, lang) {
  const ig = integrations
  if (!ig) return null
  const tgN = (ig.telegram_connections || []).length
  const fvN = (ig.fanvue_connections || []).length
  const trN = (ig.tribute_connections || []).length
  if (connId === 'tg') {
    return {
      st: tgN ? `${tgN} ${lang === 'ru' ? 'БОТА' : 'BOTS'}` : lang === 'ru' ? 'НЕ НАСТРОЕН' : 'NOT SET',
      tone: tgN ? 'active' : 'warn',
    }
  }
  if (connId === 'wavespeed') {
    if (!ig.wavespeed_configured) {
      return { st: lang === 'ru' ? 'НЕ НАСТРОЕН' : 'NOT SET', tone: 'warn' }
    }
    return {
      st: ig.wavespeed_managed_by_platform
        ? lang === 'ru' ? 'КЛЮЧ ПЛАТФОРМЫ' : 'PLATFORM KEY'
        : lang === 'ru' ? 'СВОЙ КЛЮЧ' : 'OWN KEY',
      tone: 'active',
    }
  }
  if (connId === 'fanvue') {
    return {
      st: fvN ? lang === 'ru' ? 'ПОДКЛЮЧЁН' : 'CONNECTED' : lang === 'ru' ? 'НЕ НАСТРОЕН' : 'NOT SET',
      tone: fvN ? 'active' : 'warn',
    }
  }
  if (connId === 'tribute') {
    const ok = trN || ig.tribute_configured
    return {
      st: ok ? lang === 'ru' ? 'НАСТРОЕН' : 'SET' : lang === 'ru' ? 'НЕ НАСТРОЕН' : 'NOT SET',
      tone: ok ? 'active' : 'warn',
    }
  }
  if (connId === 'ig') return { st: lang === 'ru' ? 'В РАЗРАБОТКЕ' : 'COMING SOON', tone: 'dim' }
  if (connId === 'push') {
    const on = typeof Notification !== 'undefined' && Notification.permission === 'granted'
    return { st: on ? lang === 'ru' ? 'ВКЛЮЧЕНЫ' : 'ON' : lang === 'ru' ? 'ВЫКЛ' : 'OFF', tone: on ? 'active' : 'dim' }
  }
  return null
}

export function mapDonationStats(overview, lang) {
  const cur = overview?.currency || 'RUB'
  const total = overview?.total_minor ?? 0
  const available = overview?.available_minor ?? 0
  const held = overview?.held_minor ?? 0
  const paid = overview?.paid_out_minor ?? 0
  return [
    { label: lang === 'ru' ? 'ВСЕГО' : 'TOTAL', value: fmtMoney(total, cur), color: '#F2F3F0' },
    { label: lang === 'ru' ? 'ДОСТУПНО' : 'AVAILABLE', value: fmtMoney(available, cur), color: '#4ADE80' },
    { label: lang === 'ru' ? 'НА УДЕРЖАНИИ' : 'ON HOLD', value: fmtMoney(held, cur), color: '#FB923C' },
    { label: lang === 'ru' ? 'ВЫПЛАЧЕНО' : 'PAID OUT', value: fmtMoney(paid, cur), color: '#9BA0A6' },
  ]
}

export function mapTeamKpi(chatterStats, lang) {
  const cs = chatterStats
  const self = cs?.self || cs?.self_row || {}
  const pos = self.companion_ratings_positive ?? 0
  const neg = self.companion_ratings_negative ?? 0
  const tot = pos + neg
  const sec = self.median_reply_seconds
  return [
    { label: lang === 'ru' ? 'ОТВЕТЫ / МЕС' : 'REPLIES / MO', value: String(self.outbound_messages ?? 0) },
    { label: lang === 'ru' ? 'ДИАЛОГИ' : 'DIALOGS', value: String(self.conversations_replied ?? 0) },
    {
      label: lang === 'ru' ? 'ПЕРВЫЙ ОТВЕТ' : 'FIRST REPLY',
      value: sec != null ? `${Math.floor(sec / 60)}м ${sec % 60}с` : '—',
    },
    { label: 'AI 👍 / 👎', value: tot ? `${Math.round((pos / tot) * 100)}%` : '—' },
  ]
}

const MEMBER_PERM_BITS = [
  ['CHAT', 1],
  ['STUDIO GEN', 2],
  ['MODELS', 4],
  ['INTEGRATIONS', 8],
  ['BILLING', 16],
]

export function mapMembers(members, chatterStats, models, lang) {
  return (members || []).map((m, i) => {
    const mask = Number(m.permissions_mask) || 0
    const st = (chatterStats?.members || []).find((s) => Number(s.user_id) === Number(m.id)) || {}
    const names = (m.allowed_studio_model_ids || [])
      .map((id) => modelNameById(models, id))
      .filter((n) => n !== '—')
      .join(', ')
    const sec = st.median_reply_seconds
    return {
      id: m.id,
      login: m.member_login || m.login || '—',
      meta: [
        m.is_active ? (lang === 'ru' ? 'активен' : 'active') : (lang === 'ru' ? 'выкл' : 'off'),
        names ? `${lang === 'ru' ? 'персонажи' : 'characters'}: ${names}` : '',
      ].filter(Boolean).join(' · '),
      initial: ((m.member_login || m.login || '?')[0] || '?').toUpperCase(),
      grad: { bg: AV_GRADIENTS[i % AV_GRADIENTS.length], ink: '#0A2614' },
      sla: sec != null ? `${Math.floor(sec / 60)}м ${sec % 60}с` : '—',
      replies: String(st.outbound_messages ?? 0),
      tribute: m.tribute_share_percent != null ? `${m.tribute_share_percent}%` : '—',
      rights: MEMBER_PERM_BITS.map(([label, bit]) => ({
        label,
        on: (mask & bit) === bit,
      })),
      raw: m,
    }
  })
}
