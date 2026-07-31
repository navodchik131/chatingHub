import { LinearGradient } from 'expo-linear-gradient';
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';
import { ChatAttachmentMedia } from '@/src/components/ChatAttachmentMedia';
import { TextInput } from 'react-native-gesture-handler';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  fmtThreadDayKey,
  fmtThreadDayLabel,
  REACT_CHOICES,
} from '@/src/api/helpers';
import { dialogSettingsSummary, replyLangDisplay, type ConversationSettingsPatch } from '@/src/api/dialogSettings';
import type { ConversationOut } from '@/src/api/types';
import { Avatar } from '@/src/components/ui';
import { DialogSettingsSheet } from '@/src/components/DialogSettingsSheet';
import { EmojiPickerSheet } from '@/src/components/EmojiPickerSheet';
import { IcoBack, IcoSend, IcoThemeGrid } from '@/src/components/Icons';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { CHAT_THEMES, chatThemeById, type ChatThemeId } from '@/src/styles/chatThemes';
import { color, font } from '@/src/styles/tokens';

export type ThreadMessage = {
  id: number;
  side: 'in' | 'out';
  text: string;
  tr?: string | null;
  time?: string;
  created_at?: string;
  pending?: boolean;
  attachmentUrl?: string | null;
  attachments?: { id: number; url: string; kind?: string; mime_type?: string }[];
  ownerReaction?: string | null;
};

type ThreadViewProps = {
  name: string;
  platform: string;
  vip?: boolean;
  gradIndex: number;
  messages: ThreadMessage[];
  draft: string;
  onDraftChange: (value: string) => void;
  onBack: () => void;
  onSend: () => void;
  onAttach?: () => void;
  attachmentUri?: string | null;
  onClearAttachment?: () => void;
  onEmoji?: (emoji: string) => void;
  lang?: 'ru' | 'en';
  sending?: boolean;
  convId?: number | null;
  rawConv?: ConversationOut | null;
  onPatchSettings?: (patch: ConversationSettingsPatch) => void;
  onToggleReaction?: (messageId: number, emoji: string) => void;
};

type ListItem =
  | { kind: 'day'; key: string; label: string }
  | { kind: 'msg'; key: string; msg: ThreadMessage };

const NEAR_BOTTOM_PX = 100;

function ThreadDaySeparator({ label }: { label: string }) {
  return (
    <View style={styles.dayWrap}>
      <View style={styles.dayPill}>
        <Text style={styles.dayText}>{label}</Text>
      </View>
    </View>
  );
}

function ThreadBubble({
  text,
  out,
  translation,
  time,
  pending,
  lang = 'ru',
  attachmentUrl,
  attachments,
  ownerReaction,
  onLongPress,
}: {
  text: string;
  out?: boolean;
  translation?: string | null;
  time?: string;
  pending?: boolean;
  lang?: 'ru' | 'en';
  attachmentUrl?: string | null;
  attachments?: ThreadMessage['attachments'];
  ownerReaction?: string | null;
  onLongPress?: () => void;
}) {
  const att = attachments?.[0];
  const hasMedia = Boolean(attachmentUrl);
  const isVideoNote = att?.kind === 'video_note';
  const showText = Boolean(text && text !== '📷' && text !== '—');
  const mediaOnly = hasMedia && isVideoNote && !showText;

  const footer = (
    <View style={styles.bubbleMeta}>
      <Text style={[styles.bubbleTime, out && styles.bubbleTimeOut]}>
        {time}
        {pending ? (lang === 'ru' ? ' · отправка…' : ' · sending…') : ''}
      </Text>
      {out && !pending ? <Text style={styles.bubbleChecks}>✓✓</Text> : null}
    </View>
  );

  const mediaBlock = hasMedia ? (
    <ChatAttachmentMedia
      url={attachmentUrl}
      mime={att?.mime_type}
      kind={att?.kind}
      style={styles.mediaWrap}
      withText={showText}
    />
  ) : null;

  const body = (
    <>
      {mediaBlock}
      {showText ? (
        <Text style={[styles.bubbleText, out && styles.bubbleTextOut]}>{text}</Text>
      ) : null}
      {!showText && !hasMedia ? (
        <Text style={[styles.bubbleText, out && styles.bubbleTextOut]}>—</Text>
      ) : null}
      {translation ? (
        <View style={[styles.translation, out && styles.translationOut]}>
          <Text style={[styles.translationText, out && styles.translationTextOut]}>{translation}</Text>
        </View>
      ) : null}
      {footer}
    </>
  );

  return (
    <View style={[styles.bubbleWrap, out && styles.bubbleWrapOut]}>
      <Pressable onLongPress={pending ? undefined : onLongPress} delayLongPress={280}>
        {out && !mediaOnly ? (
          <LinearGradient
            colors={[color.bubbleOutStart, color.bubbleOutEnd]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={[styles.bubble, styles.bubbleOut, pending && styles.bubblePending]}
          >
            {body}
          </LinearGradient>
        ) : mediaOnly ? (
          <View style={[styles.bubble, styles.bubbleMediaOnly, pending && styles.bubblePending]}>
            {body}
          </View>
        ) : (
          <View style={[styles.bubble, styles.bubbleIn, pending && styles.bubblePending]}>
            {body}
          </View>
        )}
      </Pressable>
      {ownerReaction ? (
        <View style={[styles.reactionPill, out && styles.reactionPillOut]}>
          <Text style={styles.reactionEmoji}>{ownerReaction}</Text>
        </View>
      ) : null}
    </View>
  );
}

function ReactionPicker({
  visible,
  lang,
  onClose,
  onPick,
}: {
  visible: boolean;
  lang: 'ru' | 'en';
  onClose: () => void;
  onPick: (emoji: string) => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.reactOverlay} onPress={onClose}>
        <View style={styles.reactBar}>
          {REACT_CHOICES.map((emoji) => (
            <Pressable
              key={emoji}
              style={styles.reactCell}
              onPress={() => {
                onPick(emoji);
                onClose();
              }}
            >
              <Text style={styles.reactEmoji}>{emoji}</Text>
            </Pressable>
          ))}
        </View>
      </Pressable>
    </Modal>
  );
}

function ThemePicker({
  visible,
  activeId,
  onClose,
  onPick,
}: {
  visible: boolean;
  activeId: ChatThemeId;
  onClose: () => void;
  onPick: (id: ChatThemeId) => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={styles.themeOverlay} onPress={onClose}>
        <Pressable style={styles.themeSheet} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.themeTitle}>Выбор темы</Text>
          <View style={styles.themeGrid}>
            {CHAT_THEMES.map((theme) => {
              const active = theme.id === activeId;
              const colors =
                theme.swatch.length === 2
                  ? ([theme.swatch[0], theme.swatch[1]] as const)
                  : ([theme.swatch[0], theme.swatch[0]] as const);
              return (
                <Pressable
                  key={theme.id}
                  style={[styles.themeTile, active && styles.themeTileActive]}
                  onPress={() => {
                    onPick(theme.id);
                    onClose();
                  }}
                >
                  <LinearGradient
                    colors={colors}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 1 }}
                    style={styles.themeSwatch}
                  >
                    <Text style={styles.themeLabel}>{theme.label}</Text>
                  </LinearGradient>
                </Pressable>
              );
            })}
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

export function ThreadView({
  name,
  platform,
  vip,
  gradIndex,
  messages,
  draft,
  onDraftChange,
  onBack,
  onSend,
  onAttach,
  attachmentUri,
  onClearAttachment,
  onEmoji,
  lang = 'ru',
  sending = false,
  convId = null,
  rawConv = null,
  onPatchSettings,
  onToggleReaction,
}: ThreadViewProps) {
  const insets = useSafeAreaInsets();
  const scrollRef = useRef<ScrollView>(null);
  const nearBottomRef = useRef(true);
  const didInitialScrollRef = useRef(false);
  const prevCountRef = useRef(0);
  const [themePickerOpen, setThemePickerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  const [reactMsgId, setReactMsgId] = useState<number | null>(null);
  const { chatTheme, setChatTheme } = useAppSettings();
  const theme = chatThemeById(chatTheme);
  const convForSettings = rawConv ?? (convId != null ? ({ id: convId, platform: platform.toUpperCase() } as ConversationOut) : null);
  const settingsSummary = rawConv ? dialogSettingsSummary(rawConv, lang) : (lang === 'ru' ? 'Настр.' : 'Settings');
  const showSettings = convId != null && Boolean(onPatchSettings);

  const items = useMemo(() => {
    const rows: ListItem[] = [];
    let lastDay = '';
    for (const msg of messages) {
      const dayKey = fmtThreadDayKey(msg.created_at);
      if (dayKey && dayKey !== lastDay) {
        rows.push({
          kind: 'day',
          key: `day-${dayKey}`,
          label: fmtThreadDayLabel(msg.created_at, lang),
        });
        lastDay = dayKey;
      }
      rows.push({ kind: 'msg', key: `msg-${msg.id}`, msg });
    }
    return rows;
  }, [messages, lang]);

  const scrollToBottom = (animated = true) => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollToEnd({ animated });
    });
  };

  const scrollToBottomIfNear = (animated = true) => {
    if (!nearBottomRef.current) return;
    scrollToBottom(animated);
  };

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const { layoutMeasurement, contentOffset, contentSize } = e.nativeEvent;
    const distanceFromBottom =
      contentSize.height - layoutMeasurement.height - contentOffset.y;
    nearBottomRef.current = distanceFromBottom <= NEAR_BOTTOM_PX;
  };

  useLayoutEffect(() => {
    const count = messages.length;
    const grew = count > prevCountRef.current;
    const last = messages[count - 1];
    const ownPending = Boolean(last?.pending && last.side === 'out');
    prevCountRef.current = count;

    if (!didInitialScrollRef.current && count > 0) {
      didInitialScrollRef.current = true;
      nearBottomRef.current = true;
      scrollToBottom(false);
      return;
    }

    if (ownPending) {
      nearBottomRef.current = true;
      scrollToBottom(true);
      return;
    }

    if (grew) scrollToBottomIfNear(true);
  }, [messages]);

  const platformLabel = platform.toUpperCase();
  const subtitleParts = [platformLabel];
  if (vip) subtitleParts.push('VIP');
  if (rawConv && !rawConv.auto_translate_disabled) {
    const replyLang = replyLangDisplay(rawConv, lang);
    if (replyLang && replyLang !== (lang === 'ru' ? 'Авто' : 'Auto')) {
      subtitleParts.push(replyLang);
    }
  }
  const subtitle = subtitleParts.join(' · ');
  const composerPadBottom = Math.max(12, insets.bottom);
  const canSend = Boolean(draft.trim() || attachmentUri) && !sending;

  const content = (
    <>
      <View style={styles.head}>
        <Pressable onPress={onBack} hitSlop={8} style={styles.backBtn}>
          <IcoBack size={22} stroke={color.muted} />
        </Pressable>
        <Avatar letter={name[0] || '?'} index={gradIndex} size={46} />
        <View style={styles.headText}>
          <View style={styles.headNameRow}>
            <Text style={styles.headName}>{name}</Text>
            {vip ? (
              <View style={styles.vipPill}>
                <Text style={styles.vipText}>VIP</Text>
              </View>
            ) : null}
          </View>
          <Text style={styles.headSub}>{subtitle}</Text>
        </View>
        {showSettings ? (
          <Pressable style={styles.headSettingsBtn} onPress={() => setSettingsOpen(true)} hitSlop={6}>
            <Text style={styles.headSettingsText} numberOfLines={1}>
              ⚙ {settingsSummary}
            </Text>
          </Pressable>
        ) : null}
        <Pressable style={styles.headThemeBtn} onPress={() => setThemePickerOpen(true)} hitSlop={8}>
          <IcoThemeGrid size={25} stroke={color.muted} />
        </Pressable>
      </View>

      <ScrollView
        ref={scrollRef}
        style={[styles.scroll, { backgroundColor: theme.background }]}
        contentContainerStyle={[styles.scrollContent, styles.scrollContentGrow]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="interactive"
        onScroll={onScroll}
        scrollEventThrottle={16}
        onContentSizeChange={() => scrollToBottomIfNear(false)}
      >
        {items.map((item) => {
          if (item.kind === 'day') {
            return <ThreadDaySeparator key={item.key} label={item.label} />;
          }
          const m = item.msg;
          return (
            <ThreadBubble
              key={item.key}
              text={m.text}
              out={m.side === 'out'}
              translation={m.tr}
              time={m.time}
              pending={m.pending}
              lang={lang}
              attachmentUrl={m.attachmentUrl}
              attachments={m.attachments}
              ownerReaction={m.ownerReaction}
              onLongPress={
                onToggleReaction && !m.pending && m.id > 0
                  ? () => setReactMsgId(m.id)
                  : undefined
              }
            />
          );
        })}
      </ScrollView>

      <View style={[styles.composer, { paddingBottom: composerPadBottom }]}>
        {attachmentUri ? (
          <View style={styles.attachPreviewRow}>
            <Image source={{ uri: attachmentUri }} style={styles.attachPreview} />
            <Pressable style={styles.attachRemove} onPress={onClearAttachment} hitSlop={8}>
              <Text style={styles.attachRemoveText}>×</Text>
            </Pressable>
            <Text style={styles.attachHint}>
              {lang === 'ru' ? 'Фото прикреплено — нажмите отправить' : 'Photo attached — tap send'}
            </Text>
          </View>
        ) : null}
        <View style={styles.composerRow}>
        <Pressable style={styles.sideBtn} hitSlop={6} onPress={onAttach}>
          <Text style={styles.sideBtnIcon}>📎</Text>
        </Pressable>
        <View style={styles.composerField}>
          <TextInput
            style={styles.input}
            placeholder={lang === 'ru' ? 'Сообщение…' : 'Message…'}
            placeholderTextColor={color.dim}
            keyboardAppearance="dark"
            selectionColor={color.lime}
            value={draft}
            onChangeText={onDraftChange}
            autoCorrect={false}
            spellCheck={false}
            autoComplete="off"
            multiline
            onFocus={() => {
              nearBottomRef.current = true;
              setTimeout(() => scrollToBottom(true), 80);
            }}
            returnKeyType="send"
          />
          <Pressable style={styles.emojiBtn} hitSlop={6} onPress={() => setEmojiPickerOpen(true)}>
            <Text style={styles.emojiIcon}>😊</Text>
          </Pressable>
        </View>
        <Pressable
          style={[styles.sendBtn, !canSend && styles.sendBtnDim]}
          onPress={() => {
            if (!canSend) return;
            nearBottomRef.current = true;
            onSend();
          }}
          disabled={!canSend}
        >
          <IcoSend size={20} stroke={color.limeText} />
        </Pressable>
        </View>
      </View>

      <ThemePicker
        visible={themePickerOpen}
        activeId={chatTheme}
        onClose={() => setThemePickerOpen(false)}
        onPick={(id) => void setChatTheme(id)}
      />

      {showSettings && convForSettings ? (
        <DialogSettingsSheet
          visible={settingsOpen}
          conv={convForSettings}
          lang={lang}
          onClose={() => setSettingsOpen(false)}
          onPatch={(patch) => void onPatchSettings?.(patch)}
        />
      ) : null}

      <EmojiPickerSheet
        visible={emojiPickerOpen}
        lang={lang}
        onClose={() => setEmojiPickerOpen(false)}
        onPick={(emoji) => onEmoji?.(emoji)}
      />

      <ReactionPicker
        visible={reactMsgId != null}
        lang={lang}
        onClose={() => setReactMsgId(null)}
        onPick={(emoji) => {
          if (reactMsgId != null) onToggleReaction?.(reactMsgId, emoji);
        }}
      />
    </>
  );

  if (Platform.OS === 'ios') {
    return (
      <KeyboardAvoidingView
        style={styles.root}
        behavior="padding"
        keyboardVerticalOffset={insets.top}
      >
        {content}
      </KeyboardAvoidingView>
    );
  }

  return <View style={styles.root}>{content}</View>;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.bg },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: color.border,
    backgroundColor: color.bg,
  },
  backBtn: { padding: 4 },
  headText: { flex: 1, minWidth: 0 },
  headNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headName: { fontFamily: font.bodyExtra, fontSize: 19, color: color.text },
  headSub: { marginTop: 3, fontSize: 14, color: color.muted },
  vipPill: {
    backgroundColor: color.lime,
    borderRadius: 5,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  vipText: { fontFamily: font.monoBold, fontSize: 8, color: color.limeText, fontWeight: '700' },
  headSettingsBtn: {
    maxWidth: 108,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.14)',
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  headSettingsText: {
    fontFamily: font.mono,
    fontSize: 10,
    color: color.muted,
  },
  headThemeBtn: { padding: 8, margin: -8 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingVertical: 16, gap: 11 },
  scrollContentGrow: { flexGrow: 1, justifyContent: 'flex-end' },
  dayWrap: { alignItems: 'center', marginVertical: 6 },
  dayPill: {
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  dayText: { fontSize: 12, color: '#C9CDD1', fontFamily: font.bodySemi, fontWeight: '600' },
  bubbleWrap: { flexDirection: 'row', justifyContent: 'flex-start', position: 'relative', marginBottom: 4 },
  bubbleWrapOut: { justifyContent: 'flex-end' },
  mediaWrap: { marginBottom: 0 },
  reactionPill: {
    position: 'absolute',
    bottom: -6,
    left: 8,
    backgroundColor: '#1F2126',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.12)',
    borderRadius: 12,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  reactionPillOut: { left: undefined, right: 8 },
  reactionEmoji: { fontSize: 14 },
  reactOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  reactBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#17181C',
    borderRadius: 16,
    padding: 14,
    maxWidth: 320,
  },
  reactCell: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.05)',
  },
  reactEmoji: { fontSize: 26 },
  bubble: {
    maxWidth: '84%',
    paddingHorizontal: 14,
    paddingVertical: 11,
    borderRadius: 14,
  },
  bubbleIn: {
    backgroundColor: color.bubbleInBg,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.06)',
    borderBottomLeftRadius: 4,
  },
  bubbleOut: {
    borderBottomRightRadius: 4,
    shadowColor: color.bubbleOutShadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 8,
    elevation: 4,
  },
  bubblePending: { opacity: 0.72 },
  bubbleMediaOnly: {
    paddingHorizontal: 0,
    paddingVertical: 0,
    backgroundColor: 'transparent',
    borderWidth: 0,
  },
  bubbleText: { fontSize: 17, lineHeight: 24, color: color.text },
  bubbleTextOut: { color: '#fff', fontSize: 16.5, lineHeight: 23 },
  translation: {
    marginTop: 7,
    paddingTop: 7,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.12)',
    borderStyle: 'dashed',
  },
  translationOut: { borderTopColor: 'rgba(255,255,255,0.35)' },
  translationText: { fontSize: 13, lineHeight: 18, color: '#C9CDD1' },
  translationTextOut: { fontSize: 15, lineHeight: 21, color: 'rgba(255,255,255,0.92)' },
  bubbleMeta: {
    marginTop: 7,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: 5,
  },
  bubbleTime: { fontFamily: font.mono, fontSize: 11, color: '#8A8F95' },
  bubbleTimeOut: { color: 'rgba(255,255,255,0.8)' },
  bubbleChecks: { fontSize: 11, color: 'rgba(255,255,255,0.85)', letterSpacing: -1 },
  composer: {
    gap: 8,
    paddingHorizontal: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: color.border,
    backgroundColor: color.composerBg,
  },
  composerRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 10,
  },
  attachPreviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingBottom: 4,
  },
  attachPreview: {
    width: 56,
    height: 56,
    borderRadius: 10,
    backgroundColor: '#2A2D33',
  },
  attachRemove: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.12)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  attachRemoveText: { color: color.text, fontSize: 18, lineHeight: 20 },
  attachHint: { flex: 1, fontSize: 12, color: color.muted },
  sideBtn: {
    width: 48,
    height: 48,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  sideBtnIcon: { fontSize: 22, color: color.muted },
  composerField: {
    flex: 1,
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1F2126',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.09)',
    borderRadius: 24,
    paddingHorizontal: 12,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    paddingVertical: 10,
    color: color.text,
    fontFamily: font.body,
    fontSize: 17,
    lineHeight: 22,
  },
  emojiBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  emojiIcon: { fontSize: 22 },
  sendBtn: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: color.lime,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDim: { opacity: 0.45 },
  themeOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'flex-end',
  },
  themeSheet: {
    backgroundColor: '#17181C',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 28,
  },
  themeTitle: { fontFamily: font.bodyExtra, fontSize: 16, color: color.text, marginBottom: 12 },
  themeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  themeTile: {
    width: '31%',
    aspectRatio: 1,
    borderRadius: 14,
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: 'transparent',
  },
  themeTileActive: { borderColor: color.lime },
  themeSwatch: { flex: 1, justifyContent: 'flex-end', padding: 8 },
  themeLabel: { fontSize: 11.5, fontWeight: '700', color: '#fff', textAlign: 'center' },
});
