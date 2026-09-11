/** Регистрация SW Unibox — scope /chat/ или / на chat.* */

import { chatScopePath } from '../lib/chatBase'

export async function registerChatServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) return null
  const scope = chatScopePath()
  try {
    return await navigator.serviceWorker.register(`${scope}sw.js`, { scope })
  } catch (e) {
    console.warn('Unibox SW register failed', e)
    return null
  }
}
