/** Заглушка: onboarding wizard пока не перенесён в единое SPA. */
export function markFirstGenWizardPending(): void {
  try {
    sessionStorage.setItem('mm_first_gen_wizard_pending', '1')
  } catch {
    /* ignore */
  }
}
