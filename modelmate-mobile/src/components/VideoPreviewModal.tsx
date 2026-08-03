import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Video, ResizeMode } from 'expo-av';
import {
  IcoChevron,
  IcoDownload,
  IcoFilm,
  IcoPlay,
  IcoSendPlane,
  IcoVideoNote,
} from '@/src/components/Icons';
import { RemoteImage } from '@/src/components/RemoteImage';
import { color, font } from '@/src/styles/tokens';
import { resolveMediaUrl } from '@/src/api/config';
import type { Strings } from '@/src/i18n/strings';
import type { ConversationOut } from '@/src/api/types';

type VideoNotePayload = { renderId?: number; generationId?: number };

type Props = {
  visible: boolean;
  onClose: () => void;
  who: string;
  metaLine?: string;
  videoUrl: string;
  posterUrl?: string;
  downloadUrl?: string;
  videoNotePath?: string | null;
  videoNotePayload?: VideoNotePayload | null;
  tgConversations?: ConversationOut[];
  t: Strings;
  onDownloadMp4?: () => void;
  onDownloadVideoNote?: () => void;
  onSendVideoNote?: (convId: number, payload: VideoNotePayload) => Promise<void>;
};

function ActionBtn({
  tone,
  icon,
  label,
  hint,
  onPress,
  disabled,
}: {
  tone: 'lime' | 'purple' | 'cyan';
  icon: ReactNode;
  label: string;
  hint?: string;
  onPress?: () => void;
  disabled?: boolean;
}) {
  const toneStyle =
    tone === 'lime'
      ? { bg: color.lime, border: 'transparent', fg: color.limeText, hint: 'rgba(23,26,5,.55)' }
      : tone === 'purple'
        ? { bg: 'rgba(192,132,252,.08)', border: 'rgba(192,132,252,.45)', fg: color.purple, hint: 'rgba(192,132,252,.75)' }
        : { bg: 'rgba(56,189,248,.08)', border: 'rgba(56,189,248,.45)', fg: color.blue, hint: 'rgba(56,189,248,.75)' };

  return (
    <Pressable
      style={[
        styles.actionBtn,
        {
          backgroundColor: toneStyle.bg,
          borderColor: toneStyle.border,
          opacity: disabled ? 0.55 : 1,
        },
      ]}
      disabled={disabled}
      onPress={onPress}
    >
      <View style={styles.actionIcon}>{icon}</View>
      <Text style={[styles.actionLabel, { color: toneStyle.fg }]}>{label}</Text>
      {hint ? <Text style={[styles.actionHint, { color: toneStyle.hint }]}>{hint}</Text> : null}
      {tone === 'cyan' ? <IcoChevron size={14} stroke={toneStyle.fg} /> : null}
    </Pressable>
  );
}

export function VideoPreviewModal({
  visible,
  onClose,
  who,
  metaLine,
  videoUrl,
  posterUrl,
  downloadUrl,
  videoNotePath,
  videoNotePayload,
  tgConversations = [],
  t,
  onDownloadMp4,
  onDownloadVideoNote,
  onSendVideoNote,
}: Props) {
  const videoRef = useRef<Video>(null);
  const [playing, setPlaying] = useState(false);
  const [durationSec, setDurationSec] = useState(0);
  const [pickOpen, setPickOpen] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!visible) {
      setPlaying(false);
      setDurationSec(0);
      setPickOpen(false);
      setSending(false);
    }
  }, [visible]);

  if (!visible) return null;

  const resolvedVideo = resolveMediaUrl(videoUrl);
  const canSend = Boolean(videoNotePayload) && tgConversations.length > 0;
  const durationLabel = durationSec > 0 ? `${Math.round(durationSec)}s` : '';

  const sendToConv = async (convId: number) => {
    if (!videoNotePayload || !onSendVideoNote || sending) return;
    setSending(true);
    try {
      await onSendVideoNote(convId, videoNotePayload);
      setPickOpen(false);
      onClose();
    } finally {
      setSending(false);
    }
  };

  const openSend = () => {
    if (!canSend) return;
    if (tgConversations.length === 1) {
      void sendToConv(tgConversations[0].id);
      return;
    }
    setPickOpen(true);
  };

  const togglePlay = async () => {
    const ref = videoRef.current;
    if (!ref) return;
    const status = await ref.getStatusAsync();
    if (!status.isLoaded) return;
    if (status.isPlaying) {
      await ref.pauseAsync();
      setPlaying(false);
    } else {
      await ref.playAsync();
      setPlaying(true);
    }
  };

  return (
    <>
      <Modal visible={visible && !pickOpen} transparent animationType="fade" onRequestClose={onClose}>
        <Pressable style={styles.backdrop} onPress={onClose}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <ScrollView bounces={false} showsVerticalScrollIndicator={false}>
              <View style={styles.head}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.title}>{who}</Text>
                  {metaLine ? <Text style={styles.meta}>{metaLine}</Text> : null}
                </View>
                <Pressable style={styles.closeBtn} onPress={onClose}>
                  <Text style={styles.closeText}>✕ {t.commonClose}</Text>
                </Pressable>
              </View>

              <Pressable style={styles.videoWrap} onPress={() => void togglePlay()}>
                {resolvedVideo ? (
                  <Video
                    ref={videoRef}
                    source={{ uri: resolvedVideo }}
                    style={styles.video}
                    resizeMode={ResizeMode.COVER}
                    useNativeControls={false}
                    posterSource={posterUrl ? { uri: resolveMediaUrl(posterUrl) } : undefined}
                    onPlaybackStatusUpdate={(st) => {
                      if (!st.isLoaded) return;
                      if (st.durationMillis && st.durationMillis > 0) {
                        setDurationSec(st.durationMillis / 1000);
                      }
                      setPlaying(st.isPlaying);
                    }}
                  />
                ) : posterUrl ? (
                  <RemoteImage uri={posterUrl} style={styles.video} gradIndex={2} contentFit="cover" />
                ) : (
                  <View style={[styles.video, styles.videoFallback]}>
                    <IcoFilm size={24} stroke={color.muted} />
                  </View>
                )}
                {!playing ? (
                  <View style={styles.playOverlay}>
                    <View style={styles.playCircle}>
                      <IcoPlay size={16} stroke="#fff" />
                    </View>
                  </View>
                ) : null}
                {durationLabel ? (
                  <View style={styles.durationBadge}>
                    <Text style={styles.durationText}>{durationLabel}</Text>
                  </View>
                ) : null}
              </Pressable>

              <View style={styles.actions}>
                {downloadUrl ? (
                  <ActionBtn
                    tone="lime"
                    icon={<IcoDownload size={17} stroke={color.limeText} />}
                    label={t.studioDownloadMp4}
                    hint="MP4"
                    onPress={onDownloadMp4}
                  />
                ) : null}
                {videoNotePath ? (
                  <ActionBtn
                    tone="purple"
                    icon={<IcoVideoNote size={17} stroke={color.purple} />}
                    label={t.studioVideoNoteDownload}
                    hint="1:1"
                    onPress={onDownloadVideoNote}
                  />
                ) : null}
                {videoNotePayload ? (
                  <ActionBtn
                    tone="cyan"
                    icon={<IcoSendPlane size={17} stroke={color.blue} />}
                    label={t.studioVideoNoteSendLong}
                    onPress={openSend}
                    disabled={!canSend || sending}
                  />
                ) : null}
                {videoNotePayload && !canSend ? (
                  <Text style={styles.noChat}>{t.studioVideoNoteNoChat}</Text>
                ) : null}
              </View>

              {videoNotePath ? <Text style={styles.hint}>{t.studioVideoNoteHint}</Text> : null}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal visible={pickOpen} transparent animationType="fade" onRequestClose={() => !sending && setPickOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => !sending && setPickOpen(false)}>
          <View style={styles.pickSheet}>
            <View style={styles.pickHead}>
              <Text style={styles.pickTitle}>{t.studioVideoNotePick}</Text>
              <Pressable onPress={() => !sending && setPickOpen(false)}>
                <Text style={styles.closeText}>✕</Text>
              </Pressable>
            </View>
            {sending ? <ActivityIndicator color={color.lime} style={{ marginVertical: 12 }} /> : null}
            <ScrollView style={{ maxHeight: 360 }}>
              {tgConversations.map((c) => (
                <Pressable
                  key={c.id}
                  style={styles.pickRow}
                  disabled={sending}
                  onPress={() => void sendToConv(c.id)}
                >
                  <Text style={styles.pickName}>{c.user_display_name || c.external_chat_id || '—'}</Text>
                  <Text style={styles.pickPlatform}>TELEGRAM</Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(6,7,9,.88)',
    justifyContent: 'center',
    padding: 20,
  },
  sheet: {
    width: '100%',
    maxWidth: 440,
    alignSelf: 'center',
    maxHeight: '94%',
  },
  head: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    marginBottom: 14,
  },
  title: {
    fontFamily: font.bodyExtra,
    fontSize: 18,
    color: color.text,
  },
  meta: {
    marginTop: 4,
    fontFamily: font.body,
    fontSize: 11.5,
    color: color.muted,
  },
  closeBtn: {
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,.14)',
    borderRadius: 9,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  closeText: {
    fontFamily: font.bodyBold,
    fontSize: 12,
    color: color.muted,
  },
  videoWrap: {
    borderRadius: 20,
    overflow: 'hidden',
    backgroundColor: '#000',
    borderWidth: 1,
    borderColor: color.border,
    aspectRatio: 9 / 16,
    maxHeight: 520,
    position: 'relative',
  },
  video: {
    width: '100%',
    height: '100%',
  },
  videoFallback: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: color.card,
  },
  playOverlay: {
    ...StyleSheet.absoluteFill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,.28)',
  },
  playCircle: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: 'rgba(0,0,0,.45)',
    alignItems: 'center',
    justifyContent: 'center',
    paddingLeft: 3,
  },
  durationBadge: {
    position: 'absolute',
    right: 10,
    bottom: 10,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    backgroundColor: 'rgba(0,0,0,.55)',
  },
  durationText: {
    fontFamily: font.mono,
    fontSize: 10,
    color: '#fff',
    fontWeight: '700',
  },
  actions: {
    gap: 10,
    marginTop: 14,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  actionIcon: {
    width: 18,
    alignItems: 'center',
  },
  actionLabel: {
    flex: 1,
    fontFamily: font.bodyExtra,
    fontSize: 13,
  },
  actionHint: {
    fontFamily: font.mono,
    fontSize: 11,
    fontWeight: '700',
  },
  noChat: {
    textAlign: 'center',
    fontFamily: font.body,
    fontSize: 11,
    color: color.muted,
  },
  hint: {
    marginTop: 12,
    textAlign: 'center',
    fontFamily: font.body,
    fontSize: 11,
    lineHeight: 16,
    color: color.muted,
    paddingHorizontal: 6,
    paddingBottom: 4,
  },
  pickSheet: {
    width: '100%',
    maxWidth: 420,
    alignSelf: 'center',
    backgroundColor: color.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: color.border,
    padding: 16,
    maxHeight: '70%',
  },
  pickHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  pickTitle: {
    fontFamily: font.bodyExtra,
    fontSize: 14,
    color: color.text,
  },
  pickRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: color.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 8,
  },
  pickName: {
    fontFamily: font.bodyBold,
    fontSize: 13,
    color: color.text,
  },
  pickPlatform: {
    fontFamily: font.mono,
    fontSize: 9,
    color: color.muted,
  },
});
