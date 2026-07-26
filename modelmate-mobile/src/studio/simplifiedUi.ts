import type { NavigationState } from '@/src/navigation/types';

export const SIMPLIFIED_CONTENT_MODE = 'nsfw' as const;
export const SIMPLIFIED_AI_ENGINE = 'Seedream 5 Pro';

export function isUiSimplified(me?: { ui_simplified?: boolean } | null): boolean {
  return me?.ui_simplified !== false;
}

export function effectiveStudioNav(
  nav: Pick<NavigationState, 'contentMode' | 'aiEngine'>,
  simplified: boolean,
): Pick<NavigationState, 'contentMode' | 'aiEngine'> {
  if (!simplified) {
    return { contentMode: nav.contentMode, aiEngine: nav.aiEngine };
  }
  return { contentMode: SIMPLIFIED_CONTENT_MODE, aiEngine: SIMPLIFIED_AI_ENGINE };
}

export function effectiveNavState(nav: NavigationState, simplified: boolean): NavigationState {
  if (!simplified) return nav;
  return { ...nav, contentMode: SIMPLIFIED_CONTENT_MODE, aiEngine: SIMPLIFIED_AI_ENGINE };
}
