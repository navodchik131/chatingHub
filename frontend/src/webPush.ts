import { apiFetch } from './api'

export function webPushEnvironmentOk(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

export function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  const out = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; i += 1) {
    out[i] = rawData.charCodeAt(i)
  }
  return out
}

const swUrl = () => new URL('sw.js', import.meta.env.BASE_URL).href
const swScope = () => import.meta.env.BASE_URL || '/'

export async function getPushSubscriptionState(): Promise<PushSubscription | null> {
  if (!webPushEnvironmentOk()) return null
  const reg = await navigator.serviceWorker.getRegistration(swScope())
  if (!reg) return null
  return reg.pushManager.getSubscription()
}

export async function subscribeWebPush(): Promise<void> {
  if (!webPushEnvironmentOk()) throw new Error('Push не поддерживается в этом браузере')
  const perm = await Notification.requestPermission()
  if (perm === 'denied') throw new Error('Уведомления запрещены')
  if (perm !== 'granted') throw new Error('Нужен доступ к уведомлениям')
  const kr = await apiFetch('/api/push/vapid-public-key')
  if (kr.status === 503) throw new Error('Сервер не настроил VAPID (ключи в .env)')
  if (!kr.ok) throw new Error('Не удалось получить ключ VAPID')
  const { public_key: pub } = (await kr.json()) as { public_key: string }
  const reg = await navigator.serviceWorker.register(swUrl(), { scope: swScope() })
  await reg.update()
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(pub) as BufferSource,
  })
  const j = sub.toJSON() as { endpoint: string; keys?: { p256dh?: string; auth?: string } }
  if (!j.endpoint || !j.keys?.p256dh || !j.keys?.auth) throw new Error('Некорректная подписка')
  const r = await apiFetch('/api/push/subscribe', {
    method: 'POST',
    body: JSON.stringify({ endpoint: j.endpoint, keys: { p256dh: j.keys.p256dh, auth: j.keys.auth } }),
  })
  if (!r.ok) throw new Error('Не удалось сохранить подписку на сервере')
}

export async function unsubscribeWebPush(): Promise<void> {
  if (!webPushEnvironmentOk()) return
  const reg = await navigator.serviceWorker.getRegistration(swScope())
  if (!reg) return
  const sub = await reg.pushManager.getSubscription()
  if (!sub) return
  const endpoint = sub.endpoint
  const r = await apiFetch('/api/push/unsubscribe', {
    method: 'POST',
    body: JSON.stringify({ endpoint }),
  })
  if (!r.ok) {
    /* всё равно снимаем локально */
  }
  await sub.unsubscribe()
}
