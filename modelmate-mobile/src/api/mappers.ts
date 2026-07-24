import type {
  ChatterStatsSummaryOut,
  ConversationOut,
  CreatorDonationEventOut,
  CreatorDonationLinkOut,
  IntegrationStatusOut,
  MessageOut,
  StudioGenerationOut,
  StudioModelOut,
  UserMeOut,
  WorkspaceMemberOut,
} from '@/src/api/types';
import { resolveMediaUrl } from '@/src/api/config';
import { fmtDateShort, fmtMoney, fmtTime, platformLabel, photoKindShortLabel, rightsFromMask } from '@/src/api/helpers';
import { archiveThumbUrl, isArchivePending } from '@/src/api/media';
import { gradients } from '@/src/styles/tokens';

export function displayName(c: ConversationOut): string {
  return (c.user_display_name || c.external_chat_id || '—').trim();
}

export function mapDialogRow(c: ConversationOut, index: number) {
  const name = displayName(c);
  return {
    id: c.id,
    index,
    name,
    plat: platformLabel(c.platform),
    msg: (c.last_message_preview || '—').slice(0, 80),
    vip: c.manual_category === 'vip',
    unread: c.unread_count || 0,
    gradIndex: index % gradients.length,
  };
}

export function mapMessage(m: MessageOut) {
  const outbound = m.direction === 'outbound';
  const translated = (m.text_translated || '').trim();
  const original = (m.text_original || '').trim();
  const tr = translated && translated !== original ? translated : null;
  return {
    id: m.id,
    side: outbound ? ('out' as const) : ('in' as const),
    text: original || '',
    tr,
    time: fmtTime(m.created_at),
    created_at: m.created_at,
    pending: Boolean(m.pending),
  };
}

export function mapCharacter(m: StudioModelOut, index: number, locale: 'ru' | 'en' = 'ru') {
  const name = m.name || '—';
  const hasPhotos = (m.images || []).length > 0;
  const draft = locale === 'en' ? 'Draft' : 'Черновик';
  const ready = locale === 'en' ? 'Ready' : 'Готов';
  return {
    id: String(m.id),
    name,
    sub: hasPhotos ? ready : draft,
    gradIndex: index % gradients.length,
    raw: m,
  };
}

export function mapArchiveTile(g: StudioGenerationOut, index: number, models: StudioModelOut[]) {
  const model = models.find((m) => m.id === g.studio_model_id);
  return {
    id: g.id,
    who: `${model?.name || '—'} · ${g.output_aspect || '9:16'}`,
    gradIndex: index % gradients.length,
    imageUrl: archiveThumbUrl(g),
    pending: isArchivePending(g),
    videoUrl: g.video_url,
    raw: g,
  };
}

export function mapIntegrationCards(integrations: IntegrationStatusOut | null) {
  if (!integrations) return [];
  const cards = [];
  const tgCount = integrations.telegram_connections?.length ?? 0;
  cards.push({
    id: 'tg',
    name: 'Telegram',
    status: tgCount ? `${tgCount} БОТА` : 'НЕ НАСТРОЕН',
    icon: 'chat' as const,
    color: '56,189,248',
  });
  cards.push({
    id: 'ws',
    name: 'WaveSpeed',
    status: !integrations.wavespeed_configured
      ? 'НЕ НАСТРОЕН'
      : integrations.wavespeed_managed_by_platform
        ? 'КЛЮЧ ПЛАТФОРМЫ'
        : 'СВОЙ КЛЮЧ',
    icon: 'bolt' as const,
    color: '215,244,82',
  });
  const fv = integrations.fanvue_connections?.length ?? 0;
  cards.push({
    id: 'fv',
    name: 'Fanvue',
    status: fv ? 'ПОДКЛЮЧЁН' : 'НЕ НАСТРОЕН',
    icon: 'heart' as const,
    color: '240,168,200',
  });
  const tr = integrations.tribute_connections?.length ?? 0;
  cards.push({
    id: 'tr',
    name: 'Tribute API',
    status: tr ? 'НАСТРОЕН' : 'НЕ НАСТРОЕН',
    icon: 'card' as const,
    color: '192,132,252',
  });
  return cards;
}

export function mapOverviewKpis(me: UserMeOut | null, conversations: ConversationOut[], donationAvailableMinor?: number) {
  const credits = me?.credits_balance ?? 0;
  const plan = me?.plan_display_name || me?.billing_plan || '—';
  const subUntil = me?.subscription_expires_at ? fmtDateShort(me.subscription_expires_at) : '—';
  const dialogs = conversations.length;
  const unread = conversations.reduce((a, c) => a + (c.unread_count || 0), 0);
  return {
    credits: String(Math.round(credits)),
    creditsSub: `≈${Math.floor(credits / 10)} кадр`,
    plan,
    planSub: subUntil !== '—' ? `до ${subUntil}` : me?.subscription_status || '',
    donations: donationAvailableMinor != null ? fmtMoney(donationAvailableMinor) : '—',
    donationsSub: 'к выплате',
    dialogs: String(dialogs),
    dialogsSub: unread ? `${unread} непрочит.` : `${me?.plan_usage?.dialogs_this_month ?? 0} ответов`,
  };
}

export function mapDonationRow(d: CreatorDonationLinkOut) {
  const status =
    d.status === 'active'
      ? 'ACTIVE'
      : d.status === 'moderation'
        ? 'МОДЕРАЦИЯ'
        : d.status.toUpperCase();
  return {
    id: d.id,
    title: d.title,
    status,
    webLink: d.web_link || '',
    telegramLink: d.telegram_link || '',
    minAmount: d.min_amount_minor != null ? fmtMoney(d.min_amount_minor, d.currency || 'RUB') : '',
    description: d.description || '',
  };
}

export function mapDonationEventRow(ev: CreatorDonationEventOut) {
  return {
    id: ev.id,
    label: ev.donor_label || ev.donation_link_title || 'Донат',
    amount: fmtMoney(ev.amount_minor, ev.currency || 'RUB'),
    time: fmtTime(ev.occurred_at),
  };
}

function modelNameById(models: StudioModelOut[], id?: number | null): string {
  if (!id) return '—';
  return models.find((m) => m.id === id)?.name || '—';
}

export function mapIntegrationConnections(
  platformId: string,
  integrations: IntegrationStatusOut | null,
  models: StudioModelOut[],
) {
  if (!integrations) return [];
  if (platformId === 'tg') {
    return (integrations.telegram_connections || []).map((c) => ({
      id: c.id,
      name: c.bot_username ? `@${c.bot_username}` : c.label || `#${c.id}`,
      meta: [
        c.webhook_registered ? 'webhook активен' : 'webhook ?',
        modelNameById(models, c.studio_model_id),
      ].join(' · '),
      studioModelId: c.studio_model_id,
    }));
  }
  if (platformId === 'fv') {
    return (integrations.fanvue_connections || []).map((c) => ({
      id: c.id,
      name: c.creator_uuid ? `${String(c.creator_uuid).slice(0, 8)}…` : c.label || `#${c.id}`,
      meta: [
        c.oauth_connected ? 'OAuth' : 'OAuth ?',
        modelNameById(models, c.studio_model_id),
      ].join(' · '),
      studioModelId: c.studio_model_id,
    }));
  }
  if (platformId === 'tr') {
    return (integrations.tribute_connections || []).map((c) => ({
      id: c.id,
      name: c.label || 'Tribute',
      meta: modelNameById(models, c.studio_model_id),
      studioModelId: c.studio_model_id,
    }));
  }
  return [];
}

export function mapIntegrationCurrent(
  platformId: string,
  integrations: IntegrationStatusOut | null,
  models: StudioModelOut[] = [],
) {
  const ig = integrations;
  if (!ig) return [] as { k: string; v: string }[];
  const modelLabel = (id?: number | null) => modelNameById(models, id);
  if (platformId === 'ws' && ig.wavespeed_configured) {
    return [
      {
        k: 'Режим',
        v: ig.wavespeed_managed_by_platform ? 'ключ платформы' : 'свой ключ',
      },
      { k: 'Статус', v: 'настроен' },
    ];
  }
  if (platformId === 'tg') {
    const bots = ig.telegram_connections || [];
    if (!bots.length) return [];
    const c = bots[0];
    return [
      { k: 'Бот', v: c.bot_username ? `@${c.bot_username}` : '—' },
      { k: 'Webhook', v: c.webhook_registered ? 'активен' : '?' },
      { k: 'Персонаж', v: modelLabel(c.studio_model_id) },
    ];
  }
  if (platformId === 'fv') {
    const rows = ig.fanvue_connections || [];
    if (!rows.length) return [];
    const c = rows[0];
    return [
      { k: 'Аккаунт', v: c.creator_uuid ? `${String(c.creator_uuid).slice(0, 12)}…` : '—' },
      { k: 'Персонаж', v: modelLabel(c.studio_model_id) },
      { k: 'OAuth', v: c.oauth_connected ? 'активен' : '—' },
    ];
  }
  if (platformId === 'tr') {
    const rows = ig.tribute_connections || [];
    if (!rows.length && !ig.tribute_configured) return [];
    const c = rows[0];
    return [
      ...(c?.label ? [{ k: 'Метка', v: c.label }] : []),
      ...(c ? [{ k: 'Персонаж', v: modelLabel(c.studio_model_id) }] : []),
      { k: 'Статус', v: ig.tribute_configured ? 'настроен' : '—' },
    ];
  }
  return [];
}

export function mapTeamMember(
  m: WorkspaceMemberOut,
  index: number,
  models: StudioModelOut[] = [],
  chatterStats?: ChatterStatsSummaryOut | null,
) {
  const letter = (m.member_login[0] || '?').toUpperCase();
  const st = (chatterStats?.members || []).find((s) => Number(s.user_id) === Number(m.id)) || {};
  const names = (m.allowed_studio_model_ids || [])
    .map((id) => modelNameById(models, id))
    .filter((n) => n !== '—')
    .join(', ');
  const sec = st.median_reply_seconds;
  const meta = [
    m.is_active === false ? 'выкл' : 'активен',
    names ? `персонажи: ${names}` : '',
    st.outbound_messages != null ? `${st.outbound_messages} ответов` : '',
    sec != null ? `SLA ${Math.floor(sec / 60)}м ${sec % 60}с` : '',
  ].filter(Boolean).join(' · ');
  return {
    id: m.id,
    letter,
    name: m.member_login,
    sub: meta || `ID ${m.id}`,
    gradIndex: index % gradients.length,
    rights: rightsFromMask(m.permissions_mask),
    raw: m,
  };
}

export function mapCharPhotoTags(images: StudioModelOut['images']) {
  return (images || []).map((img, i) => ({
    id: img.id,
    label: photoKindShortLabel(img.kind),
    gradIndex: i % gradients.length,
    url: resolveMediaUrl(img.url),
    kind: img.kind,
  }));
}

export function mapTeamKpi(chatterStats: ChatterStatsSummaryOut | null | undefined) {
  const self = chatterStats?.self || chatterStats?.self_row || {};
  const sec = self.median_reply_seconds;
  return {
    replies: String(self.outbound_messages ?? 0),
    sla: sec != null ? `${Math.floor(sec / 60)}м ${sec % 60}с` : '—',
  };
}

export function mapAdminUser(u: { id: number; email: string; role?: string; billing_plan?: string; credits_balance?: number; subscription_status?: string }) {
  return {
    id: u.id,
    email: u.email,
    role: u.role || 'владелец',
    plan: u.billing_plan || '—',
    credits: u.credits_balance ?? 0,
    sub: u.subscription_status || 'нет',
  };
}

export function userDisplayName(me: UserMeOut | null): { userName: string; userEmail: string } {
  if (!me) return { userName: '—', userEmail: '—' };
  const email = me.email || '—';
  const at = email.indexOf('@');
  const userName = at > 0 ? email.slice(0, at) : email;
  const userEmail = at > 0 ? `${email.slice(0, Math.min(at, 12))}…` : email;
  return { userName, userEmail };
}
