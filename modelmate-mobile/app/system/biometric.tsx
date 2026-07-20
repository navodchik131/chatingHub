import * as LocalAuthentication from 'expo-local-authentication';
import { router } from 'expo-router';
import { Platform, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { IcoFaceId, IcoFinger } from '@/src/components/Icons';
import { color, font } from '@/src/styles/tokens';

export default function BiometricScreen() {
  const isIOS = Platform.OS === 'ios';

  const authenticate = async () => {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    if (!hasHardware) {
      router.replace('/');
      return;
    }
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: 'Войти в ModelMate',
      cancelLabel: 'Отмена',
    });
    if (result.success) router.replace('/');
  };

  return (
    <SafeAreaView style={styles.safe}>
      <Pressable style={styles.center} onPress={authenticate}>
        <View style={[styles.iconWrap, !isIOS && styles.iconWrapRound]}>
          {isIOS ? (
            <IcoFaceId size={42} stroke={color.lime} />
          ) : (
            <IcoFinger size={40} stroke={color.lime} />
          )}
        </View>
        <Text style={styles.title}>{isIOS ? 'Face ID' : 'Отпечаток пальца'}</Text>
        <Text style={styles.sub}>Войти в ModelMate</Text>
        <Text style={styles.hint}>Нажмите для проверки</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: color.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 22 },
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
  sub: { fontSize: 12, color: color.muted },
  hint: { fontSize: 11, color: color.dim, marginTop: 8 },
});
