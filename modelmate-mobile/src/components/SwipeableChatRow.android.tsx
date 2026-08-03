import { ReactNode } from 'react';
import { Pressable, View } from 'react-native';

type Props = {
  children: ReactNode;
  rowId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPress: () => void;
  onFolderPress: () => void;
  enabled?: boolean;
};

/** Android: tap-only row — swipe actions need Reanimated (disabled on Android). */
export function SwipeableChatRow({ children, onPress, enabled = true }: Props) {
  return (
    <Pressable onPress={onPress} disabled={!enabled}>
      <View>{children}</View>
    </Pressable>
  );
}
