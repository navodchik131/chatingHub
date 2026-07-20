import { ReactNode } from 'react';
import { StyleSheet } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';

type Props = {
  children: ReactNode;
  enabled?: boolean;
  onBack: () => void;
};

const EDGE_WIDTH = 28;

export function SwipeBackWrapper({ children, enabled = true, onBack }: Props) {
  const translateX = useSharedValue(0);

  const pan = Gesture.Pan()
    .activeOffsetX(10)
    .failOffsetX(-8)
    .failOffsetY([-28, 28])
    .onUpdate((e) => {
      if (e.translationX > 0) {
        translateX.value = Math.min(e.translationX * 0.4, 56);
      }
    })
    .onEnd((e) => {
      if (e.translationX > 64 || e.velocityX > 700) {
        runOnJS(onBack)();
      }
      translateX.value = withTiming(0, { duration: 160 });
    });

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  if (!enabled) {
    return <>{children}</>;
  }

  return (
    <Animated.View style={[styles.root, animatedStyle]}>
      {children}
      <GestureDetector gesture={pan}>
        <Animated.View style={styles.edge} />
      </GestureDetector>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  edge: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    width: EDGE_WIDTH,
    zIndex: 20,
  },
});
