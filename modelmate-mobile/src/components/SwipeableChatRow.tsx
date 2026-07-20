import { ReactNode, useEffect } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Gesture, GestureDetector, Pressable } from 'react-native-gesture-handler';
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import { color, font } from '@/src/styles/tokens';

const ACTION_W = 84;

type Props = {
  children: ReactNode;
  rowId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPress: () => void;
  onFolderPress: () => void;
  enabled?: boolean;
};

export function SwipeableChatRow({
  children,
  rowId,
  open,
  onOpenChange,
  onPress,
  onFolderPress,
  enabled = true,
}: Props) {
  const translateX = useSharedValue(0);

  useEffect(() => {
    translateX.value = withTiming(open ? -ACTION_W : 0, { duration: 200 });
  }, [open, translateX]);

  const close = () => onOpenChange(false);
  const openRow = () => onOpenChange(true);
  const handlePress = () => {
    if (open) {
      close();
      return;
    }
    onPress();
  };

  const pan = Gesture.Pan()
    .enabled(enabled)
    .activeOffsetX([-16, 16])
    .failOffsetY([-10, 10])
    .onUpdate((e) => {
      if (e.translationX < 0) {
        translateX.value = Math.max(e.translationX, -ACTION_W);
      } else if (open) {
        translateX.value = Math.min(-ACTION_W + e.translationX, 0);
      }
    })
    .onEnd((e) => {
      if (e.translationX < -36 || e.velocityX < -450) {
        translateX.value = withTiming(-ACTION_W, { duration: 180 });
        runOnJS(openRow)();
      } else {
        translateX.value = withTiming(0, { duration: 180 });
        runOnJS(close)();
      }
    });

  const tap = Gesture.Tap()
    .maxDuration(250)
    .onEnd(() => {
      runOnJS(handlePress)();
    });

  const gesture = enabled ? Gesture.Race(pan, tap) : Gesture.Tap().onEnd(() => runOnJS(onPress)());

  const rowStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  if (!enabled) {
    return (
      <GestureDetector gesture={gesture}>
        <View>{children}</View>
      </GestureDetector>
    );
  }

  return (
    <View style={styles.wrap}>
      <Pressable
        style={styles.action}
        onPress={() => {
          close();
          onFolderPress();
        }}
      >
        <Text style={styles.actionText}>В{'\n'}папку</Text>
      </Pressable>
      <GestureDetector gesture={gesture}>
        <Animated.View style={[styles.row, rowStyle]}>
          {children}
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: 'relative',
    overflow: 'hidden',
  },
  action: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    width: ACTION_W,
    backgroundColor: color.purple,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionText: {
    color: '#fff',
    fontFamily: font.bodyExtra,
    fontSize: 12,
    textAlign: 'center',
    lineHeight: 16,
  },
  row: {
    backgroundColor: color.bg,
  },
});
