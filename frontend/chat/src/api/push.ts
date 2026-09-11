/** Web Push для Unibox — /api/push/* + VAPID. */

import { apiJson } from './client'

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const pad = '='.repeat((4 - (base64.length % 4)) % 4)
  const b64 = (base64 + pad).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(b64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

export async function registerChatPush(): Promise<'granted' | 'denied' | 'unsupported' | 'server-off'> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return 'unsupported'

  let publicKey: string
  try {
    const r = await apiJson<{ public_key: string }>('/api/push/vapid-public-key')
    publicKey = r.public_key
  } catch {
    return 'server-off'
  }

  const perm = await Notification.requestPermission()
  if (perm !== 'granted') return 'denied'

  const reg = await navigator.serviceWorker.ready
  let sub = await reg.pushManager.getSubscription()
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    })
  }

  const json = sub.toJSON()
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) return 'unsupported'

  await apiJson('/api/push/subscribe', {
    method: 'POST',
    body: JSON.stringify({
      endpoint: json.endpoint,
      keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    }),
  })

  return 'granted'
}

export async function unregisterChatPush(): Promise<void> {
  if (!('serviceWorker' in navigator)) return
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  if (!sub) return
  const endpoint = sub.endpoint
  await sub.unsubscribe().catch(() => {})
  await apiJson('/api/push/unsubscribe', {
    method: 'POST',
    body: JSON.stringify({ endpoint }),
  }).catch(() => {})
}

export function pushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

export function pushPermission(): NotificationPermission | 'unsupported' {
  if (!pushSupported()) return 'unsupported'
  return Notification.permission
}
