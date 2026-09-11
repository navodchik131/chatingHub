import { useEffect, useState } from 'react'
import { apiFetch, getToken, setToken } from '../api'

export type AuthSessionStatus = 'checking' | 'authenticated' | 'anonymous'

/** Проверка сессии через /api/auth/me (Bearer + HttpOnly cookie). */
export function useAuthSessionGate(): AuthSessionStatus {
  const [status, setStatus] = useState<AuthSessionStatus>('checking')

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const token = getToken()
      let r = await apiFetch('/api/auth/me')
      if (cancelled) return
      if (r.ok) {
        setStatus('authenticated')
        return
      }
      // Stale JWT в LS — сброс и повтор только с cookie
      if (token) {
        setToken(null)
        r = await fetch('/api/auth/me', { credentials: 'include' })
        if (cancelled) return
        if (r.ok) {
          setStatus('authenticated')
          return
        }
      }
      setStatus('anonymous')
    })()

    return () => {
      cancelled = true
    }
  }, [])

  return status
}
