/** Telegram Login Widget — загрузка и колбэк авторизации. */

import { apiFetch } from '../api'

export type TelegramLoginUser = {
  id: number
  first_name?: string
  last_name?: string
  username?: string
  photo_url?: string
  auth_date: number
  hash: string
}

declare global {
  interface Window {
    onTelegramAuth?: (user: TelegramLoginUser) => void
  }
}

export function mountTelegramLoginWidget(
  container: HTMLElement,
  botUsername: string,
  onAuth: (user: TelegramLoginUser) => void,
): () => void {
  const username = botUsername.trim().replace(/^@/, '')
  if (!username) return () => {}

  container.replaceChildren()
  const callbackName = `onTelegramAuth_${Math.random().toString(36).slice(2)}`
  ;(window as unknown as Record<string, (user: TelegramLoginUser) => void>)[callbackName] = onAuth

  const script = document.createElement('script')
  script.async = true
  script.src = 'https://telegram.org/js/telegram-widget.js?22'
  script.setAttribute('data-telegram-login', username)
  script.setAttribute('data-size', 'large')
  script.setAttribute('data-userpic', 'false')
  script.setAttribute('data-request-access', 'write')
  script.setAttribute('data-onauth', `${callbackName}(user)`)
  container.appendChild(script)

  return () => {
    container.replaceChildren()
    delete (window as unknown as Record<string, unknown>)[callbackName]
  }
}

export async function postTelegramAuth(
  path: '/api/auth/telegram' | '/api/auth/telegram/link',
  user: TelegramLoginUser,
  referralCode?: string | null,
): Promise<Response> {
  const body: TelegramLoginUser & { referral_code?: string } = { ...user }
  const ref = (referralCode || '').trim().toUpperCase()
  if (ref) body.referral_code = ref
  return apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
