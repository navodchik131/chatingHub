import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  Keyboard,
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
import { TextInput } from 'react-native-gesture-handler';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { fmtThreadDayKey, fmtThreadDayLabel } from '@/src/api/helpers';
import { Avatar } from '@/src/components/ui';
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
  lang?: 'ru' | 'en';
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
}: {
  text: string;
  out?: boolean;
  translation?: string | null;
  time?: string;
  pending?: boolean;
  lang?: 'ru' | 'en';
}) {
  const footer = (
    <View style={styles.bubbleMeta}>
      <Text style={[styles.bubbleTime, out && styles.bubbleTimeOut]}>
        {time}
        {pending ? (lang === 'ru' ? ' · отправка…' : ' · sending…') : ''}
      </Text>
      {out && !pending ? <Text style={styles.bubbleChecks}>✓✓</Text> : null}
    </View>
  );

  const body = (
    <>
      <Text style={[styles.bubbleText, out && styles.bubbleTextOut]}>{text || '—'}</Text>
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
      {out ? (
        <LinearGradient
          colors={[color.bubbleOutStart, color.bubbleOutEnd]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[styles.bubble, styles.bubbleOut, pending && styles.bubblePending]}
        >
          {body}
        </LinearGradient>
      ) : (
        <View style={[styles.bubble, styles.bubbleIn, pending && styles.bubblePending]}>
          {body}
        </View>
      )}
    </View>
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
  lang = 'ru',
}: ThreadViewProps) {
  const insets = useSafeAreaInsets();
  const scrollRef = useRef<ScrollView>(null);
  const nearBottomRef = useRef(true);
  const didInitialScrollRef = useRef(false);
  const prevCountRef = useRef(0);
  const [keyboardPad, setKeyboardPad] = useState(0);
  const [themePickerOpen, setThemePickerOpen] = useState(false);
  const { chatTheme, setChatTheme } = useAppSettings();
  const theme = chatThemeById(chatTheme);

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

  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const showSub = Keyboard.addListener(showEvent, (e) => {
      if (Platform.OS === 'android') {
        // resize mode in app.json + extra lift for gesture nav / OEM quirks
        const lift = Math.max(0, e.endCoordinates.height - insets.bottom + 12);
        setKeyboardPad(lift);
      } else {
        setKeyboardPad(0);
      }
      scrollToBottomIfNear(true);
    });
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardPad(0));
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, [insets.bottom]);

  const platformLabel = platform.toUpperCase();
  const subtitle = vip ? `${platformLabel} • VIP` : platformLabel;
  const composerPadBottom = keyboardPad > 0 ? 12 + keyboardPad : Math.max(12, insets.bottom);

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? insets.top : 0}
    >
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
        <Pressable style={styles.headThemeBtn} onPress={() => setThemePickerOpen(true)} hitSlop={8}>
          <IcoThemeGrid size={25} stroke={color.muted} />
        </Pressable>
      </View>

      <ScrollView
        ref={scrollRef}
        style={[styles.scroll, { backgroundColor: theme.background }]}
        contentContainerStyle={styles.scrollContent}
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
            />
          );
        })}
      </ScrollView>

      <View style={[styles.composer, { paddingBottom: composerPadBottom }]}>
        <Pressable style={styles.sideBtn} hitSlop={6}>
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
              scrollToBottom(true);
            }}
            returnKeyType="send"
          />
          <Pressable style={styles.emojiBtn} hitSlop={6}>
            <Text style={styles.emojiIcon}>😊</Text>
          </Pressable>
        </View>
        <Pressable
          style={[styles.sendBtn, !draft.trim() && styles.sendBtnDim]}
          onPress={() => {
            nearBottomRef.current = true;
            onSend();
          }}
          disabled={!draft.trim()}
        >
          <IcoSend size={20} stroke={color.limeText} />
        </Pressable>
      </View>

      <ThemePicker
        visible={themePickerOpen}
        activeId={chatTheme}
        onClose={() => setThemePickerOpen(false)}
        onPick={(id) => void setChatTheme(id)}
      />
    </KeyboardAvoidingView>
  );
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
  headThemeBtn: { padding: 8, margin: -8 },
  scroll: { flex: 1 },
  scrollContent: { paddingHorizontal: 16, paddingVertical: 16, gap: 11 },
  dayWrap: { alignItems: 'center', marginVertical: 6 },
  dayPill: {
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  dayText: { fontSize: 12, color: '#C9CDD1', fontFamily: font.bodySemi, fontWeight: '600' },
  bubbleWrap: { flexDirection: 'row', justifyContent: 'flex-start' },
  bubbleWrapOut: { justifyContent: 'flex-end' },
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
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 10,
    paddingHorizontal: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: color.border,
    backgroundColor: color.composerBg,
  },
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
