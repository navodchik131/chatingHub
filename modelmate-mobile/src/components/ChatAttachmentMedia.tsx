import { Video, ResizeMode } from 'expo-av';
import { useEffect, useRef, useState } from 'react';
import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { attachmentMediaKind } from '@/src/api/helpers';
import { resolveMediaUrl } from '@/src/api/config';
import { RemoteImage } from '@/src/components/RemoteImage';

type Props = {
  url?: string | null;
  mime?: string | null;
  style?: StyleProp<ViewStyle>;
  withText?: boolean;
};

export function ChatAttachmentMedia({ url, mime, style, withText }: Props) {
  const resolved = resolveMediaUrl(url);
  const kind = attachmentMediaKind(mime);
  const videoRef = useRef<Video>(null);
  const [videoFailed, setVideoFailed] = useState(false);

  useEffect(() => {
    if (kind !== 'video' && kind !== 'gif') return;
    void videoRef.current?.playAsync().catch(() => setVideoFailed(true));
  }, [kind, resolved]);

  if (!resolved) return null;

  const wrapStyle = [styles.wrap, withText && styles.wrapWithText, style];

  if ((kind === 'video' || kind === 'gif') && !videoFailed) {
    return (
      <View style={wrapStyle}>
        <Video
          ref={videoRef}
          source={{ uri: resolved }}
          style={styles.media}
          resizeMode={ResizeMode.COVER}
          isLooping
          isMuted
          shouldPlay
          useNativeControls={false}
          onError={() => setVideoFailed(true)}
        />
      </View>
    );
  }

  return (
    <View style={wrapStyle}>
      <RemoteImage
        uri={resolved}
        style={styles.media}
        contentFit={kind === 'gif' ? 'contain' : 'cover'}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: 10,
    overflow: 'hidden',
  },
  wrapWithText: {
    marginBottom: 8,
  },
  media: {
    width: 220,
    height: 220,
    borderRadius: 10,
    backgroundColor: '#2A2D33',
  },
});
