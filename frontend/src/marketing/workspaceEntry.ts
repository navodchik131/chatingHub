/** Полный переход в OS-кабинет (nginx отдаёт frontend-os, не React Router). */
export const WORKSPACE_URL = '/workspace/'

export function goToWorkspace(): void {
  window.location.assign(WORKSPACE_URL)
}
