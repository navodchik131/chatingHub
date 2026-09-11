/** Production path to кабинету. В едином SPA — тот же origin. */

import type { NavigateFunction } from 'react-router-dom'

export const WORKSPACE_URL = '/workspace'

/** Unibox — отдельное SPA, только полная перезагрузка (не React Router). */
export const CHAT_APP_URL = '/chat/'

export function isExternalAppPath(path: string): boolean {
  return path === '/chat' || path.startsWith('/chat/')
}

export function goToChat(): void {
  window.location.assign(CHAT_APP_URL)
}

/** После login/register: внешние SPA — assign, кабинет/маркетинг — navigate. */
export function goAfterAuthNext(next: string, navigate: NavigateFunction): void {
  if (isExternalAppPath(next)) {
    const target = next.endsWith('/') ? next : `${next}/`
    window.location.assign(target)
    return
  }
  navigate(next, { replace: true })
}



export function resolveWorkspaceUrl(pathname = WORKSPACE_URL, search = '', hash = ''): string {

  const path = pathname.startsWith('/') ? pathname : `/${pathname}`

  return `${path}${search}${hash}`

}



export function isWorkspaceAuthPath(path: string): boolean {

  const base = path.split('?')[0]?.replace(/\/$/, '') || '/'

  return base === '/workspace' || base === '/login' || base === '/en/login'

}



export function workspaceAuthUrl(search = ''): string {

  const q = search ? (search.startsWith('?') ? search : `?${search}`) : ''

  return `/login${q}`

}



export function goToWorkspace(): void {

  window.location.assign(resolveWorkspaceUrl(WORKSPACE_URL))

}



export function goToWorkspaceLogin(): void {

  window.location.assign(workspaceAuthUrl(window.location.search))

}



export function resolveAdminUrl(pathname = '/admin'): string {

  const path = pathname.startsWith('/') ? pathname : `/${pathname}`

  return path

}



export function goToAdmin(): void {

  window.location.assign(resolveAdminUrl())

}


