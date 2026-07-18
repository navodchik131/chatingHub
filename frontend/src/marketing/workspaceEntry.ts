/** Production path to кабинету. В едином SPA — тот же origin. */
export const WORKSPACE_URL = '/workspace'

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
