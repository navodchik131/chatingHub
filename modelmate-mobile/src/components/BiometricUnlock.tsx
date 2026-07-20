import * as LocalAuthentication from 'expo-local-authentication';
import { useEffect } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { IcoFaceId, IcoFinger } from '@/src/components/Icons';
import { useAppSettings } from '@/src/context/AppSettingsContext';
import { color, font } from '@/src/styles/tokens';

export function BiometricUnlock({ onUnlock }: { onUnlock: () => void }) {
  const { t } = useAppSettings();
  const isIOS = Platform.OS === 'ios';

  const authenticate = async () => {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) {
      onUnlock();
      return;
    }
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    if (!enrolled) {
      onUnlock();
      return;
    }
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: t.settingsBiometric,
      cancelLabel: 'Cancel',
    });
    if (result.success) onUnlock();
  };

  useEffect(() => {
    void authenticate();
  }, []);

  return (
    <Pressable style={styles.root} onPress={() => void authenticate()}>
      <View style={[styles.iconWrap, !isIOS && styles.iconWrapRound]}>
        {isIOS ? <IcoFaceId size={42} stroke={color.lime} /> : <IcoFinger size={40} stroke={color.lime} />}
      </View>
      <Text style={styles.title}>{t.settingsBiometric}</Text>
      <Text style={styles.hint}>{t.settingsBiometricTest}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFill,
    backgroundColor: color.bg,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 18,
    zIndex: 100,
  },
  iconWrap: {
    width: 88,
    height: 88,
    borderRadius: 26,
    borderWidth: 2,
    borderColor: color.lime,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconWrapRound: { borderRadius: 44 },
  title: { fontFamily: font.bodyBold, fontSize: 14, color: color.text },
  hint: { fontSize: 11, color: color.dim },
});
