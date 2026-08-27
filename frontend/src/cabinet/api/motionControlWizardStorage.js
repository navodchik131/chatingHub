/** Сессионное сохранение шагов Motion Control wizard (переключение вкладок кабинета). */

const STORAGE_VERSION = 1;

export function mcWizardStorageKey(backend, modelId) {
  const b = backend === 'evolink' ? 'evolink' : 'wavespeed';
  const mid = modelId != null && modelId !== '' ? String(modelId) : 'none';
  return `mm.mcWizard.${b}.${mid}`;
}

export function loadMcWizardState(key) {
  if (typeof sessionStorage === 'undefined' || !key) return null;
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || parsed.version !== STORAGE_VERSION) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveMcWizardState(key, snapshot) {
  if (typeof sessionStorage === 'undefined' || !key) return;
  try {
    sessionStorage.setItem(key, JSON.stringify({ version: STORAGE_VERSION, ...snapshot }));
  } catch {
    /* quota / private mode */
  }
}

export function clearMcWizardState(key) {
  if (typeof sessionStorage === 'undefined' || !key) return;
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}
