import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { RemoteImage } from '@/src/components/RemoteImage';
import { archiveThumbUrl } from '@/src/api/media';
import type { StudioGenerationOut } from '@/src/api/types';
import { color, font } from '@/src/styles/tokens';

type Props = {
  items: StudioGenerationOut[];
  selectedId?: number | null;
  onSelect: (id: number) => void;
  uploadLabel: string;
  onUpload: () => void;
  previewUri?: string;
};

export function StudioSlotInput({
  items,
  selectedId,
  onSelect,
  uploadLabel,
  onUpload,
  previewUri,
}: Props) {
  const picked = selectedId != null ? items.find((g) => g.id === selectedId) : undefined;
  const preview = previewUri || (picked ? archiveThumbUrl(picked) : '');

  return (
    <View style={styles.wrap}>
      <Pressable style={[styles.preview, preview ? styles.previewFilled : null]} onPress={onUpload}>
        {preview ? (
          <Image source={{ uri: preview }} style={styles.previewImg} resizeMode="cover" />
        ) : (
          <Text style={styles.uploadText}>{uploadLabel}</Text>
        )}
      </Pressable>
      {items.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
          {items.slice(0, 12).map((item, i) => {
            const thumb = archiveThumbUrl(item);
            const active = selectedId === item.id;
            return (
              <Pressable
                key={item.id}
                style={[styles.thumb, active && styles.thumbActive]}
                onPress={() => onSelect(item.id)}
              >
                {thumb ? (
                  <RemoteImage uri={thumb} style={StyleSheet.absoluteFill} gradIndex={i % 6} contentFit="cover" />
                ) : (
                  <View style={[StyleSheet.absoluteFill, { backgroundColor: color.card2 }]} />
                )}
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 8 },
  preview: {
    aspectRatio: 3 / 4,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    backgroundColor: 'rgba(255,255,255,0.03)',
  },
  previewFilled: { borderStyle: 'solid', borderColor: 'rgba(215,244,82,0.35)' },
  previewImg: { width: '100%', height: '100%' },
  uploadText: { fontFamily: font.body, fontSize: 11, color: color.dim, textAlign: 'center', paddingHorizontal: 8 },
  row: { gap: 6, paddingVertical: 2 },
  thumb: {
    width: 56,
    height: 74,
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  thumbActive: { borderColor: color.lime },
});
