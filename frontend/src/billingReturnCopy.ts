import i18n, { CHAT_NS } from './i18n'

/** Сообщение после редиректа с ЮKassa (`return_url` с query `billing=`). */
export function billingReturnCopy(raw: string | null): {
  variant: 'success' | 'warn' | 'error'
  title: string
  body: string
} | null {
  const k = (raw || '').trim().toLowerCase()
  if (!k) return null
  if (k === 'success' || k === 'ok' || k === 'paid') {
    return {
      variant: 'success',
      title: i18n.t('billingReturn.successTitle', { ns: CHAT_NS }),
      body: i18n.t('billingReturn.successBody', { ns: CHAT_NS }),
    }
  }
  if (k === 'cancel' || k === 'cancelled' || k === 'canceled') {
    return {
      variant: 'warn',
      title: i18n.t('billingReturn.cancelTitle', { ns: CHAT_NS }),
      body: i18n.t('billingReturn.cancelBody', { ns: CHAT_NS }),
    }
  }
  if (k === 'fail' || k === 'failed' || k === 'error') {
    return {
      variant: 'error',
      title: i18n.t('billingReturn.failTitle', { ns: CHAT_NS }),
      body: i18n.t('billingReturn.failBody', { ns: CHAT_NS }),
    }
  }
  return {
    variant: 'warn',
    title: i18n.t('billingReturn.unknownTitle', { ns: CHAT_NS }),
    body: i18n.t('billingReturn.unknownBody', { ns: CHAT_NS }),
  }
}
