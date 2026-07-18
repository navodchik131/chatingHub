import { useEffect, useState } from 'react'
import { apiFetch, getToken, setToken } from '../api'

export type AuthSessionStatus = 'checking' | 'authenticated' | 'anonymous'

/** Проверка токена через /api/auth/me — без мигания login при живой сессии. */
export function useAuthSessionGate(): AuthSessionStatus {
  const [status, setStatus] = useState<AuthSessionStatus>(() =>
    getToken() ? 'checking' : 'anonymous',
  )

  useEffect(() => {
    const token = getToken()
    if (!token) {
      setStatus('anonymous')
      return
    }

    let cancelled = false
    void (async () => {
      const r = await apiFetch('/api/auth/me')
      if (cancelled) return
      if (r.ok) {
        setStatus('authenticated')
        return
      }
      setToken(null)
      setStatus('anonymous')
    })()

    return () => {
      cancelled = true
    }
  }, [])

  return status
}
