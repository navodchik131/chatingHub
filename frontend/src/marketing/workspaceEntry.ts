/** Полный переход в OS-кабинет (nginx отдаёт frontend-os, не React Router). */
export const WORKSPACE_URL = '/workspace/'

export function isWorkspaceAuthPath(path: string): boolean {
  const base = path.split('?')[0]?.replace(/\/$/, '') || '/'
  return base === '/workspace' || base === '/login' || base === '/en/login'
}

export function workspaceAuthUrl(search = ''): string {
  if (!search) return WORKSPACE_URL
  return WORKSPACE_URL + (search.startsWith('?') ? search : `?${search}`)
}

export function goToWorkspace(): void {
  window.location.assign(WORKSPACE_URL)
}

export function goToWorkspaceLogin(): void {
  window.location.assign(workspaceAuthUrl(window.location.search))
}
