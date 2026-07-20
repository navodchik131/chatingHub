import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from 'react';
import {
  defaultNavState,
  NavigationState,
  TabRoot,
} from '@/src/navigation/types';

type NavContextValue = NavigationState & {
  cur: string;
  push: (id: string) => void;
  pop: () => void;
  resetTo: (id: TabRoot | 'admin') => void;
  logout: () => void;
  patch: (partial: Partial<NavigationState>) => void;
  openThread: (chatIdx: number) => void;
  startGen: (key: string) => void;
  regen: (key: string) => void;
};

const NavContext = createContext<NavContextValue | null>(null);

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<NavigationState>(defaultNavState);

  const cur = state.stack[state.stack.length - 1] ?? 'overview';

  const push = useCallback((id: string) => {
    setState((s) => ({ ...s, stack: [...s.stack, id] }));
  }, []);

  const pop = useCallback(() => {
    setState((s) => ({
      ...s,
      stack: s.stack.length > 1 ? s.stack.slice(0, -1) : s.stack,
    }));
  }, []);

  const resetTo = useCallback((id: TabRoot | 'admin') => {
    setState((s) => ({ ...s, stack: [id] }));
  }, []);

  const logout = useCallback(() => {
    setState((s) => ({ ...s, stack: ['auth'] }));
  }, []);

  const patch = useCallback((partial: Partial<NavigationState>) => {
    setState((s) => ({ ...s, ...partial }));
  }, []);

  const openThread = useCallback((chatIdx: number) => {
    setState((s) => ({ ...s, chatIdx, stack: [...s.stack, 'thread'] }));
  }, []);

  const startGen = useCallback((key: string) => {
    setState((s) => ({ ...s, genStatus: { ...s.genStatus, [key]: 'loading' } }));
  }, []);

  const regen = useCallback((key: string) => {
    setState((s) => ({ ...s, genStatus: { ...s.genStatus, [key]: 'loading' } }));
  }, []);

  const value = useMemo(
    () => ({
      ...state,
      cur,
      push,
      pop,
      resetTo,
      logout,
      patch,
      openThread,
      startGen,
      regen,
    }),
    [state, cur, push, pop, resetTo, logout, patch, openThread, startGen, regen],
  );

  return <NavContext.Provider value={value}>{children}</NavContext.Provider>;
}

export function useNav() {
  const ctx = useContext(NavContext);
  if (!ctx) throw new Error('useNav must be used within NavigationProvider');
  return ctx;
}
