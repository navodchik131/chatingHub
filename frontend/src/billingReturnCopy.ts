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
      title: 'Оплата принята',
      body:
        'Если платёж прошёл успешно, подписка или кредиты обновятся через короткое время (до нескольких минут). Зайдите в кабинет и при необходимости откройте «Тариф и пополнение».',
    }
  }
  if (k === 'cancel' || k === 'cancelled' || k === 'canceled') {
    return {
      variant: 'warn',
      title: 'Оплата не завершена',
      body: 'Вы закрыли страницу оплаты или отменили попытку. Обычно средства при этом не списываются.',
    }
  }
  if (k === 'fail' || k === 'failed' || k === 'error') {
    return {
      variant: 'error',
      title: 'Не удалось подтвердить оплату',
      body: 'Если деньги списались, сохраните чек и обратитесь в поддержку. Иначе повторите оплату из кабинета.',
    }
  }
  return {
    variant: 'warn',
    title: 'Возврат после оплаты',
    body: 'Проверьте в кабинете статус подписки и баланс кредитов.',
  }
}
