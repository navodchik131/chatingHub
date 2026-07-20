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
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { useNav } from '@/src/context/NavigationContext';
import { tabRoot } from '@/src/navigation/types';
import { color, font } from '@/src/styles/tokens';

export function TabBar() {
  const { stack, resetTo } = useNav();
  const { t } = useAppSettings();
  const active = tabRoot(stack);
  const insets = useSafeAreaInsets();

  const tabs = [
    { id: 'overview' as const, label: t.navOverview, Icon: IcoHome },
    { id: 'dialogs' as const, label: t.navDialogs, Icon: IcoChat },
    { id: 'studio' as const, label: t.navStudio, Icon: IcoWand },
    { id: 'characters' as const, label: t.navCharacters, Icon: IcoIdCard },
    { id: 'profile' as const, label: t.navProfile, Icon: IcoUser },
  ];

  return (
    <View style={[styles.bar, { paddingBottom: Math.max(12, insets.bottom + 8) }]}>
      {tabs.map(({ id, label, Icon }) => {
        const focused = id === active;
        return (
          <Pressable key={id} style={styles.item} onPress={() => resetTo(id)}>
            <Icon size={18} stroke={focused ? color.lime : color.dim} />
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
    paddingTop: 7,
    paddingHorizontal: 2,
  },
  item: { flex: 1, alignItems: 'center', gap: 2, minWidth: 0 },
  label: { fontFamily: font.bodyExtra, fontSize: 8.5, fontWeight: '700', color: color.dim },
  labelActive: { color: color.lime },
});
