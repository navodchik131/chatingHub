import { useEffect } from 'react'
import { getToken } from '../api'
import { goToWorkspace, workspaceAuthUrl } from './workspaceEntry'

/** /login и /en/login — редирект в OS-кабинет (форма входа в frontend-os). */
export function LoginPage() {
  useEffect(() => {
    if (getToken()) {
      goToWorkspace()
      return
    }
    window.location.replace(workspaceAuthUrl(window.location.search))
  }, [])

  return null
}
