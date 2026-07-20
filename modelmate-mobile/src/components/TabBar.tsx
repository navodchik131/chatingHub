import { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import {
  IcoChat,
  IcoHome,
  IcoIdCard,
  IcoUser,
  IcoWand,
} from '@/src/components/Icons';
import { useAppData } from '@/src/context/AppDataProvider';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { useNav } from '@/src/context/NavigationContext';
import { tabRoot } from '@/src/navigation/types';
import { color, font } from '@/src/styles/tokens';

function formatBadge(n: number): string {
  if (n <= 0) return '';
  if (n > 99) return '99+';
  return String(n);
}

export function TabBar() {
  const { stack, resetTo } = useNav();
  const { t } = useAppSettings();
  const { totalUnread } = useAppData();
  const active = tabRoot(stack);
  const insets = useSafeAreaInsets();
  const badge = formatBadge(totalUnread);

  const tabs = [
    { id: 'overview' as const, label: t.navOverview, Icon: IcoHome },
    { id: 'dialogs' as const, label: t.navDialogs, Icon: IcoChat, badge },
    { id: 'studio' as const, label: t.navStudio, Icon: IcoWand },
    { id: 'characters' as const, label: t.navCharacters, Icon: IcoIdCard },
    { id: 'profile' as const, label: t.navProfile, Icon: IcoUser },
  ];

  return (
    <View style={[styles.bar, { paddingBottom: Math.max(12, insets.bottom + 8) }]}>
      {tabs.map(({ id, label, Icon, badge: tabBadge }) => {
        const focused = id === active;
        return (
          <Pressable key={id} style={styles.item} onPress={() => resetTo(id)}>
            <View style={styles.iconWrap}>
              <Icon size={22} stroke={focused ? color.lime : color.dim} />
              {tabBadge ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>{tabBadge}</Text>
                </View>
              ) : null}
            </View>
            <Text style={[styles.label, focused && styles.labelActive]}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function AppShell({ children, showTabBar }: { children: ReactNode; showTabBar: boolean }) {
  return (
    <View style={styles.shell}>
      <View style={styles.content}>{children}</View>
      {showTabBar ? <TabBar /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: color.bg },
  content: { flex: 1, minHeight: 0 },
  bar: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.08)',
    backgroundColor: color.tabBar,
    paddingTop: 8,
    paddingHorizontal: 2,
  },
  item: { flex: 1, alignItems: 'center', gap: 3, minWidth: 0 },
  iconWrap: { position: 'relative', width: 28, height: 24, alignItems: 'center', justifyContent: 'center' },
  badge: {
    position: 'absolute',
    top: -6,
    right: -10,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 4,
    backgroundColor: color.lime,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: { fontFamily: font.monoBold, fontSize: 9, color: color.limeText, fontWeight: '800' },
  label: { fontFamily: font.bodyExtra, fontSize: 11, fontWeight: '700', color: color.dim },
  labelActive: { color: color.lime },
});
