import type { AppLocale } from '@/src/i18n/prefs';

export type TicketType = { id: string; label: string };
export type RightDef = { k: string; l: string };

const TICKET_TYPES_RU: TicketType[] = [
  { id: 'general', label: 'Общие вопросы' },
  { id: 'technical', label: 'Технические проблемы' },
  { id: 'payment', label: 'Оплата' },
  { id: 'subscription', label: 'Подписки' },
];

const TICKET_TYPES_EN: TicketType[] = [
  { id: 'general', label: 'General questions' },
  { id: 'technical', label: 'Technical issues' },
  { id: 'payment', label: 'Payment' },
  { id: 'subscription', label: 'Subscriptions' },
];

const RIGHTS_RU: RightDef[] = [
  { k: 'chat', l: 'Диалоги и ответы' },
  { k: 'studio', l: 'Генерация в студии' },
  { k: 'models', l: 'Персонажи' },
  { k: 'keys', l: 'Ключи интеграций' },
  { k: 'billing', l: 'Оплата и биллинг' },
];

const RIGHTS_EN: RightDef[] = [
  { k: 'chat', l: 'Dialogs & replies' },
  { k: 'studio', l: 'Studio generation' },
  { k: 'models', l: 'Characters' },
  { k: 'keys', l: 'Integration keys' },
  { k: 'billing', l: 'Billing & payments' },
];

export function getTicketTypes(locale: AppLocale): TicketType[] {
  return locale === 'en' ? TICKET_TYPES_EN : TICKET_TYPES_RU;
}

export function ticketStatusLabel(status: string, locale: AppLocale): string {
  const ru: Record<string, string> = {
    answered: 'Получен ответ',
    closed: 'Завершено',
    in_review: 'На рассмотрении',
  };
  const en: Record<string, string> = {
    answered: 'Answer received',
    closed: 'Closed',
    in_review: 'In review',
  };
  const map = locale === 'en' ? en : ru;
  return map[status] || map.in_review;
}

export function getRightsDefs(locale: AppLocale): RightDef[] {
  return locale === 'en' ? RIGHTS_EN : RIGHTS_RU;
}
