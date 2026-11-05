import { ReactNode } from 'react';

type Props = {
  children: ReactNode;
  enabled?: boolean;
  onBack: () => void;
};

/** Web preview: без edge-swipe жеста. */
export function SwipeBackWrapper({ children }: Props) {
  return <>{children}</>;
}
