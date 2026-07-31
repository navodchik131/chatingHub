import { Video, ResizeMode } from 'expo-av';
import { useEffect, useRef, useState } from 'react';
import { StyleProp, StyleSheet, View, ViewStyle } from 'react-native';
import { attachmentMediaKind } from '@/src/api/helpers';
import { resolveMediaUrl } from '@/src/api/config';
import { RemoteImage } from '@/src/components/RemoteImage';

type Props = {
  url?: string | null;
  mime?: string | null;
  kind?: string | null;
  style?: StyleProp<ViewStyle>;
  withText?: boolean;
};

const VIDEO_NOTE_SIZE = 200;

export function ChatAttachmentMedia({ url, mime, kind, style, withText }: Props) {
  const resolved = resolveMediaUrl(url);
  const isVideoNote = kind === 'video_note';
  const mediaKind = attachmentMediaKind(mime);
  const videoRef = useRef<Video>(null);
  const [videoFailed, setVideoFailed] = useState(false);

  useEffect(() => {
    if (mediaKind !== 'video' && mediaKind !== 'gif') return;
    void videoRef.current?.playAsync().catch(() => setVideoFailed(true));
  }, [mediaKind, resolved]);

  if (!resolved) return null;

  const wrapStyle = [
    styles.wrap,
    isVideoNote && styles.wrapVideoNote,
    withText && styles.wrapWithText,
    style,
  ];
  const mediaStyle = [
    styles.media,
    isVideoNote && styles.mediaVideoNote,
  ];

  if ((mediaKind === 'video' || mediaKind === 'gif') && !videoFailed) {
    return (
      <View style={wrapStyle}>
        <Video
          ref={videoRef}
          source={{ uri: resolved }}
          style={mediaStyle}
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
        style={mediaStyle}
        contentFit={mediaKind === 'gif' ? 'contain' : 'cover'}
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
  wrapVideoNote: {
    borderRadius: VIDEO_NOTE_SIZE / 2,
  },
  media: {
    width: 220,
    height: 220,
    borderRadius: 10,
    backgroundColor: '#2A2D33',
  },
  mediaVideoNote: {
    width: VIDEO_NOTE_SIZE,
    height: VIDEO_NOTE_SIZE,
    borderRadius: VIDEO_NOTE_SIZE / 2,
  },
});
