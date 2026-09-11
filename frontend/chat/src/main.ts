import { getToken, redirectToLogin } from './api/client'
import { ChatController } from './store/ChatController'
import { UniboxApp } from './ui/App'

async function boot(): Promise<void> {
  if (!getToken()) {
    redirectToLogin()
    return
  }

  const ctrl = new ChatController()
  const app = new UniboxApp(ctrl)

  try {
    await ctrl.init()
    await app.mount()

    const params = new URLSearchParams(window.location.search)
    const conv = Number(params.get('conv'))
    if (conv > 0) {
      await app.openChat(conv)
      params.delete('conv')
      const qs = params.toString()
      window.history.replaceState(null, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`)
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    document.body.innerHTML = `<div style="padding:24px;font:15px/1.5 system-ui;color:#c00">
      Не удалось загрузить чат: ${msg}</div>`
  }

  window.addEventListener('beforeunload', () => ctrl.destroy())
}

void boot()
