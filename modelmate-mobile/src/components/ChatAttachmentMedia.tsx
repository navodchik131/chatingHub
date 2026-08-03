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

/** Chat attachments without expo-av — native libexpo-av.so crashes on RN 0.86 startup. */
export function ChatAttachmentMedia({ url, mime, style, withText }: Props) {
  const resolved = resolveMediaUrl(url);
  const kind = attachmentMediaKind(mime);

  if (!resolved) return null;

  const wrapStyle = [styles.wrap, withText && styles.wrapWithText, style];

  return (
    <View style={wrapStyle}>
      <RemoteImage
        uri={resolved}
        style={styles.media}
        contentFit={kind === 'gif' || kind === 'video' ? 'contain' : 'cover'}
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
