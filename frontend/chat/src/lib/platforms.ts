/** Иконки лежат в /marketing/ на origin, не под /chat/. */

const MARKETING = '/marketing/'

export interface PlatformMeta {
  id: string
  name: string
  color: string
  iconUrl: string
}

const PLAT: Record<string, PlatformMeta> = {
  telegram: {
    id: 'tg',
    name: 'Telegram',
    color: '#2AABEE',
    iconUrl: `${MARKETING}telegram.svg`,
  },
  telegram_user: {
    id: 'tg',
    name: 'Telegram',
    color: '#2AABEE',
    iconUrl: `${MARKETING}telegram.svg`,
  },
  fanvue: {
    id: 'fv',
    name: 'Fanvue',
    color: '#7C4DFF',
    iconUrl: `${MARKETING}fanvue.svg`,
  },
  instagram: {
    id: 'ig',
    name: 'Instagram',
    color: '#E1306C',
    iconUrl: `${MARKETING}insta.svg`,
  },
}

export function platformMeta(platform: string | undefined | null): PlatformMeta {
  const key = String(platform || 'telegram').toLowerCase()
  return PLAT[key] ?? PLAT.telegram
}

export function platformSrcId(platform: string | undefined | null): string {
  return platformMeta(platform).id
}

export function platformIconImg(platform: string | undefined | null, size = 14): string {
  const p = platformMeta(platform)
  return `<img src="${p.iconUrl}" width="${size}" height="${size}" alt="" loading="lazy" decoding="async" style="display:block">`
}

export const SOURCE_TABS = [
  { id: 'all', name: 'Все сети' },
  { id: 'tg', name: 'Telegram', platform: ['telegram', 'telegram_user'] },
  { id: 'fv', name: 'Fanvue', platform: ['fanvue'] },
  { id: 'ig', name: 'Instagram', platform: ['instagram'] },
] as const
