/* Unibox PWA — scope /chat/, push о новых сообщениях */
/* global self, clients */

const CACHE_SHELL = 'unibox-shell-v1'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_SHELL).then((cache) =>
      cache.addAll(['/chat/', '/chat/index.html']),
    ),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_SHELL).map((k) => caches.delete(k))),
    ).then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (url.origin !== self.location.origin) return
  if (!url.pathname.startsWith('/chat/')) return
  if (url.pathname.startsWith('/chat/assets/')) return
  if (event.request.method !== 'GET') return

  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res.ok && url.pathname.endsWith('index.html')) {
          const copy = res.clone()
          caches.open(CACHE_SHELL).then((c) => c.put('/chat/index.html', copy))
        }
        return res
      })
      .catch(() => caches.match(event.request).then((r) => r || caches.match('/chat/index.html'))),
  )
})

self.addEventListener('push', (event) => {
  const fallback = { title: 'Новое сообщение', body: '', url: '/chat/' }
  let data = { ...fallback }
  try {
    if (event.data) data = { ...fallback, ...event.data.json() }
  } catch {
    /* text payload */
  }
  let target = '/chat/'
  if (data.url) {
    const raw = String(data.url)
    if (raw.startsWith('/chat')) target = raw
    else {
      try {
        const u = new URL(raw)
        if (u.pathname.startsWith('/chat')) target = u.pathname + u.search
      } catch {
        /* ignore */
      }
    }
  }
  event.waitUntil(
    self.registration.showNotification(data.title || fallback.title, {
      body: data.body || '',
      data: { url: target },
      icon: '/assets/logo-m.jpeg',
      badge: '/favicon.ico',
      tag: data.tag || 'unibox-message',
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/chat/'
  const openUrl = new URL(url, self.location.origin).href
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url && c.url.includes('/chat/') && 'focus' in c) {
          c.navigate(openUrl)
          return c.focus()
        }
      }
      if (clients.openWindow) return clients.openWindow(openUrl)
    }),
  )
})
