import { ReactNode } from 'react';

type Props = {
  children: ReactNode;
  enabled?: boolean;
  onBack: () => void;
};

/** Android: passthrough — Reanimated native module disabled (startup crash workaround). */
export function SwipeBackWrapper({ children }: Props) {
  return <>{children}</>;
}
