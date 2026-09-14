import { getToken } from './client'
import type { RealtimeEvent } from '../types'

export type RealtimeConnection = {
  close: () => void
}

export function connectRealtime(
  onEvent: (ev: RealtimeEvent) => void,
  onOpen?: () => void,
): RealtimeConnection {
  const token = getToken()
  if (!token) return { close: () => {} }

  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  let closed = false
  let ws: WebSocket | null = null
  let retryMs = 1500

  const connect = () => {
    if (closed) return
    ws = new WebSocket(`${proto}://${window.location.host}/api/ws?token=${encodeURIComponent(token)}`)
    ws.addEventListener('open', () => {
      retryMs = 1500
      onOpen?.()
    })
    ws.addEventListener('message', (ev) => {
      try {
        onEvent(JSON.parse(String(ev.data)) as RealtimeEvent)
      } catch {
        /* ignore malformed */
      }
    })
    ws.addEventListener('close', () => {
      if (closed) return
      window.setTimeout(connect, retryMs)
      retryMs = Math.min(retryMs * 1.4, 12000)
    })
  }

  connect()

  return {
    close: () => {
      closed = true
      try {
        ws?.close()
      } catch {
        /* ignore */
      }
    },
  }
}
