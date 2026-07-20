import { LinearGradient } from 'expo-linear-gradient';
import { ReactNode } from 'react';
import { Image, Pressable, ScrollView, StyleProp, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { color, font, gradients } from '@/src/styles/tokens';
import { IcoBack, IcoChevron } from '@/src/components/Icons';

export function ScreenScroll({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return (
    <ScrollView
      style={[styles.scroll, style]}
      contentContainerStyle={styles.scrollContent}
      showsVerticalScrollIndicator={false}
    >
      {children}
    </ScrollView>
  );
}

export function TopBar({
  title,
  onBack,
  right,
}: {
  title: string;
  onBack?: () => void;
  right?: ReactNode;
}) {
  return (
    <View style={styles.topBar}>
      {onBack ? (
        <Pressable onPress={onBack} hitSlop={8} style={styles.backBtn}>
          <IcoBack size={18} stroke={color.muted} />
        </Pressable>
      ) : null}
      <Text style={[styles.topTitle, onBack && styles.topTitleWithBack]}>{title}</Text>
      {right}
    </View>
  );
}

export function SectionLabel({ children }: { children: string }) {
  return <Text style={styles.sectionLabel}>{children}</Text>;
}

export function Kpi({ label, value, accent, sub }: { label: string; value: string; accent?: string; sub?: string }) {
  return (
    <View style={styles.kpi}>
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text style={[styles.kpiValue, accent ? { color: accent } : null]}>{value}</Text>
      {sub ? <Text style={styles.kpiSub}>{sub}</Text> : null}
    </View>
  );
}

export function Card({
  children,
  style,
  onPress,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
}) {
  const Wrapper = onPress ? Pressable : View;
  return (
    <Wrapper style={[styles.card, style]} onPress={onPress}>
      {children}
    </Wrapper>
  );
}

export function Pill({ text, bg, fg }: { text: string; bg: string; fg: string }) {
  return (
    <View style={[styles.pill, { backgroundColor: bg }]}>
      <Text style={[styles.pillText, { color: fg }]}>{text}</Text>
    </View>
  );
}

export function Avatar({
  letter,
  index = 0,
  size = 34,
  imageUrl,
}: {
  letter: string;
  index?: number;
  size?: number;
  imageUrl?: string;
}) {
  const [a, b] = gradients[index % gradients.length];
  if (imageUrl) {
    return (
      <Image
        source={{ uri: imageUrl }}
        style={[styles.avatar, { width: size, height: size, borderRadius: size / 2 }]}
      />
    );
  }
  return (
    <LinearGradient
      colors={[a, b]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={[styles.avatar, { width: size, height: size, borderRadius: size / 2 }]}
    >
      <Text style={[styles.avatarText, { fontSize: size * 0.4 }]}>{letter}</Text>
    </LinearGradient>
  );
}

export function ChipRow({ items, activeIndex = 0 }: { items: string[]; activeIndex?: number }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
      {items.map((item, i) => {
        const active = i === activeIndex;
        return (
          <View
            key={item}
            style={[
              styles.chip,
              active && { backgroundColor: 'rgba(215,244,82,0.12)', borderColor: 'rgba(215,244,82,0.35)' },
            ]}
          >
            <Text style={[styles.chipText, active && { color: color.lime }]}>{item}</Text>
          </View>
        );
      })}
    </ScrollView>
  );
}

export function MenuRow({
  icon,
  label,
  iconColor,
  badge,
  onPress,
}: {
  icon: ReactNode;
  label: string;
  iconColor?: string;
  badge?: string;
  onPress?: () => void;
}) {
  return (
    <Pressable style={styles.menuRow} onPress={onPress}>
      <View style={styles.menuIcon}>{icon}</View>
      <Text style={styles.menuLabel}>{label}</Text>
      {badge ? <Pill text={badge} bg="rgba(251,146,60,0.12)" fg={color.orange} /> : null}
      <IcoChevron size={14} stroke={color.dim} />
    </Pressable>
  );
}

export function StudioShortcut({
  icon,
  iconBg,
  iconColor,
  title,
  subtitle,
}: {
  icon: ReactNode;
  iconBg: string;
  iconColor: string;
  title: string;
  subtitle: string;
}) {
  return (
    <Card>
      <View style={styles.shortcutRow}>
        <View style={[styles.shortcutIcon, { backgroundColor: iconBg }]}>{icon}</View>
        <View style={styles.shortcutText}>
          <Text style={styles.shortcutTitle}>{title}</Text>
          <Text style={styles.shortcutSub}>{subtitle}</Text>
        </View>
        <IcoChevron size={15} stroke={color.dim} />
      </View>
    </Card>
  );
}

export function StudioRow({
  icon,
  tintRgb,
  title,
  desc,
  onPress,
}: {
  icon: ReactNode;
  tintRgb: string;
  title: string;
  desc: string;
  onPress?: () => void;
}) {
  return (
    <Card onPress={onPress}>
      <View style={styles.shortcutRow}>
        <View style={[styles.shortcutIcon, { backgroundColor: `rgba(${tintRgb},0.12)` }]}>{icon}</View>
        <View style={styles.shortcutText}>
          <Text style={styles.shortcutTitle}>{title}</Text>
          <Text style={styles.shortcutSub}>{desc}</Text>
        </View>
        <IcoChevron size={14} stroke={color.dim} />
      </View>
    </Card>
  );
}

export function ChatRow({
  name,
  platform,
  message,
  gradIndex,
  vip,
  unread,
  onPress,
  onFolderPress,
}: {
  name: string;
  platform: string;
  message: string;
  gradIndex: number;
  vip?: boolean;
  unread?: number;
  onPress?: () => void;
  onFolderPress?: () => void;
}) {
  const platColor = platform === 'FANVUE' ? color.pink : color.blue;
  return (
    <Pressable style={styles.chatRow} onPress={onPress}>
      <Avatar letter={name[0]} index={gradIndex} size={38} />
      <View style={styles.chatMain}>
        <View style={styles.chatNameRow}>
          <Text style={styles.chatName}>{name}</Text>
          {vip ? <Pill text="VIP" bg={color.lime} fg={color.limeText} /> : null}
        </View>
        <Text style={styles.chatMsg} numberOfLines={1}>
          {message}
        </Text>
      </View>
      <View style={styles.chatRight}>
        {onFolderPress ? (
          <Pressable onPress={onFolderPress} hitSlop={6} style={styles.folderBtn}>
            <Text style={styles.folderBtnText}>📁</Text>
          </Pressable>
        ) : null}
        <Text style={[styles.chatPlat, { color: platColor }]}>{platform}</Text>
        {unread ? (
          <View style={styles.unreadBadge}>
            <Text style={styles.unreadText}>{unread}</Text>
          </View>
        ) : null}
      </View>
    </Pressable>
  );
}

export function MessageBubble({ text, out, translation }: { text: string; out?: boolean; translation?: string }) {
  return (
    <View style={[styles.bubbleWrap, out && styles.bubbleWrapOut]}>
      <View
        style={[
          styles.bubble,
          out ? styles.bubbleOut : styles.bubbleIn,
        ]}
      >
        <Text style={styles.bubbleText}>{text}</Text>
        {translation ? (
          <View style={styles.translation}>
            <Text style={styles.translationText}>{translation}</Text>
          </View>
        ) : null}
      </View>
    </View>
  );
}

export function ProgressBar({ label, pct, barColor }: { label: string; pct: number; barColor: string }) {
  return (
    <View style={styles.progressBlock}>
      <View style={styles.progressHead}>
        <Text style={styles.progressLabel}>{label}</Text>
        <Text style={styles.progressPct}>{pct}%</Text>
      </View>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${pct}%`, backgroundColor: barColor }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: color.bg },
  scrollContent: { paddingHorizontal: 16, paddingTop: 4, paddingBottom: 24, gap: 10 },
  topBar: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingBottom: 12 },
  backBtn: { padding: 4 },
  topTitle: { flex: 1, fontFamily: font.display, fontSize: 19, color: color.text },
  topTitleWithBack: { flex: 1 },
  sectionLabel: {
    fontFamily: font.mono,
    fontSize: 9,
    letterSpacing: 1.8,
    color: color.dim,
    marginTop: 6,
    marginBottom: 2,
    marginHorizontal: 2,
  },
  kpi: {
    flexGrow: 1,
    flexBasis: '46%',
    backgroundColor: color.card,
    borderWidth: 1,
    borderColor: color.border,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  kpiLabel: { fontFamily: font.mono, fontSize: 8.5, letterSpacing: 1.2, color: color.dim, marginBottom: 6 },
  kpiValue: { fontFamily: font.display, fontSize: 18, color: color.text },
  kpiSub: { fontSize: 10, color: color.muted, marginTop: 3 },
  card: {
    backgroundColor: color.card,
    borderWidth: 1,
    borderColor: color.border,
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  pill: { borderRadius: 20, paddingHorizontal: 8, paddingVertical: 2 },
  pillText: { fontFamily: font.monoBold, fontSize: 9, letterSpacing: 0.5, fontWeight: '700' },
  avatar: { alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontFamily: font.bodyExtra, color: '#1a0a14' },
  chipRow: { flexDirection: 'row', gap: 6, paddingBottom: 2 },
  chip: {
    borderRadius: 20,
    paddingHorizontal: 11,
    paddingVertical: 5,
    backgroundColor: 'rgba(255,255,255,0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
  },
  chipText: { fontFamily: font.monoBold, fontSize: 9.5, color: color.muted, fontWeight: '700' },
  menuRow: { flexDirection: 'row', alignItems: 'center', gap: 11, paddingVertical: 11, paddingHorizontal: 4 },
  menuIcon: { width: 20, alignItems: 'center' },
  menuLabel: { flex: 1, fontSize: 13, fontFamily: font.bodySemi, color: color.text },
  shortcutRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  shortcutIcon: {
    width: 36,
    height: 36,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shortcutText: { flex: 1 },
  shortcutTitle: { fontFamily: font.bodyExtra, fontSize: 13.5, color: color.text },
  shortcutSub: { fontSize: 11, color: color.muted, marginTop: 1 },
  modeRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  modeIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modeText: { flex: 1 },
  modeTitle: { fontFamily: font.bodyExtra, fontSize: 13, color: color.text },
  modeDesc: { fontSize: 10.5, color: color.muted, marginTop: 2 },
  chatRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, paddingHorizontal: 4 },
  chatMain: { flex: 1, minWidth: 0 },
  chatNameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  chatName: { fontFamily: font.bodyExtra, fontSize: 13, color: color.text },
  chatMsg: { fontSize: 11.5, color: color.muted, marginTop: 2 },
  chatRight: { alignItems: 'flex-end', gap: 4 },
  folderBtn: { paddingHorizontal: 4, paddingVertical: 2 },
  folderBtnText: { fontSize: 14 },
  chatPlat: { fontFamily: font.mono, fontSize: 8 },
  unreadBadge: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: color.lime,
    alignItems: 'center',
    justifyContent: 'center',
  },
  unreadText: { fontFamily: font.monoBold, fontSize: 9, color: color.limeText, fontWeight: '800' },
  bubbleWrap: { flexDirection: 'row', justifyContent: 'flex-start' },
  bubbleWrapOut: { justifyContent: 'flex-end' },
  bubble: { maxWidth: '78%', paddingHorizontal: 12, paddingVertical: 9, borderRadius: 14, borderWidth: 1 },
  bubbleIn: { backgroundColor: color.bubbleIn, borderColor: color.border, borderBottomLeftRadius: 4 },
  bubbleOut: {
    backgroundColor: 'rgba(215,244,82,0.1)',
    borderColor: 'rgba(215,244,82,0.25)',
    borderBottomRightRadius: 4,
  },
  bubbleText: { fontSize: 13, lineHeight: 19, color: color.text },
  translation: {
    marginTop: 5,
    paddingTop: 5,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.1)',
    borderStyle: 'dashed',
  },
  translationText: { fontSize: 11, color: '#8A8F95' },
  progressBlock: { gap: 4 },
  progressHead: { flexDirection: 'row', justifyContent: 'space-between' },
  progressLabel: { fontFamily: font.bodyBold, fontSize: 11.5, color: color.text },
  progressPct: { fontFamily: font.mono, fontSize: 11.5, color: color.muted },
  progressTrack: { height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.06)' },
  progressFill: { height: '100%', borderRadius: 3 },
});
