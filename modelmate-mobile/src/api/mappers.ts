import type {
  ConversationOut,
  CreatorDonationLinkOut,
  IntegrationStatusOut,
  MessageOut,
  StudioGenerationOut,
  StudioModelOut,
  UserMeOut,
  WorkspaceMemberOut,
} from '@/src/api/types';
import { resolveMediaUrl } from '@/src/api/config';
import { fmtDateShort, fmtMoney, fmtTime, platformLabel, photoKindShortLabel } from '@/src/api/helpers';
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
  const tr =
    outbound && m.text_translated && m.text_translated !== m.text_original
      ? m.text_translated
      : null;
  return {
    id: m.id,
    side: outbound ? ('out' as const) : ('in' as const),
    text: m.text_original || '',
    tr,
    pending: Boolean(m.pending),
  };
}

export function mapCharacter(m: StudioModelOut, index: number) {
  const name = m.name || '—';
  const profile = (m.profile_text || '').trim();
  const hasPhotos = (m.images || []).length > 0;
  return {
    id: String(m.id),
    name,
    sub: hasPhotos ? 'Telegram · Fanvue' : 'Черновик',
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
    status: integrations.wavespeed_configured ? 'ПЛАТФОРМА' : 'НЕ НАСТРОЕН',
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
  return {
    id: d.id,
    title: d.title,
    status: d.status === 'active' ? 'ACTIVE' : d.status === 'moderation' ? 'МОДЕРАЦИЯ' : d.status.toUpperCase(),
  };
}

export function mapTeamMember(m: WorkspaceMemberOut, index: number) {
  const letter = (m.member_login[0] || '?').toUpperCase();
  return {
    id: m.id,
    letter,
    name: m.member_login,
    sub: `ID ${m.id}`,
    gradIndex: index % gradients.length,
  };
}

export function mapCharPhotoTags(images: StudioModelOut['images']) {
  return (images || []).slice(0, 3).map((img, i) => ({
    id: img.id,
    label: photoKindShortLabel(img.kind),
    gradIndex: i % gradients.length,
    url: resolveMediaUrl(img.url),
    kind: img.kind,
  }));
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
