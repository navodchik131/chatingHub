/* global self, clients */
self.addEventListener('push', (event) => {
  const fallback = { title: 'Новое сообщение', body: '', url: '/' }
  let data = { ...fallback }
  try {
    if (event.data) {
      const j = event.data.json()
      data = { ...fallback, ...j }
    }
  } catch {
    /* text payload */
  }
  event.waitUntil(
    self.registration.showNotification(data.title || fallback.title, {
      body: data.body || '',
      data: { url: data.url || '/' },
      icon: new URL('favicon.svg', self.location).href,
      tag: 'chating-msg',
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification.data && event.notification.data.url
  const openUrl = url || self.location.origin + '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if (c.url && 'focus' in c) return c.focus()
      }
      if (self.clients.openWindow) return self.clients.openWindow(openUrl)
    }),
  )
})
