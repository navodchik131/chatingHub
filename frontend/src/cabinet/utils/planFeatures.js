/** Краткие пункты тарифа для карточек кабинета (фиксированная длина → равная высота). */

/**
 * @param {'ru'|'en'} lang
 * @param {'solo'|'pro'|'studio'} tier
 * @param {'standard'|'pro'} billing
 * @param {'month'|'year'} period
 * @param {number} monthlyCredits
 */
export function cabinetPlanFeatures(lang, tier, billing, period, monthlyCredits) {
  const ru = lang === 'ru'
  const users = { solo: 1, pro: 3, studio: 10 }[tier] ?? 1
  const models = { solo: 1, pro: 3, studio: 10 }[tier] ?? 1
  const monthly = monthlyCredits || { solo: 150, pro: 400, studio: 1200 }[tier] || 150
  const creditsTotal = period === 'year' ? monthly * 12 : monthly

  const usersLine = ru
    ? users === 1 ? '1 оператор' : `${users} оператора`
    : users === 1 ? '1 operator' : `${users} operators`
  const modelsLine = ru
    ? models === 1 ? '1 персонаж' : `${models} персонажа`
    : models === 1 ? '1 character' : `${models} characters`

  let creditsLine
  if (billing === 'pro') {
    creditsLine = ru ? 'Свой API-ключ WaveSpeed' : 'Own WaveSpeed API key'
  } else if (period === 'year') {
    creditsLine = ru
      ? `${creditsTotal} кр. / год (${monthly}/мес)`
      : `${creditsTotal} cr / year (${monthly}/mo)`
  } else {
    creditsLine = ru ? `${creditsTotal} кредитов / мес` : `${creditsTotal} credits / mo`
  }

  const chatLine = ru ? 'Диалоги + перевод' : 'Chats + translation'
  const extra =
    tier === 'studio'
      ? (ru ? 'Без лимита диалогов' : 'Unlimited dialogs')
      : tier === 'pro'
        ? (ru ? 'Команда и KPI' : 'Team & KPI')
        : (ru ? 'Студия картинок и видео' : 'Image & video studio')

  // Всегда 5 пунктов — карточки одной высоты
  return [usersLine, modelsLine, creditsLine, chatLine, extra]
}
