import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useAppData } from '@/src/context/AppDataProvider';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { color, font } from '@/src/styles/tokens';

/** Липкий баннер ошибки — виден на любом экране, пока пользователь не закроет. */
export function AppErrorBanner({ bottomInset = 12 }: { bottomInset?: number }) {
  const { error, clearError } = useAppData();
  const { t } = useAppSettings();
  if (!error) return null;

  return (
    <View style={[styles.wrap, { bottom: bottomInset }]} accessibilityRole="alert">
      <View style={styles.card}>
        <Text style={styles.title}>{t.errorTitle}</Text>
        <Text style={styles.message}>{error}</Text>
        <Pressable style={styles.btn} onPress={clearError} hitSlop={8}>
          <Text style={styles.btnText}>{t.errorDismiss}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: 12,
    right: 12,
    zIndex: 50,
    elevation: 12,
  },
  card: {
    backgroundColor: '#2A1518',
    borderWidth: 1,
    borderColor: 'rgba(248,113,113,0.45)',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
  },
  title: {
    fontFamily: font.bodySemi,
    fontSize: 13,
    fontWeight: '700',
    color: color.red,
  },
  message: {
    fontFamily: font.body,
    fontSize: 13,
    lineHeight: 18,
    color: color.text,
  },
  btn: {
    alignSelf: 'flex-end',
    marginTop: 4,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  btnText: {
    fontFamily: font.bodySemi,
    fontSize: 12,
    fontWeight: '700',
    color: color.muted,
  },
});
