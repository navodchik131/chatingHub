import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { useState } from 'react';
import { ActivityIndicator, StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { resolveMediaUrl } from '@/src/api/config';
import { color, gradients } from '@/src/styles/tokens';

type Props = {
  uri?: string | null;
  style?: StyleProp<ViewStyle>;
  gradIndex?: number;
  pending?: boolean;
  contentFit?: 'cover' | 'contain' | 'fill';
};

export function RemoteImage({
  uri,
  style,
  gradIndex = 0,
  pending = false,
  contentFit = 'cover',
}: Props) {
  const [failed, setFailed] = useState(false);
  const resolved = resolveMediaUrl(uri);
  const [a, b] = gradients[gradIndex % gradients.length];
  const showImage = Boolean(resolved) && !failed;

  if (!showImage) {
    return (
      <LinearGradient colors={[a, b]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={style}>
        {pending ? (
          <View style={styles.pendingOverlay}>
            <ActivityIndicator color={color.lime} size="small" />
          </View>
        ) : null}
      </LinearGradient>
    );
  }

  return (
    <View style={style}>
      <Image
        source={{ uri: resolved }}
        style={StyleSheet.absoluteFill}
        contentFit={contentFit}
        cachePolicy="memory-disk"
        recyclingKey={(resolved || '').split('?')[0] || resolved}
        onError={() => setFailed(true)}
      />
      {pending ? (
        <View style={styles.pendingOverlay}>
          <ActivityIndicator color={color.lime} size="small" />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  pendingOverlay: {
    ...StyleSheet.absoluteFill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(6,7,9,0.55)',
  },
});
