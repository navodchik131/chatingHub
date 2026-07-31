import { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Video, ResizeMode } from 'expo-av';
import { IcoPlay, IcoSendPlane, IcoUpload, IcoVideoNote } from '@/src/components/Icons';
import { RemoteImage } from '@/src/components/RemoteImage';
import { color } from '@/src/styles/tokens';
import { isArchivePending } from '@/src/api/media';
import { videoNoteSendPayload, type VideoArchiveItem } from '@/src/studio/videoArchive';
import type { LocalFile } from '@/src/api/types';

type ArchiveTile = {
  id: number;
  imageUrl?: string | null;
  videoUrl?: string | null;
  gradIndex?: number;
  pending?: boolean;
  raw?: VideoArchiveItem;
};

type Props = {
  visible: boolean;
  onClose: () => void;
  archiveTiles: ArchiveTile[];
  uploadFile: LocalFile | null;
  onPickUpload: () => void;
  onClearUpload: () => void;
  onSelectArchive: (tile: ArchiveTile) => void;
  selectedTileId: number | null;
  onSend: () => void;
  sending?: boolean;
  t: {
    dlgVideoNoteTitle: string;
    dlgVideoNoteArchive: string;
    dlgVideoNoteArchiveEmpty: string;
    dlgVideoNoteOr: string;
    dlgVideoNoteUpload: string;
    dlgVideoNoteUploadHint: string;
    dlgVideoNoteSending: string;
    studioVideoNoteSendLong: string;
  };
};

function ArchiveThumb({
  tile,
  selected,
  onPress,
}: {
  tile: ArchiveTile;
  selected: boolean;
  onPress: () => void;
}) {
  const [duration, setDuration] = useState('');
  return (
    <Pressable
      style={[styles.thumb, selected && styles.thumbSelected]}
      onPress={onPress}
    >
      {tile.videoUrl ? (
        <Video
          source={{ uri: tile.videoUrl }}
          style={StyleSheet.absoluteFill}
          resizeMode={ResizeMode.COVER}
          isMuted
          shouldPlay={false}
          onLoad={(status) => {
            if (!status.isLoaded) return;
            const d = status.durationMillis ? status.durationMillis / 1000 : 0;
            if (d > 0) setDuration(`${Math.round(d)}s`);
          }}
        />
      ) : (
        <RemoteImage
          uri={tile.imageUrl}
          style={styles.thumbImg}
          gradIndex={tile.gradIndex ?? 0}
        />
      )}
      <View style={styles.playBadge}>
        <IcoPlay size={10} stroke="#fff" />
      </View>
      {duration ? <Text style={styles.duration}>{duration}</Text> : null}
    </Pressable>
  );
}

export function DialogVideoNoteModal({
  visible,
  onClose,
  archiveTiles,
  uploadFile,
  onPickUpload,
  onClearUpload,
  onSelectArchive,
  selectedTileId,
  onSend,
  sending = false,
  t,
}: Props) {
  const readyTiles = useMemo(
    () => archiveTiles.filter((tile) => {
      if (tile.pending) return false;
      if (!tile.videoUrl) return false;
      if (!tile.raw) return false;
      if (isArchivePending(tile.raw as never)) return false;
      return Boolean(videoNoteSendPayload(tile.raw));
    }),
    [archiveTiles],
  );

  useEffect(() => {
    if (!visible) return;
  }, [visible]);

  if (!visible) return null;

  const canSend = Boolean(selectedTileId != null || uploadFile) && !sending;

  return (
    <View style={styles.wrap} pointerEvents="box-none">
      <Pressable style={styles.backdrop} onPress={onClose} />
      <View style={styles.sheet}>
        <View style={styles.header}>
          <View style={styles.headerIcon}>
            <IcoVideoNote size={18} stroke={color.purple} />
          </View>
          <Text style={styles.title}>{t.dlgVideoNoteTitle}</Text>
          <Pressable onPress={onClose} hitSlop={8} style={styles.closeBtn}>
            <Text style={styles.closeText}>×</Text>
          </Pressable>
        </View>

        <Text style={styles.sectionLabel}>{t.dlgVideoNoteArchive}</Text>
        {readyTiles.length ? (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.thumbRow}>
            {readyTiles.slice(0, 12).map((tile) => (
              <ArchiveThumb
                key={tile.id}
                tile={tile}
                selected={selectedTileId === tile.id && !uploadFile}
                onPress={() => onSelectArchive(tile)}
              />
            ))}
          </ScrollView>
        ) : (
          <Text style={styles.empty}>{t.dlgVideoNoteArchiveEmpty}</Text>
        )}

        <View style={styles.dividerRow}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerText}>{t.dlgVideoNoteOr}</Text>
          <View style={styles.dividerLine} />
        </View>

        <Pressable style={[styles.uploadBox, uploadFile && styles.uploadBoxActive]} onPress={onPickUpload}>
          {uploadFile?.type?.startsWith('video/') ? (
            <Video
              source={{ uri: uploadFile.uri }}
              style={styles.uploadPreview}
              resizeMode={ResizeMode.COVER}
              isMuted
              shouldPlay={false}
            />
          ) : uploadFile ? (
            <Image source={{ uri: uploadFile.uri }} style={styles.uploadPreview} />
          ) : (
            <IcoUpload size={20} stroke={color.dim} />
          )}
          <Text style={styles.uploadLabel} numberOfLines={1}>
            {uploadFile?.name || t.dlgVideoNoteUpload}
          </Text>
          {uploadFile ? (
            <Pressable onPress={(e) => { e.stopPropagation?.(); onClearUpload(); }} hitSlop={8}>
              <Text style={styles.clearUpload}>×</Text>
            </Pressable>
          ) : null}
        </Pressable>

        <Text style={styles.hint}>{t.dlgVideoNoteUploadHint}</Text>

        <Pressable
          style={[styles.sendBtn, !canSend && styles.sendBtnDisabled]}
          disabled={!canSend}
          onPress={onSend}
        >
          {sending ? (
            <ActivityIndicator color={color.purple} />
          ) : (
            <>
              <IcoSendPlane size={16} stroke={color.purple} />
              <Text style={styles.sendLabel}>{t.studioVideoNoteSendLong}</Text>
            </>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'flex-end',
    zIndex: 20,
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,.35)',
  },
  sheet: {
    marginHorizontal: 10,
    marginBottom: 8,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(192,132,252,.35)',
    backgroundColor: color.card,
    padding: 14,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 14,
  },
  headerIcon: {
    width: 32,
    height: 32,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(192,132,252,.14)',
    borderWidth: 1,
    borderColor: 'rgba(192,132,252,.35)',
  },
  title: { flex: 1, fontSize: 15, fontWeight: '800', color: color.text },
  closeBtn: { width: 28, height: 28, alignItems: 'center', justifyContent: 'center' },
  closeText: { fontSize: 24, color: color.dim, lineHeight: 26 },
  sectionLabel: {
    fontSize: 9,
    letterSpacing: 1.2,
    color: color.dim,
    marginBottom: 8,
    fontWeight: '700',
  },
  thumbRow: { gap: 8, paddingBottom: 4, marginBottom: 12 },
  thumb: {
    width: 88,
    height: 88,
    borderRadius: 12,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,.08)',
    backgroundColor: color.card2,
  },
  thumbSelected: {
    borderWidth: 2,
    borderColor: 'rgba(192,132,252,.85)',
  },
  thumbImg: { width: '100%', height: '100%' },
  playBadge: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    marginTop: -14,
    marginLeft: -14,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(0,0,0,.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  duration: {
    position: 'absolute',
    right: 6,
    bottom: 6,
    fontSize: 9,
    fontWeight: '700',
    color: '#fff',
    backgroundColor: 'rgba(0,0,0,.55)',
    borderRadius: 6,
    paddingHorizontal: 5,
    paddingVertical: 2,
  },
  empty: { fontSize: 12, color: color.dim, marginBottom: 12 },
  dividerRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  dividerLine: { flex: 1, height: 1, backgroundColor: 'rgba(255,255,255,.08)' },
  dividerText: { fontSize: 11, color: color.dim },
  uploadBox: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: 'rgba(255,255,255,.18)',
    borderRadius: 12,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  uploadBoxActive: {
    borderColor: 'rgba(192,132,252,.55)',
    backgroundColor: 'rgba(192,132,252,.06)',
  },
  uploadPreview: { width: 44, height: 44, borderRadius: 10 },
  uploadLabel: { flex: 1, fontSize: 13, fontWeight: '700', color: color.text },
  clearUpload: { fontSize: 18, color: color.red, fontWeight: '700' },
  hint: { fontSize: 11, color: color.dim, lineHeight: 16, marginBottom: 12 },
  sendBtn: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,.12)',
    backgroundColor: color.card2,
    paddingVertical: 12,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  sendBtnDisabled: { opacity: 0.45 },
  sendLabel: { fontSize: 14, fontWeight: '800', color: color.text },
});
