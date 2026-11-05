import { ReactNode } from 'react';
import { Pressable } from 'react-native';

type Props = {
  children: ReactNode;
  rowId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPress: () => void;
  onFolderPress: () => void;
  enabled?: boolean;
};

/** Web preview: без swipe-actions, обычный tap. */
export function SwipeableChatRow({ children, onPress }: Props) {
  return <Pressable onPress={onPress}>{children}</Pressable>;
}
